"""Rule 12 driver for spec 058 T010: portfolio accounting (D-6, Rule 1).

Run: python tests/mutation/run_058_t010_mutants.py. One-site mutants of `scripts/portfolio_backtest.py`
in an isolated copy; a kill is a FAILURE (never an error) whose assertion carries the witness. Same
control and byte-identity checks as run_058_t007_mutants.py.
"""
from __future__ import annotations

import sys

import run_058_t007_mutants as base

GUARD = "scripts/portfolio_backtest.py"
TEST = "tests/test_058_portfolio.py"
# (name, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("fill at the decision close", "quotes = opens.iloc[i]", "quotes = closes.iloc[i - 1]", "T010 NEXT_OPEN"),
    ("missing row forward-filled", "quotes = opens.iloc[i]", "quotes = opens.ffill().iloc[i]", "T010 NO_ROW"),
    ("sized off the fill-session close", "value / close[ticker]", "value / closes.iloc[i + 1][ticker]",
     "T010 LOOKAHEAD"),
    ("cost read as of the fill session", "fill_cost(ticker, decision, abs(delta))",
     "fill_cost(ticker, session, abs(delta))", "T010 COST_ASOF"),
    ("marks back-filled", "marks = closes.ffill()", "marks = closes.bfill()", "T010 MARK"),
    ("buys never scaled to cash", "scale = min(1.0, ", "scale = max(1.0, ", "T010 CASH"),
)


def main() -> int:
    base.GUARD, base.TEST, base.SOURCE = GUARD, TEST, TEST
    base.COPIED, base.COLLECTED, base.MUTANTS = ("scripts", "tests/context.py", TEST), 14, MUTANTS
    return base.main()


if __name__ == "__main__":
    sys.exit(main())
