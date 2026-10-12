"""Rule 12 driver for spec 058 T012/T013: portfolio sizing, rebalance rows, H9/H10 combos and B-BH.

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
    ("vol before a full window", "ewm(span=span, min_periods=span).std()", "ewm(span=span, min_periods=1).std()",
     "T012 EWMA WARMUP"),
    ("span read as centre of mass", "ewm(span=span, min_periods=span).std()", "ewm(com=span, min_periods=span).std()",
     "T012 EWMA"),
    ("vol left daily", "min_periods=span).std()\n    return daily * np.sqrt(periods)",
     "min_periods=span).std()\n    return daily", "T012 TARGET"),
    ("vol reads the next return", "daily = log_returns(closes).ewm(", "daily = log_returns(closes).shift(-1).ewm(",
     "T012 LOOKAHEAD"),
    ("covariance before a joint window", "ewm(span=span, min_periods=span).cov()",
     "ewm(span=span, min_periods=1).cov()", "T012 PAIR GAP"),
    ("covariance reads the next return", "return log_returns(closes).ewm(", "return log_returns(closes).shift(-1).ewm(",
     "T012 LOOKAHEAD"),
    ("gross cap skipped", "return apply_gross_cap(legs * (target / np.sqrt(risk)), max_gross=max_gross)",
     "return legs * (target / np.sqrt(risk))", "T012 GROSS"),
    ("target hardcoded", "legs * (target / np.sqrt(risk))", "legs * (0.15 / np.sqrt(risk))", "T012 TARGET"),
    ("per-leg scaling restored", "legs * (target / np.sqrt(risk))", "legs * target", "T012 PORTFOLIO"),
    ("covariance read as diagonal", "risk = float(weights @ matrix @ weights)",
     "risk = float(weights @ np.diag(np.diag(matrix)) @ weights)", "T012 PORTFOLIO"),
    ("missing pair read as zero", "matrix = covariance.loc[session].loc[active, active].to_numpy(dtype=float)",
     "matrix = np.nan_to_num(covariance.loc[session].loc[active, active].to_numpy(dtype=float))",
     "T012 PAIR GAP"),
    ("daily re-targeting restored", "return book.loc[opens]", "return book", "T012 CADENCE"),
    ("first row a decision", "opens = np.zeros(len(sessions), dtype=bool)",
     "opens = np.ones(len(sessions), dtype=bool)", "T012 CADENCE"),
    ("weekly read as monthly", 'period = iso["year"].to_numpy() * 100 + iso["week"].to_numpy()',
     "period = sessions.year * 12 + sessions.month", "T012 CADENCE"),
    ("calendar year with ISO week", 'iso["year"].to_numpy() * 100', "sessions.year.to_numpy() * 100",
     "T012 CADENCE iso year"),
    ("B-BH counts every ticker", "count = selection.sum(axis=1)", "count = selection.count(axis=1)",
     "T013 B-BH listing"),
    ("H10 with one leg listed", "notna().all(axis=1)", "notna().any(axis=1)", "T013 H10 LISTING"),
    ("H9 blends a levered book", "if (book.sum(axis=1) > 1.0 + CORRELATION_TOLERANCE).any():", "if False:",
     "T013 H9 GROSS"),
    ("H9 summed, not averaged", "for book in books) / len(books)", "for book in books)", "T013 H9"),
)


def main() -> int:
    base.GUARD, base.TEST, base.SOURCE = GUARD, TEST, TEST
    base.COPIED, base.COLLECTED, base.MUTANTS = ("scripts", "tests/context.py", TEST), 11, MUTANTS
    return base.main()


if __name__ == "__main__":
    sys.exit(main())
