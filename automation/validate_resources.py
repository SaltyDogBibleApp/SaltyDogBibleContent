#!/usr/bin/env python3
"""
Validate automation/reserve-intel-sources.json.

This validator is intentionally network-free. It verifies that the source
registry is structurally safe before a scheduled monitor consumes it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_AUTHORITIES = {"official"}
ALLOWED_SOURCE_TYPES = {
    "navadmin",
    "reserve_guidance",
    "legislation",
    "pay_tables",
    "va_benefits",
    "economic_release",
    "dod_compensation",
}
ALLOWED_CATEGORIES = {
    "Legislation / NDAA",
    "Policy",
    "Pay & Benefits",
    "Retirement",
    "VA / Veteran Benefits",
    "Training & Readiness",
    "Admin",
    "Other",
}
APPROVED_HOST_SUFFIXES = {
    "mynavyhr.navy.mil",
    "navyreserve.navy.mil",
    "govinfo.gov",
    "dfas.mil",
    "va.gov",
    "bls.gov",
    "defense.gov",
}


def fail(message: str) -> None:
    raise ValueError(message)


def require_nonempty_string(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} must be a non-empty string.")
    return value.strip()


def validate_url(value: str, label: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https":
        fail(f"{label} must use https.")
    host = (parsed.hostname or "").lower()
    if not host:
        fail(f"{label} has no hostname.")
    if not any(host == suffix or host.endswith("." + suffix) for suffix in APPROVED_HOST_SUFFIXES):
        fail(f"{label} uses unapproved host: {host}")


def validate_registry(payload: dict) -> None:
    if payload.get("schemaVersion") != 1:
        fail("schemaVersion must be 1.")

    default_hours = payload.get("defaultCheckIntervalHours")
    if not isinstance(default_hours, int) or not 1 <= default_hours <= 168:
        fail("defaultCheckIntervalHours must be an integer from 1 to 168.")

    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        fail("sources must be a non-empty array.")

    seen_ids = set()

    for index, source in enumerate(sources):
        prefix = f"sources[{index}]"

        if not isinstance(source, dict):
            fail(f"{prefix} must be an object.")

        source_id = require_nonempty_string(source.get("id"), f"{prefix}.id")
        if source_id in seen_ids:
            fail(f"Duplicate source id: {source_id}")
        seen_ids.add(source_id)

        require_nonempty_string(source.get("name"), f"{prefix}.name")

        if not isinstance(source.get("enabled"), bool):
            fail(f"{prefix}.enabled must be true or false.")

        authority = source.get("authority")
        if authority not in ALLOWED_AUTHORITIES:
            fail(f"{prefix}.authority must be one of {sorted(ALLOWED_AUTHORITIES)}.")

        source_type = source.get("sourceType")
        if source_type not in ALLOWED_SOURCE_TYPES:
            fail(f"{prefix}.sourceType is not supported: {source_type!r}")

        url = require_nonempty_string(source.get("url"), f"{prefix}.url")
        validate_url(url, f"{prefix}.url")

        hours = source.get("checkIntervalHours")
        if not isinstance(hours, int) or not 1 <= hours <= 168:
            fail(f"{prefix}.checkIntervalHours must be an integer from 1 to 168.")

        categories = source.get("categories")
        if not isinstance(categories, list) or not categories:
            fail(f"{prefix}.categories must be a non-empty array.")
        if len(categories) != len(set(categories)):
            fail(f"{prefix}.categories contains duplicates.")
        unknown_categories = sorted(set(categories) - ALLOWED_CATEGORIES)
        if unknown_categories:
            fail(f"{prefix}.categories has unsupported values: {unknown_categories}")

        signals = source.get("reserveSignals")
        if not isinstance(signals, list) or not signals:
            fail(f"{prefix}.reserveSignals must be a non-empty array.")
        for signal_index, signal in enumerate(signals):
            require_nonempty_string(
                signal,
                f"{prefix}.reserveSignals[{signal_index}]"
            )

        require_nonempty_string(source.get("notes"), f"{prefix}.notes")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        default="reserve-intel-sources.json",
        help="Path to reserve-intel-sources.json",
    )
    args = parser.parse_args()

    path = Path(args.path)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            fail("Registry root must be a JSON object.")
        validate_registry(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    enabled_count = sum(1 for source in payload["sources"] if source["enabled"])
    print(
        f"VALID: {len(payload['sources'])} sources "
        f"({enabled_count} enabled), schemaVersion={payload['schemaVersion']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
