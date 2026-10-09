"""Spec 055 F02b: deliver queued summaries and incidents from ``<state>/ops/outbox``.

Guarantees: an item leaves the outbox (moved to ``ops/delivered``) only after its post succeeded,
so a failed post is retried on the next run and a delivered item is never posted twice; a corrupt
item is counted as failed and left in place for a human. Summaries append to one rolling issue,
incidents open one issue each (055 D-3). This module never reads credentials; ``gh`` uses the
workflow's ``GH_TOKEN``.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable

from ops_runtime import _fsync_dir

Poster = Callable[[str, str, str], None]  # (kind, title, body); raises on failure


def deliver(state_dir, poster: Poster) -> tuple[int, int]:
    """Post every outbox item in name order; returns (delivered, failed)."""
    box = Path(state_dir) / "ops" / "outbox"
    done = Path(state_dir) / "ops" / "delivered"
    delivered = failed = 0
    for item in sorted(box.glob("*.json")) if box.exists() else []:
        try:
            message = json.loads(item.read_text(encoding="utf-8"))
            poster(message["kind"], message["title"], message["body"])
        except Exception as error:  # noqa: BLE001 - every failure leaves the item queued
            print(f"not delivered: {item.name} ({type(error).__name__})", file=sys.stderr)
            failed += 1
            continue
        done.mkdir(parents=True, exist_ok=True)
        os.replace(item, done / item.name)
        _fsync_dir(done)
        delivered += 1
    return delivered, failed


def gh_poster(repo: str | None = None) -> Poster:
    """Post through the GitHub CLI: summaries comment on one rolling issue, incidents open an issue."""
    base = ["gh"] + ([] if repo is None else ["-R", repo])

    def run(args: list[str], body: str | None = None) -> str:
        return subprocess.run(base + args, input=body, capture_output=True, text=True, check=True).stdout

    def post(kind: str, title: str, body: str) -> None:
        if kind == "summary":
            found = json.loads(run(["issue", "list", "--state", "open", "--search", f'in:title "{title}"',
                                    "--json", "number,title"]))
            exact = [issue["number"] for issue in found if issue["title"] == title]
            if exact:
                run(["issue", "comment", str(min(exact)), "--body-file", "-"], body)
            else:
                run(["issue", "create", "--title", title, "--body-file", "-"], body)
        elif kind == "incident":
            run(["issue", "create", "--title", title, "--body-file", "-"], body)
        else:
            raise ValueError(f"unknown outbox kind {kind!r}")

    return post


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deliver queued 055 summaries and incidents")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--repo", help="owner/name; defaults to the current repository")
    args = parser.parse_args(argv)
    delivered, failed = deliver(args.state_dir, gh_poster(args.repo))
    print(json.dumps({"delivered": delivered, "failed": failed}))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
