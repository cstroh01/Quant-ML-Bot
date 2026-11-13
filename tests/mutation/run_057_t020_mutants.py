"""057 T020 Rule 12: each planted defect in the D-12 persist retry and named halt must fail the real tests.

Usage: python tests/mutation/run_057_t020_mutants.py. Restores every source byte for byte.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops/persist_state.sh"
PAPER = ROOT / "exec/paper_loop.py"
LOOP = ROOT / "exec/live_loop.py"
TESTS = ["tests/test_057_t020_persist_retry.py"]
PUSH = "git push -q origin HEAD:ops-state"
RAISE = "            raise HaltProfile(f'ops-state persist failed: {reason}') from None\n"
MUTANTS = {
    "no retry (main)": (SCRIPT, "for wait in 0 5 15; do", "for wait in 0; do"),
    "one retry only": (SCRIPT, "for wait in 0 5 15; do", "for wait in 0 5; do"),
    "four attempts": (SCRIPT, "for wait in 0 5 15; do", "for wait in 0 5 15 30; do"),
    "flat wait": (SCRIPT, "for wait in 0 5 15; do", "for wait in 0 5 5; do"),
    "no wait between attempts": (SCRIPT, '  if [ "$wait" -gt 0 ]; then sleep "$wait"; fi\n', ""),
    "first failure ends the loop": (SCRIPT, f"  if {PUSH}; then exit 0; fi\n", f"  if {PUSH}; then exit 0; else exit 4; fi\n"),
    "exhausted pushes exit 0": (SCRIPT, "done\nexit 4\n", "done\nexit 0\n"),
    "exhausted pushes exit 3": (SCRIPT, "done\nexit 4\n", "done\nexit 3\n"),
    "commit failure ignored": (SCRIPT, '|| git commit -q -m "ops state: $*" || exit 3', '|| git commit -q -m "ops state: $*" || true'),
    "add failure ignored": (SCRIPT, "git add -A || exit 3", "git add -A || true"),
    "config failure unlabelled": (SCRIPT, "git config user.name qmb-ops || exit 3\ngit config user.email qmb-ops@users.noreply.github.com || exit 3\n",
                                  "git config user.name qmb-ops\ngit config user.email qmb-ops@users.noreply.github.com\n"),
    "place persists after counting": (LOOP, "        self.persist()\n        self.place_calls+=1\n",
                                      "        self.place_calls+=1\n        self.persist()\n"),
    "forced push": (SCRIPT, f"  if {PUSH}; then", "  if git push -q --force origin HEAD:ops-state; then"),
    "bare RuntimeError (main)": (PAPER, "            raise PersistCommandFailed(result.returncode)",
                                 '            raise RuntimeError(f"persist command exited {result.returncode}")'),
    "exit status dropped": (PAPER, "        self.returncode = returncode", "        self.returncode = None"),
    "persist not wrapped (main)": (LOOP, "    persist=named_persist(persist)\n", ""),
    "exit 3 and 4 labels swapped": (LOOP, "PERSIST_FAILURES={3:'commit step failed (exit 3)',4:'push failed after 3 attempts (exit 4)'}",
                                    "PERSIST_FAILURES={4:'commit step failed (exit 3)',3:'push failed after 3 attempts (exit 4)'}"),
    "command text recorded": (LOOP, RAISE, "            raise HaltProfile(f'ops-state persist failed: {exc}') from None\n"),
    "not an exec/ halt type": (LOOP, RAISE, "            raise RuntimeError(f'ops-state persist failed: {reason}') from None\n"),
    "persist failure swallowed": (LOOP, RAISE, "            return None\n"),
    "missing persist replaced": (LOOP, "    if persist is None: return None\n", "    if persist is None: persist=lambda:None\n"),
}
def run():
    return subprocess.run([sys.executable, "-B", "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True).returncode
def main():
    paths = {path for path, _, _ in MUTANTS.values()}
    originals = {path: path.read_bytes() for path in paths}; results = {}
    try:
        assert run() == 0, "control"
        for name, (path, old, new) in MUTANTS.items():
            raw = originals[path].decode("utf-8"); crlf = "\r\n" in raw
            source = raw.replace("\r\n", "\n"); assert source.count(old) == 1, name
            mutated = source.replace(old, new)
            path.write_bytes((mutated.replace("\n", "\r\n") if crlf else mutated).encode("utf-8"))
            results[name] = "killed" if run() else "SURVIVED"
            path.write_bytes(originals[path])
    finally:
        for path, data in originals.items():
            path.write_bytes(data)
    print(json.dumps({"control": "PASS", "killed": sum(v == "killed" for v in results.values()),
                      "total": len(MUTANTS), "survivors": [k for k, v in results.items() if v != "killed"]}))
    return 0 if all(v == "killed" for v in results.values()) else 1
if __name__ == "__main__":
    sys.exit(main())
