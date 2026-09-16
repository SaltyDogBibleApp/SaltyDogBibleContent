
#!/usr/bin/env python3
"""
Serve the Reserve Intel dashboard and provide a narrowly scoped Save Draft API.

Security / safety properties:
- GitHub credentials remain in the Codespace; they are never sent to the browser.
- Save is allowed only for drafts/pending/*.json on the deterministic
  reserve-intel-review/<article_id> branch.
- The server fetches the exact current remote draft before every save.
- Only explicitly allowed editorial articleDraft fields can be modified.
- sourceURL, sourceName, source evidence, fingerprints, review metadata,
  publication gates, draftStatus, and reviewChecklist are never accepted
  from the browser and are never rewritten by the patch function.
- Reject is allowed only for the unique open Review PR whose head branch is
  reserve-intel-review/<article_id> and whose base branch is main.
- Reject closes that PR without merge and leaves archival to the existing
  reserve-intel-rejected-closed workflow.
- Approve is allowed only for the unique open Review PR whose head branch is
  reserve-intel-review/<article_id> and whose base branch is main.
- Approve requires an explicit browser confirmation, verifies the exact PR head
  SHA and pending draft gates, checks all six existing approval checkboxes in the
  PR body, marks a draft PR ready when necessary, and merges that exact head SHA.
- The dashboard never writes reserve-content-feed.json; the existing merged-PR
  publication workflow remains the only publication path.
"""

from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from typing import Any
from urllib.parse import quote, urlparse


CATEGORIES = {
    "Legislation / NDAA",
    "Policy",
    "Pay & Benefits",
    "Retirement",
    "VA / Veteran Benefits",
    "Training & Readiness",
    "Admin",
    "Other",
}

STATUSES = {
    "TRACKING",
    "PROPOSED",
    "INTRODUCED",
    "COMMITTEE",
    "PASSED HOUSE",
    "PASSED SENATE",
    "SIGNED",
    "EFFECTIVE",
    "SUPERSEDED",
}

PRIORITIES = {"NORMAL", "HIGH"}
SERVICES = {"ALL", "USN", "USMC"}
RESERVE_STATUSES = {"ALL", "SELRES", "VTU"}

REVIEW_BRANCH_PREFIX = "reserve-intel-review/"
MAX_REQUEST_BYTES = 128 * 1024
MAX_TITLE = 300
MAX_SUMMARY = 4000
MAX_WHY = 6000
MAX_DETAILS = 20000
MAX_TARGET = 120
MAX_REJECT_REASON = 2000

APPROVAL_CHECKS = [
    "I opened the official source.",
    "I verified the facts against the official source.",
    "I verified the status and effective date.",
    "I verified the intended audience.",
    "I reviewed the title, summary, Why It Matters, and details.",
    "I approve publication to Reserve Intel.",
]

ISO_MIDNIGHT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T00:00:00Z$")


class SaveError(ValueError):
    pass


def detect_repo_slug() -> str:
    configured = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if configured:
        return configured

    if shutil.which("gh") is None:
        raise SaveError("GitHub CLI (gh) is not available.")

    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        detail = result.stderr.strip() or "Could not identify the GitHub repository."
        raise SaveError(detail)

    return result.stdout.strip()


def validate_pending_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SaveError("sourceFile is required.")

    path = PurePosixPath(value.strip())
    if path.is_absolute():
        raise SaveError("sourceFile must be repository-relative.")

    parts = path.parts
    if len(parts) != 3 or parts[0] != "drafts" or parts[1] != "pending":
        raise SaveError("Save is restricted to drafts/pending/*.json.")
    if not parts[2].endswith(".json") or parts[2] in {".json", ".."}:
        raise SaveError("sourceFile must be a pending JSON draft.")
    if any(part in {"", ".", ".."} for part in parts):
        raise SaveError("Invalid sourceFile path.")

    return str(path)


def require_text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise SaveError(f"{field} must be text.")
    cleaned = value.strip()
    if not cleaned:
        raise SaveError(f"{field} cannot be empty.")
    if len(cleaned) > maximum:
        raise SaveError(f"{field} exceeds the {maximum}-character limit.")
    return cleaned


