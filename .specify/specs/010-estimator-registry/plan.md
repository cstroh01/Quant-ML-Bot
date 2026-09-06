# Implementation Plan — 010 Estimator Registry

**Spec**: `.specify/specs/010-estimator-registry/spec.md`

---

## Scope

- `scripts/estimators.py` — **new**. Registry + `build_estimator` +
  `param_grid_points` + `fit_predict_walk_forward` (FR-001 – FR-008)
- `tests/test_estimators.py` — **new** (FR-013)

Explicitly **not** touched: `logistic_baseline.py` (FR-011),
`walk_forward_cv.py`, `features.py`, `targets.py`, `metrics.py`,
`backtest_harness.py`, `signals.py`.

**No new dependency.** `HistGradientBoosting*` and `Ridge` both ship with the
scikit-learn already imported at `logistic_baseline.py:5`.

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 1 — Point-in-time correctness | Inherited rather than re-established: this module consumes a frame `features.build_features` already made causal, and never constructs a column. |
| 2 — Purge/embargo | `fit_predict_walk_forward` fits **one estimator per fold** via `walk_forward_splits` and never once on the whole frame. Asserted structurally (`test_one_estimator_is_constructed_per_fold`) rather than only by output, for the reason in *Test defects* below. The per-fold `train_dates.max() < test_dates.min()` assertion from `logistic_baseline.py` is carried over verbatim. |
| 4 — Baselines | Not yet. This spec produces predictions; grading them against buy-and-hold and a random signal is spec 013. |
| 5 — Tests | 30 tests, plus an 8-defect mutation check. |
| 6 — Dependencies | None added — the Rule 6 line for the PR is that scikit-learn is already a dependency and gradient boosting adds no package. |
| 8 — Layer separation | Asserted by AST import-set comparison, not by convention or a source grep. |
| 9 — The merge gate | Two files. The only subtle piece is the `params=None` / `default_params` contract, explained below. |
| 10 — Version control | No `git` run beyond read-only status/diff checks to confirm `logistic_baseline.py` is untouched. Camden commits. |

---

## Design

### Why gradient boosting is here and not deferred

The first draft of this spec deferred `hgb` to "a later spec." That left the
first of Camden's five Phase 3 features owned by no spec at all. Adding it as
a registry entry costs the fit/predict loop nothing — no branch, no special
case — which is the entire argument for having built a registry. If adding
the second model family had required touching the loop, the registry would
have failed at its one job.

`HistGradientBoosting*` rather than LightGBM or XGBoost because Rule 6 wants
a line on what a new dependency does that existing ones cannot, and here
there is nothing to say yet. That line becomes writable only when there is a
result showing scikit-learn's implementation is the binding constraint.

### `params=None` means `default_params`, not `{}`

This is the one contract in the module a reviewer should check twice, and it
is the one my own tests initially failed to pin (see below). An empty dict
silently accepts scikit-learn's defaults; `default_params` is what this
registry declares, tests, and hands spec 011 as its no-inner-folds fallback.
The two agree today for `logistic` (`C=1.0`) and `ridge` (`alpha=1.0`) purely
because scikit-learn's defaults happen to match — and that coincidence is
exactly what makes the distinction easy to lose.

### The registry key is `(name, task)`, not `task`

Keyed on task alone, "which model" would not be expressible, and `hgb` could
not exist for both tasks. Keyed on name alone, asking for `logistic` on a
regression target would hand back a classifier and fail deep inside `.fit`
with a message about continuous labels rather than at the lookup with a
message about the registry. Both wrong-key cases have a test.

### `default_params` must be a grid point

Asserted by test (FR-009). Spec 011 falls back to `default_params` when an
outer fold supports no inner folds; if that value were not in the grid, the
fallback would land on a configuration nothing else ever exercises — and the
early folds are exactly where a fallback is most likely, so it would be a
silently-untested path on the most fragile data.

### Grid sizes

Four points each, capped at eight and enforced by `param_grid_points` itself
rather than by comment. Spec 011 fits one model per grid point per inner fold
per outer fold, so this number multiplies three times over. The grids are not
claimed to be well-chosen; they are a starting point to select over, and
revising them belongs with a real result.

---

## Verification — as run

```powershell
./venv/Scripts/python.exe -m unittest discover -s tests
```

**Result: 210 tests, OK.** Suite was 180 after spec 009; 30 added here.

`scripts/logistic_baseline.py` confirmed unmodified via `git status` /
`git diff --stat` (read-only; FR-011).

### Mutation check

Eight deliberate defects injected into `estimators.py`:

| Injected defect | Result |
|---|---|
| Swap the `logistic` and `ridge` factories | **FAILED** (10 errors) |
| `random_state` not forwarded (hardcoded `0`) | **FAILED** (5 failures) |
| Classification filler becomes `NaN`/`float64` | **FAILED** (2 failures) |
| `params=None` means `{}` instead of `default_params` | **FAILED** (2 failures) |
| Fit once on fold 1, reuse for every later fold | **FAILED** (1 failure) |
| `params` accepted then ignored | **FAILED** (3 failures) |
| Grid key order unsorted (non-deterministic points) | **FAILED** (1 failure) |
| Zero-fold guard removed | **FAILED** (1 failure) |

### Two test defects found by that check, and fixed

Both are recorded because both would have produced a green suite proving less
than it appeared to. The first mutation run caught only 3 of 5 defects.

1. **`params=None` → `{}` survived.** The test compared `ridge`'s built
   `alpha` against `1.0`, which is *also* scikit-learn's own default — so an
   implementation ignoring `default_params` entirely passed. Fixed by
   asserting every entry's built estimator against its own declared
   `default_params`; `hgb`'s `max_depth=3` differs from scikit-learn's
   `None`, which is what gives the assertion teeth.

2. **"Fit once, reuse across folds" survived** — the Rule 2-adjacent defect,
   and the more serious miss. `_synthetic_features` (reused from
   `test_logistic_baseline.py`) pairs random features with alternating
   labels, so nothing is learnable and every fold predicts the same constant.
   The equivalence test was passing *vacuously*: it would have matched a
   fit-once implementation just as well. Fixed with two structural tests — a
   spy counting one `build_estimator` call per fold, and a check on a
   learnable frame that the first and last fold genuinely fit different
   coefficients, which also guards the fixture itself from silently becoming
   non-discriminating.

   This is worth carrying into spec 011: an output-equality test against
   `logistic_baseline` on that fixture is weaker evidence than it looks, and
   011's own equivalence test (FR-011) should not be relied on alone.
