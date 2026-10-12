"""Rule 12 driver for queue Q97 (spec 033 amendment 2026-10-11): trial counts bound to one ledger head.

Run: python tests/mutation/run_033_counts_mutants.py. Reuses run_058_t007_mutants.py's isolated copy,
control, witness-carrying-failure and byte-identity checks, once per guarded module.
"""
from __future__ import annotations

import sys

import run_058_t007_mutants as base

TEST = "tests/test_033_dsr.py"
DECLARATION = ".specify/specs/058-edge-research-program/declaration.json"
# (name, exact old fragment, mutant fragment, witness in the assertion message), per guarded module
GUARDS = (
    ("scripts/trial_registry.py", (
        ("family N from a second verification", 'status = _family_count(family, state["events"], ledger.root)',
         "status = family_status(family, ledger)", "Q97 ONE HEAD"),
        ("family head from a second verification",
         '"reverted_to_lifetime": not status["within_cap"],\n                            "ledger_head_hash": state["head"]}',
         '"reverted_to_lifetime": not status["within_cap"],\n                            "ledger_head_hash": ledger.verify()["head"]}',
         "Q97 ONE HEAD"),
    )),
    ("scripts/selection_bias.py", (
        ("selection_bias reads the ledger itself", "lifetime_count = trial_counts\n",
         "def lifetime_count(backfill, ledger, *, family=None):\n    ledger.verify()\n"
         "    return trial_counts(backfill, ledger, family=family)\n", "Q97 PURE"),
    )),
)


def main() -> int:
    failed = 0
    for guard, mutants in GUARDS:
        base.GUARD, base.TEST, base.SOURCE = guard, TEST, DECLARATION
        base.COPIED, base.COLLECTED, base.MUTANTS = ("scripts", "tests/context.py", "tests/spec033_support.py", "tests/fixtures/spec_033",
                                                      DECLARATION, TEST), 30, mutants
        print(f"== {guard}")
        failed |= base.main()
    return failed


if __name__ == "__main__":
    sys.exit(main())
