"""033 T067-T069: two required gate proofs plus index integrity, in guarded disposable copies.

Run: python tests/mutation/run_spec_033_gate_mutants.py.
Controls collect all 97 Gate 3 cases; a kill requires an assertion failure carrying
the intended witness, never a collection/import error. Source and ledger hashes
are checked by the existing mutation isolation helper.
"""
from __future__ import annotations

import sys

import run_058_t007_mutants as base

GUARDS = (
    ("scripts/generate_gate3_evidence.py", (
        ("DSR >= .95 weakened to DSR > 0", "dsr_value < DSR_THRESHOLD", "dsr_value <= 0", "T065 HISTORY GATE"),
    )),
    ("scripts/selection_bias.py", (
        ("lifetime N replaced by surviving matrix columns", 'n_current=counts["n_current"]',
         'n_current=len(matrix["columns"])', "T068 LIFETIME COUNT"),
    )),
    ("reports/api/routes/capital_gate.py", (
        ("index digest unchecked", '_require(hashlib.sha256(raw).hexdigest() == row["sha256"])',
         '_require(True)', "T063 INDEX DIGEST"),
    )),
)


def main() -> int:
    failed = 0
    for guard, mutants in GUARDS:
        base.GUARD, base.TEST = guard, "tests/test_033_gate3.py"
        base.SOURCE = "tests/fixtures/spec_033/gate_strategy.json"
        base.COPIED = ("scripts", "reports", "tests/context.py", "tests/spec033_support.py",
                       "tests/fixtures/spec_033", base.TEST,
                       ".specify/specs/058-edge-research-program/declaration.json")
        base.COLLECTED, base.MUTANTS = 97, mutants
        print(f"GUARD {guard}", flush=True)
        failed |= base.main()
    return failed


if __name__ == "__main__":
    sys.exit(main())
