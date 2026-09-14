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
from datetime import datetime, timezone
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

STATE_SCHEMA_VERSION = 1
USER_AGENT = "SaltyDogBible-ReserveIntelMonitor/1.0"
MAX_RESPONSE_BYTES = 5_000_000
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
    for link in links:
        label = normalize_whitespace(link["title"])
        if NAVADMIN_ID_RE.fullmatch(label):
            linked_rows.append((label, link["url"]))

    # Fallback only for unusual markup/test fixtures.
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

        result.append(
            {
                "id": f"{source_type}-{sha256_text(url)[:20]}",
                "title": title or url,
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


def source_fingerprint(page_text: str, items: list[dict]) -> str:
    # Include both visible text and extracted index items. This catches in-place
    # rate/guidance changes as well as newly linked documents.
    stable = {
        "text": page_text,
        "items": sorted(items, key=lambda value: value["id"]),
    }
    return sha256_text(json.dumps(stable, sort_keys=True, ensure_ascii=False))


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
) -> str:
    lines = [
        "# Reserve Intel Monitor Report",
        "",
        f"Run time: **{iso_z(run_time)}**",
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

    for source in registry["sources"]:
        if not source.get("enabled", False):
            continue

        source_id = source["id"]
        previous = state.setdefault("sources", {}).get(source_id)

        try:
            raw_html, final_url = fetch_html(source["url"])
            page_text, links = parse_page(raw_html, final_url)
            items = extract_items(source, page_text, links, final_url)
            fingerprint = source_fingerprint(page_text, items)

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

                    candidate_text = f"{item.get('title', '')} {page_text[:3000]}"
                    signals = signal_matches(
                        candidate_text,
                        source.get("reserveSignals", [])
                    )

                    # NAVADMIN is a very broad feed, so require a Reserve-related
                    # signal. Other registry entries are already narrowly curated.
                    if source["sourceType"] == "navadmin" and not signals:
                        continue

                    candidates.append(
                        {
                            "sourceName": source["name"],
                            "sourceType": source["sourceType"],
                            "title": item.get("title") or source["name"],
                            "date": item.get("date", ""),
                            "url": item.get("url") or source["url"],
                            "signals": signals,
                            "categoryHints": source.get("categories", [])[:4],
                        }
                    )

                if previous.get("fingerprint") != fingerprint and not new_items:
                    changed_sources.append(
                        {
                            "name": source["name"],
                            "url": source["url"],
                        }
                    )

            state["sources"][source_id] = {
                "name": source["name"],
                "url": source["url"],
                "fingerprint": fingerprint,
                "itemIDs": sorted(current_item_ids),
                "itemCount": len(current_item_ids),
                "lastCheckedAt": iso_z(run_time),
                "lastError": None,
            }

        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
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
        report_markdown(run_time, bootstrap, candidates, changed_sources, errors) + "\n",
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
        },
        args.github_output,
    )

    print(
        f"Monitor complete: bootstrap={bootstrap}, "
        f"candidates={len(candidates)}, "
        f"changed_sources={len(changed_sources)}, errors={len(errors)}"
    )
    return 0


def self_test() -> int:
    html_fixture = """
    <html><body>
      <a href="/nav208.pdf">208/26</a>
      ORDER TO ACCOUNT FOR PERSONNEL ICO HURRICANE LOWELL 09/08/2026
      <a href="/nav204.pdf">204/26</a>
      MODIFICATION TO NAVADMIN 084/26 - FISCAL YEAR 2026 CYBERSECURITY
      AWARENESS CHALLENGE TRAINING REQUIREMENTS 08/31/2026
      <a href="/nav200.pdf">200/26</a>
      IMPLEMENTATION OF MANDATORY ANNUAL CBRN PROTECTIVE MASK FIT TRAINING
      AND TESTING 08/20/2026
    </body></html>
    """
    page_text, links = parse_page(
        html_fixture,
        "https://www.mynavyhr.navy.mil/References/Messages/NAVADMIN-2026/",
    )
    items = navadmin_items(
        page_text,
        links,
        "https://www.mynavyhr.navy.mil/References/Messages/NAVADMIN-2026/",
    )

    assert [item["id"] for item in items] == [
        "NAVADMIN-208/26",
        "NAVADMIN-204/26",
        "NAVADMIN-200/26",
    ]
    assert "084/26" in items[1]["title"]
    assert "CYBERSECURITY" in items[1]["title"]
    assert signal_matches(items[1]["title"], ["CYBERSECURITY"]) == ["CYBERSECURITY"]

    ignored = {
        "sourceType": "navadmin"
    }
    assert ignored_item(
        ignored,
        {"title": "NAVY RESERVE PROMOTIONS TO THE PERMANENT GRADES OF CAPTAIN"}
    )

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
