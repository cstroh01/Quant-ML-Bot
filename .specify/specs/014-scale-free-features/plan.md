# Implementation Plan — 014 Scale-Free Features and Fold-Fit Standardization

**Spec**: `.specify/specs/014-scale-free-features/spec.md`

---

## Scope

- `scripts/features.py` — **modified**. Two named feature sets, a
  `feature_columns()` accessor, three derived ratio columns, a
  `volume_window` argument, and the non-finite guard (FR-001 – FR-006).
- `scripts/estimators.py` — **modified**. `EstimatorSpec.scale`, the
  `Pipeline` wrapping in `build_estimator`, the `scale` override on
  `fit_predict_walk_forward`, and the `final_estimator` / `fitted_scaler`
  accessors (FR-007 – FR-009).
- `scripts/model_cv.py` — **modified**. `scale` threaded through
  `tune_on_fold` and `nested_walk_forward` to both fit sites (FR-010).
- `scripts/feature_diagnostics.py` — **new**. Correlation, VIF, condition
  number; a levels-vs-scale_free report.
- `scripts/feature_set_comparison.py` — **new**. The FR-012 paired
  significance tests.
- `tests/test_feature_scaling.py` — **new**. 39 tests (SC-001 – SC-005,
  SC-008).
- `tests/test_targets.py`, `tests/test_estimators.py`,
  `tests/test_model_cv.py` — **modified**. The equivalence tests pin
  `feature_set="levels"` and `scale=False` (FR-011, SC-006).
- `docs/PROJECT_CONTEXT.md` — **modified**. 011 recorded as done, 014 added,
  012/013 recorded as held.

Explicitly **not** touched: `logistic_baseline.py` (the frozen control, spec
009 FR-011), `signals.py`, `walk_forward_cv.py`, `backtest_harness.py`,
`data.py`, `targets.py`, `plotting.py`.

**No new dependency** (FR-014). `sklearn.pipeline` and `sklearn.preprocessing`
are new imports of `scikit-learn==1.9.0`, already at `requirements.txt:24`.
`scipy==1.16.2` and `statsmodels==0.14.6` are already listed and were already
installed; the two diagnostic scripts are their first use in this repository.

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 1 — Point-in-time correctness | Three new columns, all trailing-window or same-row ratios. Two tests perturb a future close and a future volume separately and assert no earlier feature moves — separately, because `Rel_Volume` has its own window and its own way to leak. |
| 2 — Purge/embargo | Not re-established, but newly *at risk*: a scaler is a fitted object, and one fitted on the whole frame would leak every test window's mean into every fold. The `Pipeline` makes the scaler fit wherever the estimator fits, which is per fold. Three tests assert the statistics are the training slice's, differ from the frame's, and differ between folds. |
| 3 — Costs | Not applicable. Nothing in this spec computes a return, a Sharpe, or a P&L. `feature_set_comparison.py` says so in its own report rather than printing a commission line that would imply otherwise. |
| 4 — Baselines | The comparison's baseline is the level feature set, run over identical bars with identical splits and seed — a paired control, which is stronger than the unpaired kind for this question. Buy-and-hold and random-signal baselines belong to spec 013's runner and are not displaced. |
| 5 — Tests | 39 new tests; the suite goes 256 → 295, all passing. The pairwise-collinearity class (SC-002) earned its keep during implementation: it caught a `Close_To_Long` definition that passed every other test and still correlated 0.865. |
| 6 — Dependencies | None added. The PR's Rule 6 line is that there is no line. |
| 8 — Layer separation | `features.py` still imports only `signals` and `targets`. `estimators.py`'s AST import-set assertion still holds — `sklearn.pipeline` and `sklearn.preprocessing` both collapse to the top-level name `sklearn`, so `tests/test_estimators.py:496` needed no change. The two new scripts are entry points above the layers, not new layers. |
| 9 — The merge gate | Three modified modules, two new scripts, one new test file. The two things to check twice are in **Design** below: why the `Pipeline` is leakage-safe for free, and why `Close_To_Short` rather than the more natural-sounding `Close_To_Long`. |
| 10 — Version control | No `git` run at all. Local session, not the Actions lane, so the amended Rule 10 exception does not apply. Camden commits. |

