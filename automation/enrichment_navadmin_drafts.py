#!/usr/bin/env python3
"""
Salty Dog Bible — Reserve Intel NAVADMIN draft enrichment (IT-2D.6A)

Purpose:
- Read one pending Reserve Intel draft.
- Fetch the exact official NAVADMIN source URL.
- Extract source text from PDF or HTML.
- Build source-grounded Summary / Why It Matters / Details.
- Improve category/status/effective-date metadata where the source clearly supports it.
- Keep every human-approval gate locked.

Safety:
- Does NOT edit reserve-content-feed.json.
- Does NOT mark a draft publishReady.
- Does NOT mark a draft active.
- Does NOT mark any human-review checklist item true.
- Only approved official government hosts may be fetched.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import html
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - handled with a clear runtime error
    PdfReader = None

USER_AGENT = "SaltyDogBible-ReserveIntelEnrichment/1.0"
MAX_RESPONSE_BYTES = 10_000_000
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

CATEGORY_KEYWORDS = [
    ("Training & Readiness", ("training", "readiness", "cybersecurity", "cbrn", "exercise")),
    ("Pay & Benefits", ("pay", "bonus", "allowance", "compensation", "incentive")),
    ("Retirement", ("retirement", "retired", "non-regular retirement")),
    ("VA / Veteran Benefits", ("veteran", "va disability", "disability compensation")),
    ("Admin", ("administrative", "admin", "records", "muster", "accountability")),
    ("Policy", ("policy", "guidance", "requirement", "requirements")),
]

ACTION_WORDS = (
    "effective immediately",
    "required to",
    "must ",
    "shall ",
    "supersedes",
    "applies",
    "changed",
    "changes",
    "within",
    "every ",
)

RESERVE_WORDS = (
    "reserve",
    "selres",
    "selected reserve",
    "tar",
    "training and administration of the reserve",
)


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data:
            self.parts.append(data)


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_text(value: str) -> str:
    value = html.unescape(value)
    value = value.replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def collapse(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def host_is_approved(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in APPROVED_HOST_SUFFIXES)


def fetch_source(url: str) -> tuple[bytes, str, str]:
    if not host_is_approved(url):
        raise ValueError(f"Unapproved source host: {url}")

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,text/html,application/xhtml+xml,*/*;q=0.1",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )

    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        final_url = response.geturl()
        if not host_is_approved(final_url):
            raise ValueError(f"Redirected to unapproved host: {final_url}")

        content_type = response.headers.get("Content-Type", "").lower()
        chunks: list[bytes] = []
        total = 0

        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ValueError("Source exceeded 10 MB enrichment limit.")
            chunks.append(chunk)

    return b"".join(chunks), content_type, final_url


def extract_pdf_text(data: bytes) -> str:
    if PdfReader is None:
        raise RuntimeError(
            "pypdf is required for NAVADMIN PDF enrichment. "
            "Install automation/requirements-enrichment.txt first."
        )
    reader = PdfReader(BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return normalize_text("\n".join(pages))


def extract_html_text(data: bytes) -> str:
    parser = VisibleTextParser()
    parser.feed(data.decode("utf-8", errors="replace"))
    return normalize_text("\n".join(parser.parts))


def extract_source_text(data: bytes, content_type: str, url: str) -> str:
    path = urlparse(url).path.lower()
    if "pdf" in content_type or path.endswith(".pdf"):
        return extract_pdf_text(data)
    return extract_html_text(data)


def load_draft(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Draft root must be an object.")
    if payload.get("draftStatus") != "PENDING_HUMAN_REVIEW":
        raise ValueError("Draft is not pending human review.")
    if payload.get("requiresHumanReview") is not True:
        raise ValueError("Draft must require human review.")
    if payload.get("publishReady") is not False:
        raise ValueError("Pending draft must remain publishReady=false.")

    article = payload.get("articleDraft")
    evidence = payload.get("sourceEvidence")
    if not isinstance(article, dict):
        raise ValueError("articleDraft is missing.")
    if not isinstance(evidence, dict):
        raise ValueError("sourceEvidence is missing.")

    if evidence.get("sourceType") != "navadmin":
        raise ValueError("IT-2D.6A currently enriches NAVADMIN drafts only.")

    source_url = article.get("sourceURL")
    if not isinstance(source_url, str) or not source_url:
        raise ValueError("articleDraft.sourceURL is missing.")
    if not host_is_approved(source_url):
        raise ValueError("articleDraft.sourceURL is not on an approved official host.")

    return payload


def extract_navadmin_number(text: str) -> str | None:
    match = re.search(r"\bNAVADMIN\s+(\d{3}/\d{2})\b", text, re.I)
    return match.group(1) if match else None


def extract_subject(text: str) -> str | None:
    match = re.search(r"\bSubj/(.+?)//", text, re.I | re.S)
    if not match:
        return None
    return collapse(match.group(1))


def numbered_sections(text: str) -> dict[int, str]:
    """
    Parse numbered RMKS sections such as:
      RMKS/1. Purpose....
      2. Policy Update....
      3. Civilian...
    """
    start = re.search(r"\bRMKS/", text, re.I)
    body = text[start.end():] if start else text

    matches = list(re.finditer(r"(?m)(?:^|\n)\s*(\d+)\.\s+", body))
    sections: dict[int, str] = {}

    for index, match in enumerate(matches):
        number = int(match.group(1))
        section_start = match.end()
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        section = collapse(body[section_start:section_end])
        if section:
            sections[number] = section

    return sections


def sentences(text: str) -> list[str]:
    if not text:
        return []
    # NAVADMIN prose is formal and usually sentence-delimited.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", collapse(text))
    return [part.strip() for part in parts if len(part.strip()) >= 20]


def unique_sentences(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = collapse(value).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(collapse(value))
    return result


def strip_section_heading(sentence: str) -> str:
    # "Policy Update. Effective immediately..." -> "Effective immediately..."
    known = (
        "Purpose.",
        "Policy Update.",
        "Civilian and Contractor Personnel.",
        "Training Systems Configuration.",
        "Network Access Restrictions.",
    )
    result = sentence.strip()
    for heading in known:
        if result.startswith(heading):
            result = result[len(heading):].strip()
    return result


def plain_language(sentence: str) -> str:
    value = strip_section_heading(sentence)
    replacements = {
        "periodicity": "frequency",
        "three (3) years": "three years",
        "shall ": "must ",
        "officially changed": "changed",
    }
    for old, new in replacements.items():
        value = re.sub(re.escape(old), new, value, flags=re.I)
    return collapse(value)


def infer_category(subject: str, text: str, existing: str) -> str:
    haystack = f"{subject} {text[:6000]}".lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return category
    return existing or "Policy"


def parse_listed_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*", value)
    if not match:
        return None
    month, day, year = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def source_grounded_fields(payload: dict, source_text: str) -> dict:
    article = payload["articleDraft"]
    evidence = payload["sourceEvidence"]

    number = extract_navadmin_number(source_text)
    subject = extract_subject(source_text) or article.get("title", "NAVADMIN update")
    sections = numbered_sections(source_text)

    all_sentences: list[str] = []
    for number_key in sorted(sections):
        all_sentences.extend(sentences(sections[number_key]))

    purpose_candidates = sentences(sections.get(1, ""))
    policy_candidates = sentences(sections.get(2, ""))
    system_candidates = sentences(sections.get(4, ""))
    network_candidates = sentences(sections.get(5, ""))

    effective_sentence = next(
        (s for s in all_sentences if "effective immediately" in s.lower()),
        None,
    )
    reserve_sentence = next(
        (s for s in all_sentences if any(word in s.lower() for word in RESERVE_WORDS)),
        None,
    )
    requirement_sentence = next(
        (
            s for s in policy_candidates + all_sentences
            if "required to" in s.lower()
            or "must " in s.lower()
            or "shall " in s.lower()
        ),
        None,
    )
    supersedes_sentence = next(
        (s for s in policy_candidates + all_sentences if "supersedes" in s.lower()),
        None,
    )
    command_action_sentence = next(
        (
            s for s in system_candidates + network_candidates
            if "command" in s.lower()
            and ("track" in s.lower() or "ensure" in s.lower())
        ),
        None,
    )

    summary_parts = unique_sentences(
        [
            plain_language(effective_sentence) if effective_sentence else "",
            plain_language(requirement_sentence) if requirement_sentence else "",
            plain_language(supersedes_sentence) if supersedes_sentence else "",
        ]
    )

    if not summary_parts and purpose_candidates:
        summary_parts = [plain_language(purpose_candidates[0])]

    summary = " ".join(summary_parts[:3])

    why_parts = unique_sentences(
        [
            plain_language(reserve_sentence) if reserve_sentence else "",
            plain_language(command_action_sentence) if command_action_sentence else "",
        ]
    )
    if why_parts:
        why_it_matters = " ".join(why_parts[:2])
    else:
        why_it_matters = (
            "This NAVADMIN may affect Navy Reserve training or readiness requirements. "
            "Review the official source and confirm the exact Reserve applicability before publication."
        )

    detail_candidates: list[str] = []
    for section_number in (1, 2, 3, 4, 5):
        section = sections.get(section_number)
        if section:
            detail_candidates.append(section)

    details = "\n\n".join(detail_candidates[:5])
    if not details:
        details = source_text[:5000]

    effective_date = article.get("effectiveDate")
    if effective_sentence and "effective immediately" in effective_sentence.lower():
        effective_date = parse_listed_date(evidence.get("listedDate"))

    status = article.get("status", "TRACKING")
    if effective_sentence and "effective immediately" in effective_sentence.lower():
        status = "EFFECTIVE"

    category = infer_category(
        subject,
        " ".join(detail_candidates),
        article.get("category", "Policy"),
    )

    return {
        "navadminNumber": number,
        "subject": subject,
        "sections": {str(k): v for k, v in sections.items()},
        "summary": summary,
        "whyItMatters": why_it_matters,
        "details": details,
        "effectiveDate": effective_date,
        "status": status,
        "category": category,
    }


def enrich_payload(payload: dict, source_text: str, source_url: str) -> dict:
    fields = source_grounded_fields(payload, source_text)
    article = payload["articleDraft"]

    article["title"] = fields["subject"]
    article["summary"] = fields["summary"]
    article["whyItMatters"] = fields["whyItMatters"]
    article["details"] = fields["details"]
    article["effectiveDate"] = fields["effectiveDate"]
    article["status"] = fields["status"]
    article["category"] = fields["category"]
    article["updatedAt"] = utc_now_iso()

    # Hard safety gates remain locked.
    article["isActive"] = False
    payload["requiresHumanReview"] = True
    payload["publishReady"] = False
    payload["draftStatus"] = "PENDING_HUMAN_REVIEW"

    # Never silently mark human review as complete.
    checklist = payload.get("reviewChecklist")
    if isinstance(checklist, dict):
        for key in checklist:
            checklist[key] = False

    payload["sourceEvidence"]["sourceURL"] = source_url
    payload["sourceEvidence"]["sourceTextSHA256"] = hashlib.sha256(
        source_text.encode("utf-8")
    ).hexdigest()

    payload["enrichment"] = {
        "schemaVersion": 1,
        "method": "deterministic-navadmin-source-extraction-v1",
        "enrichedAt": utc_now_iso(),
        "sourceURL": source_url,
        "sourceTextSHA256": payload["sourceEvidence"]["sourceTextSHA256"],
        "navadminNumber": fields["navadminNumber"],
        "subject": fields["subject"],
        "extractedSections": fields["sections"],
        "humanReviewStillRequired": True,
    }

    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", required=True)
    parser.add_argument(
        "--source-file",
        default=None,
        help="Optional local source file for testing (.txt/.html/.pdf).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    draft_path = Path(args.draft)

    try:
        payload = load_draft(draft_path)
        source_url = payload["articleDraft"]["sourceURL"]

        if args.source_file:
            source_path = Path(args.source_file)
            raw = source_path.read_bytes()
            suffix = source_path.suffix.lower()
            if suffix == ".pdf":
                source_text = extract_pdf_text(raw)
            elif suffix in {".html", ".htm"}:
                source_text = extract_html_text(raw)
            else:
                source_text = normalize_text(raw.decode("utf-8"))
            final_url = source_url
        else:
            raw, content_type, final_url = fetch_source(source_url)
            source_text = extract_source_text(raw, content_type, final_url)

        if len(source_text) < 100:
            raise ValueError("Source text extraction returned too little text.")

        enriched = enrich_payload(payload, source_text, final_url)

    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"ENRICHMENT FAILED: {exc}", file=sys.stderr)
        return 1

    article = enriched["articleDraft"]

    if args.dry_run:
        print(json.dumps({
            "title": article["title"],
            "category": article["category"],
            "status": article["status"],
            "effectiveDate": article["effectiveDate"],
            "summary": article["summary"],
            "whyItMatters": article["whyItMatters"],
        }, indent=2, ensure_ascii=False))
        return 0

    draft_path.write_text(
        json.dumps(enriched, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"ENRICHED: {draft_path}")
    print(f"TITLE: {article['title']}")
    print(f"CATEGORY: {article['category']}")
    print(f"STATUS: {article['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
