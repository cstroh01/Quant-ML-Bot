# 053 F02: fold-local tests pin fit rows and the embargo gap

Source: Codex cross-review 2026-10-08 (fold-mutant-survivors.json, private folder): two FR-002
mutants survived all four 053 fold tests on main. Synthetic data only. EXAMPLE — NOT A RESULT.

No production code changed. Tests added to `tests/test_053_fold_local.py`:

- `test_model_is_fit_on_exactly_the_folds_training_rows` — a `LogisticRegression` subclass records
  the rows each `fit` sees (y's index); every fit must equal that fold's reported training rows,
  share none with its test rows, and end before the test window.
- `test_each_embargo_gap_stays_out_of_every_later_folds_training` — for every test window, the
  `embargo` rows after it are absent from every later fold's training set, and the next row is
  present (gap is exactly `embargo`, not longer).

## Rule 12 (`python tests/mutation/run_053_fold_local_mutants.py` → 3/3 killed)

| Mutant | Old 4 tests | New 2 tests alone |
|---|---|---|
| embargo passed as `embargo_bars - 1` | 4 passed (survived) | 1 failed (killed) |
| fit on train+test | killed in this form | 1 failed (killed) |
| scaler refit on all data | killed | — |