def optional_target(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SaveError(f"{field} must be text or null.")
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_TARGET:
        raise SaveError(f"{field} exceeds the {MAX_TARGET}-character limit.")
    return cleaned


def validate_patch(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SaveError("articleDraftPatch must be an object.")

    expected = {
        "title",
        "summary",
        "whyItMatters",
        "details",
        "category",
        "status",
        "priority",
        "effectiveDate",
        "audience",
        "isPinned",
    }
    extra = set(value) - expected
    missing = expected - set(value)
    if extra:
        raise SaveError("Unexpected editable fields: " + ", ".join(sorted(extra)))
    if missing:
        raise SaveError("Missing editable fields: " + ", ".join(sorted(missing)))

    category = value.get("category")
    status = value.get("status")
    priority = value.get("priority")
    if category not in CATEGORIES:
        raise SaveError(f"Unsupported category: {category}")
    if status not in STATUSES:
        raise SaveError(f"Unsupported status: {status}")
    if priority not in PRIORITIES:
        raise SaveError(f"Unsupported priority: {priority}")

    effective = value.get("effectiveDate")
    if effective is not None:
        if not isinstance(effective, str) or not ISO_MIDNIGHT_RE.fullmatch(effective):
            raise SaveError("effectiveDate must be null or YYYY-MM-DDT00:00:00Z.")

    audience = value.get("audience")
    if not isinstance(audience, dict):
        raise SaveError("audience must be an object.")

    audience_expected = {"service", "reserveStatus", "trainingWing", "squadron"}
    if set(audience) != audience_expected:
        raise SaveError("audience must contain only service, reserveStatus, trainingWing, and squadron.")

    service = audience.get("service")
    reserve_status = audience.get("reserveStatus")
    if service not in SERVICES:
        raise SaveError(f"Unsupported service audience: {service}")
    if reserve_status not in RESERVE_STATUSES:
        raise SaveError(f"Unsupported Reserve-status audience: {reserve_status}")

    pinned = value.get("isPinned")
    if not isinstance(pinned, bool):
        raise SaveError("isPinned must be true or false.")

    return {
        "title": require_text(value.get("title"), "title", MAX_TITLE),
        "summary": require_text(value.get("summary"), "summary", MAX_SUMMARY),
        "whyItMatters": require_text(value.get("whyItMatters"), "whyItMatters", MAX_WHY),
        "details": require_text(value.get("details"), "details", MAX_DETAILS),
        "category": category,
        "status": status,
        "priority": priority,
        "effectiveDate": effective,
        "audience": {
            "service": service,
            "reserveStatus": reserve_status,
            "trainingWing": optional_target(audience.get("trainingWing"), "trainingWing"),
            "squadron": optional_target(audience.get("squadron"), "squadron"),
        },
        "isPinned": pinned,
    }


def apply_editor_patch(draft: dict[str, Any], article_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    if draft.get("draftStatus") != "PENDING_HUMAN_REVIEW":
        raise SaveError("Remote draft is not pending human review.")
    if draft.get("requiresHumanReview") is not True:
        raise SaveError("Remote draft must require human review.")
    if draft.get("publishReady") is not False:
        raise SaveError("Remote draft is unexpectedly publish-ready.")

    article = draft.get("articleDraft")
    if not isinstance(article, dict):
        raise SaveError("Remote draft articleDraft is missing.")
    if article.get("id") != article_id:
        raise SaveError("Remote draft article ID does not match the requested article.")

    updated = deepcopy(draft)
    target = updated["articleDraft"]
    for key, value in patch.items():
        target[key] = deepcopy(value)

    return updated


def gh_api_json(args: list[str], *, stdin_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    command = ["gh", "api", *args]
    input_text = None

    if stdin_payload is not None:
        command.extend(["--input", "-"])
        input_text = json.dumps(stdin_payload)

    result = subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "GitHub API request failed."
        raise SaveError(detail)

    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SaveError("GitHub API returned invalid JSON.") from exc

    if not isinstance(value, dict):
        raise SaveError("GitHub API returned an unexpected response.")
    return value


def fetch_remote_draft(repo: str, branch: str, path: str) -> tuple[dict[str, Any], str]:
    api_path = f"repos/{repo}/contents/{quote(path, safe='/')}"
    response = gh_api_json(
        [
            "--method",
            "GET",
            api_path,
            "-f",
            f"ref={branch}",
        ]
    )

    sha = response.get("sha")
    encoded = response.get("content")
    if not isinstance(sha, str) or not sha:
        raise SaveError("GitHub did not return the current file SHA.")
    if not isinstance(encoded, str):
        raise SaveError("GitHub did not return draft file content.")

    try:
        raw = base64.b64decode(encoded).decode("utf-8")
        draft = json.loads(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SaveError("Could not decode the remote draft JSON.") from exc

    if not isinstance(draft, dict):
        raise SaveError("Remote draft root must be a JSON object.")
    return draft, sha


def commit_remote_draft(
    repo: str,
    branch: str,
    path: str,
    sha: str,
    draft: dict[str, Any],
    article_id: str,
) -> dict[str, Any]:
    content = json.dumps(draft, indent=2, ensure_ascii=False) + "\n"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    api_path = f"repos/{repo}/contents/{quote(path, safe='/')}"
    return gh_api_json(
        ["--method", "PUT", api_path],
        stdin_payload={
            "message": f"Update Reserve Intel review: {article_id}",
            "content": encoded,
            "sha": sha,
            "branch": branch,
        },
    )


def save_request(payload: dict[str, Any], repo: str) -> dict[str, Any]:
    article_id = payload.get("articleId")
    if not isinstance(article_id, str) or not article_id.strip():
        raise SaveError("articleId is required.")
    article_id = article_id.strip()

    source_file = validate_pending_path(payload.get("sourceFile"))
    expected_branch = f"{REVIEW_BRANCH_PREFIX}{article_id}"

    branch = payload.get("reviewBranch")
    if branch != expected_branch:
        raise SaveError("Review branch does not match the article ID.")

    patch = validate_patch(payload.get("articleDraftPatch"))

    remote_draft, sha = fetch_remote_draft(repo, branch, source_file)
    updated = apply_editor_patch(remote_draft, article_id, patch)

    if updated == remote_draft:
        return {
            "ok": True,
            "changed": False,
            "article": updated["articleDraft"],
            "branch": branch,
            "sourceFile": source_file,
            "commitSha": None,
        }

    response = commit_remote_draft(
        repo,
        branch,
        source_file,
        sha,
        updated,
        article_id,
    )

    commit = response.get("commit") if isinstance(response.get("commit"), dict) else {}
    commit_sha = commit.get("sha") if isinstance(commit.get("sha"), str) else None
    commit_url = commit.get("html_url") if isinstance(commit.get("html_url"), str) else None

    return {
        "ok": True,
        "changed": True,
        "article": updated["articleDraft"],
        "branch": branch,
        "sourceFile": source_file,
        "commitSha": commit_sha,
        "commitURL": commit_url,
    }



def validate_rejection_reason(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SaveError("reason must be text.")
    cleaned = value.strip()
    if len(cleaned) > MAX_REJECT_REASON:
        raise SaveError(f"reason exceeds the {MAX_REJECT_REASON}-character limit.")
    return cleaned


def gh_pr_list_json(repo: str, branch: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--base",
            "main",
            "--head",
            branch,
            "--json",
            "number,headRefName,baseRefName,url,title,isDraft",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Could not query Review PRs."
        raise SaveError(detail)

    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SaveError("GitHub returned invalid Review PR JSON.") from exc

    if not isinstance(value, list):
        raise SaveError("GitHub returned an unexpected Review PR response.")

    return [item for item in value if isinstance(item, dict)]


def find_unique_open_review_pr(repo: str, branch: str) -> dict[str, Any]:
    candidates = [
        pr
        for pr in gh_pr_list_json(repo, branch)
        if pr.get("headRefName") == branch and pr.get("baseRefName") == "main"
    ]

    if not candidates:
        raise SaveError(
            "No open Review PR matches this article. A unique open Review PR is required."
        )

    if len(candidates) != 1:
        numbers = ", ".join(str(pr.get("number")) for pr in candidates)
        raise SaveError(
            f"More than one open Review PR matches this article: {numbers}"
        )

    pr = candidates[0]
    if not isinstance(pr.get("number"), int):
        raise SaveError("Matching Review PR does not have a valid PR number.")
    return pr


def build_rejection_comment(article_id: str, reason: str) -> str:
    lines = [
        "Rejected from the Reserve Intel Mac review dashboard.",
        "",
        f"Article ID: `{article_id}`",
    ]
    if reason:
        lines.extend(["", "Reason:", reason])
    else:
        lines.extend(["", "Reason: No reason provided."])
    return "\n".join(lines)


def close_review_pr(repo: str, pr_number: int, comment: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            "gh",
            "pr",
            "close",
            str(pr_number),
            "--repo",
            repo,
            "--comment",
            comment,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Could not close Review PR."
        raise SaveError(detail)

    verify = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            repo,
            "--json",
            "number,state,mergedAt,headRefName,baseRefName,url",
        ],
        capture_output=True,
        text=True,
    )
    if verify.returncode != 0:
        detail = verify.stderr.strip() or verify.stdout.strip() or "Could not verify closed Review PR."
        raise SaveError(detail)

    try:
        value = json.loads(verify.stdout)
    except json.JSONDecodeError as exc:
        raise SaveError("GitHub returned invalid closed-PR verification JSON.") from exc

    if not isinstance(value, dict):
        raise SaveError("GitHub returned an unexpected closed-PR verification response.")
    if value.get("state") != "CLOSED":
        raise SaveError("Review PR did not reach CLOSED state.")
    if value.get("mergedAt") is not None:
        raise SaveError("Safety check failed: rejected Review PR shows a merge timestamp.")

    return value



def fetch_review_pr(repo: str, pr_number: int) -> dict[str, Any]:
    api_path = f"repos/{repo}/pulls/{pr_number}"
    value = gh_api_json(["--method", "GET", api_path])

    head = value.get("head")
    base = value.get("base")
    if not isinstance(head, dict) or not isinstance(base, dict):
        raise SaveError("Review PR is missing head/base metadata.")

    return value


def approve_pr_body(body: Any, article_id: str) -> str:
    if not isinstance(body, str) or not body.strip():
        raise SaveError("Review PR body is missing.")

    marker = f"<!-- reserve-intel-article-id: {article_id} -->"
    if marker not in body:
        raise SaveError("Review PR body does not contain the expected Reserve Intel article marker.")

    updated = body
    missing: list[str] = []

    for label in APPROVAL_CHECKS:
        pattern = re.compile(
            r"(?mi)^(\s*-\s*)\[[ xX]\](\s*" + re.escape(label) + r"\s*)$"
        )
        if not pattern.search(updated):
            missing.append(label)
            continue
        updated = pattern.sub(r"\1[x]\2", updated, count=1)

    if missing:
        raise SaveError(
            "Review PR approval checklist is incomplete or malformed: " + "; ".join(missing)
        )

    return updated


def update_review_pr_body(repo: str, pr_number: int, body: str) -> None:
    api_path = f"repos/{repo}/pulls/{pr_number}"
    gh_api_json(
        ["--method", "PATCH", api_path],
        stdin_payload={"body": body},
    )


def mark_pr_ready(repo: str, pr_number: int) -> None:
    result = subprocess.run(
        ["gh", "pr", "ready", str(pr_number), "--repo", repo],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Could not mark Review PR ready."
        raise SaveError(detail)


def merge_review_pr(repo: str, pr_number: int, head_sha: str, article_id: str) -> dict[str, Any]:
    api_path = f"repos/{repo}/pulls/{pr_number}/merge"
    result = gh_api_json(
        ["--method", "PUT", api_path],
        stdin_payload={
            "sha": head_sha,
            "merge_method": "merge",
            "commit_title": f"Approve Reserve Intel review: {article_id}",
        },
    )

    if result.get("merged") is not True:
        message = result.get("message")
        if not isinstance(message, str) or not message.strip():
            message = "GitHub did not merge the Review PR."
        raise SaveError(message)

    return result


def approve_request(payload: dict[str, Any], repo: str) -> dict[str, Any]:
    article_id = payload.get("articleId")
    if not isinstance(article_id, str) or not article_id.strip():
        raise SaveError("articleId is required.")
    article_id = article_id.strip()

    if payload.get("approvalConfirmed") is not True:
        raise SaveError("Explicit approval confirmation is required.")

    source_file = validate_pending_path(payload.get("sourceFile"))
    expected_branch = f"{REVIEW_BRANCH_PREFIX}{article_id}"

    branch = payload.get("reviewBranch")
    if branch != expected_branch:
        raise SaveError("Review branch does not match the article ID.")

    pr_summary = find_unique_open_review_pr(repo, branch)
    pr_number = pr_summary["number"]
    pr = fetch_review_pr(repo, pr_number)

    head = pr.get("head")
    base = pr.get("base")
    head_ref = head.get("ref") if isinstance(head, dict) else None
    head_sha = head.get("sha") if isinstance(head, dict) else None
    base_ref = base.get("ref") if isinstance(base, dict) else None

    if head_ref != branch or base_ref != "main":
        raise SaveError("Review PR branch verification failed.")
    if not isinstance(head_sha, str) or not head_sha:
        raise SaveError("Review PR head SHA is missing.")
    if pr.get("state") != "open":
        raise SaveError("Review PR is not open.")
    if pr.get("merged") is True or pr.get("merged_at") is not None:
        raise SaveError("Review PR is already merged.")

    labels = pr.get("labels")
    label_names = {
        label.get("name")
        for label in labels
        if isinstance(label, dict) and isinstance(label.get("name"), str)
    } if isinstance(labels, list) else set()
    if "reserve-intel-review" not in label_names:
        raise SaveError("Review PR is missing the reserve-intel-review label.")

    # Validate the exact immutable PR head that will be merged, not merely the
    # current branch name. If the branch changes after this point, the merge API
    # is constrained by the same head SHA and fails closed.
    remote_draft, _ = fetch_remote_draft(repo, head_sha, source_file)

    if remote_draft.get("draftStatus") != "PENDING_HUMAN_REVIEW":
        raise SaveError("Remote draft is not pending human review.")
    if remote_draft.get("requiresHumanReview") is not True:
        raise SaveError("Remote draft must require human review.")
    if remote_draft.get("publishReady") is not False:
        raise SaveError("Remote draft is unexpectedly publish-ready.")

    evidence = remote_draft.get("sourceEvidence")
    if not isinstance(evidence, dict) or evidence.get("officialHostVerified") is not True:
        raise SaveError("Official source host has not been verified.")

    article = remote_draft.get("articleDraft")
    if not isinstance(article, dict) or article.get("id") != article_id:
        raise SaveError("Remote draft article ID does not match the requested article.")

    approved_body = approve_pr_body(pr.get("body"), article_id)
    update_review_pr_body(repo, pr_number, approved_body)

    if pr.get("draft") is True:
        mark_pr_ready(repo, pr_number)

    merge_result = merge_review_pr(repo, pr_number, head_sha, article_id)
    verified = fetch_review_pr(repo, pr_number)

    verified_head = verified.get("head")
    verified_base = verified.get("base")
    if not isinstance(verified_head, dict) or not isinstance(verified_base, dict):
        raise SaveError("Merged PR verification is missing head/base metadata.")
    if verified_head.get("ref") != branch or verified_base.get("ref") != "main":
        raise SaveError("Merged PR branch verification failed.")
    if verified.get("merged") is not True or verified.get("merged_at") is None:
        raise SaveError("Review PR merge could not be verified.")

    return {
        "ok": True,
        "prNumber": pr_number,
        "prURL": verified.get("html_url") or pr.get("html_url"),
        "merged": True,
        "mergedAt": verified.get("merged_at"),
        "mergeCommitSha": merge_result.get("sha"),
        "reviewHeadSha": head_sha,
        "branch": branch,
        "sourceFile": source_file,
    }


def reject_request(payload: dict[str, Any], repo: str) -> dict[str, Any]:
    article_id = payload.get("articleId")
    if not isinstance(article_id, str) or not article_id.strip():
        raise SaveError("articleId is required.")
    article_id = article_id.strip()

    source_file = validate_pending_path(payload.get("sourceFile"))
    expected_branch = f"{REVIEW_BRANCH_PREFIX}{article_id}"

    branch = payload.get("reviewBranch")
    if branch != expected_branch:
        raise SaveError("Review branch does not match the article ID.")

    reason = validate_rejection_reason(payload.get("reason"))

    # Re-fetch the exact remote draft and re-validate its review gates immediately
    # before closing the PR. This prevents a stale dashboard from rejecting an
    # article that is no longer pending human review.
    remote_draft, _ = fetch_remote_draft(repo, branch, source_file)
    if remote_draft.get("draftStatus") != "PENDING_HUMAN_REVIEW":
        raise SaveError("Remote draft is not pending human review.")
    if remote_draft.get("requiresHumanReview") is not True:
        raise SaveError("Remote draft must require human review.")
    if remote_draft.get("publishReady") is not False:
        raise SaveError("Remote draft is unexpectedly publish-ready.")

    article = remote_draft.get("articleDraft")
    if not isinstance(article, dict) or article.get("id") != article_id:
        raise SaveError("Remote draft article ID does not match the requested article.")

    pr = find_unique_open_review_pr(repo, branch)
    comment = build_rejection_comment(article_id, reason)
    closed = close_review_pr(repo, pr["number"], comment)

    if closed.get("headRefName") != branch or closed.get("baseRefName") != "main":
        raise SaveError("Closed PR branch verification failed.")

    return {
        "ok": True,
        "prNumber": closed.get("number"),
        "prURL": closed.get("url") or pr.get("url"),
        "state": closed.get("state"),
        "mergedAt": closed.get("mergedAt"),
        "branch": branch,
        "sourceFile": source_file,
    }


def self_test() -> int:
    original = {
        "draftStatus": "PENDING_HUMAN_REVIEW",
        "requiresHumanReview": True,
        "publishReady": False,
        "sourceEvidence": {
            "officialHostVerified": True,
            "fingerprint": "DO-NOT-CHANGE",
        },
        "reviewChecklist": {
            "sourceOpenedAndRead": False,
            "approvedForPublication": False,
        },
        "articleDraft": {
            "id": "intel-test",
            "title": "Old title",
            "summary": "Old summary",
            "whyItMatters": "Old why",
            "details": "Old details",
            "category": "Admin",
            "status": "TRACKING",
            "priority": "NORMAL",
            "effectiveDate": None,
            "sourceName": "Official Source",
            "sourceURL": "https://example.mil/source.pdf?keep=this",
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

    patch = validate_patch(
        {
            "title": "New title",
            "summary": "New summary",
            "whyItMatters": "New why",
            "details": "New details",
            "category": "Training & Readiness",
            "status": "EFFECTIVE",
            "priority": "HIGH",
            "effectiveDate": "2026-09-15T00:00:00Z",
            "audience": {
                "service": "USN",
                "reserveStatus": "SELRES",
                "trainingWing": "TW-1",
                "squadron": "VT-7",
            },
            "isPinned": True,
        }
    )

    updated = apply_editor_patch(original, "intel-test", patch)

    assert updated["articleDraft"]["title"] == "New title"
    assert updated["articleDraft"]["priority"] == "HIGH"
    assert updated["articleDraft"]["audience"]["reserveStatus"] == "SELRES"

    # Safety-critical fields remain untouched.
    assert updated["articleDraft"]["sourceURL"] == original["articleDraft"]["sourceURL"]
    assert updated["articleDraft"]["sourceName"] == original["articleDraft"]["sourceName"]
    assert updated["sourceEvidence"] == original["sourceEvidence"]
    assert updated["reviewChecklist"] == original["reviewChecklist"]
    assert updated["draftStatus"] == "PENDING_HUMAN_REVIEW"
    assert updated["requiresHumanReview"] is True
    assert updated["publishReady"] is False

    assert validate_pending_path("drafts/pending/intel-test.json") == "drafts/pending/intel-test.json"

    blocked = False
    try:
        validate_pending_path("../reserve-content-feed.json")
    except SaveError:
        blocked = True
    assert blocked

    assert validate_rejection_reason(None) == ""
    assert validate_rejection_reason("  Needs source correction.  ") == "Needs source correction."
    comment = build_rejection_comment("intel-test", "Needs source correction.")
    assert "intel-test" in comment
    assert "Needs source correction." in comment

    too_long_blocked = False
    try:
        validate_rejection_reason("x" * (MAX_REJECT_REASON + 1))
    except SaveError:
        too_long_blocked = True
    assert too_long_blocked

    approval_body = (
        "# Reserve Intel Review\n\n"
        + "\n".join(f"- [ ] {label}" for label in APPROVAL_CHECKS)
        + "\n\n<!-- reserve-intel-article-id: intel-test -->\n"
    )
    approved_body = approve_pr_body(approval_body, "intel-test")
    for label in APPROVAL_CHECKS:
        assert f"- [x] {label}" in approved_body

    missing_marker_blocked = False
    try:
        approve_pr_body("\n".join(f"- [ ] {label}" for label in APPROVAL_CHECKS), "intel-test")
    except SaveError:
        missing_marker_blocked = True
    assert missing_marker_blocked

    malformed_checklist_blocked = False
    try:
        approve_pr_body(
            "# Review\n- [ ] I opened the official source.\n"
            "<!-- reserve-intel-article-id: intel-test -->\n",
            "intel-test",
        )
    except SaveError:
        malformed_checklist_blocked = True
    assert malformed_checklist_blocked

    print("SELF-TEST PASSED")
    return 0


class DashboardHandler(SimpleHTTPRequestHandler):
    server_version = "ReserveIntelDashboard/3C"

    def _json_response(self, status: int, payload: dict[str, Any]) -> None:
        raw = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/reserve-intel/health":
            repo = getattr(self.server, "repo_slug", None)
            self._json_response(
                200,
                {
                    "ok": True,
                    "saveEnabled": bool(repo),
                    "repository": repo,
                    "approveEnabled": bool(repo),
                    "rejectEnabled": bool(repo),
                },
            )
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/reserve-intel/save", "/api/reserve-intel/reject", "/api/reserve-intel/approve"}:
            self._json_response(404, {"ok": False, "error": "Unknown API endpoint."})
            return

        content_length_raw = self.headers.get("Content-Length", "")
        try:
            content_length = int(content_length_raw)
        except ValueError:
            self._json_response(400, {"ok": False, "error": "Invalid Content-Length."})
            return

        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            self._json_response(413, {"ok": False, "error": "Save request is empty or too large."})
            return

        try:
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise SaveError("Request body must be a JSON object.")

            repo = getattr(self.server, "repo_slug", None)
            if not repo:
                raise SaveError("Save service is not connected to a GitHub repository.")

            if parsed.path == "/api/reserve-intel/save":
                result = save_request(payload, repo)
            elif parsed.path == "/api/reserve-intel/reject":
                result = reject_request(payload, repo)
            else:
                result = approve_request(payload, repo)
        except (UnicodeDecodeError, json.JSONDecodeError, SaveError) as exc:
            self._json_response(400, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:
            print(f"UNEXPECTED SAVE ERROR: {exc}", file=sys.stderr)
            self._json_response(500, {"ok": False, "error": "Unexpected Save service error."})
            return

        self._json_response(200, result)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[dashboard] {self.address_string()} - {format % args}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--root", default=".")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"ERROR: dashboard root does not exist: {root}", file=sys.stderr)
        return 1

    try:
        repo = args.repo.strip() if isinstance(args.repo, str) and args.repo.strip() else detect_repo_slug()
    except SaveError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    os.chdir(root)

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    server.repo_slug = repo

    print(f"Reserve Intel dashboard: http://{args.host}:{args.port}/docs/reserve-intel/")
    print(f"Repository: {repo}")
    print("Save Draft: ENABLED for eligible review-branch drafts")
    print("Reject: ENABLED for eligible review PRs")
    print("Approve: ENABLED for eligible review PRs")
    print("Press Ctrl-C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
