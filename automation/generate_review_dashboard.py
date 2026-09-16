#!/usr/bin/env python3
"""
Generate Reserve Intel review dashboard data.

Phase 3A:
- reads pending draft JSON from main
- when possible, reads the current enriched draft from its review branch
- reads the live Reserve Intel feed for recently published items
- writes docs/reserve-intel/data.json
- optionally injects one dashboard-only demo pending article with --demo
- never modifies drafts, reviews, branches, or reserve-content-feed.json

Real Save Draft writes are handled separately by review_dashboard_server.py.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any
from urllib.parse import quote


REVIEW_BRANCH_PREFIX = "reserve-intel-review/"


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


def review_branch_for(article_id: str) -> str:
    return f"{REVIEW_BRANCH_PREFIX}{article_id}"


def detect_repo_slug() -> str | None:
    configured = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if configured:
        return configured

    if shutil.which("gh") is None:
        return None

    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    value = result.stdout.strip()
    return value or None


def github_branch_json(repo: str, branch: str, path: str) -> dict[str, Any] | None:
    if shutil.which("gh") is None:
        return None

    api_path = f"repos/{repo}/contents/{quote(path, safe='/')}"
    result = subprocess.run(
        [
            "gh",
            "api",
            "--method",
            "GET",
            api_path,
            "-f",
            f"ref={branch}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    try:
        response = json.loads(result.stdout)
        encoded = response.get("content")
        if not isinstance(encoded, str):
            return None
        raw = base64.b64decode(encoded).decode("utf-8")
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None

    return value if isinstance(value, dict) else None


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


def dashboard_item(
    draft: dict[str, Any],
    path: Path,
    *,
    content_origin: str,
    review_branch: str,
    save_eligible: bool,
) -> dict[str, Any]:
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
        "_reviewBranch": review_branch,
        "_contentOrigin": content_origin,
        "_saveEligible": save_eligible,
        "_demo": False,
    }


def pending_item(path: Path, repo: str | None) -> dict[str, Any]:
    main_draft = load_json(path)
    main_article = as_dict(main_draft.get("articleDraft"))
    article_id = main_article.get("id") or path.stem
    if not isinstance(article_id, str) or not article_id:
        article_id = path.stem

    branch = review_branch_for(article_id)

    if repo:
        branch_draft = github_branch_json(repo, branch, str(path))
        if branch_draft is not None:
            branch_article = as_dict(branch_draft.get("articleDraft"))
            if branch_article.get("id") == article_id:
                return dashboard_item(
                    branch_draft,
                    path,
                    content_origin="reviewBranch",
                    review_branch=branch,
                    save_eligible=True,
                )

    return dashboard_item(
        main_draft,
        path,
        content_origin="main",
        review_branch=branch,
        save_eligible=False,
    )


def demo_pending_item() -> dict[str, Any]:
    """Return a dashboard-only fake article for exercising the Phase 3A editor."""
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
            "The demo lets you evaluate the Mac editing experience before any Reject "
            "or Approve action is connected to GitHub."
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
        "_reviewBranch": None,
        "_contentOrigin": "demo",
        "_saveEligible": False,
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
    use_review_branch_content: bool = True,
) -> dict[str, Any]:
    pending: list[dict[str, Any]] = []
    repo = detect_repo_slug() if use_review_branch_content else None

    if pending_dir.exists():
        for path in sorted(pending_dir.glob("*.json")):
            pending.append(pending_item(path, repo))

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
        "repository": repo,
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
    parser.add_argument(
        "--no-review-branch-content",
        action="store_true",
        help="Do not attempt to load enriched draft content from remote review branches.",
    )
    args = parser.parse_args()

    payload = generate(
        Path(args.pending_dir),
        Path(args.feed),
        Path(args.output),
        demo=args.demo,
        use_review_branch_content=not args.no_review_branch_content,
    )

    branch_backed = sum(
        1 for item in payload["pending"]
        if isinstance(item, dict) and item.get("_contentOrigin") == "reviewBranch"
    )

    print(f"Dashboard data written: {args.output}")
    print(f"Demo mode: {'ON' if args.demo else 'OFF'}")
    print(f"Pending reviews: {len(payload['pending'])}")
    print(f"Review-branch drafts loaded: {branch_backed}")
    print(f"Published articles: {len(payload['published'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
