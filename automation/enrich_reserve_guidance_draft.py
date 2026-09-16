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
import difflib
import hashlib
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import ModuleType
from urllib.parse import unquote, urlparse


SOURCE_TYPE = "reserve_guidance"
EXPECTED_SOURCE_NAME_TOKENS = ("respersman", "resfor notices")
NAVY_RESERVE_HOST_SUFFIX = "navyreserve.navy.mil"
ALLOWED_DETECTION_KINDS = {
    "linked_document_changed",
    "new_linked_document",
}

CHAPTER_RE = re.compile(r"(?<!\d)(\d{4}-\d{3})(?!\d)")
COMNAVRESFORNOTE_RE = re.compile(r"\bCOMNAVRESFORNOTE\b", re.I)
DEFAULT_EVIDENCE_ROOT = Path("automation/reserve-intel-evidence/navyreserve-respersman")
RESFOR_NOTICES_EVIDENCE_ROOT = Path("automation/reserve-intel-evidence/navyreserve-resfor-notices")
MAX_DIFF_HUNKS = 12
MAX_DIFF_LINES_PER_SIDE = 8
MAX_DIFF_LINE_CHARS = 500
ARTICLE_TITLE_LABEL_RE = re.compile(r"^article\s+title\s*:?\s*$", re.I)
NUMBERED_HEADING_RE = re.compile(
    r"^\d+(?:\.\d+)*\.?\s+[A-Za-z][^.!?]{0,120}$"
)
SECTION_HEADING_RE = re.compile(
    r"^(?:purpose|scope|background|policy|responsibilit(?:y|ies)|"
    r"procedures?|requirements?|definitions?|administration|training|"
    r"records?|reporting|eligibility|applicability|references?|overview|"
    r"general information|action|discussion|table of contents)"
    r"(?:\s*[:\-–—]\s*[^.!?;]{1,100})?$",
    re.I,
)


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


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def snapshot_path(evidence_root: Path, source_url: str, fingerprint: str) -> Path:
    return evidence_root / sha256_text(source_url)[:20] / f"{fingerprint}.json"


def load_text_snapshot(
    evidence_root: Path,
    source_url: str,
    fingerprint: str | None,
) -> tuple[dict | None, Path | None, str | None]:
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        return None, None, "fingerprint_not_available"

    path = snapshot_path(evidence_root, source_url, fingerprint.strip())
    if not path.exists():
        return None, path, "snapshot_not_found"

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, path, f"snapshot_unreadable: {exc}"

    if not isinstance(payload, dict):
        return None, path, "snapshot_root_not_object"
    if payload.get("fingerprint") != fingerprint.strip():
        return None, path, "snapshot_fingerprint_mismatch"
    if payload.get("sourceURL") != source_url:
        return None, path, "snapshot_source_url_mismatch"

    return payload, path, None


def line_page(snapshot: dict, line_number: int | None) -> int | None:
    if not isinstance(line_number, int) or line_number <= 0:
        return None
    ranges = snapshot.get("pageLineRanges")
    if not isinstance(ranges, list):
        return None
    for item in ranges:
        if not isinstance(item, dict):
            continue
        start = item.get("startLine")
        end = item.get("endLine")
        page = item.get("page")
        if isinstance(start, int) and isinstance(end, int) and start <= line_number <= end:
            return page if isinstance(page, int) else None
    return None


def structural_heading_candidate(lines: list[str], pos: int) -> str | None:
    candidate = lines[pos].strip()
    if not 3 <= len(candidate) <= 140:
        return None
    if candidate.startswith(("•", "-", "*")):
        return None

    # RESPERSMAN change summaries often put the real article title immediately
    # after an "Article Title" label. Prefer that mixed-case title over nearby
    # signature/OCR noise.
    if pos > 0 and ARTICLE_TITLE_LABEL_RE.fullmatch(lines[pos - 1].strip()):
        return candidate[:140]

    # A bare RESPERSMAN article number is structural context even when the PDF
    # does not expose a conventional section heading nearby.
    if CHAPTER_RE.fullmatch(candidate):
        return candidate

    # Normal manual section headings such as "1. Purpose" or "3. Procedures".
    if NUMBERED_HEADING_RE.fullmatch(candidate):
        return candidate[:140]

    # Unnumbered structural headings are intentionally restricted to known
    # manual-style labels. Returning no heading is safer than surfacing a name,
    # signature block, sentence fragment, or OCR artifact as a section heading.
    if SECTION_HEADING_RE.fullmatch(candidate):
        return candidate[:140]

    return None


