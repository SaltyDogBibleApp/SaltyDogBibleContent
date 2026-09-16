#!/usr/bin/env python3
"""
Salty Dog Bible — DFAS pay-table draft enrichment.

Source-grounding only. This script:
- handles sourceEvidence.sourceType == "pay_tables"
- refetches the official DFAS source
- verifies the monitored source fingerprint when one was supplied
- captures the current authoritative pay-table snapshot
- rewrites placeholder article text conservatively from verified current evidence
- NEVER edits reserve-content-feed.json
- NEVER approves or publishes a draft

Important limitation:
The monitor stores the prior fingerprint, not the prior source body. Therefore an
in-place source change can be confirmed, but automation cannot safely claim which
specific dollar value, table, date, or policy text changed. Human review remains
required before publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import check_sources as monitor


MAX_RELEVANT_LINKS = 30
MAX_SECTION_SNIPPET_CHARS = 650

SECTION_HEADINGS = (
    "Basic Pay Rates",
    "Drill Pay Rates",
    "Basic Allowance for Subsistence",
    "Aviation Incentive Pays",
    "Career Sea Pay",
    "Hazardous Duty Incentive Pay",
    "Health Professions Officers",
    "Muster Duty Allowance",
)

MONTHS = (
    r"January|February|March|April|May|June|July|August|September|October|"
    r"November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|"
    r"Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?"
)

EFFECTIVE_DATE_RE = re.compile(
    rf"\bEffective\s+((?:{MONTHS})\s+\d{{1,2}},\s+\d{{4}})",
    re.I,
)
POSTED_MONTH = (
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|"
    r"Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?)"
)

# DFAS has a few entries with imperfect closing punctuation, so stop at the
# date itself instead of consuming arbitrary text until the next ")".
POSTED_DATE_RE = re.compile(
    rf"\(Posted\.?\s+({POSTED_MONTH}\s+(?:\d{{1,2}},\s+)?\d{{4}})\b",
    re.I,
)


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_official_dfas_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "dfas.mil" or host.endswith(".dfas.mil")


def unique_preserve_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def validate_pending_pay_tables_draft(payload: dict) -> tuple[dict, dict]:
    if not isinstance(payload, dict):
        raise ValueError("Draft root must be a JSON object.")
    if payload.get("draftStatus") != "PENDING_HUMAN_REVIEW":
        raise ValueError("Draft must be PENDING_HUMAN_REVIEW.")
    if payload.get("requiresHumanReview") is not True:
        raise ValueError("requiresHumanReview must be true.")
    if payload.get("publishReady") is not False:
        raise ValueError("Pending draft must have publishReady=false.")

    evidence = payload.get("sourceEvidence")
    if not isinstance(evidence, dict):
        raise ValueError("sourceEvidence is missing.")
    if evidence.get("sourceType") != "pay_tables":
        raise ValueError("DFAS enricher only handles sourceType=pay_tables.")
    if evidence.get("officialHostVerified") is not True:
        raise ValueError("sourceEvidence.officialHostVerified must be true.")

    source_url = evidence.get("sourceURL")
    if not isinstance(source_url, str) or not is_official_dfas_url(source_url):
        raise ValueError("sourceEvidence.sourceURL must be an official dfas.mil URL.")

    article = payload.get("articleDraft")
    if not isinstance(article, dict):
        raise ValueError("articleDraft is missing.")
    if article.get("isActive") is not False:
        raise ValueError("Pending articleDraft.isActive must be false.")
    if not isinstance(article.get("id"), str) or not article["id"].strip():
        raise ValueError("articleDraft.id is missing.")

    article_url = article.get("sourceURL")
    if not isinstance(article_url, str) or not is_official_dfas_url(article_url):
        raise ValueError("articleDraft.sourceURL must be an official dfas.mil URL.")

    return evidence, article


def relevant_pay_links(items: list[dict]) -> list[dict[str, str]]:
    """
    Keep only concrete descendants of the DFAS Military Pay Tables hub.

    The monitor's generic pay-table discovery intentionally uses broad keyword
    matching. That is useful for change detection, but too broad for review
    evidence: words such as "reserve" can pull in travel pages, and the substring
    "fica" can appear inside unrelated words such as "verification".

    For enrichment evidence, require the authoritative DFAS URL path itself to be
    under /pay-tables/ and exclude the hub self-link. This keeps the review focused
    on actual basic-pay, drill-pay, BAS, aviation/incentive, allowance, and other
    pay-table descendants.
    """
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in items:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not url or url in seen or not is_official_dfas_url(url):
            continue

        path = (urlparse(url).path or "").lower()
        normalized_path = path.rstrip("/")

        if "/pay-tables/" not in path:
            continue
        if normalized_path.endswith("/pay-tables"):
            continue

        seen.add(url)
        results.append({"title": title or url, "url": url})
        if len(results) >= MAX_RELEVANT_LINKS:
            break

    return results


def section_snippets(page_text: str) -> dict[str, str]:
    lower = page_text.lower()
    found: dict[str, str] = {}

    positions: list[tuple[int, str]] = []
    for heading in SECTION_HEADINGS:
        pos = lower.find(heading.lower())
        if pos >= 0:
            positions.append((pos, heading))

    positions.sort()
    for index, (pos, heading) in enumerate(positions):
        end = (
            positions[index + 1][0]
            if index + 1 < len(positions)
            else min(len(page_text), pos + MAX_SECTION_SNIPPET_CHARS)
        )
        end = min(end, pos + MAX_SECTION_SNIPPET_CHARS)
        snippet = monitor.normalize_whitespace(page_text[pos:end])
        if snippet:
            found[heading] = snippet

    return found


def current_signals(page_text: str, configured_signals: list[str]) -> list[str]:
    upper = page_text.upper()
    return [
        signal
        for signal in configured_signals
        if isinstance(signal, str) and signal.upper() in upper
    ]


def enrich_payload(
    payload: dict,
    *,
    raw_html: str | None = None,
    final_url: str | None = None,
    enriched_at: str | None = None,
) -> dict:
    evidence, article = validate_pending_pay_tables_draft(payload)
    source_url = evidence["sourceURL"]

    if raw_html is None:
        raw_html, fetched_final_url = monitor.fetch_html(source_url)
        final_url = fetched_final_url
    elif final_url is None:
        final_url = source_url

    if not isinstance(final_url, str) or not is_official_dfas_url(final_url):
        raise ValueError("DFAS source redirected to a non-DFAS host.")

    page_text, links = monitor.parse_page(raw_html, final_url)
    if not page_text:
        raise ValueError("DFAS source returned no readable page text.")

    source_descriptor = {"sourceType": "pay_tables"}
    items = monitor.extract_items(source_descriptor, page_text, links, final_url)
    observed_fingerprint = monitor.source_fingerprint(page_text, items)

    expected_fingerprint = evidence.get("sourceFingerprint")
    if expected_fingerprint:
        if not isinstance(expected_fingerprint, str):
            raise ValueError("sourceEvidence.sourceFingerprint must be a string.")
        if expected_fingerprint != observed_fingerprint:
            raise ValueError(
                "DFAS source changed again after detection. "
                "Observed fingerprint does not match sourceEvidence.sourceFingerprint. "
                "Run the monitor again before reviewing this draft."
            )

    configured_signals = evidence.get("reserveSignals") or []
    if not isinstance(configured_signals, list):
        raise ValueError("sourceEvidence.reserveSignals must be an array.")

    signals_present = current_signals(page_text, configured_signals)
    relevant_links = relevant_pay_links(items)
    snippets = section_snippets(page_text)

    effective_dates = unique_preserve_order(
        match.group(1).strip() for match in EFFECTIVE_DATE_RE.finditer(page_text)
    )
    posted_dates = unique_preserve_order(
        match.group(1).strip() for match in POSTED_DATE_RE.finditer(page_text)
    )

    enriched_at = enriched_at or utc_now_iso()
    fingerprint_verified = bool(expected_fingerprint)

    change_attribution = (
        "The current DFAS page is source-grounded and the detected fingerprint "
        "was verified when available. The prior page body is not retained, so "
        "automation cannot safely identify which specific rate, table, date, or "
        "policy text changed."
    )

    payload["enrichment"] = {
        "schemaVersion": 1,
        "sourceType": "pay_tables",
        "method": "dfas_pay_tables_snapshot",
        "enrichedAt": enriched_at,
        "fetchedURL": final_url,
        "officialHostVerified": True,
        "pageTextSHA256": sha256_text(page_text),
        "monitorFingerprintExpected": expected_fingerprint,
        "monitorFingerprintObserved": observed_fingerprint,
        "monitorFingerprintMatch": (
            observed_fingerprint == expected_fingerprint
            if expected_fingerprint
            else None
        ),
        "currentSignalsPresent": signals_present,
        "effectiveDateTextCandidates": effective_dates,
        "postedDateTextCandidates": posted_dates,
        "relevantLinks": relevant_links,
        "sectionSnippets": snippets,
        "changeAttribution": change_attribution,
        "humanReviewStillRequired": True,
    }

    article["updatedAt"] = enriched_at
    article["summary"] = (
        "DFAS's official Military Pay Tables source was refetched for this review. "
        + (
            "The current page matches the fingerprint captured by Reserve Intel monitoring. "
            if fingerprint_verified
            else "No monitor fingerprint was supplied for this item, so the current source snapshot was captured without historical fingerprint verification. "
        )
        + "Human review is still required to identify and verify the specific pay-table change before publication."
    )

    article["whyItMatters"] = (
        "DFAS publishes authoritative military pay, Reserve drill pay, allowances, "
        "and incentive-pay information that may affect Salty Dog Bible pay-related "
        "features. The current source contains reserve/pay signals that warrant review, "
        "but those signals do not prove which specific value changed."
    )

    link_titles = [item["title"] for item in relevant_links[:8]]
    link_summary = "; ".join(link_titles) if link_titles else "No specific pay-table links were extracted."

    article["details"] = (
        f"Current DFAS source snapshot captured {len(relevant_links)} relevant pay-related link(s). "
        f"Examples: {link_summary}. "
        f"Signals present on the current page: {', '.join(signals_present) or 'None from the configured list'}. "
        f"{change_attribution} "
        "Before approval, open the official source, determine the exact table or rate that changed, "
        "verify the effective date and affected audience, and rewrite this article with those verified facts."
    )

    # Safety invariants remain hard-set.
    payload["requiresHumanReview"] = True
    payload["publishReady"] = False
    article["isActive"] = False

    return payload


def self_test() -> int:
    dfas_url = "https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/"
    fixture = """
    <html><body>
      <a href="/MilitaryMembers/travelpay/Army-TDY/">Army Active Duty &amp; Reserve TDY</a>
      <a href="/Portals/98/DoD Employment Verification.pdf">DoD Employee Verification</a>
      <a href="/MilitaryMembers/payentitlements/fsa/">Family Separation Allowance</a>

      <h4>Military Pay Tables &amp; Information</h4>
      <a href="/militarymembers/payentitlements/Pay-Tables/">Pay/Special Pay/Allowance Tables</a>
      <p>Basic Pay Rates:</p>
      <a href="/militarymembers/payentitlements/Pay-Tables/Basic-Pay/CO/">Commissioned Officers</a>
      (Posted Jan 2026)
      <p>Drill Pay Rates:</p>
      <a href="/militarymembers/payentitlements/Pay-Tables/Drill-Pay/Drill-Pay-CO/">Commissioned Officers Drill Pay</a>
      (Posted Jan 2026
      <p>Reserve Component Drill Pay Effective January 1, 2026</p>
      <a href="/militarymembers/payentitlements/Pay-Tables/bas/">Basic Allowance for Subsistence (BAS)</a>
      (Posted Dec 2025)
      <p>Aviation Incentive Pays</p>
      <a href="/militarymembers/payentitlements/Pay-Tables/AVIP/">Monthly Navy Aviation Incentive Pay Rates</a>
      (Posted. Aug. 2022)
      <p>DRILL PAY BASIC PAY AVIATION INCENTIVE PAY BAS ALLOWANCE</p>
    </body></html>
    """

    page_text, links = monitor.parse_page(fixture, dfas_url)
    items = monitor.extract_items({"sourceType": "pay_tables"}, page_text, links, dfas_url)
    fingerprint = monitor.source_fingerprint(page_text, items)

    payload = {
        "draftSchemaVersion": 1,
        "draftStatus": "PENDING_HUMAN_REVIEW",
        "requiresHumanReview": True,
        "publishReady": False,
        "sourceEvidence": {
            "sourceName": "DFAS Military Pay Tables",
            "sourceType": "pay_tables",
            "sourceURL": dfas_url,
            "reserveSignals": [
                "DRILL PAY",
                "BASIC PAY",
                "AVIATION INCENTIVE PAY",
                "BAS",
                "ALLOWANCE",
            ],
            "sourceFingerprint": fingerprint,
            "officialHostVerified": True,
        },
        "articleDraft": {
            "id": "intel-dfas-test",
            "title": "DFAS Military Pay Tables — source content changed",
            "category": "Pay & Benefits",
            "status": "TRACKING",
            "priority": "HIGH",
            "summary": "placeholder",
            "whyItMatters": "placeholder",
            "details": "placeholder",
            "sourceName": "DFAS Military Pay Tables",
            "sourceURL": dfas_url,
            "audience": {
                "service": "ALL",
                "reserveStatus": "ALL",
                "trainingWing": None,
                "squadron": None,
            },
            "isPinned": False,
            "isActive": False,
        },
    }

    result = enrich_payload(
        payload,
        raw_html=fixture,
        final_url=dfas_url,
        enriched_at="2026-09-15T23:59:00Z",
    )

    enrichment = result["enrichment"]
    assert enrichment["sourceType"] == "pay_tables"
    assert enrichment["monitorFingerprintMatch"] is True
    assert enrichment["humanReviewStillRequired"] is True
    assert "January 1, 2026" in enrichment["effectiveDateTextCandidates"]

    relevant_urls = [item["url"].lower() for item in enrichment["relevantLinks"]]
    assert len(relevant_urls) == 4
    assert all("/pay-tables/" in url for url in relevant_urls)
    assert not any("travelpay" in url for url in relevant_urls)
    assert not any("verification" in url for url in relevant_urls)
    assert not any("/fsa/" in url for url in relevant_urls)
    assert not any(url.rstrip("/").endswith("/pay-tables") for url in relevant_urls)

    assert enrichment["postedDateTextCandidates"] == [
        "Jan 2026",
        "Dec 2025",
        "Aug. 2022",
    ]
    assert "Drill Pay Rates" in enrichment["sectionSnippets"]
    assert result["articleDraft"]["isActive"] is False
    assert result["publishReady"] is False
    assert "Human review is still required" in result["articleDraft"]["summary"]

    stale = json.loads(json.dumps(payload))
    stale["sourceEvidence"]["sourceFingerprint"] = "stale-fingerprint"
    try:
        enrich_payload(
            stale,
            raw_html=fixture,
            final_url=dfas_url,
            enriched_at="2026-09-15T23:59:00Z",
        )
    except ValueError as exc:
        assert "changed again after detection" in str(exc)
    else:
        raise AssertionError("Stale DFAS fingerprint must fail enrichment.")

    wrong_type = json.loads(json.dumps(payload))
    wrong_type["sourceEvidence"]["sourceType"] = "navadmin"
    try:
        enrich_payload(
            wrong_type,
            raw_html=fixture,
            final_url=dfas_url,
            enriched_at="2026-09-15T23:59:00Z",
        )
    except ValueError as exc:
        assert "sourceType=pay_tables" in str(exc)
    else:
        raise AssertionError("Non-pay_tables draft must fail enrichment.")

    print("SELF-TEST PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", default=None)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    if not args.draft:
        print("ERROR: --draft is required unless --self-test is used.", file=sys.stderr)
        return 2

    path = Path(args.draft)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        enriched = enrich_payload(payload)
        path.write_text(
            json.dumps(enriched, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"ENRICHED DFAS PAY TABLE DRAFT: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
