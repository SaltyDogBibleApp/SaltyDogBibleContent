#!/usr/bin/env python3
"""
Salty Dog Bible — Reserve Intel GitHub review preview builder (IT-2D.5).

Creates a human-readable Markdown review page / PR body from one pending draft.
It does NOT edit reserve-content-feed.json and does NOT publish anything.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

CHECKS = [
    "I opened the official source.",
    "I verified the facts against the official source.",
    "I verified the status and effective date.",
    "I verified the intended audience.",
    "I reviewed the title, summary, Why It Matters, and details.",
    "I approve publication to Reserve Intel.",
]


def fail(message: str) -> None:
    raise ValueError(message)


def load_draft(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail("Draft root must be a JSON object.")
    if payload.get("draftStatus") != "PENDING_HUMAN_REVIEW":
        fail("Draft is not PENDING_HUMAN_REVIEW.")
    if payload.get("requiresHumanReview") is not True:
        fail("requiresHumanReview must be true.")
    if payload.get("publishReady") is not False:
        fail("Pending draft must have publishReady=false.")

    article = payload.get("articleDraft")
    if not isinstance(article, dict):
        fail("articleDraft is missing.")

    for key in ("id", "title", "category", "status", "priority", "summary",
                "whyItMatters", "details", "sourceName", "sourceURL"):
        if not isinstance(article.get(key), str) or not article[key].strip():
            fail(f"articleDraft.{key} is missing.")

    parsed = urlparse(article["sourceURL"])
    if parsed.scheme != "https" or not parsed.hostname:
        fail("articleDraft.sourceURL must be https.")

    return payload


def render_markdown(payload: dict) -> str:
    article = payload["articleDraft"]
    audience = article.get("audience") or {}
    evidence = payload.get("sourceEvidence") or {}
    impact = payload.get("appImpact") or {}
    impact_features = impact.get("features") or []
    impact_basis = impact.get("basis") or []

    lines = [
        "# Reserve Intel Review",
        "",
        "> **Human approval required.** Nothing in this review is live in the app yet.",
        "> Merging this pull request is the approval action. The publish workflow will",
        "> refuse to publish unless every approval checkbox below is checked.",
        "",
        f"## {article['title']}",
        "",
        "| Field | Proposed value |",
        "| --- | --- |",
        f"| Category | {article['category']} |",
        f"| Status | {article['status']} |",
        f"| Priority | {article['priority']} |",
        f"| Service | {audience.get('service', 'ALL')} |",
        f"| Reserve status | {audience.get('reserveStatus', 'ALL')} |",
        f"| Training Wing | {audience.get('trainingWing') or 'All'} |",
        f"| Squadron | {audience.get('squadron') or 'All'} |",
        "",
        "### Summary",
        "",
        article["summary"],
        "",
        "### Why It Matters",
        "",
        article["whyItMatters"],
        "",
        "### Details",
        "",
        article["details"],
        "",
        "### Official Source",
        "",
        f"**{article['sourceName']}**",
        "",
        f"{article['sourceURL']}",
        "",
        "### Detection Evidence",
        "",
        f"- Source type: `{evidence.get('sourceType', 'unknown')}`",
        f"- Listed date: {evidence.get('listedDate') or 'Not supplied'}",
        f"- Reserve signals: {', '.join(evidence.get('reserveSignals', [])) or 'None'}",
        f"- Official host verified: {'Yes' if evidence.get('officialHostVerified') else 'No'}",
        "",
        "### Potential Salty Dog Bible Impact",
        "",
        "> **Informational only.** These tags are an automated first-pass for the reviewer.",
        "> They do not change app behavior, app content, or the live Reserve Intel feed.",
        "",
        f"- App review recommended: {'Yes' if impact.get('requiresReview') else 'No'}",
        f"- Potentially affected features: {', '.join(impact_features) or 'None identified'}",
        f"- Tagging basis: {', '.join(impact_basis) or 'No specific app-impact match'}",
        f"- Note: {impact.get('note') or 'Human review is required before making any app change.'}",
        "",
        "## Approval Checklist",
        "",
    ]

    lines.extend(f"- [ ] {check}" for check in CHECKS)

    lines += [
        "",
        "### What the buttons mean",
        "",
        "- **Merge pull request** = approve this article for publication.",
        "- **Close pull request** = reject / do not publish.",
        "",
        "The live `reserve-content-feed.json` is not changed by this review PR itself.",
        "Publication happens only after a merged PR passes the approval gate.",
        "",
        f"<!-- reserve-intel-article-id: {article['id']} -->",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--metadata", default=None)
    args = parser.parse_args()

    try:
        payload = load_draft(Path(args.draft))
        rendered = render_markdown(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")

    if args.metadata:
        article = payload["articleDraft"]
        Path(args.metadata).write_text(
            json.dumps(
                {
                    "articleID": article["id"],
                    "title": article["title"],
                    "sourceURL": article["sourceURL"],
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

    print(f"REVIEW PREVIEW CREATED: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
