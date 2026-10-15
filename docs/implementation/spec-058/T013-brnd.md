# 058 T013 B-RND wiring (queue Q132), 2026-10-15

EXAMPLE evidence only — synthetic panels and a synthetic ledger. No real data, no T015 run.

- `BRND_SEEDS = range(20261015, 20261035)`, 20 seeds, fixed in code before T015. `require_brnd_seeds` refuses any other set.
- Per candidate c: activity = `matched_activity(target_book(c) > 0 carried forward)`, fitted on the research-window panel
  only (the seal is checked first). Same cadence as c (H8 weekly), same sizing class:
  inverse-vol vol target (H1-*, H2-*, H4, H5, H9), D-8 equal legs (H3-*, H6-*, H7, H8), unscaled equal weight (H10).
- Same fills, `fill_cost`, commission, capital and walk-forward test windows as `run_configuration`.
- Recorded one `research_attempt` per (c, seed), role `random_signal_baseline`, `model.name = "B-RND"`. Baselines
  never count toward N_family. 15 x 20 = 300 records at T015.
- `brnd_dispersion`: mean/sd/min/max over seeds of annualized net Sharpe (risk-free 0, as recorded), annualized log
  return, annualized volatility and max drawdown. Report-only; never used for selection.

Verification: `tests/test_058_walk_forward.py` 28 passed (10 new). `tests/mutation/run_058_brnd_mutants.py`:
control PASS, 6/6 killed (M1 one seed, M2 seed ignored, M3 role candidate, M4 sizing swap, M5 activity past
RESEARCH_END, M6 cadence ignored), source restored. Real `docs/trials/` bytes unchanged.

Known limitation (disclose in T017/T018): for an almost-always-invested candidate (H4, H10, and any book holding
every name), matched activity is ~ initial 1 / exit 0, so B-RND nearly reproduces the candidate and its seed
dispersion collapses toward zero. That is the matched-activity design (#192), not a bug: the Rule 4 comparison is
informative only for candidates that switch. B-BH remains the comparison for always-invested books.
