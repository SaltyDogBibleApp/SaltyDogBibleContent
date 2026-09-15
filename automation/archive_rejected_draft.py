#!/usr/bin/env python3
"""
Salty Dog Bible — archive a rejected Reserve Intel review.

Purpose:
- handles a Reserve Intel review PR that was closed without merge
- moves its pending draft from drafts/pending to drafts/rejected
- records rejection metadata for auditability
- preserves the PR review body under reviews/rejected
- NEVER edits reserve-content-feed.json
- NEVER activates an article
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} root must be a JSON object.")
    return value


def archive_rejected(
    draft_path: Path,
    rejected_dir: Path,
    review_body: str,
    review_marker: Path | None,
    review_rejected_dir: Path,
    pr_number: str,
    pr_url: str,
    pr_title: str,
) -> str:
    draft = load_json(draft_path)

    if draft.get("draftStatus") != "PENDING_HUMAN_REVIEW":
        raise ValueError("Draft is not pending human review.")
    if draft.get("requiresHumanReview") is not True:
        raise ValueError("Draft must require human review.")
    if draft.get("publishReady") is not False:
        raise ValueError("Unexpected pending draft publishReady value.")

    article = draft.get("articleDraft")
    if not isinstance(article, dict):
        raise ValueError("articleDraft is missing.")

    article_id = article.get("id")
    if not isinstance(article_id, str) or not article_id.strip():
        raise ValueError("Article ID is missing.")

    # Rejected material must never become active or publish-ready.
    if article.get("isActive") is not False:
        raise ValueError("Rejected pending draft must have articleDraft.isActive=false.")

    rejected_dir.mkdir(parents=True, exist_ok=True)
    rejected_path = rejected_dir / draft_path.name
    if rejected_path.exists():
        raise ValueError(f"Rejected archive already exists: {rejected_path}")

    now = utc_now_iso()

    archived = deepcopy(draft)
    archived["draftStatus"] = "REJECTED"
    archived["requiresHumanReview"] = False
    archived["publishReady"] = False
    archived["rejectedAt"] = now
    archived["rejection"] = {
        "reason": "review_pr_closed_without_merge",
        "pullRequestNumber": str(pr_number),
        "pullRequestURL": pr_url,
        "pullRequestTitle": pr_title,
        "reviewBodySHA256": hashlib.sha256(
            review_body.encode("utf-8")
        ).hexdigest(),
    }
    archived["articleDraft"]["isActive"] = False

    rejected_path.write_text(
        json.dumps(archived, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    draft_path.unlink()

    review_rejected_dir.mkdir(parents=True, exist_ok=True)
    rejected_review_path = review_rejected_dir / f"{article_id}.md"

    if rejected_review_path.exists():
        raise ValueError(f"Rejected review archive already exists: {rejected_review_path}")

    # If a review marker somehow already exists on main, preserve it verbatim.
    # Normally a rejected review PR was never merged, so the PR body is the
    # authoritative review record available on main.
    if review_marker and review_marker.exists():
        shutil.move(str(review_marker), str(rejected_review_path))
    else:
        header = [
            "# Rejected Reserve Intel Review",
            "",
            f"- Rejected at: {now}",
            f"- Pull request: #{pr_number}",
            f"- Pull request URL: {pr_url}",
            "- Disposition: Closed without merge",
            "",
            "---",
            "",
        ]
        rejected_review_path.write_text(
            "\n".join(header) + review_body.rstrip() + "\n",
            encoding="utf-8",
        )

    return article_id


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        draft_path = root / "drafts/pending/intel-test-rejection.json"
        rejected_dir = root / "drafts/rejected"
        review_rejected_dir = root / "reviews/rejected"
        review_marker = root / "reviews/pending/intel-test-rejection.md"

        draft_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "draftSchemaVersion": 1,
            "draftStatus": "PENDING_HUMAN_REVIEW",
            "requiresHumanReview": True,
            "publishReady": False,
            "reviewChecklist": {
                "sourceOpenedAndRead": False,
            },
            "articleDraft": {
                "id": "intel-test-rejection",
                "title": "Test rejection",
                "isActive": False,
            },
        }
        draft_path.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

        body = "# Reserve Intel Review\n\n- [ ] Test checkbox\n"
        article_id = archive_rejected(
            draft_path=draft_path,
            rejected_dir=rejected_dir,
            review_body=body,
            review_marker=review_marker,
            review_rejected_dir=review_rejected_dir,
            pr_number="123",
            pr_url="https://github.com/example/repo/pull/123",
            pr_title="Reserve Intel Review: Test rejection",
        )

        assert article_id == "intel-test-rejection"
        assert not draft_path.exists()

        archived_path = rejected_dir / "intel-test-rejection.json"
        assert archived_path.exists()
        archived = load_json(archived_path)
        assert archived["draftStatus"] == "REJECTED"
        assert archived["requiresHumanReview"] is False
        assert archived["publishReady"] is False
        assert archived["articleDraft"]["isActive"] is False
        assert archived["rejection"]["reason"] == "review_pr_closed_without_merge"
        assert archived["rejection"]["pullRequestNumber"] == "123"

        review_path = review_rejected_dir / "intel-test-rejection.md"
        assert review_path.exists()
        review_text = review_path.read_text(encoding="utf-8")
        assert "Closed without merge" in review_text
        assert body.strip() in review_text

    print("SELF-TEST PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft")
    parser.add_argument("--rejected-dir", default="drafts/rejected")
    parser.add_argument("--review-body-file")
    parser.add_argument("--review-marker", default=None)
    parser.add_argument("--review-rejected-dir", default="reviews/rejected")
    parser.add_argument("--pr-number")
    parser.add_argument("--pr-url")
    parser.add_argument("--pr-title", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        try:
            return self_test()
        except (AssertionError, OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"SELF-TEST FAILED: {exc}", file=sys.stderr)
            return 1

    required = {
        "--draft": args.draft,
        "--review-body-file": args.review_body_file,
        "--pr-number": args.pr_number,
        "--pr-url": args.pr_url,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        print(
            "REJECTION ARCHIVE BLOCKED: missing required argument(s): "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    try:
        body = Path(args.review_body_file).read_text(encoding="utf-8")
        article_id = archive_rejected(
            draft_path=Path(args.draft),
            rejected_dir=Path(args.rejected_dir),
            review_body=body,
            review_marker=Path(args.review_marker) if args.review_marker else None,
            review_rejected_dir=Path(args.review_rejected_dir),
            pr_number=str(args.pr_number),
            pr_url=str(args.pr_url),
            pr_title=str(args.pr_title or ""),
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"REJECTION ARCHIVE BLOCKED: {exc}", file=sys.stderr)
        return 1

    print(f"REJECTED ARCHIVED: {article_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
