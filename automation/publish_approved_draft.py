#!/usr/bin/env python3
"""
Salty Dog Bible — publish a merged/approved Reserve Intel draft (IT-2D.5).

Hard safety gate:
- requires all six PR approval checkboxes to be checked
- requires an official/verified source flag
- refuses duplicate article IDs and ambiguous source matches
- updates an existing active article when the authoritative source identity matches
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
import tempfile
from urllib.parse import unquote, urlsplit, urlunsplit

CHECKS = [
    "I opened the official source.",
    "I verified the facts against the official source.",
    "I verified the status and effective date.",
    "I verified the intended audience.",
    "I reviewed the title, summary, Why It Matters, and details.",
    "I approve publication to Reserve Intel.",
]


NAVADMIN_FILENAME_RE = re.compile(
    r"^NAV(?P<year>\d{2})(?P<number>\d{3})\.pdf$",
    re.I,
)
NAVADMIN_TEXT_RE = re.compile(
    r"\bNAVADMIN\s+(?P<number>\d{1,3})\s*[/\-]\s*(?P<year>\d{2,4})\b",
    re.I,
)


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )



def normalize_iso_datetime(value: object, field_name: str, *, allow_none: bool = False) -> str | None:
    if value is None:
        if allow_none:
            return None
        raise ValueError(f"{field_name} is required.")

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty date string.")

    raw = value.strip()

    # Accept the date-only form produced by some source parsers and normalize it
    # to midnight UTC so the iOS feed decoder receives one consistent format.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ValueError(f"{field_name} contains an invalid calendar date: {raw}") from exc
        return parsed.isoformat().replace("+00:00", "Z")

    # Accept ISO-8601 date-times. A trailing Z is converted for fromisoformat,
    # then every accepted value is emitted in UTC with a Z suffix.
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO-8601: {raw}") from exc

    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone: {raw}")

    return (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_article_dates(article: dict) -> None:
    article["publishedAt"] = normalize_iso_datetime(
        article.get("publishedAt"),
        "articleDraft.publishedAt",
    )
    article["effectiveDate"] = normalize_iso_datetime(
        article.get("effectiveDate"),
        "articleDraft.effectiveDate",
        allow_none=True,
    )

    # updatedAt is always refreshed at publication, so no draft value is trusted.


def canonical_source_url(value: object) -> str | None:
    """Return a comparison key for an authoritative source URL.

    Query strings and fragments are intentionally excluded because official
    publishers frequently append cache/version tokens to the same document.
    """

    if not isinstance(value, str) or not value.strip():
        return None

    raw = value.strip()
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        return None

    path = unquote(parsed.path or "/")
    path = re.sub(r"/{2,}", "/", path)
    if path != "/":
        path = path.rstrip("/")

    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            "",
        )
    )


def navadmin_document_identity(article: dict) -> str | None:
    """Return a normalized NAVADMIN identity, preferring the source URL.

    MyNavyHR filenames such as NAV26204.pdf encode NAVADMIN 204/26. The source
    URL is authoritative and therefore takes precedence over generated titles,
    which may contain stale or incorrect NAVADMIN references.
    """

    source_url = article.get("sourceURL")
    if isinstance(source_url, str) and source_url.strip():
        filename = Path(unquote(urlsplit(source_url.strip()).path)).name
        match = NAVADMIN_FILENAME_RE.fullmatch(filename)
        if match:
            year = int(match.group("year"))
            number = int(match.group("number"))
            return f"NAVADMIN-{number:03d}-{year:02d}"

    for field in ("sourceName", "title"):
        value = article.get(field)
        if not isinstance(value, str):
            continue
        match = NAVADMIN_TEXT_RE.search(value)
        if not match:
            continue

        number = int(match.group("number"))
        raw_year = match.group("year")
        year = int(raw_year[-2:])
        return f"NAVADMIN-{number:03d}-{year:02d}"

    return None


def source_match_reasons(incoming: dict, existing: dict) -> list[str]:
    """Describe authoritative-source keys shared by two articles."""

    reasons: list[str] = []

    incoming_url = canonical_source_url(incoming.get("sourceURL"))
    existing_url = canonical_source_url(existing.get("sourceURL"))
    if incoming_url and existing_url and incoming_url == existing_url:
        reasons.append(f"canonicalSourceURL={incoming_url}")

    incoming_document = navadmin_document_identity(incoming)
    existing_document = navadmin_document_identity(existing)
    if (
        incoming_document
        and existing_document
        and incoming_document == existing_document
    ):
        reasons.append(f"documentIdentity={incoming_document}")

    return reasons


def find_active_source_match(article: dict, articles: list[dict]) -> int | None:
    """Find one active live-feed article representing the same source.

    Multiple matches are refused rather than guessed so publication remains a
    human-review-controlled operation.
    """

    matches: list[tuple[int, dict, list[str]]] = []

    for index, existing in enumerate(articles):
        if not isinstance(existing, dict):
            continue
        if existing.get("isActive") is not True:
            continue

        reasons = source_match_reasons(article, existing)
        if reasons:
            matches.append((index, existing, reasons))

    if len(matches) > 1:
        details = "; ".join(
            f"{existing.get('id', '<missing-id>')} ({', '.join(reasons)})"
            for _, existing, reasons in matches
        )
        raise ValueError(
            "Ambiguous live-feed source match. More than one active article "
            f"matches the approved source: {details}"
        )

    return matches[0][0] if matches else None

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

    # Article IDs remain globally unique. A repeated ID indicates a publication
    # replay or collision and is never treated as an update.
    for existing in articles:
        if not isinstance(existing, dict):
            continue
        if existing.get("id") == article_id:
            raise ValueError(f"Article ID already exists in live feed: {article_id}")

    matching_index = find_active_source_match(article, articles)

    normalize_article_dates(article)

    now = utc_now_iso()
    article["isActive"] = True
    article["updatedAt"] = now

    if matching_index is None:
        # A genuinely new authoritative source becomes a new live Intel record.
        feed["intelArticles"] = [article] + articles
        published_article_id = article_id
    else:
        # The authoritative source is already represented by one active article.
        # Preserve the stable app identity and original publication timestamp,
        # while replacing the approved content with the newly reviewed version.
        existing = articles[matching_index]

        existing_id = existing.get("id")
        if not isinstance(existing_id, str) or not existing_id:
            raise ValueError("Matched live-feed article is missing a stable ID.")

        existing_published_at = normalize_iso_datetime(
            existing.get("publishedAt"),
            "existingArticle.publishedAt",
        )

        article["id"] = existing_id
        article["publishedAt"] = existing_published_at
        articles[matching_index] = article
        feed["intelArticles"] = articles
        published_article_id = existing_id

    feed["generatedAt"] = now
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

    return published_article_id


def self_test() -> int:
    approval_body = "\n".join(f"- [x] {label}" for label in CHECKS)

    def make_draft(article: dict) -> dict:
        return {
            "draftStatus": "PENDING_HUMAN_REVIEW",
            "requiresHumanReview": True,
            "publishReady": False,
            "sourceEvidence": {"officialHostVerified": True},
            "articleDraft": article,
        }

    def write_json(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # Canonical URL matching must ignore MyNavyHR version-query noise.
    assert canonical_source_url(
        "https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/"
        "NAV2026/NAV26204.pdf?ver=abc#page=1"
    ) == canonical_source_url(
        "https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/"
        "NAV2026/NAV26204.pdf"
    )

    # The authoritative filename must win over an incorrect/stale generated title.
    identity_fixture = {
        "sourceURL": (
            "https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/"
            "NAV2026/NAV26204.pdf?ver=abc"
        ),
        "sourceName": "MyNavyHR NAVADMIN",
        "title": "Modification to NAVADMIN 084/26",
    }
    assert navadmin_document_identity(identity_fixture) == "NAVADMIN-204-26"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # Real-world NAVADMIN 204/26 regression:
        # an automated article with a ?ver= token updates the already-active
        # manual article instead of adding a second card.
        feed_path = root / "feed.json"
        draft_path = root / "pending" / "navadmin-204-update.json"
        published_dir = root / "published"

        existing = {
            "id": "intel-navadmin-204-26-cyber",
            "publishedAt": "2026-08-31T18:38:00Z",
            "updatedAt": "2026-09-14T14:35:00Z",
            "title": (
                "NAVADMIN 204/26 — Cyber Awareness Moves to Every 3 Years "
                "for Military Personnel"
            ),
            "category": "Training & Readiness",
            "status": "EFFECTIVE",
            "priority": "HIGH",
            "summary": "Old reviewed content.",
            "whyItMatters": "Old reviewed content.",
            "details": "Old reviewed content.",
            "effectiveDate": "2026-08-31T00:00:00Z",
            "sourceName": "NAVADMIN 204/26 — MyNavyHR",
            "sourceURL": (
                "https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/"
                "NAV2026/NAV26204.pdf"
            ),
            "audience": {
                "service": "USN",
                "reserveStatus": "ALL",
                "trainingWing": None,
                "squadron": None,
            },
            "isPinned": False,
            "isActive": True,
        }
        write_json(
            feed_path,
            {
                "schemaVersion": 1,
                "generatedAt": "2026-09-14T14:35:00Z",
                "intelArticles": [existing],
                "tipperMessages": [],
            },
        )

        incoming = deepcopy(existing)
        incoming.update(
            {
                "id": (
                    "intel-modification-to-navadmin-084-26-fiscal-year-2026-"
                    "cybersecurity-a-a282de7970"
                ),
                "publishedAt": "2026-09-15T15:17:01Z",
                "updatedAt": None,
                "title": "Cybersecurity Awareness Training Changes to Every 3 Years",
                "summary": "New approved content.",
                "whyItMatters": "New approved why-it-matters.",
                "details": "New approved details.",
                "sourceName": "MyNavyHR NAVADMIN",
                "sourceURL": (
                    "https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/"
                    "NAV2026/NAV26204.pdf?ver=Z0SgLUjWKMJuHZr8CPoubQ%3d%3d"
                ),
            }
        )
        write_json(draft_path, make_draft(incoming))

        result_id = publish(
            draft_path,
            feed_path,
            approval_body,
            published_dir,
            None,
            None,
        )

        updated_feed = load_json(feed_path)
        assert len(updated_feed["intelArticles"]) == 1
        updated = updated_feed["intelArticles"][0]
        assert result_id == "intel-navadmin-204-26-cyber"
        assert updated["id"] == "intel-navadmin-204-26-cyber"
        assert updated["publishedAt"] == "2026-08-31T18:38:00Z"
        assert updated["title"] == "Cybersecurity Awareness Training Changes to Every 3 Years"
        assert updated["summary"] == "New approved content."
        assert updated["sourceURL"].endswith(
            "NAV26204.pdf?ver=Z0SgLUjWKMJuHZr8CPoubQ%3d%3d"
        )
        assert updated["isActive"] is True
        assert isinstance(updated.get("updatedAt"), str)

        archived = load_json(published_dir / "navadmin-204-update.json")
        assert archived["articleDraft"]["id"] == "intel-navadmin-204-26-cyber"
        assert archived["articleDraft"]["publishedAt"] == "2026-08-31T18:38:00Z"

        # NAVADMIN identity is a backup when the canonical URL path changes.
        feed_path_2 = root / "feed-identity.json"
        draft_path_2 = root / "pending" / "navadmin-identity-update.json"
        existing_2 = deepcopy(existing)
        existing_2["id"] = "intel-navadmin-204-26-existing"
        write_json(
            feed_path_2,
            {
                "schemaVersion": 1,
                "generatedAt": "2026-09-14T14:35:00Z",
                "intelArticles": [existing_2],
                "tipperMessages": [],
            },
        )

        incoming_2 = deepcopy(incoming)
        incoming_2["id"] = "intel-navadmin-204-26-new-path"
        incoming_2["sourceURL"] = (
            "https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/"
            "Archive/NAV26204.pdf?ver=new"
        )
        write_json(draft_path_2, make_draft(incoming_2))

        result_id_2 = publish(
            draft_path_2,
            feed_path_2,
            approval_body,
            root / "published-identity",
            None,
            None,
        )
        updated_feed_2 = load_json(feed_path_2)
        assert len(updated_feed_2["intelArticles"]) == 1
        assert result_id_2 == "intel-navadmin-204-26-existing"

        # Multiple active matches must fail closed instead of choosing one.
        feed_path_3 = root / "feed-ambiguous.json"
        draft_path_3 = root / "pending" / "navadmin-ambiguous.json"
        duplicate_a = deepcopy(existing)
        duplicate_a["id"] = "duplicate-a"
        duplicate_b = deepcopy(existing)
        duplicate_b["id"] = "duplicate-b"
        duplicate_b["sourceURL"] = (
            "https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/"
            "Archive/NAV26204.pdf"
        )
        write_json(
            feed_path_3,
            {
                "schemaVersion": 1,
                "generatedAt": "2026-09-14T14:35:00Z",
                "intelArticles": [duplicate_a, duplicate_b],
                "tipperMessages": [],
            },
        )
        ambiguous_incoming = deepcopy(incoming)
        ambiguous_incoming["id"] = "ambiguous-new"
        write_json(draft_path_3, make_draft(ambiguous_incoming))

        try:
            publish(
                draft_path_3,
                feed_path_3,
                approval_body,
                root / "published-ambiguous",
                None,
                None,
            )
        except ValueError as exc:
            assert "Ambiguous live-feed source match" in str(exc)
        else:
            raise AssertionError("Ambiguous source matches must block publication.")

        # Reusing an existing article ID remains a hard publication failure.
        feed_path_4 = root / "feed-id-collision.json"
        draft_path_4 = root / "pending" / "id-collision.json"
        write_json(
            feed_path_4,
            {
                "schemaVersion": 1,
                "generatedAt": "2026-09-14T14:35:00Z",
                "intelArticles": [existing],
                "tipperMessages": [],
            },
        )
        id_collision = deepcopy(incoming)
        id_collision["id"] = existing["id"]
        write_json(draft_path_4, make_draft(id_collision))

        try:
            publish(
                draft_path_4,
                feed_path_4,
                approval_body,
                root / "published-id-collision",
                None,
                None,
            )
        except ValueError as exc:
            assert "Article ID already exists" in str(exc)
        else:
            raise AssertionError("Duplicate article IDs must block publication.")

    print("SELF-TEST PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", default=None)
    parser.add_argument("--feed", default="reserve-content-feed.json")
    parser.add_argument("--approval-body-file", default=None)
    parser.add_argument("--published-dir", default="drafts/published")
    parser.add_argument("--review-marker", default=None)
    parser.add_argument("--review-published-dir", default="reviews/published")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    if not args.draft:
        print("--draft is required unless --self-test is used.", file=sys.stderr)
        return 2
    if not args.approval_body_file:
        print("--approval-body-file is required unless --self-test is used.", file=sys.stderr)
        return 2

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
