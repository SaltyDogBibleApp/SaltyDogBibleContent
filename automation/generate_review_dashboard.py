#!/usr/bin/env python3
"""
Generate the read-only Reserve Intel review dashboard data.

Phase 1 is intentionally read-only:
- reads pending draft JSON
- reads the live Reserve Intel feed for recently published items
- writes docs/reserve-intel/data.json
- never modifies drafts, reviews, or reserve-content-feed.json
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} root must be a JSON object.")
    return value


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_hunk(hunk: Any) -> dict[str, Any] | None:
    if not isinstance(hunk, dict):
        return None

    removed = hunk.get("removedLines")
    added = hunk.get("addedLines")

    return {
        "page": hunk.get("page"),
        "heading": hunk.get("heading"),
        "removedLines": removed if isinstance(removed, list) else [],
        "addedLines": added if isinstance(added, list) else [],
    }


def extract_text_comparison(draft: dict[str, Any]) -> dict[str, Any] | None:
    """
    The Reserve Intel enrichment pipeline has evolved over time, so inspect a
    small set of known evidence containers instead of assuming one exact path.
    """
    candidates: list[Any] = []

    for key in ("textComparison", "extractedTextComparison"):
        if key in draft:
            candidates.append(draft.get(key))

    evidence = as_dict(draft.get("sourceEvidence"))
    for key in ("textComparison", "extractedTextComparison"):
        if key in evidence:
            candidates.append(evidence.get(key))

    enrichment = as_dict(draft.get("enrichment"))
    for key in ("textComparison", "extractedTextComparison"):
        if key in enrichment:
            candidates.append(enrichment.get(key))

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        hunks_raw = candidate.get("hunks")
        hunks = []
        if isinstance(hunks_raw, list):
            for hunk in hunks_raw:
                normalized = normalize_hunk(hunk)
                if normalized:
                    hunks.append(normalized)

        return {
            "available": candidate.get("available") is True,
            "changed": candidate.get("changed") is True,
            "addedLines": candidate.get("addedLines"),
            "removedLines": candidate.get("removedLines"),
            "hunks": hunks,
        }

    return None


def pending_item(path: Path) -> dict[str, Any]:
    draft = load_json(path)
    article = as_dict(draft.get("articleDraft"))

    return {
        "id": article.get("id") or path.stem,
        "title": article.get("title") or path.stem,
        "publishedAt": article.get("publishedAt"),
        "updatedAt": article.get("updatedAt"),
        "category": article.get("category"),
        "status": article.get("status"),
        "priority": article.get("priority"),
        "summary": article.get("summary"),
        "whyItMatters": article.get("whyItMatters"),
        "details": article.get("details"),
        "effectiveDate": article.get("effectiveDate"),
        "sourceName": article.get("sourceName"),
        "sourceURL": article.get("sourceURL"),
        "audience": as_dict(article.get("audience")),
        "isPinned": article.get("isPinned"),
        "isActive": article.get("isActive"),
        "draftStatus": draft.get("draftStatus"),
        "requiresHumanReview": draft.get("requiresHumanReview"),
        "publishReady": draft.get("publishReady"),
        "reviewChecklist": as_dict(draft.get("reviewChecklist")),
        "textComparison": extract_text_comparison(draft),
        "_sourceFile": str(path),
    }


def published_items(feed_path: Path) -> list[dict[str, Any]]:
    if not feed_path.exists():
        return []

    feed = load_json(feed_path)
    articles = feed.get("intelArticles")
    if not isinstance(articles, list):
        raise ValueError("reserve-content-feed.json intelArticles must be an array.")

    result: list[dict[str, Any]] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        item = dict(article)
        item["reviewChecklist"] = {}
        item["textComparison"] = None
        result.append(item)

    result.sort(
        key=lambda item: str(item.get("updatedAt") or item.get("publishedAt") or ""),
        reverse=True,
    )
    return result


def generate(
    pending_dir: Path,
    feed_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    pending: list[dict[str, Any]] = []

    if pending_dir.exists():
        for path in sorted(pending_dir.glob("*.json")):
            pending.append(pending_item(path))

    pending.sort(
        key=lambda item: (
            item.get("priority") != "HIGH",
            str(item.get("updatedAt") or item.get("publishedAt") or ""),
        )
    )

    payload = {
        "generatedAt": utc_now_iso(),
        "pending": pending,
        "published": published_items(feed_path),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pending-dir", default="drafts/pending")
    parser.add_argument("--feed", default="reserve-content-feed.json")
    parser.add_argument("--output", default="docs/reserve-intel/data.json")
    args = parser.parse_args()

    payload = generate(
        Path(args.pending_dir),
        Path(args.feed),
        Path(args.output),
    )

    print(f"Dashboard data written: {args.output}")
    print(f"Pending reviews: {len(payload['pending'])}")
    print(f"Published articles: {len(payload['published'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
