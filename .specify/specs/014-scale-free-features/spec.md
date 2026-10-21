# Feature Specification: Scale-Free Features and Fold-Fit Standardization

Historical figures are [struck]; their original result artifacts are unavailable. [Backfill record](../../../docs/trials/backfill/manifest.json) provides counts only, not returns; [archival audit](../../../docs/audit-2026-09-12/AUDIT.md) is not results provenance. Operating requirements and historical task states below are preserved.

**Feature Branch**: `014-scale-free-features`

**Created**: 2026-09-06

**Status**: Draft

**Input**: The quoted Phase 3 outcomes are [struck]; original result artifacts
are unavailable. Two earlier places in this repository described the feature-design
concern and deferred it — `features.py:25-28`
("These are price *levels*, not ratios, which is a real weakness for a linear
model and a blocker for any pooled cross-sectional model") and
`.specify/specs/009-selectable-target/spec.md:238-242`, which called it "a
separate change with its own effect on results" that "does not belong in the
same PR as a new target". That change is this spec. It is sequenced ahead of
012 and 013, both of which are on hold: a cost-aware entry rule built on
these predictions, or a five-ticker table comparing four flavours of unverified outcomes, would spend real work on a design matrix requiring a separate conditioning check.

**Owns / must not know about** (per CLAUDE.md's module table): `features.py`
keeps owning feature construction and gains a feature-set selector;
`estimators.py` keeps owning model declaration and gains a standardization
flag. Two new diagnostic entry points, `scripts/feature_diagnostics.py` and
`scripts/feature_set_comparison.py`, sit *above* the signal and model layers:
they import `data`, `features`, `estimators` and `model_cv`, and neither
knows anything of fills, positions, or P&L. No metric either one prints is a
return. `logistic_baseline.py` is not touched at all.

---

## Background

`features.FEATURE_COLUMNS` listed five columns, three of which were price and
volume *levels*: `Short_SMA`, `Long_SMA`, `Volume`. That is two distinct
defects, and conflating them is why "add a `StandardScaler`" looked like a
sufficient fix.

**Defect 1 — non-stationarity.** A level drifts with the history. A
walk-forward fold trained on $50 bars predicts $200 bars by extrapolating
outside its own training support, and every later fold is worse than the
first by construction. No amount of standardization helps: a scaler fitted on
the training rows maps the *test* rows to z-scores far outside the range the
model ever saw, which is the same extrapolation wearing different units.

**Defect 2 — collinearity.** Historical AAPL correlation, condition-number
and VIF figures are [struck]. The mechanical concern is **scale-invariant**:
standardization is a diagonal transform and cannot change a correlation.
The conventional condition-number reference of 30 is not an observed result.

Only a change of *feature* fixes either one. The scaler is still worth having,
for a third and smaller reason: `Log_Return` (~0.01) and `Volume` (~10⁷) differ
by six orders of magnitude, so a single ridge `alpha` or logistic `C` is
really asking "how much to penalize whichever column happens to be largest".
That is a real defect and standardization is exactly its fix — it is simply
not the defect that was reported.

---

## Design constraint — a decomposition, not two views of the same thing

The obvious scale-free replacement for the two SMA columns is to divide each
by the price: `Short_SMA/Close` and `Long_SMA/Close`. That is scale-free and
still collinear, because the two averages remain nearly the same series.

The less obvious trap is subtler, and this spec fell into it during
implementation before the tests caught it. Replacing the pair with
"crossover spread" plus "price against the long trend" —
`Short/Long - 1` and `Close/Long - 1` — can remain collinear; its historical measured
correlation is [struck]. The algebraic dependence is

```
Close/Long  ==  (Close/Short) * (Short/Long)
```

so "price against the long average" is the product of the crossover spread
and something else. Including it alongside the spread re-measures the spread.

The correct split is the two legs of that identity: a **fast** leg
(`Close/Short - 1`, price against its short average) and a **slow** leg
(`Short/Long - 1`, short average against long). Their product recovers the
long-trend quantity exactly, so nothing is lost. The historical fixture
correlations are [struck]; FR-005 and SC-002 still define the required bounds.

This is why FR-005 is stated pairwise and asserted pairwise. A whole-matrix
condition number improves under the wrong split too — the units get fixed
either way — so it cannot distinguish the two designs, and an aggregate-only
test would have shipped the collinear one.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A model is trained on features that do not drift (Priority: P1)

An agent builds features for a ten-year history and fits any registered
estimator per walk-forward fold. Every feature is a ratio, so the values a
late fold predicts on lie in the same range as the values an early fold
trained on. Nothing extrapolates.

**Acceptance:** multiplying every price and volume in the input by a constant
leaves every scale-free feature bit-for-bit unchanged, and leaves the level
features changed.

### User Story 2 - A penalized linear model is standardized without leaking (Priority: P1)

`build_estimator` returns a `Pipeline` for the two linear entries, so the
scaler is fitted wherever the estimator is fitted — which is per fold, at
every one of the three fit sites, with no change at any call site.

**Acceptance:** the fitted scaler's `mean_` equals the fold's *training*
slice's column means, differs from the whole frame's, and differs between the
first and last fold.

### User Story 3 - The committed control result does not move (Priority: P1)

`docs/PROJECT_CONTEXT.md` quotes an AAPL result from `logistic_baseline.py`.
Every Phase 3 comparison is measured against it. Spec 014 changes two
defaults at once — the feature set and, for `logistic`, standardization — and
either one silently applied to the control would move the goalpost without
anything saying so.

**Acceptance:** the equivalence tests still pass element-for-element, and
they now say `feature_set="levels", scale=False` explicitly rather than
depending on the defaults staying put.

### User Story 4 - The improvement is measured, not asserted (Priority: P1)

Better conditioning is a property of the matrix. It is not evidence that any
prediction improved. Camden runs two scripts on real cached data and pastes
both outputs into the PR.

**Acceptance:** all four registry entries are paired-tested under both
feature sets and all four p-values are reported, whatever they say.

### Edge Cases

- **A halted ticker.** A zero trailing-mean volume makes `Rel_Volume`
  infinite. No estimator raises on an infinity and every estimator is wrecked
  by one, so it must become `NaN` and be dropped.
- **A `volume_window` longer than `long_window`.** Its warm-up is a leading
  run of `NaN`, removed by the existing completeness drop; no wider slice is
  needed and adding one would change the level path.
- **A `feature_set` that is not registered.** Raises, naming the valid sets.
  There is no fallback, for the reason `estimators.get_spec` gives.
- **An outer fold whose two feature sets cover different dates.** The warm-up
  lengths differ, so the coverage sets differ; the paired test must
  intersect on `Date` rather than assume a shared row offset.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `features.py` MUST declare the feature sets by name —
  `LEVEL_FEATURE_COLUMNS` and `SCALE_FREE_FEATURE_COLUMNS`, exposed through
  `FEATURE_SETS` and a `feature_columns(feature_set)` accessor that returns a
  copy and raises `ValueError` naming the registered sets for an unknown one.
- **FR-002** *(the point of the spec)*: every column of the scale-free set
  MUST be invariant to a change of price and volume units.
- **FR-003**: the three derived columns MUST be `SMA_Spread =
  Short_SMA/Long_SMA - 1`, `Close_To_Short = Close/Short_SMA - 1`, and
  `Rel_Volume = Volume / Volume.rolling(volume_window).mean()`. All three
  MUST be computed whichever set is selected, so one frame can be diagnosed
  under both.
- **FR-004** *(Rule 1)*: every feature at row `t` MUST be computable from
  data at or before `t`. The three ratios divide same-row quantities and add
  no new time dependency; `Rel_Volume`'s window is trailing.
- **FR-005**: `SMA_Spread` and `Close_To_Short` MUST each have a VIF below 5
  against the rest of the set, and MUST correlate below 0.5 in absolute value
  with each other. This is asserted **pairwise and by name**, not only
  through the aggregate condition number — see *Design constraint* for why an
  aggregate test cannot distinguish the correct split from the collinear one.
- **FR-006**: a non-finite ratio MUST become `NaN` so the existing
  completeness drop removes the row. It MUST NOT reach an estimator.
- **FR-007** *(Rule 2)*: standardization MUST be fitted on each fold's
  training rows alone. Wrapping the estimator in a `Pipeline` achieves this at
  all three fit sites (`estimators.py`'s loop, and `model_cv.py`'s inner and
  outer fits) with no change at any call site.
- **FR-008**: `EstimatorSpec` MUST carry a `scale` flag, `True` for
  `("logistic", classification)` and `("ridge", regression)` and `False` for
  both `hgb` entries. `build_estimator`, `fit_predict_walk_forward`,
  `tune_on_fold` and `nested_walk_forward` MUST accept `scale: bool | None`
  overriding it, defaulting to the registry's answer.
- **FR-009**: parameter grids MUST keep plain names (`{"alpha": ...}`, not
  `{"model__alpha": ...}`). Params are applied to the estimator before it is
  wrapped. A registry entry describes its model, not the plumbing around it.
- **FR-010**: `scale` MUST be forwarded to both the tuner and the outer fit.
  Passing it to one and not the other would tune one model and report
  another.
- **FR-011** *(the control)*: the `logistic_baseline` equivalence tests MUST
  still pass element-for-element, and MUST pin `feature_set="levels"` and
  `scale=False` explicitly rather than relying on defaults.
- **FR-012** *(mandatory evidence, not optional)*: a new
  `scripts/feature_set_comparison.py` MUST run `nested_walk_forward` for all
  four registry entries under both feature sets on real cached data and
  paired-test the results — **McNemar** (`statsmodels.stats.contingency_
  tables.mcnemar`) on correct/incorrect outcomes for the two classification
  entries, **Wilcoxon signed-rank** (`scipy.stats.wilcoxon`) on per-bar
  squared-error differences for the two regression entries. It MUST report
  all four p-values. Its output is a merge requirement, alongside
  `feature_diagnostics.py`'s condition-number and VIF table.
- **FR-013** *(what FR-012's bar means)*: `p < 0.10` one-sided on at least
  one entry is the threshold for "spec 014 shows real improvement, not just
  better conditioning". The spec MUST state, in the script and in the PR,
  that this is a **screening** threshold — cheap evidence, four comparisons,
  one ticker — and **not** the project's capital-readiness bar, which is the
  deflated Sharpe step and comes later. A null result still merges; it rules
  out claiming 014 as evidence about the model, not the conditioning fix
  itself.
- **FR-014** *(Rule 6)*: no new dependency. `scikit-learn==1.9.0`,
  `scipy==1.16.2` and `statsmodels==0.14.6` are already in
  `requirements.txt`; `sklearn.pipeline` and `sklearn.preprocessing` are new
  imports of an existing package.
- **FR-015** *(Rule 10)*: no `git` is run. This is a local session, not the
  Actions lane, so the amended Rule 10 exception does not apply. Camden
  commits.

### Key Entities

- **Feature set** — a named list of column names. Two are registered:
  `levels` (the control, identical to `logistic_baseline.FEATURE_COLUMNS`)
  and `scale_free` (the default).
- **`EstimatorSpec.scale`** — a property of the model *family*, not of the
  caller. A penalized linear model shares one penalty across columns and so
  depends on their units; a tree splits each column independently and cannot
  tell.
- **A paired comparison** — two prediction series over the same trading days,
  under the same splits and seed, differing only in the feature matrix.

---

## Success Criteria *(mandatory)*

- **SC-001**: multiplying every price by 10 and every volume by 1000 leaves
  all five scale-free columns unchanged to 1e-9 relative, and leaves
  `Short_SMA`, `Long_SMA` and `Volume` changed.
- **SC-002**: on the test fixture, `VIF(SMA_Spread) < 5`,
  `VIF(Close_To_Short) < 5`, and `|corr(SMA_Spread, Close_To_Short)| < 0.5`,
  while the `Short_SMA`/`Long_SMA` pair they replace correlates above 0.9.
- **SC-003**: the standardized condition number of the scale-free matrix is
  less than half the level matrix's, and maximum VIF drops.
- **SC-004**: for every fold, the fitted scaler's `mean_` equals that fold's
  training slice's column means; it differs from the whole frame's, and the
  first and last folds' differ from each other.
- **SC-005**: `scale=True` and `scale=False` produce different ridge
  predictions on the level set (standardization is not ceremony), and
  identical `hgb` predictions (which is why the tree entries decline it).
- **SC-006**: the `logistic_baseline` equivalence tests pass element-for-
  element under `feature_set="levels", scale=False`.
- **SC-007**: `feature_set_comparison.py` reports four p-values on real
  cached AAPL data, and the PR carries them beside the fold geometry — fold
  count, purge length, embargo length — that CLAUDE.md requires of any
  reported metric.
- **SC-008** *(mutation check)*: each of these six injected defects MUST fail
  the suite. Historical run outcomes and failure counts are [struck]:

  | # | Injected defect | Failures |
  |---|---|---|
  | 1 | drop the `- 1` from `SMA_Spread` | [struck] |
  | 2 | define `Close_To_Short` against `Long_SMA` (the long-average collinearity trap) | [struck] |
  | 3 | shift `Rel_Volume`'s trailing window forward one bar | [struck] |
  | 4 | default `feature_set` back to `"levels"` | [struck] |
  | 5 | fit the model on the whole frame instead of the fold (so the scaler is fitted on it too) | [struck] |
  | 6 | forward `scale` to the outer fit but not the tuner | [struck] |

  Defect 6 initially passed. The gap was real, not a mutation-harness
  artifact: no test compared what the tuner built against what the outer
  fold fitted. `TestScaleReachesEveryFit` was added for it, and records the
  `scale` every `build_estimator` call receives rather than comparing
  outputs — forwarding to one site and not the other changes predictions
  only slightly and only sometimes, which is precisely what an output
  comparison misses.

---

## Assumptions

- **`volume_window` defaults to `long_window` and is not independently
  tuned.** This is a deliberate deferral, not a claim that the two windows
  should be equal — volume mean-reversion has no reason to share a timescale
  with a price trend. It is named here rather than left implicit because this
  codebase's existing pattern is to name feature-scaling deferrals out loud
  (`features.py:25-28`, `009/spec.md:238-242`), and that pattern is the only
  reason the present defect was findable at all. **Revisit trigger:** spec
  013's multi-ticker run, where one window across five tickers is a stronger
  assumption than across one, or a dedicated feature-tuning spec — whichever
  comes first.
- **Neither `hgb` entry is standardized.** A split threshold is chosen per
  column, so a monotone rescaling moves the threshold and leaves the
  partition — and every prediction — identical. SC-005 asserts this rather
  than assuming it; if it ever failed, the registry entries would need
  revisiting rather than the test relaxing.
- **The level set survives as the control, not as a fallback.** It is what
  the committed AAPL result was computed on and what spec 013's comparison
  will report against. It is not an option a caller should reach for
  otherwise.
- **`Log_Return` and `Close_To_Short` share their most recent bar.** Their
  quoted historical correlation is [struck]. FR-005 still governs its named
  feature pair; the requirement is not weakened by removing an unsourced figure.
- **The screening threshold is not a significance claim about the strategy.**
  See FR-013. Four comparisons on one ticker at p < 0.10 is a screen; the
  deflated Sharpe step is the bar that matters, and it is not this spec.
