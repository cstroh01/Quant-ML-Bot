# 051 F01: fail-closed numeric inputs and canonical state isolation

Source: Codex cross-review 2026-10-08 (CROSS-REVIEW-MAIN.md, private folder), 051 P1 findings at
`scripts/mode_config.py` L77, L177, L236, L254 of main 2c72c9a. Synthetic tests only.
EXAMPLE — NOT A RESULT.

## Red (main 2c72c9a, `tests/test_051_finite_inputs.py`)
```
FAILED tests/test_051_finite_inputs.py::test_concentration_gate_fails_closed[prices4-qty4-kwargs4-refused4]
FAILED tests/test_051_finite_inputs.py::test_concentration_gate_fails_closed[prices5-qty5-kwargs5-refused5]
25 failed, 3 passed in 0.18s
```

## Fixes (`scripts/mode_config.py`)
- `load_profiles`: `state_dir` compared after separator, `.`/`..` and case normalization, and a
  directory nested in another profile's is refused; `log_namespace` compared case-insensitively.
- `bot_budget_usd` must be finite (infinity passed `> 0`).
- `bound_buys`: non-finite `settled_cash`/`deployed_today_usd`/`min_notional_usd` raise; negative
  `deployed_today_usd` raises (it used to enlarge the remaining daily cap).
- `sizing_equity`: non-finite inputs raise (`min(budget, NaN)` returned the full budget).
- `bot_sell_quantities`: a non-finite target raises (`max(0, NaN)` read as 0 → full liquidation).
- `concentration_refusals`: fails closed — missing/NaN/non-positive price or NaN quantity refuses that
  ticker; invalid portfolio value or limit refuses every ticker. Previously NaN compared False and
  passed; a missing price raised KeyError.

- Follow-up from Codex's independent Windows review (2026-10-08): `state_dir` must be relative and
  stay inside the repo — absolute, drive-letter, UNC and `..`-escaping paths are refused, since
  `state/x` and `/abs/.../state/x` can name the same directory and no base is known at load time.

- Second Codex follow-up: `state_dir='.'` (or anything normalizing to the repo root) contained
  every other profile's state and passed. Red on 63e2098: `.`, `./`, `state/..` loaded beside
  `state/paper_large`. Now refused; the causal control loads the identical pair with a sibling dir.

- Third Codex follow-up (2026-10-09): distinct `state_dir`s passed while `log_namespace=
  'paper_small/../paper_large'` made T007's `state_paths` resolve to `paper_large`'s gate DB and run
  log. `name` and `log_namespace` must now be portable storage identifiers (`[a-z0-9][a-z0-9_-]{0,62}`,
  one path component, not a Windows device name). Red on c109fe3: 16 of 16 new cases failed. The
  consuming `state_paths` refusal lives on #107 (it doesn't exist on this branch's base).

## Rule 12
`python tests/mutation/run_051_finite_inputs_mutants.py` → 13/13 killed (the case-fold namespace mutant is retired as equivalent: identifiers are lowercase-only).