def nearby_heading(lines: list[str], index: int) -> str | None:
    if not lines:
        return None
    index = min(max(index, 0), len(lines) - 1)
    for pos in range(max(0, index - 20), index + 1)[::-1]:
        candidate = structural_heading_candidate(lines, pos)
        if candidate is not None:
            return candidate
    return None


def clipped_lines(lines: list[str]) -> tuple[list[str], bool]:
    clipped = [line[:MAX_DIFF_LINE_CHARS] for line in lines[:MAX_DIFF_LINES_PER_SIDE]]
    return clipped, len(lines) > MAX_DIFF_LINES_PER_SIDE


def build_text_comparison(
    previous_snapshot: dict | None,
    current_snapshot: dict | None,
    previous_path: Path | None,
    current_path: Path | None,
    unavailable_reason: str | None = None,
) -> dict:
    base = {
        "comparisonKind": "normalized_extracted_text_diff",
        "available": False,
        "policyInterpretationClaimed": False,
        "note": (
            "This comparison is based on normalized text extracted from two PDF versions. "
            "PDF layout or extraction behavior can create apparent text differences. Human "
            "review of the official source is required before describing policy effect."
        ),
    }

    if previous_path is not None:
        base["previousSnapshotPath"] = previous_path.as_posix()
    if current_path is not None:
        base["currentSnapshotPath"] = current_path.as_posix()

    if previous_snapshot is None or current_snapshot is None:
        base["unavailableReason"] = unavailable_reason or "snapshot_not_available"
        return base

    previous_text = previous_snapshot.get("normalizedText")
    current_text = current_snapshot.get("normalizedText")
    if not isinstance(previous_text, str) or not isinstance(current_text, str):
        base["unavailableReason"] = "normalized_text_missing"
        return base

    previous_status = previous_snapshot.get("extractionStatus")
    current_status = current_snapshot.get("extractionStatus")
    usable = {"ok", "partial", "truncated"}
    if previous_status not in usable or current_status not in usable:
        base["unavailableReason"] = (
            f"unusable_extraction_status: previous={previous_status}, current={current_status}"
        )
        return base

    previous_lines = previous_text.splitlines()
    current_lines = current_text.splitlines()
    matcher = difflib.SequenceMatcher(
        a=previous_lines,
        b=current_lines,
        autojunk=False,
    )

    hunks: list[dict] = []
    removed_line_count = 0
    added_line_count = 0
    total_hunks = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        total_hunks += 1
        removed = previous_lines[i1:i2]
        added = current_lines[j1:j2]
        removed_line_count += len(removed)
        added_line_count += len(added)

        if len(hunks) >= MAX_DIFF_HUNKS:
            continue

        removed_preview, removed_truncated = clipped_lines(removed)
        added_preview, added_truncated = clipped_lines(added)
        old_line = i1 + 1 if i2 > i1 else None
        new_line = j1 + 1 if j2 > j1 else None
        context = nearby_heading(current_lines, j1) if current_lines else None
        if context is None and previous_lines:
            context = nearby_heading(previous_lines, i1)

        hunks.append(
            {
                "kind": tag,
                "oldStartLine": old_line,
                "newStartLine": new_line,
                "oldPage": line_page(previous_snapshot, old_line),
                "newPage": line_page(current_snapshot, new_line),
                "nearbyHeadingHeuristic": context,
                "removed": removed_preview,
                "added": added_preview,
                "removedPreviewTruncated": removed_truncated,
                "addedPreviewTruncated": added_truncated,
            }
        )

    base.update(
        {
            "available": True,
            "extractedTextChanged": previous_text != current_text,
            "previousTextSHA256": previous_snapshot.get("textSHA256"),
            "currentTextSHA256": current_snapshot.get("textSHA256"),
            "previousPageCount": previous_snapshot.get("pageCount"),
            "currentPageCount": current_snapshot.get("pageCount"),
            "previousExtractionStatus": previous_status,
            "currentExtractionStatus": current_status,
            "removedLineCount": removed_line_count,
            "addedLineCount": added_line_count,
            "totalHunkCount": total_hunks,
            "shownHunkCount": len(hunks),
            "hunksTruncated": total_hunks > len(hunks),
            "hunks": hunks,
        }
    )
    return base


