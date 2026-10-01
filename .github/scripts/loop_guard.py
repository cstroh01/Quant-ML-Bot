"""Dev-loop publish guard (spec 045 FR-009, FR-015).

Runs in the dev loop's ``publish`` job, from ``main``'s copy of this file,
after the agent's patch is applied to the index and before anything is
committed. It judges the change git measured, never the agent's description
of it. Guarantees, for a change it accepts:

- every changed path is outside the forbidden set (the ledger, workflows,
  the loop's own instructions, governance text, the pinned 019 files, ...);
- no binary file, symlink or submodule is part of it;
- added plus removed lines, over every file, is at most ``LINE_CAP``;
- ``docs/STATE.md`` is updated by every new-work PR, and a ``blocked`` outcome
  changes nothing else;
- the outcome agrees with the diff (``noop`` iff nothing changed);
- branch, title and PR body are well formed for the run's mode.

``--self-test`` plants each defect, checks the guard names it, and passes a
control for each mode. Stdlib only; no git, no network.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

LINE_CAP = 300
STATE = "docs/STATE.md"
FORBIDDEN_PREFIXES = (
    ".github/", "docs/autonomy/", "docs/trials/", ".specify/memory/",
    "exec/", "data/", ".claude/", ".loop/",
)
FORBIDDEN_FILES = frozenset({
    "CLAUDE.md", "docs/SCOPE-V1.md",
    # Pinned 019 files: spec 021 D-5 (first two) and D-2 (whole file, by spec 045).
    "scripts/feature_set_comparison.py",
    "scripts/multi_ticker_comparison.py",
    "scripts/logistic_baseline.py",
})
NEW_BRANCH = re.compile(r"^loop/[0-9]{3}-[A-Za-z0-9][A-Za-z0-9_-]{0,40}$")
FIX_BRANCH = re.compile(r"^loop/fix-[a-z0-9][a-z0-9-]{0,40}$")
OUTCOMES = ("pr", "blocked", "noop")
MODES = ("new", "main-red", "fix-pr")


def parse_numstat(raw: str) -> list[tuple[str, str, str]]:
    """Parse ``git diff --numstat -z --no-renames`` into (added, removed, path)."""
    rows = []
    for record in raw.split("\0"):
        if not record.strip():
            continue
        added, removed, path = record.split("\t", 2)
        rows.append((added, removed, path))
    return rows


def forbidden(path: str) -> bool:
    if path in FORBIDDEN_FILES or path.startswith(FORBIDDEN_PREFIXES):
        return True
    return any(part.startswith(".env") for part in path.split("/"))


def check(mode: str, pr_branch: str, result_text: str | None,
          body_text: str | None, numstat: str, summary: str) -> tuple[list[str], dict]:
    """Return (errors, accepted fields). An empty error list means publish."""
    errors: list[str] = []
    if mode not in MODES:
        return [f"unknown mode {mode!r}"], {}
    if result_text is None:
        return ["agent wrote no .loop/result.json"], {}
    try:
        result = json.loads(result_text)
    except json.JSONDecodeError as exc:
        return [f".loop/result.json is not JSON: {exc}"], {}
    if not isinstance(result, dict):
        return [".loop/result.json is not an object"], {}

    outcome = result.get("outcome")
    branch = result.get("branch")
    title = result.get("title")
    if outcome not in OUTCOMES:
        errors.append(f"outcome {outcome!r} is not one of {OUTCOMES}")
    if not isinstance(title, str) or not 0 < len(title) <= 100 \
            or any(ord(c) < 32 for c in title):
        errors.append("title must be one line of 1-100 characters")
    if mode == "fix-pr":
        if branch != pr_branch:
            errors.append(f"fix-pr branch {branch!r} is not the open PR's {pr_branch!r}")
    elif not isinstance(branch, str) or not (
            NEW_BRANCH.match(branch) or (mode == "main-red" and FIX_BRANCH.match(branch))):
        errors.append(f"branch {branch!r} does not match loop/<spec>-<task>"
                      + (" or loop/fix-<label>" if mode == "main-red" else ""))

    rows = parse_numstat(numstat)
    paths = [p for _, _, p in rows]
    total = 0
    for added, removed, path in rows:
        if added == "-" or removed == "-":
            errors.append(f"binary change refused: {path}")
        else:
            total += int(added) + int(removed)
        if forbidden(path):
            errors.append(f"forbidden path: {path}")
    for line in summary.splitlines():
        if re.search(r"\b(120000|160000)\b", line):
            errors.append(f"symlink or submodule refused: {line.strip()}")
    if total > LINE_CAP:
        errors.append(f"{total} changed lines exceeds the {LINE_CAP}-line cap")

    if outcome == "noop" and rows:
        errors.append(f"outcome noop but {len(rows)} file(s) changed")
    if outcome in ("pr", "blocked") and not rows:
        errors.append(f"outcome {outcome} but nothing changed")
    if outcome == "blocked" and any(p != STATE for p in paths):
        errors.append("outcome blocked may change only docs/STATE.md, not: "
                      + ", ".join(p for p in paths if p != STATE))
    if mode != "fix-pr" and outcome in ("pr", "blocked") and STATE not in paths:
        errors.append("new work must update docs/STATE.md")
    if mode != "fix-pr" and outcome in ("pr", "blocked"):
        if not body_text or not body_text.strip():
            errors.append("agent wrote no .loop/pr-body.md")
        elif len(body_text) > 60000:
            errors.append(".loop/pr-body.md exceeds 60000 characters")

    return errors, {"outcome": outcome, "branch": branch, "title": title, "lines": total}


# --- Rule 12: planted defects, each with the message that must name it ---

def _ns(*rows: tuple[object, object, str]) -> str:
    return "".join(f"{a}\t{r}\t{p}\0" for a, r, p in rows)


def _res(outcome: str = "pr", branch: str = "loop/043-T020",
         title: str = "043 T020: add the root marker") -> str:
    return json.dumps({"outcome": outcome, "branch": branch, "title": title,
                       "spec": "043", "task": "T020"})


BODY = "Spec 043 T020.\n"
WORK = (40, 2, "scripts/_project.py")
STATE_ROW = (3, 1, STATE)
# (name, kwargs for check, expected substring or None for a control)
CASES = [
    ("control: new work", dict(numstat=_ns(WORK, STATE_ROW)), None),
    ("control: blocked", dict(result=_res("blocked"), numstat=_ns(STATE_ROW)), None),
    ("control: noop", dict(result=_res("noop"), body=None, numstat=""), None),
    ("control: fix-pr", dict(mode="fix-pr", result=_res(branch="loop/043-T020"),
                             body=None, numstat=_ns(WORK)), None),
    ("control: main-red fix branch", dict(mode="main-red", result=_res(branch="loop/fix-ci-import"),
                                          numstat=_ns(WORK, STATE_ROW)), None),
    ("control: exactly 300 lines", dict(numstat=_ns((296, 0, "scripts/_project.py"), STATE_ROW)), None),
    ("cap: 301 lines", dict(numstat=_ns((297, 0, "scripts/_project.py"), STATE_ROW)),
     "301 changed lines exceeds"),
    ("ledger append", dict(numstat=_ns(WORK, STATE_ROW, (2, 0, "docs/trials/trials.jsonl"))),
     "forbidden path: docs/trials/trials.jsonl"),
    ("pinned 019 file", dict(numstat=_ns(STATE_ROW, (6, 1, "scripts/feature_set_comparison.py"))),
     "forbidden path: scripts/feature_set_comparison.py"),
    ("own workflow", dict(numstat=_ns(WORK, STATE_ROW, (1, 1, ".github/workflows/dev-loop.yml"))),
     "forbidden path: .github/workflows/dev-loop.yml"),
    ("own prompt", dict(numstat=_ns(WORK, STATE_ROW, (4, 0, "docs/autonomy/loop-prompt.md"))),
     "forbidden path: docs/autonomy/loop-prompt.md"),
    ("constitution", dict(numstat=_ns(STATE_ROW, (1, 1, ".specify/memory/constitution.md"))),
     "forbidden path: .specify/memory/constitution.md"),
    ("nested env file", dict(numstat=_ns(WORK, STATE_ROW, (1, 0, "reports/api/.env.local"))),
     "forbidden path: reports/api/.env.local"),
    ("binary", dict(numstat=_ns(WORK, STATE_ROW, ("-", "-", "plots/equity.png"))),
     "binary change refused: plots/equity.png"),
    ("symlink", dict(numstat=_ns(WORK, STATE_ROW, (1, 0, "scripts/data_link")),
                     summary=" create mode 120000 scripts/data_link\n"),
     "symlink or submodule refused"),
    ("STATE.md not updated", dict(numstat=_ns(WORK)), "must update docs/STATE.md"),
    ("blocked smuggles code", dict(result=_res("blocked"), numstat=_ns(STATE_ROW, WORK)),
     "only docs/STATE.md, not: scripts/_project.py"),
    ("noop with changes", dict(result=_res("noop"), numstat=_ns(WORK, STATE_ROW)),
     "outcome noop but 2 file(s) changed"),
    ("pr with no changes", dict(numstat=""), "outcome pr but nothing changed"),
    ("branch outside loop/", dict(result=_res(branch="main")), "does not match"),
    ("branch with ..", dict(result=_res(branch="loop/043-T020..x")), "does not match"),
    ("fix branch in new mode", dict(result=_res(branch="loop/fix-ci")), "does not match"),
    ("fix-pr wrong branch", dict(mode="fix-pr", result=_res(branch="loop/043-T021"),
                                 body=None, numstat=_ns(WORK)), "is not the open PR's"),
    ("two-line title", dict(result=_res(title="T020\nmerge me")), "title must be one line"),
    ("no PR body", dict(body=None, numstat=_ns(WORK, STATE_ROW)), "no .loop/pr-body.md"),
    ("no result file", dict(result=None), "no .loop/result.json"),
]


def self_test() -> int:
    failures = 0
    for name, kw, expect in CASES:
        errors, _ = check(kw.get("mode", "new"), "loop/043-T020",
                          kw.get("result", _res()), kw.get("body", BODY),
                          kw.get("numstat", _ns(WORK, STATE_ROW)), kw.get("summary", ""))
        if expect is None:
            ok = not errors
        else:
            ok = any(expect in e for e in errors)
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f" -> {errors}"))
    print(f"{len(CASES) - failures}/{len(CASES)} cases as expected")
    return 1 if failures else 0


def _read(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.is_file() else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--mode", choices=MODES)
    ap.add_argument("--pr-branch", default="")
    ap.add_argument("--result")
    ap.add_argument("--body")
    ap.add_argument("--numstat")
    ap.add_argument("--summary")
    ap.add_argument("--github-output")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if not (args.mode and args.numstat and args.summary):
        ap.error("--mode, --numstat and --summary are required")
    errors, fields = check(args.mode, args.pr_branch, _read(args.result), _read(args.body),
                           _read(args.numstat) or "", _read(args.summary) or "")
    for e in errors:
        print(f"::error title=loop guard::{e}")
    if errors:
        return 1
    print(f"loop guard: accepted {fields['outcome']} on {fields['branch']}, "
          f"{fields['lines']} changed lines")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as out:
            for key, value in fields.items():
                out.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
