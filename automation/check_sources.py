#!/usr/bin/env python3
"""
Salty Dog Bible — Reserve Intel source monitor (IT-2D.2)

Detection only. This script:
- reads automation/reserve-intel-sources.json
- checks enabled official/public sources
- compares them with automation/source-state.json
- writes automation/monitor-report.md
- NEVER edits reserve-content-feed.json

The first run establishes a baseline so old material does not flood the review queue.
"""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Iterable
from http.client import InvalidURL
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

STATE_SCHEMA_VERSION = 1
USER_AGENT = "SaltyDogBible-ReserveIntelMonitor/1.0"
MAX_RESPONSE_BYTES = 5_000_000
MAX_LINKED_DOCUMENT_BYTES = 25_000_000
RESERVE_GUIDANCE_MAX_DOCUMENTS = 100
REQUEST_TIMEOUT_SECONDS = 30

APPROVED_HOST_SUFFIXES = {
    "mynavyhr.navy.mil",
    "navyreserve.navy.mil",
    "govinfo.gov",
    "dfas.mil",
    "va.gov",
    "bls.gov",
    "defense.gov",
}

NAVADMIN_ID_RE = re.compile(r"^\d{3}/\d{2}$")
NAVADMIN_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")
NAVADMIN_URL_RE = re.compile(r"NAV(?P<year>\d{2})(?P<number>\d{3})\.pdf", re.I)

NAVADMIN_IGNORE_TITLE_PATTERNS = [
    re.compile(r"NAVY RESERVE PROMOTIONS TO THE PERMANENT GRADES", re.I),
    re.compile(r"ACTIVE[- ]DUTY PROMOTIONS TO THE PERMANENT GRADES", re.I),
]


class TextLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_chunks: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._skip_depth = 0
        self._active_href: str | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "a":
            self._active_href = dict(attrs).get("href")
            self._active_text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "a" and self._active_href is not None:
            self.links.append(
                (self._active_href, normalize_whitespace(" ".join(self._active_text)))
            )
            self._active_href = None
            self._active_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data:
            self.text_chunks.append(data)
            if self._active_href is not None:
                self._active_text.append(data)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def source_check_interval_hours(registry: dict, source: dict) -> float:
    value = source.get(
        "checkIntervalHours",
        registry.get("defaultCheckIntervalHours", 24),
    )

    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(
            f"Invalid check interval for source {source.get('id', '<unknown>')}: {value!r}"
        )

    return float(value)


def source_is_due(
    registry: dict,
    source: dict,
    previous: dict | None,
    run_time: datetime,
    bootstrap: bool,
) -> bool:
    # Baseline initialization and newly added sources are always checked.
    if bootstrap or previous is None:
        return True

    # A failed source gets retried on the next monitor run instead of waiting
    # through its normal 12/24-hour cadence.
    if previous.get("lastError"):
        return True

    last_checked = parse_iso_datetime(previous.get("lastCheckedAt"))
    if last_checked is None:
        return True

    interval = timedelta(hours=source_check_interval_hours(registry, source))
    return run_time >= last_checked + interval


def host_is_approved(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in APPROVED_HOST_SUFFIXES)


def fetch_html(url: str) -> tuple[str, str]:
    if not host_is_approved(url):
        raise ValueError(f"Unapproved source hostname: {url}")

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.1",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )

    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        final_url = response.geturl()
        if not host_is_approved(final_url):
            raise ValueError(f"Redirected to unapproved hostname: {final_url}")

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ValueError("Source response exceeded the 5 MB monitor limit.")
            chunks.append(chunk)

    return b"".join(chunks).decode("utf-8", errors="replace"), final_url


def is_pdf_url(url: str) -> bool:
    return (urlparse(url).path or "").lower().endswith(".pdf")


def request_safe_url(url: str) -> str:
    """
    Percent-encode unsafe characters in a URL before handing it to urllib.

    Navy Reserve RESPERSMAN currently exposes some PDF hrefs with literal spaces
    in the path (for example "Reserve Military Personnel Manual/RPM Acronyms.pdf").
    urllib rejects those URLs before a network request is made. Keep existing
    percent escapes intact while encoding spaces/control characters safely.
    """
    parts = urlsplit(url)

    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"Invalid linked-document URL: {url}")

    safe_path = quote(
        parts.path,
        safe="/%:@-._~!$&'()*+,;=",
    )
    safe_query = quote(
        parts.query,
        safe="=&%:@/?-._~!$'()*+,;",
    )

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            safe_path,
            safe_query,
            parts.fragment,
        )
    )


