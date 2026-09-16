#!/usr/bin/env python3
"""
Start the Reserve Intel Mac review dashboard in one command.

Phase 4B startup flow:
- locate the Git repository root
- fetch origin so origin/main is current
- remove stale generated dashboard data
- regenerate docs/reserve-intel/data.json from origin/main plus live review branches
- exec the existing review dashboard server on the requested host/port

This script does not modify drafts, reviews, branches, or reserve-content-feed.json.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


DEFAULT_OUTPUT = Path("docs/reserve-intel/data.json")
GENERATOR = Path("automation/generate_review_dashboard.py")
SERVER = Path("automation/review_dashboard_server.py")
MAIN_REF = "origin/main"


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def detect_root(explicit_root: str | None) -> Path:
    if explicit_root:
        root = Path(explicit_root).expanduser().resolve()
        if not root.exists():
            raise SystemExit(f"ERROR: repository root does not exist: {root}")
        return root

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        detail = result.stderr.strip() or "Could not locate the Git repository root."
        raise SystemExit(f"ERROR: {detail}")

    return Path(result.stdout.strip()).resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument(
        "--no-review-branch-content",
        action="store_true",
        help="Generate dashboard data without loading remote review-branch drafts.",
    )
    args = parser.parse_args()

    root = detect_root(args.root)

    generator = root / GENERATOR
    server = root / SERVER
    output = root / DEFAULT_OUTPUT

    for required in (generator, server):
        if not required.exists():
            raise SystemExit(f"ERROR: required dashboard file is missing: {required}")

    print(f"Repository root: {root}")
    print(f"Fetching origin for {MAIN_REF}...")
    run(["git", "fetch", "origin"], cwd=root)

    # Never leave an old dashboard snapshot in place if regeneration fails.
    if output.exists():
        output.unlink()

    env = os.environ.copy()
    if isinstance(args.repo, str) and args.repo.strip():
        env["GITHUB_REPOSITORY"] = args.repo.strip()

    generate_command = [
        sys.executable,
        str(GENERATOR),
        "--output",
        str(DEFAULT_OUTPUT),
        "--main-ref",
        MAIN_REF,
    ]
    if args.demo:
        generate_command.append("--demo")
    if args.no_review_branch_content:
        generate_command.append("--no-review-branch-content")

    print("Generating current Reserve Intel dashboard data...")
    run(generate_command, cwd=root, env=env)

    print()
    print("Dashboard data is ready.")
    print(f"Starting server on http://{args.host}:{args.port}/docs/reserve-intel/")
    print("The server will refresh dashboard data after Save, Reject, and Approve actions.")
    print()

    server_command = [
        sys.executable,
        str(SERVER),
        "--root",
        str(root),
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if isinstance(args.repo, str) and args.repo.strip():
        server_command.extend(["--repo", args.repo.strip()])

    # Replace the launcher process with the server so Ctrl-C behaves exactly as
    # it did when review_dashboard_server.py was started directly.
    os.execvpe(
        sys.executable,
        [sys.executable, *server_command[1:]],
        env,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