def current_text_evidence(snapshot: dict | None, path: Path | None) -> dict:
    if snapshot is None:
        return {
            "available": False,
            "snapshotPath": path.as_posix() if path is not None else None,
        }
    return {
        "available": True,
        "snapshotPath": path.as_posix() if path is not None else None,
        "extractionStatus": snapshot.get("extractionStatus"),
        "extractionMethod": snapshot.get("extractionMethod"),
        "textSHA256": snapshot.get("textSHA256"),
        "pageCount": snapshot.get("pageCount"),
        "pagesWithText": snapshot.get("pagesWithText"),
        "characterCount": snapshot.get("characterCount"),
        "lineCount": snapshot.get("lineCount"),
        "truncated": bool(snapshot.get("truncated")),
    }


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
    if not any(
        token in source_name.lower()
        for token in EXPECTED_SOURCE_NAME_TOKENS
    ):
        raise EnrichmentError(
            "Reserve-guidance enricher only accepts supported official Navy Reserve guidance sources."
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


def human_change_note(detection_kind: str, text_comparison: dict | None = None) -> str:
    if detection_kind == "linked_document_changed":
        if isinstance(text_comparison, dict) and text_comparison.get("available") is True:
            if text_comparison.get("extractedTextChanged") is True:
                return (
                    "Prior and current normalized extracted-text snapshots are available. "
                    "Automation identified extraction-level additions and removals for human "
                    "review, but it has not determined the meaning, applicability, or policy "
                    "effect of those differences. PDF layout/extraction can also create apparent "
                    "text changes. Human comparison of the official source is required."
                )
            return (
                "The PDF bytes changed, but the prior and current normalized extracted-text "
                "snapshots are identical. The difference may be metadata, layout, non-text "
                "content, or something not represented by text extraction. Human source review "
                "is required."
            )
        return (
            "The monitor detected different PDF bytes at an already-known official document "
            "URL, but a usable prior/current extracted-text comparison is not available for "
            "this detected pair. Human comparison and source review are required."
        )

    return (
        "The monitor detected a new linked official Navy Reserve guidance PDF. "
        "Automated tooling verified the current document fingerprint but has not "
        "determined the document's policy effect. Human source review is required."
    )


def enriched_summary(
    label: str,
    detection_kind: str,
    text_comparison: dict | None = None,
) -> str:
    if detection_kind == "linked_document_changed":
        comparison_available = (
            isinstance(text_comparison, dict)
            and text_comparison.get("available") is True
        )
        if comparison_available:
            if text_comparison.get("extractedTextChanged") is True:
                comparison_sentence = (
                    "A normalized extracted-text comparison is available for human review. "
                    "No automated conclusion has been made about the policy meaning or effect "
                    "of those differences."
                )
            else:
                comparison_sentence = (
                    "The normalized extracted text is unchanged even though the PDF bytes differ; "
                    "human review is required to determine what changed."
                )
        else:
            comparison_sentence = (
                "A usable prior/current extracted-text comparison is not available for this "
                "detected pair."
            )

        return (
            f"The Reserve Intel monitor detected a new version of {label} at its "
            "official Navy Reserve PDF URL. The current PDF was re-fetched and "
            "matches the fingerprint captured at detection. "
            + comparison_sentence
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
    text_comparison: dict | None = None,
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

    comparison_text = ""
    if isinstance(text_comparison, dict) and text_comparison.get("available") is True:
        comparison_text = (
            " Extracted-text comparison: "
            f"{text_comparison.get('removedLineCount', 0)} removed line(s), "
            f"{text_comparison.get('addedLineCount', 0)} added line(s), "
            f"{text_comparison.get('totalHunkCount', 0)} change hunk(s)."
        )

    return (
        f"Automated evidence verification for {label}: detection kind "
        f"`{detection_kind}`. The official Navy Reserve PDF was re-fetched from "
        f"{final_url} and its SHA-256 fingerprint matched the fingerprint stored "
        f"with the detected draft.{metadata_text}{comparison_text} HTTP Last-Modified "
        "metadata is not treated as a policy effective date or revision date. "
        + human_change_note(detection_kind, text_comparison)
    )



def enrich_draft(
    draft: dict,
    monitor_module: ModuleType,
    enriched_at: str | None = None,
    evidence_root: Path | None = None,
) -> dict:
    evidence, article = validate_draft(draft)

    source_url = evidence["sourceURL"]
    detected_fingerprint = evidence["sourceFingerprint"].strip()
    previous_fingerprint = evidence.get("previousFingerprint")
    root = evidence_root or (
        RESFOR_NOTICES_EVIDENCE_ROOT
        if "resfor notices" in str(evidence.get("sourceName") or "").lower()
        else DEFAULT_EVIDENCE_ROOT
    )

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

    current_snapshot, current_path, current_error = load_text_snapshot(
        root, source_url, detected_fingerprint
    )
    previous_snapshot = None
    previous_path = None
    previous_error = None
    if detection_kind == "linked_document_changed":
        previous_snapshot, previous_path, previous_error = load_text_snapshot(
            root, source_url,
            previous_fingerprint if isinstance(previous_fingerprint, str) else None,
        )

    if detection_kind == "linked_document_changed":
        unavailable_parts = []
        if previous_error:
            unavailable_parts.append(f"previous={previous_error}")
        if current_error:
            unavailable_parts.append(f"current={current_error}")
        text_comparison = build_text_comparison(
            previous_snapshot,
            current_snapshot,
            previous_path,
            current_path,
            "; ".join(unavailable_parts) if unavailable_parts else None,
        )
    else:
        text_comparison = {
            "comparisonKind": "normalized_extracted_text_diff",
            "available": False,
            "unavailableReason": "new_linked_document_has_no_prior_version",
            "currentSnapshotPath": current_path.as_posix() if current_path else None,
            "policyInterpretationClaimed": False,
            "note": (
                "This is a newly linked document, so there is no earlier monitored version "
                "to compare. Human source review is required."
            ),
        }

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
        "currentTextEvidence": current_text_evidence(current_snapshot, current_path),
        "textComparison": text_comparison,
        "automatedChangeAttributionClaimed": False,
        "effectiveDateInferred": False,
        "changeAttributionNote": human_change_note(detection_kind, text_comparison),
    }

    enriched["articleDraft"]["summary"] = enriched_summary(
        label,
        detection_kind,
        text_comparison,
    )
    enriched["articleDraft"]["whyItMatters"] = enriched_why_it_matters()
    enriched["articleDraft"]["details"] = enriched_details(
        label,
        detection_kind,
        final_url,
        fetched.get("lastModified"),
        fetched.get("contentLength"),
        text_comparison,
    )

    # Never infer an effective date from HTTP Last-Modified, PDF metadata, or text diffs.
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

    with tempfile.TemporaryDirectory() as tmp:
        evidence_root = Path(tmp) / "evidence"
        source_url = base_draft["sourceEvidence"]["sourceURL"]

        def write_snapshot(fingerprint: str, text: str) -> None:
            path = snapshot_path(evidence_root, source_url, fingerprint)
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = text.splitlines()
            payload = {
                "schemaVersion": 1,
                "sourceType": "reserve_guidance",
                "sourceURL": source_url,
                "finalURL": source_url,
                "title": "RESPERSMAN 1570-010",
                "fingerprint": fingerprint,
                "capturedAt": "2026-09-16T00:00:00Z",
                "extractionStatus": "ok",
                "extractionMethod": "pypdf-test-fixture",
                "pageCount": 1,
                "pagesWithText": 1,
                "characterCount": len(text),
                "lineCount": len(lines),
                "textSHA256": sha256_text(text),
                "truncated": False,
                "pageLineRanges": [{"page": 1, "startLine": 1, "endLine": len(lines)}],
                "warnings": [],
                "normalizedText": text,
            }
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        write_snapshot(
            "old-fingerprint",
            "1. Purpose\nMembers shall complete 12 drills.\n2. Administration",
        )
        write_snapshot(
            "new-fingerprint",
            "1. Purpose\nMembers shall complete 14 drills.\n2. Administration",
        )

        enriched = enrich_draft(
            base_draft,
            FakeMonitor,
            "2026-09-16T01:00:00Z",
            evidence_root,
        )

    assert enriched["enrichment"]["sourceType"] == "reserve_guidance"
    assert enriched["enrichment"]["fingerprintMatchesDetection"] is True
    assert enriched["enrichment"]["documentKind"] == "RESPERSMAN"
    assert enriched["enrichment"]["documentIdentifier"] == "1570-010"
    assert enriched["enrichment"]["automatedChangeAttributionClaimed"] is False
    assert enriched["enrichment"]["effectiveDateInferred"] is False
    comparison = enriched["enrichment"]["textComparison"]
    assert comparison["available"] is True
    assert comparison["extractedTextChanged"] is True
    assert comparison["removedLineCount"] == 1
    assert comparison["addedLineCount"] == 1
    assert comparison["hunks"][0]["oldPage"] == 1
    assert comparison["hunks"][0]["newPage"] == 1
    assert "12 drills" in comparison["hunks"][0]["removed"][0]
    assert "14 drills" in comparison["hunks"][0]["added"][0]
    assert comparison["hunks"][0]["nearbyHeadingHeuristic"] == "1. Purpose"

    # Heading heuristics must prefer structural RESPERSMAN context and reject
    # signature/OCR noise such as the name-like line seen in real 1570-030 text.
    heading_fixture = [
        "J. A. s@oMMER",
        "Deputy",
        "Article No.",
        "1570-030",
        "Article Title",
        "Individual Inactive Duty Trainin2 Record Maintenance",
        "• Simplifies and updates existing procedures.",
        "• Removed the requirement for non-IDT orders to be maintained in the",
    ]
    assert nearby_heading(heading_fixture, len(heading_fixture) - 1) == (
        "Individual Inactive Duty Trainin2 Record Maintenance"
    )
    assert nearby_heading(["J. A. s@oMMER", "Deputy"], 1) is None

    # Sentence fragments that merely begin with a section-like word must not
    # outrank the actual article title. This mirrors the real 1570-030 text
    # extraction where a wrapped bullet line begins with "Record Maintenance".
    wrapped_body_fixture = [
        "Article Title",
        "Individual Inactive Duty Trainin2 Record Maintenance",
        "• Simplifies and updates existing Individual Inactive Duty (IDT) Training",
        "Record Maintenance procedures and responsibilities.",
        "• Removed the requirement for non-IDT orders to be maintained in the",
    ]
    assert nearby_heading(wrapped_body_fixture, len(wrapped_body_fixture) - 1) == (
        "Individual Inactive Duty Trainin2 Record Maintenance"
    )
    assert structural_heading_candidate(
        ["Record Maintenance procedures and responsibilities."], 0
    ) is None
    assert enriched["enrichment"]["currentTextEvidence"]["available"] is True
    assert enriched["articleDraft"]["effectiveDate"] is None
    assert enriched["articleDraft"]["isActive"] is False
    assert enriched["publishReady"] is False
    assert enriched["requiresHumanReview"] is True
    assert enriched["reviewChecklist"]["approvedForPublication"] is False
    assert "normalized extracted-text comparison is available" in (
        enriched["articleDraft"]["summary"]
    )
    assert "not treated as a policy effective date" in enriched["articleDraft"]["details"]

    # PDF bytes may change while normalized extracted text remains identical.
    with tempfile.TemporaryDirectory() as tmp:
        evidence_root = Path(tmp) / "evidence"
        source_url = base_draft["sourceEvidence"]["sourceURL"]
        identical_text = "1. Purpose\nNo textual policy change detected by extraction."
        for fingerprint in ("old-fingerprint", "new-fingerprint"):
            path = snapshot_path(evidence_root, source_url, fingerprint)
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = identical_text.splitlines()
            path.write_text(
                json.dumps(
                    {
                        "sourceURL": source_url,
                        "fingerprint": fingerprint,
                        "extractionStatus": "ok",
                        "pageCount": 1,
                        "textSHA256": sha256_text(identical_text),
                        "pageLineRanges": [{"page": 1, "startLine": 1, "endLine": len(lines)}],
                        "normalizedText": identical_text,
                    }
                ) + "\n",
                encoding="utf-8",
            )
        identical = enrich_draft(
            base_draft, FakeMonitor, "2026-09-16T01:00:00Z", evidence_root
        )
        assert identical["enrichment"]["textComparison"]["available"] is True
        assert identical["enrichment"]["textComparison"]["extractedTextChanged"] is False
        assert "normalized extracted text is unchanged" in identical["articleDraft"]["summary"]

    # New linked PDFs use the same verification path but different wording.
    new_document = copy.deepcopy(base_draft)
    new_document["sourceEvidence"]["detectionKind"] = "new_linked_document"
    new_document["sourceEvidence"]["previousFingerprint"] = None
    enriched_new = enrich_draft(
        new_document,
        FakeMonitor,
        "2026-09-16T01:00:00Z",
        Path(tempfile.mkdtemp()) / "evidence",
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

    # CLI must leave evidence-root unset by default so enrich_draft()
    # can select the correct source-specific evidence directory.
    parser_defaults = build_arg_parser().parse_args(["--self-test"])
    assert parser_defaults.evidence_root is None

    print("SELF-TEST PASSED")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--monitor-path", default=None)
    parser.add_argument("--evidence-root", default=None)
    parser.add_argument("--enriched-at", default=None)
    parser.add_argument("--self-test", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

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
            Path(args.evidence_root) if args.evidence_root else None,
        )
        atomic_write_json(output_path, enriched)
    except (json.JSONDecodeError, EnrichmentError, OSError) as exc:
        print(f"Reserve-guidance enrichment failed: {exc}", file=sys.stderr)
        return 2

    print(f"ENRICHED RESERVE GUIDANCE DRAFT: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
