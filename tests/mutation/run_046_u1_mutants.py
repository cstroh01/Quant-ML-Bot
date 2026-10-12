"""Rule 12 driver for spec 046 U1 (T003-T006): M1-M4, M7 and M10 against `scripts/cost_model.py`.

Run: python tests/mutation/run_046_u1_mutants.py. Reuses run_058_t007_mutants.py's isolated copy,
collection count and byte-identity checks. A kill is a FAILURE (never an error) of the named test;
any surviving mutant, error or non-green control exits 1.
"""
from __future__ import annotations

import sys

import run_058_t007_mutants as base

GUARD = "scripts/cost_model.py"
TEST = "tests/test_046_cost_model.py"
COLLECTED = 32
REFUSE = 'raise CostUnavailable("spread_undefined", "EDGE is undefined on this window")'
# (name, exact old fragment, mutant fragment, test that must fail)
MUTANTS = (
    ("M1 sigma reads t+1", 'np.log(window["Close"]', 'np.log(history.loc[window.index[1]:].iloc[:WINDOW + 1]["Close"]',
     "test_future_bars_cannot_move_the_estimate"),
    ("M1 ADV reads t+1", 'adv = float(recent["Volume"].mean())',
     'adv = float(history.loc[recent.index[1]:].iloc[:WINDOW]["Volume"].mean())', "test_future_bars_cannot_move_the_estimate"),
    ("M1 centered spread window", 's2 = edge_squared(recent["Open"], recent["High"], recent["Low"], recent["Close"])',
     's2 = edge_squared(*(history.loc[recent.index[10]:].iloc[:WINDOW][k] for k in ("Open", "High", "Low", "Close")))',
     "test_future_bars_cannot_move_the_estimate"),
    ("M2 linear impact", "math.sqrt(quantity / adv)", "(quantity / adv)",
     "test_impact_is_square_root_in_quantity_with_spread_unchanged"),
    ("M3 unverified volume accepted", '{"nominal_reconstructed", "provider_nominal"}',
     '{"nominal_reconstructed", "provider_nominal", "provider_unverified", "adjusted"}',
     "test_only_verified_volume_bases_are_accepted"),
    ("M4 warm-up shortened", "if len(past) < WINDOW + 1:", "if len(past) < 3:",
     "test_warmup_refuses_until_the_first_complete_window"),
    ("M4 missing session accepted", "if not window.index.equals(expected):", "if False:",
     "test_holidays_pass_but_a_missing_session_refuses"),
    ("M7 full spread as half", "half = math.sqrt(abs(s2)) / 2.", "half = math.sqrt(abs(s2))",
     "test_half_spread_matches_bidask_oracle"),
    ("M7 negative S^2 to zero", "half = math.sqrt(abs(s2)) / 2.", "half = math.sqrt(max(s2, 0.)) / 2.",
     "test_half_spread_matches_bidask_oracle"),
    ("M7 undefined S to zero", REFUSE, "s2 = 0.", "test_unusable_inputs_refuse_rather_than_trade_free"),
    ("M10 best robustness Y as primary", "if self.impact_coef != 1.0:", "if self.impact_coef not in (0.5, 1.0, 2.0):",
     "test_primary_config_is_fixed"),
    ("M10 robustness Y unchecked", "if self.impact_coef not in ROBUSTNESS_COEFS:", "if False:",
     "test_robustness_rows_are_labelled_and_cannot_stand_in_for_primary"),
    ("M10 robustness Y not applied", "impact = config.impact_coef * sigma", "impact = 1.0 * sigma",
     "test_robustness_rows_are_labelled_and_cannot_stand_in_for_primary"),
    ("M10 convention dropped from config", "return asdict(self)",
     'return {k: v for k, v in asdict(self).items() if k != "spread_handling"}',
     "test_canonical_config_records_every_convention_and_refuses_altered_ones"),
    ("M10 altered convention accepted", "if getattr(self, name) != value:", "if False:",
     "test_canonical_config_records_every_convention_and_refuses_altered_ones"),
    ("M10 convention text drifts", "sample std ddof=1, not annualized", "sample std ddof=0, annualized",
     "test_canonical_config_records_every_convention_and_refuses_altered_ones"),
    ("M10 unknown role accepted", 'elif self.role == "robustness":', 'elif self.role in ("robustness", "best"):',
     "test_robustness_rows_are_labelled_and_cannot_stand_in_for_primary"),
    ("invented source accepted", "if self.source != SOURCE:", "if False:",
     "test_robustness_rows_are_labelled_and_cannot_stand_in_for_primary"),
    ("unvalidated config accepted", "if not isinstance(config, CostConfig):", "if False:",
     "test_robustness_rows_are_labelled_and_cannot_stand_in_for_primary"),
    ("split check removed", "if any(recent.index[0]", "if False and any(recent.index[0]",
     "test_split_inside_the_window_refuses_and_before_it_does_not"),
    ("split check from t-19", "if any(recent.index[0]", "if any(recent.index[1]",
     "test_split_inside_the_window_refuses_and_before_it_does_not"),
    ("zero ADV accepted", "if adv <= 0:", "if False:", "test_unusable_inputs_refuse_rather_than_trade_free"),
    ("as_of check removed", "if as_of not in index:", "if False:", "test_unusable_inputs_refuse_rather_than_trade_free"),
    ("fill-price check removed", "if not half + impact < 1.:", "if False:",
     "test_unusable_inputs_refuse_rather_than_trade_free"),
)


def main() -> int:
    base.GUARD, base.TEST, base.SOURCE = GUARD, TEST, TEST
    base.COPIED, base.COLLECTED = ("scripts", "tests/context.py", TEST), COLLECTED
    watched = [GUARD, TEST]
    sources, ledger = base.tree_digest(watched), base.tree_digest(["docs/trials"])
    with base.guarded():
        control = base.run_copy(None)
        assert not control, f"unchanged copy is not green: {control}"
        print(f"CONTROL green (unchanged copy, {COLLECTED} collected)")
        killed = 0
        for mutant in MUTANTS:
            results = base.run_copy(mutant)
            ok = not any(k == "error" for k, _, _ in results) and any(
                k == "failure" and name.startswith(mutant[3]) for k, name, _ in results)
            killed += ok
            print("KILLED  " if ok else "SURVIVED", f"{mutant[0]} -> {mutant[3]}")
    assert base.tree_digest(watched) == sources, "sources changed"
    assert base.tree_digest(["docs/trials"]) == ledger, "docs/trials changed"
    print(f"{killed}/{len(MUTANTS)} killed; sources and docs/trials ({len(ledger)} files) byte-identical")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