---

## Design

### Why the `Pipeline` is leakage-safe without touching a call site

There are exactly three places a model is fitted in live code:
`estimators.py`'s walk-forward loop, and `model_cv.py`'s inner-tuning and
outer fits. All three already build a fresh estimator per fold and call
`.fit` on that fold's training slice — that is what Rule 2 required of them
before this spec.

A `Pipeline` is fitted by the same `.fit` call. So making `build_estimator`
return `Pipeline([("scaler", StandardScaler()), ("model", estimator)])`
inherits the per-fold discipline the three sites already had, and none of
them changes. The alternative — standardizing the frame up front, or fitting
a scaler beside the loop — would have required getting the same argument
right three times.

Two consequences worth stating:

- `_predict_for_scoring` reads `model.classes_`. A `Pipeline` forwards
  `classes_` and `predict_proba` from its final step, so it needed no change.
- Anything reading a fitted attribute (`coef_`, `alpha`) now needs to know
  whether it holds a bare estimator or a pipeline. Rather than let seven call
  sites each grow an `isinstance` branch, `estimators.py` exposes
  `final_estimator(model)` and `fitted_scaler(model)`, with the step names as
  module constants.

### Why `Close_To_Short` and not `Close_To_Long`

This is the part to check twice, because the wrong answer looks right.

`Close/Long == (Close/Short) * (Short/Long)`. So a feature set containing
both the crossover spread (`Short/Long - 1`) and price-against-long-trend
(`Close/Long - 1`) contains one quantity and its own product with another —
they measured 0.865 correlated on the spec's fixture, which is a long way
past the FR-005 bound of 0.5.

Taking the two *legs* of that identity instead — `Close/Short - 1` (fast) and
`Short/Long - 1` (slow) — loses nothing, because their product recovers the
long-trend quantity exactly, and measured 0.325 on the same fixture.

The first implementation of this spec used `Close_To_Long`. Every
scale-invariance test passed, the condition number improved 9x, and the
collinearity was still there. Only the pairwise assertions in
`TestCollinearity` caught it. That is the argument for FR-005 being stated
pairwise rather than as a condition-number threshold, and the reason the
class carries a docstring recording the near-miss.

### Why the level set stays

Deleting it would have been simpler. It stays for two reasons: it is what the
committed AAPL result in `docs/PROJECT_CONTEXT.md` was computed on, so the
equivalence tests need it to keep passing; and FR-012's paired comparison
needs both sets runnable over the same bars, which is the whole design of the
evidence step. A one-off script that reconstructed the old columns would have
worked for neither.

`features.FEATURE_COLUMNS` is **removed** rather than repointed at the new
default. The name meant the level set and would now mean the scale-free one;
leaving it would change what existing code computes without changing what it
says, which is precisely the failure this spec exists to correct. The
compile-time break is the point.

### Where the drop is judged

`build_features` computes all eight feature columns whichever set is
selected, and judges the row-completeness drop against the *selected* set
only. Both halves matter:

- Computing both is what lets `feature_diagnostics.py` and
  `feature_set_comparison.py` diagnose one frame under both sets.
- Dropping on the selected set only is what keeps `feature_set="levels"`
  reproducing `logistic_baseline.build_features` row for row. Dropping on the
  union would discard `Rel_Volume`'s extra warm-up rows from the level path
  too, and move the committed control.

### Measured outcome (10y AAPL, cached)

| | levels | scale_free |
|---|---|---|
| standardized condition number | 36.17 | 2.15 |
| max VIF | 268.31 | 1.60 |
| largest \|correlation\| | 0.998 (`Short_SMA`/`Long_SMA`) | 0.527 (`Log_Return`/`Close_To_Short`) |

36.17 is above the conventional ill-conditioning line of 30, which is the
independent confirmation of the reported defect. The FR-012 significance
results are a separate artifact and go in the PR beside this table.
