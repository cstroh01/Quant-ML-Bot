"""Ledger verify cache (2026-10-16) Rule 12 mutants: each must fail a named assertion; bytes restored."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = "scripts/trial_registry.py"
MUTANTS = {
    "M1 stat ignored": ("    if _VERIFIED_SIDECARS.get(key) == (claim, stamp):", "    if key in _VERIFIED_SIDECARS:"),
    "M2 never cached": ("    _VERIFIED_SIDECARS[key] = (claim, stamp)\n", "    pass\n"),
    "M3 claim ignored": ("    if _VERIFIED_SIDECARS.get(key) == (claim, stamp):",
                         "    if _VERIFIED_SIDECARS.get(key, (None, None))[1] == stamp:"),
}


def run() -> int:
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_043_verify_cache.py", "-q",
                           "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True).returncode


def main() -> int:
    original = (ROOT / SRC).read_text(encoding="utf-8")
    for name, (old, _) in MUTANTS.items():
        assert original.count(old) == 1, f"{name}: expected one site"
    killed = 0
    try:
        assert run() == 0, "control must pass"
        for name, (old, new) in MUTANTS.items():
            (ROOT / SRC).write_text(original.replace(old, new), encoding="utf-8")
            ok = run() != 0
            killed += ok
            print(("KILLED  " if ok else "SURVIVED"), name)
    finally:
        (ROOT / SRC).write_text(original, encoding="utf-8")
    print(f"{killed}/{len(MUTANTS)} killed")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
