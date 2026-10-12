"""Rule 12 driver for spec 058 T011: signals H1-H8 (Rule 1 lookahead, listing-date eligibility).

Run: python tests/mutation/run_058_t011_mutants.py. Reuses run_058_t007_mutants.py's isolated copy,
control, witness-carrying-failure and byte-identity checks against `scripts/signals.py`.
"""
from __future__ import annotations

import sys

import run_058_t007_mutants as base

GUARD = "scripts/signals.py"
TEST = "tests/test_058_signals.py"
# (name, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("vol lookback one row short", "_observed(closes, VOL_SESSIONS + 1)", "_observed(closes, VOL_SESSIONS)",
     "T011 LISTING"),
    ("pre-listing rows back-filled", "return closes.notna()", "return closes.bfill().notna()", "T011 LISTING"),
    ("centred SMA window", "rolling(sessions, min_periods=sessions)",
     "rolling(sessions, min_periods=sessions, center=True)", "T011 LOOKAHEAD"),
    ("return ends after t", "closes.shift(end_lag) /", "closes.shift(-end_lag) /", "T011 LOOKAHEAD"),
    ("vol read one row ahead", "np.log(s).diff().rolling", "np.log(s).diff().shift(-1).rolling", "T011 LOOKAHEAD"),
    ("momentum includes the last month", "_past_return(closes, lag, MONTH_SESSIONS) > 0",
     "_past_return(closes, lag) > 0", "T011 SKIP"),
    ("dual momentum against zero", "max(axis=1) > total[SAFE_ASSET]", "max(axis=1) > 0", "T011 DUAL"),
    ("ranking direction flipped", "ascending=not highest", "ascending=highest", "T011 LISTING"),
    ("fewer than k still picked", ".mul(enough, axis=0)", ".mul(True, axis=0)", "T011 FEW"),
    ("a gap inside the window ignored", ".sum().eq(rows)", ".sum().ge(rows - 1)", "T011 GAP"),
)


def main() -> int:
    base.GUARD, base.TEST, base.SOURCE = GUARD, TEST, TEST
    base.COPIED, base.COLLECTED, base.MUTANTS = ("scripts", "tests/context.py", TEST), 32, MUTANTS
    return base.main()


if __name__ == "__main__":
    sys.exit(main())
