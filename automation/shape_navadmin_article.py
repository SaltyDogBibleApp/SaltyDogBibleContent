#!/usr/bin/env python3
"""
Salty Dog Bible — Reserve Intel human-friendly article shaping (IT-2D.6B)

Input:
- one already-enriched NAVADMIN pending draft

Output:
- rewrites only articleDraft.title / summary / whyItMatters / details
- preserves source-grounded facts from enrichment.extractedSections
- keeps all human approval gates locked

Safety:
- does NOT publish
- does NOT edit reserve-content-feed.json
- does NOT mark any review checkbox complete
- refuses to run if source enrichment is missing
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys


PLACEHOLDER_PHRASES = (
    "automated draft from an official source",
    "may affect reserve policy",
    "replace this placeholder",
    "this draft was created automatically",
)

SECTION_HEADING_PREFIXES = (
    "Purpose.",
    "Policy Update.",
    "Civilian and Contractor Personnel.",
    "Training Systems Configuration.",
    "Network Access Restrictions.",
)


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def collapse(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def sentence_split(value: str) -> list[str]:
    text = collapse(value)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [p.strip() for p in parts if p.strip()]


def strip_section_heading(value: str) -> str:
    text = collapse(value)
    for prefix in SECTION_HEADING_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text


def strip_list_marker(value: str) -> str:
    return re.sub(r"^(?:[a-z]\.|[0-9]+\.)\s+", "", value.strip(), flags=re.I)


def plain_language(value: str) -> str:
    text = strip_list_marker(strip_section_heading(value))

    substitutions = (
        (r"\bperiodicity\b", "frequency"),
        (r"\bthree\s*\(3\)\s*years\b", "three years"),
        (r"\bthirty[- ]six\s*\(36\)\s*months\b", "36 months"),
        (r"\bshall\b", "must"),
        (r"\bofficially changed\b", "changed"),
        (r"\bactive duty\b", "active-duty"),
    )
    for pattern, replacement in substitutions:
        text = re.sub(pattern, replacement, text, flags=re.I)

    # Remove source-outline artifacts that survive PDF extraction.
    text = re.sub(r"\s+[a-z]\.\s+", " ", text)
    return collapse(text)


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = collapse(value)
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def find_sentence(sections: dict[str, str], predicate) -> str | None:
    for key in sorted(sections, key=lambda x: int(x) if str(x).isdigit() else 999):
        for sentence in sentence_split(sections[key]):
            clean = plain_language(sentence)
            if predicate(clean.lower()):
                return clean
    return None


def section_sentences(sections: dict[str, str], number: str) -> list[str]:
    return [plain_language(s) for s in sentence_split(sections.get(number, ""))]


def is_cac_change(subject: str, sections: dict[str, str]) -> bool:
    haystack = " ".join([subject] + list(sections.values())).lower()
    return (
        "cybersecurity awareness challenge" in haystack
        and "every three" in haystack
    )


def shape_title(subject: str, sections: dict[str, str]) -> str:
    if is_cac_change(subject, sections):
        return "Cybersecurity Awareness Training Changes to Every 3 Years"

    title = collapse(subject)
    title = re.sub(
        r"^MODIFICATION TO NAVADMIN\s+\d{3}/\d{2}\s*[-–—:]\s*",
        "",
        title,
        flags=re.I,
    )
    title = re.sub(r"^FISCAL YEAR\s+\d{4}\s+", "", title, flags=re.I)

    if title.isupper():
        title = title.title()

    return title[:140].strip()


def shape_cac_summary(sections: dict[str, str]) -> str:
    return (
        "Navy Cybersecurity Awareness Challenge (CAC) training for active-duty and "
        "Reserve military personnel is no longer an annual requirement. Effective "
        "immediately, members must complete CAC when initially granted network access "
        "and every three years thereafter."
    )


def shape_cac_why_it_matters(sections: dict[str, str]) -> str:
    local_tracking = find_sentence(
        sections,
        lambda s: "commands" in s
        and "locally track" in s
        and "36 months" in s,
    )

    first = (
        "Reservists who completed CAC within the previous 36 months fall within the "
        "new three-year training cycle."
    )

    if local_tracking:
        second = (
            "Until Navy training systems are updated, commands must locally track and "
            "document qualifying military personnel so compliant members do not have "
            "network access erroneously suspended."
        )
        return f"{first} {second}"

    return first


def shape_cac_details(sections: dict[str, str]) -> str:
    paragraph1 = (
        "NAVADMIN 204/26 modifies NAVADMIN 084/26 and changes Cybersecurity Awareness "
        "Challenge training for active-duty and Reserve military personnel. Military "
        "members must complete CAC when initially granted network access and every "
        "three years thereafter, replacing the previous annual fiscal-year requirement."
    )

    civilian = find_sentence(
        sections,
        lambda s: "civilian" in s and "annual" in s,
    )
    paragraph2 = (
        "The relaxed training frequency applies to military personnel. Civilian "
        "employees and contractors remain subject to annual CAC training."
        if civilian
        else ""
    )

    systems_text = " ".join(section_sentences(sections, "4")).lower()
    network_text = " ".join(section_sentences(sections, "5")).lower()

    paragraph3_parts: list[str] = []
    if "fltmps" in systems_text or "twms" in systems_text:
        paragraph3_parts.append(
            "FLTMPS and TWMS are being updated to reflect the three-year military "
            "training cycle."
        )
    if "locally track" in systems_text:
        paragraph3_parts.append(
            "Until those updates are complete, commands must locally track and "
            "document military personnel who completed CAC within the preceding "
            "36 months."
        )
    if "automated account disablement" in network_text or "disablement" in network_text:
        paragraph3_parts.append(
            "Echelon II CIOs must ensure automated account-disablement processes "
            "account for the modified frequency."
        )

    paragraphs = [p for p in (paragraph1, paragraph2, " ".join(paragraph3_parts)) if p]
    return "\n\n".join(paragraphs)


def generic_summary(sections: dict[str, str]) -> str:
    policy = section_sentences(sections, "2")
    purpose = section_sentences(sections, "1")

    candidates = unique(policy + purpose)
    if not candidates:
        raise ValueError("No source sentences available for summary shaping.")

    # Prefer the first two operationally meaningful sentences.
    ranked = sorted(
        candidates,
        key=lambda s: (
            0 if "effective" in s.lower() else 1,
            0 if any(word in s.lower() for word in ("required", "must", "changed", "supersedes")) else 1,
        ),
    )
    return " ".join(ranked[:2])


def generic_why_it_matters(sections: dict[str, str]) -> str:
    reserve = find_sentence(
        sections,
        lambda s: any(token in s for token in ("reserve", "selres", "selected reserve")),
    )
    command = find_sentence(
        sections,
        lambda s: "command" in s and any(token in s for token in ("must", "track", "ensure")),
    )

    values = unique([reserve or "", command or ""])
    if not values:
        return (
            "This NAVADMIN contains a Reserve-relevant requirement. Review the official "
            "source to confirm who is affected and what action, if any, is required."
        )
    return " ".join(values[:2])


def generic_details(sections: dict[str, str]) -> str:
    paragraphs: list[str] = []
    for number in ("1", "2", "3", "4", "5"):
        values = section_sentences(sections, number)
        if not values:
            continue
        # Keep the source structure but make it readable; limit each section.
        paragraphs.append(" ".join(values[:3]))
    if not paragraphs:
        raise ValueError("No extracted sections available for details shaping.")
    return "\n\n".join(paragraphs[:4])


def load_payload(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Draft root must be an object.")
    if payload.get("draftStatus") != "PENDING_HUMAN_REVIEW":
        raise ValueError("Draft is not pending human review.")
    if payload.get("requiresHumanReview") is not True:
        raise ValueError("Draft must require human review.")
    if payload.get("publishReady") is not False:
        raise ValueError("Pending draft must remain publishReady=false.")

    enrichment = payload.get("enrichment")
    if not isinstance(enrichment, dict):
        raise ValueError("Draft has not been source-enriched yet.")

    sections = enrichment.get("extractedSections")
    if not isinstance(sections, dict) or not sections:
        raise ValueError("Enrichment is missing extractedSections.")

    article = payload.get("articleDraft")
    if not isinstance(article, dict):
        raise ValueError("articleDraft is missing.")

    return payload


def assert_safety(payload: dict) -> None:
    if payload.get("draftStatus") != "PENDING_HUMAN_REVIEW":
        raise ValueError("Shaping changed draftStatus unexpectedly.")
    if payload.get("requiresHumanReview") is not True:
        raise ValueError("Shaping disabled requiresHumanReview.")
    if payload.get("publishReady") is not False:
        raise ValueError("Shaping set publishReady unexpectedly.")

    article = payload["articleDraft"]
    if article.get("isActive") is not False:
        raise ValueError("Shaping activated the article unexpectedly.")

    checklist = payload.get("reviewChecklist")
    if isinstance(checklist, dict) and any(value is not False for value in checklist.values()):
        raise ValueError("Shaping changed a human-review checklist item.")

    for field in ("title", "summary", "whyItMatters", "details"):
        value = collapse(article.get(field, ""))
        if not value:
            raise ValueError(f"Shaped article field is empty: {field}")
        lower = value.lower()
        if any(phrase in lower for phrase in PLACEHOLDER_PHRASES):
            raise ValueError(f"Placeholder language remains in {field}.")


def shape(payload: dict) -> dict:
    article = payload["articleDraft"]
    enrichment = payload["enrichment"]
    sections = enrichment["extractedSections"]
    subject = collapse(enrichment.get("subject") or article.get("title") or "")

    cac = is_cac_change(subject, sections)

    article["title"] = shape_title(subject, sections)
    article["summary"] = shape_cac_summary(sections) if cac else generic_summary(sections)
    article["whyItMatters"] = (
        shape_cac_why_it_matters(sections) if cac else generic_why_it_matters(sections)
    )
    article["details"] = shape_cac_details(sections) if cac else generic_details(sections)
    article["updatedAt"] = utc_now_iso()

    payload["shaping"] = {
        "schemaVersion": 1,
        "method": "deterministic-human-friendly-navadmin-v1",
        "shapedAt": utc_now_iso(),
        "sourceTextSHA256": enrichment.get("sourceTextSHA256"),
        "specializedTemplate": "cybersecurity-awareness-three-year-cycle" if cac else None,
        "humanReviewStillRequired": True,
    }

    # Re-assert the publication lock.
    payload["draftStatus"] = "PENDING_HUMAN_REVIEW"
    payload["requiresHumanReview"] = True
    payload["publishReady"] = False
    article["isActive"] = False

    checklist = payload.get("reviewChecklist")
    if isinstance(checklist, dict):
        for key in checklist:
            checklist[key] = False

    assert_safety(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = Path(args.draft)

    try:
        payload = load_payload(path)
        shaped = shape(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"SHAPING FAILED: {exc}", file=sys.stderr)
        return 1

    article = shaped["articleDraft"]

    if args.dry_run:
        print(json.dumps(
            {
                "title": article["title"],
                "summary": article["summary"],
                "whyItMatters": article["whyItMatters"],
                "details": article["details"],
                "status": article.get("status"),
                "category": article.get("category"),
            },
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    path.write_text(
        json.dumps(shaped, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"SHAPED: {path}")
    print(f"TITLE: {article['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
