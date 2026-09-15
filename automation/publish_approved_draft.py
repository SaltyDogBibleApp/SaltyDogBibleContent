#!/usr/bin/env python3
"""
Salty Dog Bible — publish a merged/approved Reserve Intel draft (IT-2D.5).

Hard safety gate:
- requires all six PR approval checkboxes to be checked
- requires an official/verified source flag
- refuses duplicate article IDs or source URLs
- only then activates the article and updates reserve-content-feed.json
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys

CHECKS = [
    "I opened the official source.",
    "I verified the facts against the official source.",
    "I verified the status and effective date.",
    "I verified the intended audience.",
    "I reviewed the title, summary, Why It Matters, and details.",
    "I approve publication to Reserve Intel.",
]


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def checkbox_checked(body: str, label: str) -> bool:
    pattern = re.compile(
        r"(?mi)^\s*-\s*\[[xX]\]\s*" + re.escape(label) + r"\s*$"
    )
    return bool(pattern.search(body))


def verify_approval_body(body: str) -> None:
    missing = [label for label in CHECKS if not checkbox_checked(body, label)]
    if missing:
        raise ValueError(
            "Approval gate failed. Unchecked items: " + "; ".join(missing)
        )


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} root must be a JSON object.")
    return value


def publish(
    draft_path: Path,
    feed_path: Path,
    approval_body: str,
    published_dir: Path,
    review_marker: Path | None,
    review_published_dir: Path | None,
) -> str:
    verify_approval_body(approval_body)

    draft = load_json(draft_path)
    if draft.get("draftStatus") != "PENDING_HUMAN_REVIEW":
        raise ValueError("Draft is not pending human review.")
    if draft.get("requiresHumanReview") is not True:
        raise ValueError("Draft must require human review.")
    if draft.get("publishReady") is not False:
        raise ValueError("Unexpected pending draft publishReady value.")

    evidence = draft.get("sourceEvidence")
    if not isinstance(evidence, dict) or evidence.get("officialHostVerified") is not True:
        raise ValueError("Official source host has not been verified.")

    article = deepcopy(draft.get("articleDraft"))
    if not isinstance(article, dict):
        raise ValueError("articleDraft is missing.")

    article_id = article.get("id")
    source_url = article.get("sourceURL")
    if not isinstance(article_id, str) or not article_id:
        raise ValueError("Article ID is missing.")
    if not isinstance(source_url, str) or not source_url:
        raise ValueError("Article sourceURL is missing.")

    feed = load_json(feed_path)
    articles = feed.get("intelArticles")
    if not isinstance(articles, list):
        raise ValueError("Feed intelArticles must be an array.")

    for existing in articles:
        if not isinstance(existing, dict):
            continue
        if existing.get("id") == article_id:
            raise ValueError(f"Article ID already exists in live feed: {article_id}")
        if existing.get("sourceURL") == source_url:
            raise ValueError(
                f"An article with this sourceURL already exists in the live feed: {source_url}"
            )

    now = utc_now_iso()
    article["isActive"] = True
    article["updatedAt"] = now

    feed["generatedAt"] = now
    feed["intelArticles"] = [article] + articles
    feed_path.write_text(
        json.dumps(feed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    published_dir.mkdir(parents=True, exist_ok=True)
    archived = deepcopy(draft)
    archived["draftStatus"] = "PUBLISHED"
    archived["requiresHumanReview"] = False
    archived["publishReady"] = True
    archived["approvedAt"] = now
    archived["articleDraft"] = article

    published_path = published_dir / draft_path.name
    published_path.write_text(
        json.dumps(archived, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    draft_path.unlink()

    if review_marker and review_marker.exists() and review_published_dir:
        review_published_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(
            str(review_marker),
            str(review_published_dir / review_marker.name),
        )

    return article_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", required=True)
    parser.add_argument("--feed", default="reserve-content-feed.json")
    parser.add_argument("--approval-body-file", required=True)
    parser.add_argument("--published-dir", default="drafts/published")
    parser.add_argument("--review-marker", default=None)
    parser.add_argument("--review-published-dir", default="reviews/published")
    args = parser.parse_args()

    try:
        body = Path(args.approval_body_file).read_text(encoding="utf-8")
        article_id = publish(
            Path(args.draft),
            Path(args.feed),
            body,
            Path(args.published_dir),
            Path(args.review_marker) if args.review_marker else None,
            Path(args.review_published_dir) if args.review_published_dir else None,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"PUBLISH BLOCKED: {exc}", file=sys.stderr)
        return 1

    print(f"PUBLISHED: {article_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
