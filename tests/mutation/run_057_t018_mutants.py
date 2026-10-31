"""057 T018 Rule 12: each planted defect in the D-10 cash-stamp bound must fail the real tests.

Usage: python tests/mutation/run_057_t018_mutants.py. Restores every source byte for byte.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "exec/fidelity_live.py"
TESTS = ["tests/test_057_t018_cash_stamp.py", "tests/test_057_q139.py"]
BOUND = "if when > latest + _CASH_STAMP_SKEW or when.astimezone("
READ = "            latest = max(as_of, _read_clock())\n"
ACCOUNTS = "            accounts = self._client.balances.get_balances([self.__account]).accounts\n"
MUTANTS = {
    "bound is pre-login as_of": (LIVE, BOUND, "if when > as_of or when.astimezone("),
    "no skew": (LIVE, BOUND, "if when > latest or when.astimezone("),
    "no upper bound": (LIVE, BOUND, "if when.astimezone("),
    "skew five minutes": (LIVE, "timedelta(seconds=60)", "timedelta(seconds=300)"),
    "skew long by one": (LIVE, "timedelta(seconds=60)", "timedelta(seconds=61)"),
    "skew short by one": (LIVE, "timedelta(seconds=60)", "timedelta(seconds=59)"),
    "clock can lower bound": (LIVE, READ, "            latest = _read_clock()\n"),
    "clock read before response": (LIVE, ACCOUNTS, READ + ACCOUNTS),
    "day check removed": (LIVE, "!= as_of.astimezone(ZoneInfo('America/New_York')).date():\n                    continue",
                          "!= when.astimezone(ZoneInfo('America/New_York')).date():\n                    continue"),
    "offsets not recorded": (LIVE, "                offsets.append(int((when - latest).total_seconds()))\n", ""),
    "amount in stamps": (LIVE, "{'snapshots': len(types), 'stamp_types': types, 'offsets_s': offsets}",
                         "{'snapshots': len(types), 'stamp_types': types, 'offsets_s': offsets, 'amount': snapshots[0].cash_detail.settled_amt}"),
    "stamp value recorded": (LIVE, "types.append(type(stamp).__name__)", "types.append(str(stamp))"),
    "float offsets": (LIVE, "offsets.append(int((when - latest).total_seconds()))", "offsets.append((when - latest).total_seconds())"),
    "always millis": (LIVE, "stamp / 1000 if abs(stamp) > 100000000000 else stamp", "stamp / 1000"),
    "bad amount skipped": (LIVE, "or amount < 0:\n                    raise ValueError\n                core =", "or amount < 0:\n                    continue\n                core ="),
    "stamps always set": (LIVE, "        offsets, types = [], []\n        try:\n", "        offsets, types = [], []\n        self.cash_stamps = {}\n        try:\n"),
    "stamps not in diagnostic": (LIVE, "            facts['cash_stamps'] = self.cash_stamps  # D-10\n", "            pass\n"),
    "naive clock": (LIVE, "return datetime.now(timezone.utc)", "return datetime.now()"),
}


def main():
    survivors = []
    for name, (path, old, new) in MUTANTS.items():
        original = path.read_bytes()
        text = original.decode("utf-8")
        if text.count(old) != 1:
            raise SystemExit(f"mutant target not unique: {name}")
        if name == "clock read before response":
            text = text.replace(READ, "", 1)
        path.write_bytes(text.replace(old, new).encode("utf-8"))
        try:
            run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", *TESTS], cwd=ROOT, capture_output=True)
        finally:
            path.write_bytes(original)
        print(("killed  " if run.returncode else "SURVIVED"), name)
        if not run.returncode:
            survivors.append(name)
    print(json.dumps({"mutants": len(MUTANTS), "survivors": survivors}))
    return 1 if survivors else 0


if __name__ == "__main__":
    raise SystemExit(main())
