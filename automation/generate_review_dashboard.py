#!/usr/bin/env python3
"""
Generate Reserve Intel review dashboard data.

Phase 2B remains read-only with respect to the repository's review pipeline:
- reads pending draft JSON
- reads the live Reserve Intel feed for recently published items
- writes docs/reserve-intel/data.json
- optionally injects one dashboard-only demo pending article with --demo
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
        "_demo": False,
    }


def demo_pending_item() -> dict[str, Any]:
    """Return a dashboard-only fake article for exercising the Phase 2B editor."""
    return {
        "id": "demo-reserve-intel-editor-preview",
        "title": "Demo Review — Reserve Training Requirement Update",
        "publishedAt": utc_now_iso(),
        "updatedAt": utc_now_iso(),
        "category": "Training & Readiness",
        "status": "TRACKING",
        "priority": "NORMAL",
        "summary": (
            "This is a dashboard-only demo article used to test the Reserve Intel "
            "editor. Change this text freely; it cannot modify the repository."
        ),
        "whyItMatters": (
            "The demo lets you evaluate the Mac editing experience before any Save, "
            "Reject, or Approve action is connected to GitHub."
        ),
        "details": (
            "Use the editor to change the title and article text. Try the priority, "
            "status, category, service, Reserve status, date, targeting, and pinned controls.\n\n"
            "The source and detected evidence areas remain read-only."
        ),
        "effectiveDate": None,
        "sourceName": "Demo Official Source — Read Only",
        "sourceURL": "https://www.navyreserve.navy.mil/",
        "audience": {
            "service": "USN",
            "reserveStatus": "ALL",
            "trainingWing": None,
            "squadron": None,
        },
        "isPinned": False,
        "isActive": False,
        "draftStatus": "PENDING_HUMAN_REVIEW",
        "requiresHumanReview": True,
        "publishReady": False,
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
        "textComparison": {
            "available": True,
            "changed": True,
            "addedLines": 1,
            "removedLines": 1,
            "hunks": [
                {
                    "page": 2,
                    "heading": "Demo Extracted Text Evidence",
                    "removedLines": ["Annual completion is required."],
                    "addedLines": ["Completion is required every three years."],
                }
            ],
        },
        "_sourceFile": None,
        "_demo": True,
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
        item["_demo"] = False
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
    *,
    demo: bool = False,
) -> dict[str, Any]:
    pending: list[dict[str, Any]] = []

    if pending_dir.exists():
        for path in sorted(pending_dir.glob("*.json")):
            pending.append(pending_item(path))

    if demo:
        pending.insert(0, demo_pending_item())

    pending.sort(
        key=lambda item: (
            item.get("priority") != "HIGH",
            str(item.get("updatedAt") or item.get("publishedAt") or ""),
        )
    )

    payload = {
        "generatedAt": utc_now_iso(),
        "demoMode": demo,
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
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Inject one dashboard-only fake pending article for editor testing.",
    )
    args = parser.parse_args()

    payload = generate(
        Path(args.pending_dir),
        Path(args.feed),
        Path(args.output),
        demo=args.demo,
    )

    print(f"Dashboard data written: {args.output}")
    print(f"Demo mode: {'ON' if args.demo else 'OFF'}")
    print(f"Pending reviews: {len(payload['pending'])}")
    print(f"Published articles: {len(payload['published'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
