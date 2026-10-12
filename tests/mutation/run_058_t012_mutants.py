"""Rule 12 driver for spec 058 T012/T013: sizing, H9/H10 combos and the buy-and-hold baseline book.

Run: python tests/mutation/run_058_t012_mutants.py. Reuses run_058_t007_mutants.py's isolated copy,
control, witness-carrying-failure and byte-identity checks against `scripts/portfolio_risk.py`.
"""
from __future__ import annotations

import sys

import run_058_t007_mutants as base

GUARD = "scripts/portfolio_risk.py"
TEST = "tests/test_058_sizing.py"
# (name, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("vol before a full window", "ewm(span=span, min_periods=span)", "ewm(span=span, min_periods=1)",
     "T012 EWMA WARMUP"),
    ("span read as centre of mass", "ewm(span=span, min_periods", "ewm(com=span, min_periods", "T012 EWMA"),
    ("vol left daily", "min_periods=span).std()\n    return daily * np.sqrt(periods)",
     "min_periods=span).std()\n    return daily", "T012 TARGET"),
    ("vol reads the next return", "log_returns(closes).ewm(", "log_returns(closes).shift(-1).ewm(",
     "T012 LOOKAHEAD"),
    ("gross cap skipped", "return apply_gross_cap(standalone, max_gross=max_gross)", "return standalone",
     "T012 GROSS"),
    ("target hardcoded", "target_volatility=target_volatility\n", "target_volatility=0.15\n", "T012 TARGET"),
    ("B-BH counts every ticker", "count = selection.sum(axis=1)", "count = selection.count(axis=1)",
     "T013 B-BH listing"),
    ("H10 with one leg listed", "notna().all(axis=1)", "notna().any(axis=1)", "T013 H10 LISTING"),
    ("H9 summed, not averaged", "for book in books) / len(books)", "for book in books)", "T013 H9"),
)


def main() -> int:
    base.GUARD, base.TEST, base.SOURCE = GUARD, TEST, TEST
    base.COPIED, base.COLLECTED, base.MUTANTS = ("scripts", "tests/context.py", TEST), 7, MUTANTS
    return base.main()


if __name__ == "__main__":
    sys.exit(main())
