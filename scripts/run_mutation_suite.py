"""§11.3 item 1 evidence: the full pytest suite, then every Rule 12 driver in tests/mutation/, serially.

Drivers mutate sources in place and restore them, so they must never run in parallel in one checkout;
this runner runs them one at a time, gives each that takes an output folder its own, and checks after
each that no tracked file is left changed. Writes one JSON record (commit, UTC time, suite summary,
per-driver exit code and last line) and exits 0 only when the suite and every driver passed.

Usage: python scripts/run_mutation_suite.py --out <record.json> [--work <scratch dir>] [--skip-suite]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def _last_line(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""


def run_suite() -> dict:
    started = time.monotonic()
    proc = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True)
    return {"exit_code": proc.returncode, "summary": _last_line(proc.stdout), "seconds": round(time.monotonic() - started)}


def run_drivers(work: Path) -> list[dict]:
    results = []
    for driver in sorted((ROOT / "tests" / "mutation").glob("run_*.py")):
        args = [sys.executable, "-B", str(driver)]
        if "sys.argv[1]" in driver.read_text(encoding="utf-8"):
            args.append(str(work / driver.stem))
        started = time.monotonic()
        proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
        dirty = _git("status", "--porcelain", "--untracked-files=no")
        results.append({"driver": driver.relative_to(ROOT).as_posix(), "exit_code": proc.returncode,
                        "last_line": _last_line(proc.stdout + "\n" + proc.stderr),
                        "seconds": round(time.monotonic() - started), "tree_clean_after": dirty == ""})
        if dirty:
            raise RuntimeError(f"{driver.name} left tracked files changed:\n{dirty}")
    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--work", type=Path)
    p.add_argument("--skip-suite", action="store_true")
    a = p.parse_args(argv)
    if _git("status", "--porcelain", "--untracked-files=no"):
        print("refused: tracked files are changed; run on a clean checkout", file=sys.stderr)
        return 2
    record = {"label": "§11.3 item 1 evidence", "commit": _git("rev-parse", "HEAD"),
              "started_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
              "python": sys.version.split()[0]}
    record["suite"] = None if a.skip_suite else run_suite()
    with tempfile.TemporaryDirectory() as scratch:
        record["drivers"] = run_drivers(a.work or Path(scratch))
    record["finished_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    passed = [d for d in record["drivers"] if d["exit_code"] == 0]
    record["verdict"] = ("PASS" if len(passed) == len(record["drivers"])
                         and (record["suite"] is None or record["suite"]["exit_code"] == 0) else "FAIL")
    record["drivers_passed"] = f"{len(passed)}/{len(record['drivers'])}"
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(f"{record['verdict']}: suite {record['suite'] and record['suite']['summary']}; drivers {record['drivers_passed']}")
    return 0 if record["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
