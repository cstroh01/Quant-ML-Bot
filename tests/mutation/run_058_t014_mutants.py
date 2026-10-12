"""Rule 12 driver for spec 058 T014: the walk-forward runner.

Run: python tests/mutation/run_058_t014_mutants.py. Reuses run_058_t007_mutants.py's isolated copy,
control, witness-carrying-failure and byte-identity checks (docs/trials included) against
`scripts/edge_walk_forward.py`.
"""
from __future__ import annotations

import sys

import run_058_t007_mutants as base

GUARD = "scripts/edge_walk_forward.py"
TEST = "tests/test_058_walk_forward.py"
DECLARATION = ".specify/specs/058-edge-research-program/declaration.json"
# (name, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("embargo only the label horizon", "EMBARGO = LONGEST_LOOKBACK", "EMBARGO = LABEL_HORIZON", "T014 EMBARGO"),
    ("lookback understated", "12 * MONTH_SESSIONS + 1", "6 * MONTH_SESSIONS + 1", "T014 EMBARGO"),
    ("training rows recorded", "daily = daily.loc[tested].dropna()", "daily = daily.dropna()", "T014 TRAIN"),
    ("returns function ignores the seal",
     "        raise HoldoutSealError(f\"the walk-forward panel must end by {RESEARCH_END}; the holdout is sealed\")\n"
     "    result = run_portfolio_backtest",
     "        pass\n    result = run_portfolio_backtest", "T014 SEAL"),
    ("runner ignores the seal",
     "        raise HoldoutSealError(f\"the walk-forward panel must end by {RESEARCH_END}; the holdout is sealed\")\n"
     "    require_buildable(config_id)",
     "        pass\n    require_buildable(config_id)", "T014 REFUSE holdout session"),
    ("undecided sizing refused only after start", "    require_buildable(config_id)\n    _, cv = oos_sessions(",
     "    _, cv = oos_sessions(", "T014 REFUSE undecided"),
    ("flat-bps costs accepted",
     "if not isinstance(slippage, dict) or slippage.get(\"model\") != COST_MODEL or \"commission\" not in costs:",
     "if not isinstance(slippage, dict) or \"commission\" not in costs:", "T014 REFUSE flat bps costs"),
    ("recorded as in-sample", "\"oos\": True, \"cv\": cv", "\"oos\": False, \"cv\": cv", "T014 RECORD metadata"),
    ("recorded outside the family", "research_attempt(config, role=role, family=FAMILY)",
     "research_attempt(config, role=role)", "T014 RECORD"),
    ("re-targeted every session", "return book.loc[decision_sessions(book.index, cadence=\"monthly\")]",
     "return book", "T014 CADENCE"),
    ("H9 blends the wrong trend filter", "H9_PARTS = (\"H1-12\", \"H2-200\", \"H4\")",
     "H9_PARTS = (\"H1-12\", \"H2-100\", \"H4\")", "T014 H9"),
    ("costs dropped", "commission_per_fill=commission_per_fill, fill_cost=fill_cost)",
     "commission_per_fill=0.0, fill_cost=lambda *_: 0.0)", "T014 OOS"),
    ("simple returns recorded as log", "daily = np.log(equity / equity.shift(1))",
     "daily = equity / equity.shift(1) - 1", "T014 OOS"),
    ("book reads the next close", "hypothesis_selection(part, closes), closes",
     "hypothesis_selection(part, closes.shift(-1).ffill()), closes", "T014 LOOKAHEAD book"),
    ("started config without the fold count", "    _, cv = oos_sessions(closes.index)", "    _, cv = oos_sessions(closes.index)\n    cv = {k: v for k, v in cv.items() if k != \"folds\"}",
     "T014 ELIGIBLE"),
)


def main() -> int:
    base.GUARD, base.TEST, base.SOURCE = GUARD, TEST, DECLARATION
    base.COPIED, base.COLLECTED, base.MUTANTS = ("scripts", "tests/context.py", "tests/conftest.py", DECLARATION,
                                                  TEST), 12, MUTANTS
    return base.main()


if __name__ == "__main__":
    sys.exit(main())
