#!/usr/bin/env python3
"""
Salty Dog Bible — Navy Reserve guidance draft enrichment.

This script enriches only pending human-review drafts produced from the
"Navy Reserve RESPERSMAN" reserve_guidance source when the monitor supplied
a linked-document fingerprint.

Safety model:
- source-specific: reserve_guidance + Navy Reserve RESPERSMAN only
- official navyreserve.navy.mil PDF required
- live PDF is re-fetched and SHA-256 verified against the monitor fingerprint
- if the source changed again after detection, enrichment fails closed
- no automated policy-change attribution is claimed
- no effective date is inferred from HTTP metadata
- human-review / publication gates remain closed
- NEVER publishes or activates an article
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import ModuleType
from urllib.parse import unquote, urlparse


SOURCE_TYPE = "reserve_guidance"
EXPECTED_SOURCE_NAME_TOKEN = "respersman"
NAVY_RESERVE_HOST_SUFFIX = "navyreserve.navy.mil"
ALLOWED_DETECTION_KINDS = {
    "linked_document_changed",
    "new_linked_document",
}

CHAPTER_RE = re.compile(r"(?<!\d)(\d{4}-\d{3})(?!\d)")
COMNAVRESFORNOTE_RE = re.compile(r"\bCOMNAVRESFORNOTE\b", re.I)


class EnrichmentError(ValueError):
    pass


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def navy_reserve_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == NAVY_RESERVE_HOST_SUFFIX or host.endswith(
        "." + NAVY_RESERVE_HOST_SUFFIX
    )


def pdf_url(url: str) -> bool:
    return unquote(urlparse(url).path or "").lower().endswith(".pdf")


def load_monitor_module(path: str | None = None) -> ModuleType:
    monitor_path = (
        Path(path)
        if path
        else Path(__file__).resolve().with_name("check_sources.py")
    )

    if not monitor_path.exists():
        raise EnrichmentError(
            f"Reserve Intel monitor not found: {monitor_path}"
        )

    spec = importlib.util.spec_from_file_location(
        "reserve_intel_check_sources_for_guidance_enrichment",
        monitor_path,
    )
    if spec is None or spec.loader is None:
        raise EnrichmentError(
            f"Could not load Reserve Intel monitor: {monitor_path}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not callable(getattr(module, "fetch_linked_document", None)):
        raise EnrichmentError(
            "Reserve Intel monitor does not expose fetch_linked_document()."
        )

    return module


def validate_draft(draft: dict) -> tuple[dict, dict]:
    if not isinstance(draft, dict):
        raise EnrichmentError("Draft must be a JSON object.")

    if draft.get("draftStatus") != "PENDING_HUMAN_REVIEW":
        raise EnrichmentError(
            "Reserve-guidance enrichment requires draftStatus=PENDING_HUMAN_REVIEW."
        )

    if draft.get("requiresHumanReview") is not True:
        raise EnrichmentError(
            "Reserve-guidance enrichment requires requiresHumanReview=true."
        )

    if draft.get("publishReady") is not False:
        raise EnrichmentError(
            "Reserve-guidance enrichment requires publishReady=false."
        )

    evidence = draft.get("sourceEvidence")
    if not isinstance(evidence, dict):
        raise EnrichmentError("Draft is missing sourceEvidence.")

    if evidence.get("sourceType") != SOURCE_TYPE:
        raise EnrichmentError(
            "Reserve-guidance enricher only accepts sourceType=reserve_guidance."
        )

    source_name = str(evidence.get("sourceName") or "")
    if EXPECTED_SOURCE_NAME_TOKEN not in source_name.lower():
        raise EnrichmentError(
            "Reserve-guidance enricher only accepts the Navy Reserve RESPERSMAN source."
        )

    detection_kind = evidence.get("detectionKind")
    if detection_kind not in ALLOWED_DETECTION_KINDS:
        raise EnrichmentError(
            "Reserve-guidance enricher requires detectionKind "
            "linked_document_changed or new_linked_document."
        )

    source_url = str(evidence.get("sourceURL") or "")
    if not navy_reserve_host(source_url):
        raise EnrichmentError(
            f"Reserve-guidance source is not on an official Navy Reserve host: {source_url}"
        )

    if not pdf_url(source_url):
        raise EnrichmentError(
            "Reserve-guidance enrichment currently requires a linked PDF source."
        )

    detected_fingerprint = evidence.get("sourceFingerprint")
    if not isinstance(detected_fingerprint, str) or not detected_fingerprint.strip():
        raise EnrichmentError(
            "Reserve-guidance draft is missing the detected sourceFingerprint."
        )

    article = draft.get("articleDraft")
    if not isinstance(article, dict):
        raise EnrichmentError("Draft is missing articleDraft.")

    if article.get("isActive") is not False:
        raise EnrichmentError(
            "Reserve-guidance enrichment refuses an already-active article."
        )

    return evidence, article


def document_identity(title: str, source_url: str) -> dict:
    decoded_url = unquote(source_url)
    filename = Path(urlparse(decoded_url).path).name
    searchable = f"{title} {filename} {decoded_url}"

    chapter_match = CHAPTER_RE.search(searchable)
    if chapter_match:
        chapter = chapter_match.group(1)
        return {
            "documentKind": "RESPERSMAN",
            "documentIdentifier": chapter,
            "documentLabel": f"RESPERSMAN {chapter}",
            "sourceFilename": filename or None,
        }

    if COMNAVRESFORNOTE_RE.search(searchable):
        return {
            "documentKind": "COMNAVRESFORNOTE",
            "documentIdentifier": None,
            "documentLabel": title or filename or "Navy Reserve guidance document",
            "sourceFilename": filename or None,
        }

    return {
        "documentKind": "Navy Reserve guidance",
        "documentIdentifier": None,
        "documentLabel": title or filename or "Navy Reserve guidance document",
        "sourceFilename": filename or None,
    }


def human_change_note(detection_kind: str) -> str:
    if detection_kind == "linked_document_changed":
        return (
            "The monitor detected different PDF bytes at an already-known official "
            "document URL. The monitor retains document fingerprints, not the prior "
            "PDF body, so automated tooling cannot identify which paragraphs, tables, "
            "requirements, dates, or policy language changed. Human comparison and "
            "source review are required."
        )

    return (
        "The monitor detected a new linked official Navy Reserve guidance PDF. "
        "Automated tooling verified the current document fingerprint but has not "
        "determined the document's policy effect. Human source review is required."
    )


def enriched_summary(label: str, detection_kind: str) -> str:
    if detection_kind == "linked_document_changed":
        return (
            f"The Reserve Intel monitor detected a new version of {label} at its "
            "official Navy Reserve PDF URL. The current PDF was re-fetched and "
            "matches the fingerprint captured at detection. The exact policy-language "
            "changes have not been automatically determined."
        )

    return (
        f"The Reserve Intel monitor detected a newly linked official Navy Reserve "
        f"guidance document: {label}. The current PDF was re-fetched and matches "
        "the fingerprint captured at detection. Human review is required before "
        "describing its policy effect."
    )


def enriched_why_it_matters() -> str:
    return (
        "Official Navy Reserve personnel guidance can affect Reserve administration, "
        "training, readiness, pay or benefits, retirement, assignments, and related "
        "member requirements. The automated detection does not establish which of "
        "those areas changed or who is affected. Review the source before making any "
        "Salty Dog Bible content or app change."
    )


def enriched_details(
    label: str,
    detection_kind: str,
    final_url: str,
    http_last_modified: str | None,
    content_length: int | None,
) -> str:
    metadata_parts = []
    if http_last_modified:
        metadata_parts.append(f"HTTP Last-Modified: {http_last_modified}")
    if isinstance(content_length, int):
        metadata_parts.append(f"downloaded size: {content_length:,} bytes")

    metadata_text = (
        " Source-server metadata observed during verification: "
        + "; ".join(metadata_parts)
        + "."
        if metadata_parts
        else ""
    )

    return (
        f"Automated evidence verification for {label}: detection kind "
        f"`{detection_kind}`. The official Navy Reserve PDF was re-fetched from "
        f"{final_url} and its SHA-256 fingerprint matched the fingerprint stored "
        f"with the detected draft.{metadata_text} HTTP Last-Modified metadata is "
        "not treated as a policy effective date or revision date. "
        + human_change_note(detection_kind)
    )


def enrich_draft(
    draft: dict,
    monitor_module: ModuleType,
    enriched_at: str | None = None,
) -> dict:
    evidence, article = validate_draft(draft)

    source_url = evidence["sourceURL"]
    detected_fingerprint = evidence["sourceFingerprint"].strip()

    fetched = monitor_module.fetch_linked_document(source_url, None)
    if not isinstance(fetched, dict):
        raise EnrichmentError(
            "Reserve Intel monitor returned invalid linked-document evidence."
        )

    observed_fingerprint = fetched.get("fingerprint")
    if not isinstance(observed_fingerprint, str) or not observed_fingerprint:
        raise EnrichmentError(
            "Live linked-document verification did not return a fingerprint."
        )

    if observed_fingerprint != detected_fingerprint:
        raise EnrichmentError(
            "Official Reserve guidance changed again after detection: "
            f"detected fingerprint {detected_fingerprint}, "
            f"live fingerprint {observed_fingerprint}. "
            "Do not enrich this stale draft; allow the monitor to detect the newer version."
        )

    final_url = str(fetched.get("finalURL") or source_url)
    if not navy_reserve_host(final_url):
        raise EnrichmentError(
            f"Verified PDF redirected outside the official Navy Reserve host: {final_url}"
        )

    title = str(article.get("title") or "")
    identity = document_identity(title, source_url)
    detection_kind = evidence["detectionKind"]
    label = identity["documentLabel"]
    timestamp = enriched_at or utc_now_iso()

    enriched = copy.deepcopy(draft)

    # Keep all publication gates closed.
    enriched["draftStatus"] = "PENDING_HUMAN_REVIEW"
    enriched["requiresHumanReview"] = True
    enriched["publishReady"] = False
    enriched["articleDraft"]["isActive"] = False

    review_checklist = enriched.get("reviewChecklist")
    if isinstance(review_checklist, dict):
        review_checklist["approvedForPublication"] = False

    enriched["enrichment"] = {
        "sourceType": SOURCE_TYPE,
        "enrichmentKind": "navy_reserve_linked_document_verification",
        "enrichedAt": timestamp,
        "fetchedURL": final_url,
        "detectedFingerprint": detected_fingerprint,
        "observedFingerprint": observed_fingerprint,
        "fingerprintMatchesDetection": True,
        "httpLastModified": fetched.get("lastModified"),
        "contentLength": fetched.get("contentLength"),
        "etag": fetched.get("etag"),
        "documentKind": identity["documentKind"],
        "documentIdentifier": identity["documentIdentifier"],
        "sourceFilename": identity["sourceFilename"],
        "automatedChangeAttributionClaimed": False,
        "effectiveDateInferred": False,
        "changeAttributionNote": human_change_note(detection_kind),
    }

    enriched["articleDraft"]["summary"] = enriched_summary(
        label,
        detection_kind,
    )
    enriched["articleDraft"]["whyItMatters"] = enriched_why_it_matters()
    enriched["articleDraft"]["details"] = enriched_details(
        label,
        detection_kind,
        final_url,
        fetched.get("lastModified"),
        fetched.get("contentLength"),
    )

    # Never infer an effective date from HTTP Last-Modified or file metadata.
    enriched["articleDraft"]["effectiveDate"] = None

    return enriched


def atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def self_test() -> int:
    class FakeMonitor:
        @staticmethod
        def fetch_linked_document(url, previous=None):
            return {
                "url": url,
                "finalURL": (
                    "https://www.navyreserve.navy.mil/Portals/35/"
                    "RESPERSMAN%201570-010.pdf"
                ),
                "fingerprint": "new-fingerprint",
                "etag": None,
                "lastModified": "Tue, 15 Sep 2026 18:00:00 GMT",
                "contentLength": 123456,
            }

    base_draft = {
        "draftSchemaVersion": 1,
        "draftStatus": "PENDING_HUMAN_REVIEW",
        "requiresHumanReview": True,
        "publishReady": False,
        "detectedAt": "2026-09-15T18:00:00Z",
        "appImpact": {
            "requiresReview": True,
            "features": ["Drill / Orders", "Admin Gouge"],
            "basis": ["keyword: IDT"],
            "note": "Human review required.",
        },
        "sourceEvidence": {
            "sourceName": "Navy Reserve RESPERSMAN",
            "sourceType": "reserve_guidance",
            "sourceURL": (
                "https://www.navyreserve.navy.mil/Portals/35/"
                "RESPERSMAN 1570-010.pdf"
            ),
            "listedDate": None,
            "reserveSignals": ["INACTIVE DUTY TRAINING"],
            "categoryHints": ["Policy", "Training & Readiness"],
            "detectionKind": "linked_document_changed",
            "sourceFingerprint": "new-fingerprint",
            "previousFingerprint": "old-fingerprint",
            "officialHostVerified": True,
        },
        "reviewChecklist": {
            "sourceOpenedAndRead": False,
            "factsVerifiedAgainstSource": False,
            "statusVerified": False,
            "effectiveDateVerified": False,
            "audienceVerified": False,
            "summaryRewrittenFromSource": False,
            "whyItMattersRewrittenFromSource": False,
            "detailsRewrittenFromSource": False,
            "approvedForPublication": False,
        },
        "articleDraft": {
            "id": "intel-respersman-test",
            "publishedAt": "2026-09-15T18:00:00Z",
            "updatedAt": "2026-09-15T18:00:00Z",
            "title": "RESPERSMAN 1570-010",
            "category": "Policy",
            "status": "TRACKING",
            "priority": "HIGH",
            "summary": "placeholder",
            "whyItMatters": "placeholder",
            "details": "placeholder",
            "effectiveDate": None,
            "sourceName": "Navy Reserve RESPERSMAN",
            "sourceURL": (
                "https://www.navyreserve.navy.mil/Portals/35/"
                "RESPERSMAN 1570-010.pdf"
            ),
            "audience": {
                "service": "USN",
                "reserveStatus": "ALL",
                "trainingWing": None,
                "squadron": None,
            },
            "isPinned": False,
            "isActive": False,
        },
    }

    enriched = enrich_draft(
        base_draft,
        FakeMonitor,
        "2026-09-16T01:00:00Z",
    )

    assert enriched["enrichment"]["sourceType"] == "reserve_guidance"
    assert enriched["enrichment"]["fingerprintMatchesDetection"] is True
    assert enriched["enrichment"]["documentKind"] == "RESPERSMAN"
    assert enriched["enrichment"]["documentIdentifier"] == "1570-010"
    assert enriched["enrichment"]["automatedChangeAttributionClaimed"] is False
    assert enriched["enrichment"]["effectiveDateInferred"] is False
    assert enriched["articleDraft"]["effectiveDate"] is None
    assert enriched["articleDraft"]["isActive"] is False
    assert enriched["publishReady"] is False
    assert enriched["requiresHumanReview"] is True
    assert enriched["reviewChecklist"]["approvedForPublication"] is False
    assert "exact policy-language changes have not been automatically determined" in (
        enriched["articleDraft"]["summary"]
    )
    assert "not treated as a policy effective date" in enriched["articleDraft"]["details"]

    # New linked PDFs use the same verification path but different wording.
    new_document = copy.deepcopy(base_draft)
    new_document["sourceEvidence"]["detectionKind"] = "new_linked_document"
    new_document["sourceEvidence"]["previousFingerprint"] = None
    enriched_new = enrich_draft(
        new_document,
        FakeMonitor,
        "2026-09-16T01:00:00Z",
    )
    assert "newly linked official Navy Reserve guidance document" in (
        enriched_new["articleDraft"]["summary"]
    )

    # Same-URL source changed again after detection: fail closed.
    class StaleMonitor:
        @staticmethod
        def fetch_linked_document(url, previous=None):
            return {
                "url": url,
                "finalURL": url,
                "fingerprint": "newer-fingerprint",
                "etag": None,
                "lastModified": None,
                "contentLength": 10,
            }

    try:
        enrich_draft(base_draft, StaleMonitor)
    except EnrichmentError as exc:
        assert "changed again after detection" in str(exc)
    else:
        raise AssertionError("Stale fingerprint must fail enrichment.")

    # Wrong source type must not enter this enricher.
    wrong_type = copy.deepcopy(base_draft)
    wrong_type["sourceEvidence"]["sourceType"] = "pay_tables"
    try:
        enrich_draft(wrong_type, FakeMonitor)
    except EnrichmentError as exc:
        assert "sourceType=reserve_guidance" in str(exc)
    else:
        raise AssertionError("Wrong source type must fail enrichment.")

    # Non-Navy host must fail before fetching.
    wrong_host = copy.deepcopy(base_draft)
    wrong_host["sourceEvidence"]["sourceURL"] = "https://example.com/1570-010.pdf"
    try:
        enrich_draft(wrong_host, FakeMonitor)
    except EnrichmentError as exc:
        assert "official Navy Reserve host" in str(exc)
    else:
        raise AssertionError("Non-official host must fail enrichment.")

    # Generic Reserve guidance files on the RESPERSMAN page may not contain a
    # ####-### chapter number; they must still enrich conservatively.
    note_draft = copy.deepcopy(base_draft)
    note_draft["articleDraft"]["title"] = (
        "COMNAVRESFORNOTE 1100 2 FY26 SELRES Enlisted Recruiting and Retention Incentives"
    )
    note_draft["sourceEvidence"]["sourceURL"] = (
        "https://www.navyreserve.navy.mil/Portals/35/"
        "COMNAVRESFORNOTE 1100 2 FY26 SELRES Enlisted Recruiting and Retention "
        "Incentives (19SEPT2025).pdf"
    )
    note_draft["articleDraft"]["sourceURL"] = note_draft["sourceEvidence"]["sourceURL"]
    note_enriched = enrich_draft(
        note_draft,
        FakeMonitor,
        "2026-09-16T01:00:00Z",
    )
    assert note_enriched["enrichment"]["documentKind"] == "COMNAVRESFORNOTE"
    assert note_enriched["enrichment"]["documentIdentifier"] is None

    print("SELF-TEST PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--monitor-path", default=None)
    parser.add_argument("--enriched-at", default=None)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    if not args.input:
        print("--input is required unless --self-test is used.", file=sys.stderr)
        return 2

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Draft not found: {input_path}", file=sys.stderr)
        return 2

    output_path = Path(args.output) if args.output else input_path

    try:
        draft = json.loads(input_path.read_text(encoding="utf-8"))
        monitor_module = load_monitor_module(args.monitor_path)
        enriched = enrich_draft(
            draft,
            monitor_module,
            args.enriched_at,
        )
        atomic_write_json(output_path, enriched)
    except (json.JSONDecodeError, EnrichmentError, OSError) as exc:
        print(f"Reserve-guidance enrichment failed: {exc}", file=sys.stderr)
        return 2

    print(f"ENRICHED RESERVE GUIDANCE DRAFT: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