def fetch_linked_document(
    url: str,
    previous: dict | None = None,
) -> dict:
    """
    Fetch and fingerprint one official linked document.

    Conditional GET headers are reused when the server supplied ETag or
    Last-Modified metadata on a prior run. A 304 response reuses the prior
    content fingerprint without downloading the PDF again.
    """
    if not host_is_approved(url):
        raise ValueError(f"Unapproved linked-document hostname: {url}")

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/pdf,application/octet-stream,*/*;q=0.1",
        "Accept-Language": "en-US,en;q=0.9",
    }

    if isinstance(previous, dict):
        etag = previous.get("etag")
        last_modified = previous.get("lastModified")
        if isinstance(etag, str) and etag.strip():
            headers["If-None-Match"] = etag
        if isinstance(last_modified, str) and last_modified.strip():
            headers["If-Modified-Since"] = last_modified

    request_url = request_safe_url(url)
    request = Request(request_url, headers=headers, method="GET")

    try:
        response = urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS)
    except HTTPError as exc:
        if (
            exc.code == 304
            and isinstance(previous, dict)
            and isinstance(previous.get("fingerprint"), str)
            and previous["fingerprint"]
        ):
            return dict(previous)
        raise

    with response:
        final_url = response.geturl()
        if not host_is_approved(final_url):
            raise ValueError(f"Linked document redirected to unapproved hostname: {final_url}")

        content_length_header = response.headers.get("Content-Length")
        if content_length_header:
            try:
                declared_size = int(content_length_header)
            except ValueError:
                declared_size = None
            if declared_size is not None and declared_size > MAX_LINKED_DOCUMENT_BYTES:
                raise ValueError(
                    f"Linked document exceeded the {MAX_LINKED_DOCUMENT_BYTES} byte monitor limit."
                )

        digest = hashlib.sha256()
        total = 0

        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_LINKED_DOCUMENT_BYTES:
                raise ValueError(
                    f"Linked document exceeded the {MAX_LINKED_DOCUMENT_BYTES} byte monitor limit."
                )
            digest.update(chunk)

        return {
            "url": url,
            "finalURL": final_url,
            "fingerprint": digest.hexdigest(),
            "etag": response.headers.get("ETag"),
            "lastModified": response.headers.get("Last-Modified"),
            "contentLength": total,
        }


def reserve_guidance_display_title(title: str, url: str) -> str:
    normalized = normalize_whitespace(title)
    decoded_url = unquote(url)
    doc_match = re.search(r"\b\d{4}-\d{3}\b", f"{normalized} {decoded_url}")

    generic_titles = {
        "",
        "open pdf",
        "pdf",
        "open file",
        "view pdf",
        "file",
    }

    if normalized.lower() in generic_titles and doc_match:
        return f"RESPERSMAN {doc_match.group(0)}"

    if normalized:
        return normalized

    if doc_match:
        return f"RESPERSMAN {doc_match.group(0)}"

    filename = Path(urlparse(decoded_url).path).name
    return normalize_whitespace(filename) or url


def reserve_guidance_linked_documents(
    items: list[dict],
    previous_documents: dict | None,
) -> tuple[dict[str, dict], list[dict]]:
    """
    Fingerprint official RESPERSMAN PDFs without turning a single broken chapter
    link into a failure for the entire index source.

    When a chapter cannot be fetched, its prior fingerprint is retained when
    available and the failure is surfaced in the monitor error section.
    """
    documents: dict[str, dict] = {}
    errors: list[dict] = []
    pdf_items = [item for item in items if is_pdf_url(item.get("url", ""))]

    if len(pdf_items) > RESERVE_GUIDANCE_MAX_DOCUMENTS:
        raise ValueError(
            "Reserve-guidance source exposed more linked PDFs than the monitor safety limit."
        )

    previous_documents = previous_documents if isinstance(previous_documents, dict) else {}

    for item in pdf_items:
        item_id = item["id"]
        prior = previous_documents.get(item_id)
        try:
            documents[item_id] = fetch_linked_document(item["url"], prior)
        except (HTTPError, URLError, TimeoutError, InvalidURL, ValueError, OSError) as exc:
            if isinstance(prior, dict) and isinstance(prior.get("fingerprint"), str):
                documents[item_id] = dict(prior)

            errors.append(
                {
                    "name": item.get("title") or item["url"],
                    "message": str(exc),
                }
            )

    return documents, errors


def reserve_guidance_changed_candidates(
    source: dict,
    items: list[dict],
    current_documents: dict[str, dict],
    previous_documents: dict[str, dict] | None,
) -> list[dict]:
    """
    Promote same-URL RESPERSMAN PDF revisions to normal pending-draft candidates.

    A missing previous_documents mapping means this is the migration/baseline run
    for linked-document fingerprints, so no historical-change claim is made.
    """
    if not isinstance(previous_documents, dict):
        return []

    item_by_id = {item["id"]: item for item in items}
    candidates: list[dict] = []

    for item_id, current in current_documents.items():
        previous = previous_documents.get(item_id)
        item = item_by_id.get(item_id)

        if not isinstance(previous, dict) or item is None:
            continue

        current_fingerprint = current.get("fingerprint")
        previous_fingerprint = previous.get("fingerprint")

        if (
            not isinstance(current_fingerprint, str)
            or not isinstance(previous_fingerprint, str)
            or not current_fingerprint
            or not previous_fingerprint
            or current_fingerprint == previous_fingerprint
        ):
            continue

        title = item.get("title") or source["name"]
        candidates.append(
            {
                "sourceName": source["name"],
                "sourceType": source["sourceType"],
                "title": title,
                "date": item.get("date", ""),
                "url": item.get("url") or source["url"],
                "signals": signal_matches(title, source.get("reserveSignals", [])),
                "categoryHints": source.get("categories", [])[:4],
                "detectionKind": "linked_document_changed",
                "sourceFingerprint": current_fingerprint,
                "previousFingerprint": previous_fingerprint,
            }
        )

    return candidates


def parse_page(raw_html: str, base_url: str) -> tuple[str, list[dict[str, str]]]:
    parser = TextLinkParser()
    parser.feed(raw_html)

    text = normalize_whitespace(" ".join(parser.text_chunks))

    links: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for href, title in parser.links:
        absolute = urljoin(base_url, href).split("#", 1)[0]
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if not host_is_approved(absolute):
            continue

        key = (absolute, title)
        if key in seen:
            continue
        seen.add(key)
        links.append({"url": absolute, "title": title})

    return text, links


def signal_matches(text: str, signals: Iterable[str]) -> list[str]:
    upper = text.upper()
    return [signal for signal in signals if signal.upper() in upper]


def navadmin_items(
    page_text: str,
    links: list[dict[str, str]],
    fallback_url: str,
) -> list[dict]:
    """
    Prefer the linked NAVADMIN message numbers on the official index. That keeps
    a referenced message number inside a subject (for example NAVADMIN 084/26)
    from being mistaken for its own table row.
    """
    linked_rows: list[tuple[str, str]] = []
    seen_nav_ids: set[str] = set()

    for link in links:
        label = normalize_whitespace(link["title"])
        nav_id: str | None = None

        if NAVADMIN_ID_RE.fullmatch(label):
            nav_id = label
        else:
            # MyNavyHR NAVADMIN PDF links commonly encode the message as
            # NAV<YY><NNN>.pdf, for example NAV26204.pdf -> 204/26.
            url_match = NAVADMIN_URL_RE.search(link["url"])
            if url_match:
                nav_id = f"{url_match.group('number')}/{url_match.group('year')}"

        if nav_id and nav_id not in seen_nav_ids:
            seen_nav_ids.add(nav_id)
            linked_rows.append((nav_id, link["url"]))

    # Fallback only for unusual markup/test fixtures. When this fallback is used,
    # the item URL will remain the index URL, but relevance is still determined
    # only from the individual item's title so adjacent NAVADMIN text cannot leak in.
    if not linked_rows:
        ids = re.findall(r"\b\d{3}/\d{2}\b", page_text)
        linked_rows = [(value, fallback_url) for value in dict.fromkeys(ids)]

    # Locate each official row id in visible text. For row boundaries, use only
    # message numbers known from actual message links, not every number in a subject.
    located: list[tuple[int, str, str]] = []
    search_from = 0
    for nav_id, url in linked_rows:
        position = page_text.find(nav_id, search_from)
        if position < 0:
            position = page_text.find(nav_id)
        if position >= 0:
            located.append((position, nav_id, url))
            search_from = position + len(nav_id)

    located.sort(key=lambda value: value[0])

    items: list[dict] = []
    for index, (position, nav_id, item_url) in enumerate(located):
        start = position + len(nav_id)
        end = located[index + 1][0] if index + 1 < len(located) else min(len(page_text), start + 1200)
        segment = normalize_whitespace(page_text[start:end])

        date_match = NAVADMIN_DATE_RE.search(segment)
        if date_match:
            title = normalize_whitespace(segment[:date_match.start()])
            date_text = date_match.group(0)
        else:
            title = normalize_whitespace(segment[:500])
            date_text = ""

        title = title.strip("| :-")
        if len(title) < 4:
            continue

        items.append(
            {
                "id": f"NAVADMIN-{nav_id}",
                "title": title,
                "date": date_text,
                "url": item_url,
            }
        )

    deduped = {item["id"]: item for item in items}
    return list(deduped.values())


def generic_link_items(links: list[dict[str, str]], source_type: str) -> list[dict]:
    result: list[dict] = []

    for link in links:
        title = normalize_whitespace(link["title"])
        url = link["url"]
        combined = f"{title} {url}".lower()

        if source_type == "reserve_guidance":
            include = (
                ".pdf" in url.lower()
                or "respersman" in combined
                or bool(re.search(r"\b\d{4}-\d{3}\b", title))
            )
        elif source_type == "pay_tables":
            include = any(
                word in combined
                for word in ("pay", "drill", "allowance", "aviation", "incentive", "fica", "bas")
            )
        else:
            include = len(title) >= 8

        if not include:
            continue

        display_title = (
            reserve_guidance_display_title(title, url)
            if source_type == "reserve_guidance"
            else (title or url)
        )

        result.append(
            {
                "id": f"{source_type}-{sha256_text(url)[:20]}",
                "title": display_title,
                "date": "",
                "url": url,
            }
        )

    return list({item["id"]: item for item in result}.values())


def extract_items(source: dict, page_text: str, links: list[dict[str, str]], final_url: str) -> list[dict]:
    if source["sourceType"] == "navadmin":
        return navadmin_items(page_text, links, final_url)
    return generic_link_items(links, source["sourceType"])


def ignored_item(source: dict, item: dict) -> bool:
    if source["sourceType"] != "navadmin":
        return False
    return any(pattern.search(item.get("title", "")) for pattern in NAVADMIN_IGNORE_TITLE_PATTERNS)


def candidate_signal_text(source: dict, item: dict, page_text: str) -> str:
    """
    Return the text used for relevance-signal matching.

    NAVADMIN is a broad index page containing many unrelated messages. For a
    NAVADMIN candidate, use only that message's own title. Using the entire page
    can leak words such as RESERVE, TAR, or CONTINUATION from neighboring
    messages and create false positives.

    Other registry sources are deliberately narrower, so they may continue to
    use a limited page-text window in addition to the item title.
    """
    title = item.get("title", "")
    if source.get("sourceType") == "navadmin":
        return title
    return f"{title} {page_text[:3000]}"


def source_fingerprint(page_text: str, items: list[dict]) -> str:
    # Include both visible text and extracted index items. This catches in-place
    # rate/guidance changes as well as newly linked documents.
    stable = {
        "text": page_text,
        "items": sorted(items, key=lambda value: value["id"]),
    }
    return sha256_text(json.dumps(stable, sort_keys=True, ensure_ascii=False))


def in_place_change_candidate(
    source: dict,
    page_text: str,
    final_url: str,
    fingerprint: str,
    previous_fingerprint: str | None,
) -> dict | None:
    """
    Promote selected in-place source changes into normal pending-draft candidates.

    This is intentionally conservative: only DFAS pay-table sources are promoted
    for now. Other source types continue to surface only as changed-source review
    items until they have dedicated source-specific enrichment.
    """
    if source.get("sourceType") != "pay_tables":
        return None

    signals = signal_matches(page_text, source.get("reserveSignals", []))
    return {
        "sourceName": source["name"],
        "sourceType": source["sourceType"],
        "title": f"{source['name']} — source content changed",
        "date": "",
        "url": final_url or source["url"],
        "signals": signals,
        "categoryHints": source.get("categories", [])[:4],
        "detectionKind": "source_changed_in_place",
        "sourceFingerprint": fingerprint,
        "previousFingerprint": previous_fingerprint,
    }


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def github_output(values: dict[str, str], explicit_path: str | None = None) -> None:
    output_path = explicit_path or os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={str(value).replace(chr(10), ' ')}\n")


def report_markdown(
    run_time: datetime,
    bootstrap: bool,
    candidates: list[dict],
    changed_sources: list[dict],
    errors: list[dict],
    checked_source_count: int,
    skipped_source_count: int,
) -> str:
    lines = [
        "# Reserve Intel Monitor Report",
        "",
        f"Run time: **{iso_z(run_time)}**",
        "",
        "## Source check cadence",
        "",
        f"- Checked this run: {checked_source_count}",
        f"- Skipped until configured interval: {skipped_source_count}",
        "",
    ]

    if bootstrap:
        lines += [
            "## Baseline initialized",
            "",
            "This was the first automated monitor run.",
            "Existing source material was recorded as the baseline and **was not submitted as new Intel**.",
            "",
        ]

    if candidates:
        lines += ["## New potentially relevant items", ""]
        for item in candidates:
            lines += [
                f"### {item['title']}",
                "",
                f"- Source: **{item['sourceName']}**",
                f"- Type: `{item['sourceType']}`",
                f"- URL: {item['url']}",
                f"- Reserve signals: {', '.join(item['signals']) or 'Curated source change'}",
                f"- Category hints: {', '.join(item['categoryHints']) or 'Review required'}",
            ]
            if item.get("date"):
                lines.append(f"- Listed date: {item['date']}")
            if item.get("detectionKind"):
                lines.append(f"- Detection: `{item['detectionKind']}`")
            if item.get("sourceFingerprint"):
                lines.append(f"- Source fingerprint: `{item['sourceFingerprint']}`")
            if item.get("previousFingerprint"):
                lines.append(f"- Previous fingerprint: `{item['previousFingerprint']}`")
            lines += [
                "",
                "**Human review required. Detection does not mean this item should be published.**",
                "",
            ]
    elif not bootstrap:
        lines += ["## New potentially relevant items", "", "None detected.", ""]

    if changed_sources:
        lines += ["## Official sources changed in place", ""]
        for source in changed_sources:
            lines.append(f"- **{source['name']}** — {source['url']}")
        lines += [
            "",
            "These pages changed without exposing a clean new linked item. Review the official source before drafting Intel.",
            "",
        ]

    if errors:
        lines += ["## Source-check errors", ""]
        for error in errors:
            lines.append(f"- **{error['name']}** — {error['message']}")
        lines.append("")

    lines += [
        "## Publishing safety",
        "",
        "IT-2D.2 is detection-only. The monitor does **not** edit `reserve-content-feed.json`.",
        "Nothing reaches the app until it is separately reviewed and approved.",
        "",
    ]

    return "\n".join(lines)


def run_monitor(args) -> int:
    registry_path = Path(args.registry)
    state_path = Path(args.state)
    report_path = Path(args.report)

    registry = load_json(registry_path, None)
    if not isinstance(registry, dict) or not isinstance(registry.get("sources"), list):
        print("Source registry is missing or invalid.", file=sys.stderr)
        return 2

    state = load_json(
        state_path,
        {
            "schemaVersion": STATE_SCHEMA_VERSION,
            "initializedAt": None,
            "sources": {},
        },
    )

    run_time = now_utc()
    bootstrap = not bool(state.get("initializedAt"))
    candidates: list[dict] = []
    changed_sources: list[dict] = []
    errors: list[dict] = []
    checked_source_count = 0
    skipped_source_count = 0

    for source in registry["sources"]:
        if not source.get("enabled", False):
            continue

        source_id = source["id"]
        previous = state.setdefault("sources", {}).get(source_id)

        try:
            if not source_is_due(registry, source, previous, run_time, bootstrap):
                skipped_source_count += 1
                continue

            checked_source_count += 1
            raw_html, final_url = fetch_html(source["url"])
            page_text, links = parse_page(raw_html, final_url)
            items = extract_items(source, page_text, links, final_url)
            fingerprint = source_fingerprint(page_text, items)

            linked_documents: dict[str, dict] = {}
            previous_linked_documents: dict[str, dict] | None = None

            if source.get("sourceType") == "reserve_guidance":
                previous_value = (previous or {}).get("linkedDocuments")
                if isinstance(previous_value, dict):
                    previous_linked_documents = previous_value

                linked_documents, linked_errors = reserve_guidance_linked_documents(
                    items,
                    previous_linked_documents,
                )
                for linked_error in linked_errors:
                    errors.append(
                        {
                            "name": f"{source['name']} — {linked_error['name']}",
                            "message": linked_error["message"],
                        }
                    )

            previous_item_ids = set((previous or {}).get("itemIDs", []))
            current_item_ids = {item["id"] for item in items}
            new_items = [
                item for item in items
                if item["id"] not in previous_item_ids
            ]

            if not bootstrap and previous is not None:
                for item in new_items:
                    if ignored_item(source, item):
                        continue

                    candidate_text = candidate_signal_text(
                        source,
                        item,
                        page_text,
                    )
                    signals = signal_matches(
                        candidate_text,
                        source.get("reserveSignals", [])
                    )

                    # NAVADMIN is a very broad feed, so require a Reserve-related
                    # signal. Other registry entries are already narrowly curated.
                    if source["sourceType"] == "navadmin" and not signals:
                        continue

                    candidate = {
                        "sourceName": source["name"],
                        "sourceType": source["sourceType"],
                        "title": item.get("title") or source["name"],
                        "date": item.get("date", ""),
                        "url": item.get("url") or source["url"],
                        "signals": signals,
                        "categoryHints": source.get("categories", [])[:4],
                    }

                    if source.get("sourceType") == "reserve_guidance":
                        document = linked_documents.get(item["id"])
                        if isinstance(document, dict) and document.get("fingerprint"):
                            candidate["detectionKind"] = "new_linked_document"
                            candidate["sourceFingerprint"] = document["fingerprint"]

                    candidates.append(candidate)

                if source.get("sourceType") == "reserve_guidance":
                    candidates.extend(
                        reserve_guidance_changed_candidates(
                            source,
                            items,
                            linked_documents,
                            previous_linked_documents,
                        )
                    )

                if previous.get("fingerprint") != fingerprint and not new_items:
                    previous_fingerprint = previous.get("fingerprint")
                    changed_sources.append(
                        {
                            "name": source["name"],
                            "url": source["url"],
                        }
                    )

                    in_place_candidate = in_place_change_candidate(
                        source,
                        page_text,
                        final_url,
                        fingerprint,
                        previous_fingerprint,
                    )
                    if in_place_candidate is not None:
                        candidates.append(in_place_candidate)

            source_state = {
                "name": source["name"],
                "url": source["url"],
                "fingerprint": fingerprint,
                "itemIDs": sorted(current_item_ids),
                "itemCount": len(current_item_ids),
                "lastCheckedAt": iso_z(run_time),
                "lastError": None,
            }

            if source.get("sourceType") == "reserve_guidance":
                source_state["linkedDocuments"] = linked_documents
                source_state["linkedDocumentCount"] = len(linked_documents)

            state["sources"][source_id] = source_state

        except (HTTPError, URLError, TimeoutError, InvalidURL, ValueError, OSError) as exc:
            message = str(exc)
            errors.append({"name": source["name"], "message": message})
            old = previous or {}
            state["sources"][source_id] = {
                **old,
                "name": source["name"],
                "url": source["url"],
                "lastCheckedAt": iso_z(run_time),
                "lastError": message,
            }

    if bootstrap:
        state["initializedAt"] = iso_z(run_time)

    state["schemaVersion"] = STATE_SCHEMA_VERSION
    state["lastRunAt"] = iso_z(run_time)

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        report_markdown(
            run_time,
            bootstrap,
            candidates,
            changed_sources,
            errors,
            checked_source_count,
            skipped_source_count,
        ) + "\n",
        encoding="utf-8",
    )

    review_items = bool(candidates or changed_sources)
    github_output(
        {
            "bootstrap": "true" if bootstrap else "false",
            "review_items": "true" if review_items else "false",
            "candidate_count": str(len(candidates)),
            "changed_source_count": str(len(changed_sources)),
            "error_count": str(len(errors)),
            "checked_source_count": str(checked_source_count),
            "skipped_source_count": str(skipped_source_count),
        },
        args.github_output,
    )

    print(
        f"Monitor complete: bootstrap={bootstrap}, "
        f"candidates={len(candidates)}, "
        f"changed_sources={len(changed_sources)}, errors={len(errors)}, "
        f"checked_sources={checked_source_count}, skipped_sources={skipped_source_count}"
    )
    return 0


def self_test() -> int:
    # Regression fixture: 205/26 is unrelated to Reserve Intel while adjacent
    # 204/26 is cybersecurity-related. The broad index page contains Reserve
    # words elsewhere, so only item-level matching may qualify 204/26.
    html_fixture = """
    <html><body>
      <a href="/Portals/55/Messages/NAVADMIN/NAV2026/NAV26205.pdf">205/26</a>
      FISCAL YEAR 2027 VICE ADMIRAL JAMES BOND STOCKDALE LEADERSHIP AWARD
      09/01/2026

      <a href="/Portals/55/Messages/NAVADMIN/NAV2026/NAV26204.pdf">204/26</a>
      MODIFICATION TO NAVADMIN 084/26 - FISCAL YEAR 2026 CYBERSECURITY
      AWARENESS CHALLENGE TRAINING REQUIREMENTS 08/31/2026

      <a href="/Portals/55/Messages/NAVADMIN/NAV2026/NAV26200.pdf">200/26</a>
      IMPLEMENTATION OF MANDATORY ANNUAL CBRN PROTECTIVE MASK FIT TRAINING
      AND TESTING 08/20/2026

      <p>Elsewhere on this broad index: RESERVE TAR CONTINUATION SELRES.</p>
    </body></html>
    """

    base_url = "https://www.mynavyhr.navy.mil/References/Messages/NAVADMIN-2026/"
    page_text, links = parse_page(html_fixture, base_url)
    items = navadmin_items(page_text, links, base_url)

    assert [item["id"] for item in items] == [
        "NAVADMIN-205/26",
        "NAVADMIN-204/26",
        "NAVADMIN-200/26",
    ]

    # Specific authoritative document URLs must be preserved.
    assert items[0]["url"].endswith("NAV26205.pdf")
    assert items[1]["url"].endswith("NAV26204.pdf")
    assert items[2]["url"].endswith("NAV26200.pdf")

    source = {
        "sourceType": "navadmin",
        "reserveSignals": [
            "RESERVE",
            "TAR",
            "CONTINUATION",
            "SELRES",
            "CYBERSECURITY",
            "CBRN",
        ],
    }

    stockdale_text = candidate_signal_text(source, items[0], page_text)
    cyber_text = candidate_signal_text(source, items[1], page_text)
    cbrn_text = candidate_signal_text(source, items[2], page_text)

    # The Stockdale award must NOT inherit Reserve words from neighboring rows.
    assert signal_matches(stockdale_text, source["reserveSignals"]) == []

    # The two genuinely relevant titles still match their own signals.
    assert signal_matches(cyber_text, source["reserveSignals"]) == ["CYBERSECURITY"]
    assert signal_matches(cbrn_text, source["reserveSignals"]) == ["CBRN"]

    # Preserve existing protection against recurring promotion bulletins.
    ignored = {"sourceType": "navadmin"}
    assert ignored_item(
        ignored,
        {"title": "NAVY RESERVE PROMOTIONS TO THE PERMANENT GRADES OF CAPTAIN"},
    )

    # Cadence regression fixtures.
    cadence_registry = {"defaultCheckIntervalHours": 12}
    cadence_run_time = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

    six_hour_source = {
        "id": "six-hour-source",
        "checkIntervalHours": 6,
    }
    twelve_hour_source = {
        "id": "twelve-hour-source",
    }

    assert source_is_due(
        cadence_registry,
        six_hour_source,
        {"lastCheckedAt": "2026-09-15T06:00:00Z", "lastError": None},
        cadence_run_time,
        False,
    )
    assert not source_is_due(
        cadence_registry,
        six_hour_source,
        {"lastCheckedAt": "2026-09-15T07:00:00Z", "lastError": None},
        cadence_run_time,
        False,
    )
    assert source_is_due(
        cadence_registry,
        twelve_hour_source,
        {"lastCheckedAt": "2026-09-15T00:00:00Z", "lastError": None},
        cadence_run_time,
        False,
    )
    assert not source_is_due(
        cadence_registry,
        twelve_hour_source,
        {"lastCheckedAt": "2026-09-15T01:00:00Z", "lastError": None},
        cadence_run_time,
        False,
    )

    # Missing/malformed timestamps and prior failures are conservatively retried.
    assert source_is_due(
        cadence_registry,
        twelve_hour_source,
        {"lastCheckedAt": None, "lastError": None},
        cadence_run_time,
        False,
    )
    assert source_is_due(
        cadence_registry,
        twelve_hour_source,
        {"lastCheckedAt": "not-a-date", "lastError": None},
        cadence_run_time,
        False,
    )
    assert source_is_due(
        cadence_registry,
        twelve_hour_source,
        {"lastCheckedAt": "2026-09-15T11:30:00Z", "lastError": "temporary failure"},
        cadence_run_time,
        False,
    )

    # Bootstrap and newly added sources must always establish a baseline.
    assert source_is_due(
        cadence_registry,
        twelve_hour_source,
        {"lastCheckedAt": "2026-09-15T11:30:00Z", "lastError": None},
        cadence_run_time,
        True,
    )
    assert source_is_due(
        cadence_registry,
        twelve_hour_source,
        None,
        cadence_run_time,
        False,
    )

    # Full-path regression: the same DFAS item IDs with a changed page fingerprint
    # must produce both changed_sources=1 and candidates=1.
    dfas_url = "https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/"
    dfas_html = """
    <html><body>
      <h1>Military Pay Tables</h1>
      <p>2027 DRILL PAY BASIC PAY</p>
      <a href="https://www.dfas.mil/militarymembers/payentitlements/Pay-Tables/Drill-Pay/">Drill Pay</a>
    </body></html>
    """

    dfas_page_text, dfas_links = parse_page(dfas_html, dfas_url)
    dfas_items = generic_link_items(dfas_links, "pay_tables")
    dfas_item_ids = sorted(item["id"] for item in dfas_items)

    test_registry = {
        "defaultCheckIntervalHours": 12,
        "sources": [
            {
                "id": "dfas-test",
                "name": "DFAS Military Pay Tables",
                "url": dfas_url,
                "sourceType": "pay_tables",
                "enabled": True,
                "checkIntervalHours": 1,
                "reserveSignals": ["DRILL PAY", "BASIC PAY"],
                "categories": ["Pay & Benefits"],
            }
        ],
    }

    test_state = {
        "schemaVersion": STATE_SCHEMA_VERSION,
        "initializedAt": "2026-09-14T00:00:00Z",
        "lastRunAt": "2026-09-14T00:00:00Z",
        "sources": {
            "dfas-test": {
                "name": "DFAS Military Pay Tables",
                "url": dfas_url,
                "fingerprint": "SIMULATED-OLD-DFAS-FINGERPRINT",
                "itemIDs": dfas_item_ids,
                "itemCount": len(dfas_item_ids),
                "lastCheckedAt": "2000-01-01T00:00:00Z",
                "lastError": None,
            }
        },
    }

    original_fetch_html = globals()["fetch_html"]
    try:
        globals()["fetch_html"] = lambda url: (dfas_html, dfas_url)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "registry.json"
            state_path = tmp_path / "state.json"
            report_path = tmp_path / "report.md"
            output_path = tmp_path / "github-output.txt"

            registry_path.write_text(
                json.dumps(test_registry, indent=2) + "\n",
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(test_state, indent=2) + "\n",
                encoding="utf-8",
            )

            class TestArgs:
                registry = str(registry_path)
                state = str(state_path)
                report = str(report_path)
                github_output = str(output_path)

            assert run_monitor(TestArgs()) == 0

            output_values = {}
            for line in output_path.read_text(encoding="utf-8").splitlines():
                key, value = line.split("=", 1)
                output_values[key] = value

            assert output_values["candidate_count"] == "1"
            assert output_values["changed_source_count"] == "1"

            report_text = report_path.read_text(encoding="utf-8")
            assert "DFAS Military Pay Tables — source content changed" in report_text
            assert "- Type: `pay_tables`" in report_text
            assert "- Detection: `source_changed_in_place`" in report_text
            assert "- Source fingerprint:" in report_text
            assert "## Official sources changed in place" in report_text
    finally:
        globals()["fetch_html"] = original_fetch_html

    # URL-safety regression: Navy Reserve currently exposes some RESPERSMAN
    # hrefs with literal spaces. They must be encoded before urllib Request().
    unsafe_respersman_url = (
        "https://www.navyreserve.navy.mil/Portals/35/Documents/RESPERMAN/"
        "Reserve Military Personnel Manual/RPM Acronyms.pdf"
    )
    safe_respersman_url = request_safe_url(unsafe_respersman_url)
    assert "Reserve%20Military%20Personnel%20Manual/RPM%20Acronyms.pdf" in safe_respersman_url
    assert " " not in safe_respersman_url

    already_encoded_url = (
        "https://www.navyreserve.navy.mil/Portals/35/Documents/RESPERMAN/"
        "Reserve%20Military%20Personnel%20Manual/RPM%20Acronyms.pdf"
    )
    assert request_safe_url(already_encoded_url) == already_encoded_url

    # RESPERSMAN linked-document regression:
    # same index URL/title + changed PDF bytes must create one review candidate.
    respersman_url = (
        "https://www.navyreserve.navy.mil/Resources/"
        "Official-RESFOR-Guidance/RESPERSMAN/"
    )
    respersman_html = """
    <html><body>
      <p>1570-010 INACTIVE DUTY TRAINING (IDT) ADMINISTRATION
      <a href="/Portals/35/RESPERMAN%201570-010.pdf">Open PDF</a></p>
      <p>1571-010 ANNUAL TRAINING (AT) AND ACTIVE DUTY TRAINING (ADT)
      <a href="/Portals/35/RESPERMAN%201571-010.pdf">Open PDF</a></p>
    </body></html>
    """

    respersman_page_text, respersman_links = parse_page(respersman_html, respersman_url)
    respersman_items = generic_link_items(respersman_links, "reserve_guidance")
    assert len(respersman_items) == 2
    assert respersman_items[0]["title"] == "RESPERSMAN 1570-010"
    assert respersman_items[1]["title"] == "RESPERSMAN 1571-010"

    respersman_index_fingerprint = source_fingerprint(
        respersman_page_text,
        respersman_items,
    )
    respersman_item_ids = sorted(item["id"] for item in respersman_items)
    item_1570 = next(
        item for item in respersman_items
        if "1570-010" in unquote(item["url"])
    )
    item_1571 = next(
        item for item in respersman_items
        if "1571-010" in unquote(item["url"])
    )

    respersman_registry = {
        "defaultCheckIntervalHours": 12,
        "sources": [
            {
                "id": "respersman-test",
                "name": "Navy Reserve RESPERSMAN",
                "url": respersman_url,
                "sourceType": "reserve_guidance",
                "enabled": True,
                "checkIntervalHours": 1,
                "reserveSignals": [
                    "INACTIVE DUTY TRAINING",
                    "ANNUAL TRAINING",
                    "ACTIVE DUTY TRAINING",
                ],
                "categories": ["Policy", "Training & Readiness", "Admin"],
            }
        ],
    }

    respersman_state = {
        "schemaVersion": STATE_SCHEMA_VERSION,
        "initializedAt": "2026-09-14T00:00:00Z",
        "lastRunAt": "2026-09-14T00:00:00Z",
        "sources": {
            "respersman-test": {
                "name": "Navy Reserve RESPERSMAN",
                "url": respersman_url,
                "fingerprint": respersman_index_fingerprint,
                "itemIDs": respersman_item_ids,
                "itemCount": len(respersman_item_ids),
                "linkedDocuments": {
                    item_1570["id"]: {
                        "url": item_1570["url"],
                        "finalURL": item_1570["url"],
                        "fingerprint": "OLD-1570-FINGERPRINT",
                        "etag": None,
                        "lastModified": None,
                        "contentLength": 100,
                    },
                    item_1571["id"]: {
                        "url": item_1571["url"],
                        "finalURL": item_1571["url"],
                        "fingerprint": "SAME-1571-FINGERPRINT",
                        "etag": None,
                        "lastModified": None,
                        "contentLength": 100,
                    },
                },
                "linkedDocumentCount": 2,
                "lastCheckedAt": "2000-01-01T00:00:00Z",
                "lastError": None,
            }
        },
    }

    original_fetch_html = globals()["fetch_html"]
    original_fetch_linked_document = globals()["fetch_linked_document"]

    def fake_respersman_document(url, previous=None):
        fingerprint = (
            "NEW-1570-FINGERPRINT"
            if "1570-010" in unquote(url)
            else "SAME-1571-FINGERPRINT"
        )
        return {
            "url": url,
            "finalURL": url,
            "fingerprint": fingerprint,
            "etag": '"test-etag"',
            "lastModified": "Tue, 15 Sep 2026 12:00:00 GMT",
            "contentLength": 100,
        }

    try:
        globals()["fetch_html"] = lambda url: (respersman_html, respersman_url)
        globals()["fetch_linked_document"] = fake_respersman_document

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "registry.json"
            state_path = tmp_path / "state.json"
            report_path = tmp_path / "report.md"
            output_path = tmp_path / "github-output.txt"

            registry_path.write_text(
                json.dumps(respersman_registry, indent=2) + "\n",
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(respersman_state, indent=2) + "\n",
                encoding="utf-8",
            )

            class RespersmanArgs:
                registry = str(registry_path)
                state = str(state_path)
                report = str(report_path)
                github_output = str(output_path)

            assert run_monitor(RespersmanArgs()) == 0

            output_values = {}
            for line in output_path.read_text(encoding="utf-8").splitlines():
                key, value = line.split("=", 1)
                output_values[key] = value

            assert output_values["candidate_count"] == "1"
            assert output_values["changed_source_count"] == "0"
            assert output_values["error_count"] == "0"

            report_text = report_path.read_text(encoding="utf-8")
            assert "RESPERSMAN 1570-010" in report_text
            assert "- Type: `reserve_guidance`" in report_text
            assert "- Detection: `linked_document_changed`" in report_text
            assert "- Source fingerprint: `NEW-1570-FINGERPRINT`" in report_text
            assert "- Previous fingerprint: `OLD-1570-FINGERPRINT`" in report_text

            saved_state = json.loads(state_path.read_text(encoding="utf-8"))
            saved_docs = saved_state["sources"]["respersman-test"]["linkedDocuments"]
            assert saved_docs[item_1570["id"]]["fingerprint"] == "NEW-1570-FINGERPRINT"
            assert saved_docs[item_1571["id"]]["fingerprint"] == "SAME-1571-FINGERPRINT"

        # Migration regression: an existing RESPERSMAN state that predates linked-
        # document fingerprints must establish the baseline without creating 47+
        # false "changed chapter" candidates.
        migration_state = {
            "schemaVersion": STATE_SCHEMA_VERSION,
            "initializedAt": "2026-09-14T00:00:00Z",
            "lastRunAt": "2026-09-14T00:00:00Z",
            "sources": {
                "respersman-test": {
                    "name": "Navy Reserve RESPERSMAN",
                    "url": respersman_url,
                    "fingerprint": respersman_index_fingerprint,
                    "itemIDs": respersman_item_ids,
                    "itemCount": len(respersman_item_ids),
                    "lastCheckedAt": "2000-01-01T00:00:00Z",
                    "lastError": None,
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry_path = tmp_path / "registry.json"
            state_path = tmp_path / "state.json"
            report_path = tmp_path / "report.md"
            output_path = tmp_path / "github-output.txt"

            registry_path.write_text(
                json.dumps(respersman_registry, indent=2) + "\n",
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(migration_state, indent=2) + "\n",
                encoding="utf-8",
            )

            class MigrationArgs:
                registry = str(registry_path)
                state = str(state_path)
                report = str(report_path)
                github_output = str(output_path)

            assert run_monitor(MigrationArgs()) == 0

            output_values = {}
            for line in output_path.read_text(encoding="utf-8").splitlines():
                key, value = line.split("=", 1)
                output_values[key] = value

            assert output_values["candidate_count"] == "0"
            migrated_state = json.loads(state_path.read_text(encoding="utf-8"))
            assert migrated_state["sources"]["respersman-test"]["linkedDocumentCount"] == 2
    finally:
        globals()["fetch_html"] = original_fetch_html
        globals()["fetch_linked_document"] = original_fetch_linked_document

    print("SELF-TEST PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="automation/reserve-intel-sources.json")
    parser.add_argument("--state", default="automation/source-state.json")
    parser.add_argument("--report", default="automation/monitor-report.md")
    parser.add_argument("--github-output", default=None)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    return run_monitor(args)


if __name__ == "__main__":
    raise SystemExit(main())
