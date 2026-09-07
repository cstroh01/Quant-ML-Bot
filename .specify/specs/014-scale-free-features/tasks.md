# Tasks — 014 Scale-Free Features and Fold-Fit Standardization

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — The feature sets

- [x] **T001** `LEVEL_FEATURE_COLUMNS` and `SCALE_FREE_FEATURE_COLUMNS` as
  named constants, plus `FEATURE_SETS` and `DEFAULT_FEATURE_SET`. The level
  list stays identical to `logistic_baseline.FEATURE_COLUMNS`, in its order.
  (FR-001)
- [x] **T002** `feature_columns(feature_set)` — returns a copy; raises
  `ValueError` naming the registered sets. Same shape as
  `estimators.get_spec`, for the same reason. (FR-001)
- [x] **T003** Remove `features.FEATURE_COLUMNS`. Not repointed at the new
  default — the name meant the level set, and a silent change of meaning is
  the failure this spec is correcting. The compile-time break is intended.
  (FR-001)
- [x] **T004** The three derived columns: `SMA_Spread`, `Close_To_Short`,
  `Rel_Volume`. Computed unconditionally, whichever set is selected.
  (FR-003)
- [x] **T005** `volume_window` argument, defaulting to `long_window`;
  rejects values below 1. (FR-003)
- [x] **T006** Non-finite guard: `±inf` from a zero denominator becomes
  `NaN` before the completeness drop. (FR-006)
- [x] **T007** `build_features(feature_set=...)` judges the completeness drop
  against the *selected* set only — which is what preserves the level path
  row for row. (FR-001, FR-011)

## Phase 2 — Standardization in the registry

- [x] **T008** `EstimatorSpec.scale: bool = False`; `True` on the two linear
  entries, `False` on both `hgb` entries, each with the reason in a comment.
  (FR-008)
- [x] **T009** `SCALER_STEP` / `MODEL_STEP` constants, and `build_estimator`
  wrapping in `Pipeline` when scaling applies. Params applied to the
  estimator *before* wrapping, so grids keep plain names. (FR-007, FR-009)
- [x] **T010** `scale: bool | None = None` override on `build_estimator` —
  `None` means the registry's answer. (FR-008)
- [x] **T011** `final_estimator()` and `fitted_scaler()` accessors, so no
  caller grows its own `isinstance` branch. (FR-008)
- [x] **T012** `scale` threaded through `fit_predict_walk_forward`. (FR-008)
- [x] **T013** `scale` threaded through `tune_on_fold` **and**
  `nested_walk_forward`, and forwarded from the latter to both the tuner and
  the outer fit. (FR-010)

## Phase 3 — Diagnostics

- [x] **T014** `scripts/feature_diagnostics.py` — `standardized_matrix`,
  `condition_number`, `variance_inflation_factors` (from the pseudo-inverted
  correlation matrix, no `statsmodels` needed), `correlation_frame`,
  `max_abs_offdiagonal_correlation`, `diagnose`, `format_report`, `main`.
- [x] **T015** `[P]` `scripts/feature_set_comparison.py` — per-entry runs
  under both sets, `Date`-aligned pairing, McNemar for classification,
  Wilcoxon signed-rank for regression, all four p-values reported, screening
  threshold stated as such. (FR-012, FR-013)
- [x] **T016** Both scripts request the five-ticker universe so they hit the
  existing `AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv` cache rather than triggering a
  download.

## Phase 4 — Preserving the control

- [x] **T017** `tests/test_targets.py` — the `FEATURE_COLUMNS` equality
  assertion is repointed at `LEVEL_FEATURE_COLUMNS`, not deleted; the
  frame-equality test passes `feature_set="levels"`. (FR-011)
- [x] **T018** `tests/test_estimators.py` — the two equivalence tests and the
  pinned-construction test pass `scale=False` explicitly. (FR-011)
- [x] **T019** `tests/test_model_cv.py` — the equivalence fixture is built
  with `feature_set="levels"` and every call in that class passes
  `scale=False`; the class docstring says why. (FR-011)
- [x] **T020** Attribute reads on a possibly-wrapped model go through
  `final_estimator`. (FR-008)

## Phase 5 — Tests (Rule 5)

- [x] **T021** `TestScaleInvariance` — prices ×10, volumes ×1000; scale-free
  unchanged, levels changed. Both halves, because the second is what makes
  the first mean anything. (SC-001)
- [x] **T022** `TestCollinearity` — **pairwise and by name**: VIF < 5 for
  each of the two ratios, `|corr| < 0.5` between them, and a control
  assertion that the pair they replace correlates above 0.9. This is the
  class that caught the `Close_To_Long` near-miss. (SC-002)
- [x] **T023** `TestConditioning` — condition number and max VIF as
  inequalities with a margin, never pinned constants. (SC-003)
- [x] **T024** `TestPointInTimeCorrectness` — a future close and a future
  volume perturbed *separately*; `Rel_Volume` has its own window and its own
  way to leak. (Rule 1, FR-004)
- [x] **T025** `TestScalerIsFitOnTrainingRowsOnly` — statistics match the
  training slice, differ from the whole frame, and differ between first and
  last fold. (SC-004, Rule 2)
- [x] **T026** `TestScalingChangesTheAnswer` — ridge predictions move,
  `hgb` predictions do not. The second is the registry's `scale=False`
  justification, asserted rather than assumed. (SC-005)
- [x] **T027** `TestRegistryScaling` — which entries wrap, the override in
  both directions, and that grids keep plain parameter names. (FR-008,
  FR-009)
- [x] **T028** `TestNonFiniteGuard` — zero-volume rows dropped from the
  scale-free path and *kept* in the level path, so the drop is shown to be
  the ratio's doing rather than a blanket filter. (FR-006)
- [x] **T029** `TestRatioDefinitions` — each ratio is what it claims, plus
  `test_the_decomposition_closes`: `(1+Close_To_Short)(1+SMA_Spread) ==
  Close/Long_SMA` exactly. That identity is the argument for the design, so
  it is asserted, not just written down. (FR-003)
- [x] **T030** `TestScaleReachesEveryFit` — records the `scale` every
  `build_estimator` call receives and asserts they all agree. Written
  *because* the SC-008 mutation run found the gap: the suite passed with
  `scale` forwarded to the outer fit and not the tuner. An output
  comparison would not have caught it. (FR-010)
- [x] **T030b** Full suite green: 256 → 295 tests, no network, no new
  test dependency.

## Phase 6 — Evidence and record (outside the agent lane where noted)

- [x] **T031** Run `feature_diagnostics.py` on cached 10y AAPL. Result:
  condition number 36.17 → 2.15, max VIF 268.31 → 1.60, largest
  |correlation| 0.998 → 0.527.
- [ ] **T032** Run `feature_set_comparison.py` on the same data and record
  all four p-values. **Merge requirement** (FR-012), not optional.
- [x] **T033** `docs/PROJECT_CONTEXT.md` — record 011 as done (it is
  code-complete on disk but still listed pending), add 014 with the
  measured table, and record 012/013 as deliberately held until 014 lands.
- [ ] **T034** PR description carries: the spec number; what changed and why
  it is correct; the fold geometry beside every metric (fold count, purge
  length, embargo length — with an explicit note that commission and
  slippage are not applicable because nothing here is a backtest); the
  paired level-set control; and the Rule 6 line, which is that no dependency
  was added.
