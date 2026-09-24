# Spec 021 Handoff

**Status:** The consumer test migration and Lane D guard proof are implemented
locally. The full-suite residual-ID and SC-002 gates pass. T052's historical
frozen-file fingerprints remain open; no
spec-021 pull request was found merged in the GitHub PR list on 2026-09-23.

**Checked at:** 2026-09-23 23:48 UTC.

## Delivered

- Lane G re-anchors the two equivalence classes to D-2's frozen pre-019
  control. Target tests pin the exact close-vs-open label divergence and match
  retained baseline dates to the complete calendar's level features. Model-CV
  tests compare a one-point tuner with the in-contract untuned logistic loop,
  using the returned availability span, train-eligible rows, and `scale=False`.
- Lane D's original zero-only fixture produced `0/0 = NaN`, so removing the
  infinity replacement could not turn it red. A new positive subnormal-volume
  case produces a rounded-zero rolling mean and `+inf` before the guard. The
  in-memory no-replacement mutant is killed; the unmutated and `levels`
  controls pass. No library file was edited.
- The task evidence records the two Lane G killed mutants, the full-suite
  residual comparison, collection count, structural audit, fingerprint drift,
  and the inputs for Camden-numbered follow-ons.

## Verification

| Check | Result |
|---|---|
| Focused equivalence, non-finite, and named-width checks after the SC-002 edit | `12 passed` |
| Random-baseline structural selection | `8 passed, 4 deselected` |
| Collection | `861 tests collected`, versus 860 in the preceding spec-034 run |
| Canonical full suite | `python -m pytest tests -q --tb=no --junitxml=C:\Users\Owner\AppData\Local\Temp\spec021-finish-20260923\final-stable.xml` → **12 failed, 840 passed, 9 errors**, 1386 subtests passed in 359.38s |

The requested spec-034 comparison baseline was **18 failed, 833 passed,
9 errors**, 860 collected. The differential is **6 fewer failures, 7 more
passes, no change in errors, and 1 more collected test**. The six cleared
node IDs are exactly the two old target-equivalence tests and four old
model-CV-equivalence tests named under Lane G in research R-1. No new failure
or error node ID appeared. Parsing `final.xml` and research R-1 yields **21
actual residual IDs = 21 expected**, with empty unexpected and missing sets.
The remaining 12 failures and 9 setup errors belong to the two frozen
comparison modules and spec 018's `test_backtest_tearsheet`.
After this run, SC-002 added explanatory comments and replaced two equivalent
literal width arguments in a hand-built test with one named local variable.
The affected focused tests passed; no production or fixture behavior changed.

## Red and green evidence

| Gate | Red mutant | Green control |
|---|---|---|
| T036 ±inf replacement | In-memory `features.py` replacement removed; positive subnormal row fails `Rel_Volume at row 129 must be NaN` | Three `TestNonFiniteGuard` cases pass; `levels` keeps the row eligible |
| T036 scaler fit | Earlier Lane D record: whole eligible frame fit is killed by per-fold scaler statistics | Per-fold training-row statistics pass |
| T047 executable endpoints | In-memory close-based endpoint mutant is killed by the pinned divergence test | Unmutated test passes |
| T047 tuner equivalence | In-memory `tune_on_fold` result `{'C': 0.5}` is killed against `{'C': 1.0}` | Unmutated one-point test passes |

The earlier lane entries in `tasks.md` cover the other R-10 red/green pairs.

## Gate limits and protected boundaries

- T004's original SHA-256 prefixes no longer match six whole files:
  `scripts/estimators.py`, `scripts/model_cv.py`,
  `scripts/feature_set_comparison.py`, `scripts/multi_ticker_comparison.py`,
  `reports/api/routes/backtest.py`, and `docs/PROJECT_CONTEXT.md`. All
  recorded frozen fixture regions, frozen `logistic_baseline.py` functions,
  and other whole-file digests still match. The six differing files were not
  edited in this close-out. T052 therefore cannot be marked unchanged against
  the historical T004 snapshot. Camden directed on 2026-09-23 to leave T052
  open and retain the original snapshot.
- Quickstart's raw SC-002 grep now has 68 hits, all with inline explanations:
  14 forecast-horizon arguments passed to `build_features`, and 54 literal
  splitter/CV widths on R-9's label-agnostic synthetic fixture. There are zero
  unexplained hits and no price-derived CV literal purge or embargo.
- No Git command was run. A read-only GitHub PR listing found no spec-021
  merged PR; PR-A through PR-G remain lane labels, and no merge is claimed.
- No frozen production module or fixture, `routes/backtest.py`,
  `requirements*.txt`, or `docs/PROJECT_CONTEXT.md` was edited. In
  particular, `ma_crossover_backtest.py`'s data source was not changed.

## Follow-on inputs for Camden to number

- **Frozen comparisons:** `feature_set_comparison.py:367` and `:428` cast
  unknown covered labels to `int`; score known-label rows and report the
  unscored count. `multi_ticker_comparison.py:133`, `:141`, and `:269` need
  declared capital and terminal policy, while `:230` needs the 020 loader.
  Its tables remain blocked on Rule 4 baseline compliance.
- **Span naming:** research R-3 lists the two distinct keyword renames, the
  migrated span-valued call sites, three legacy attrs fallbacks, stale library
  docs/demo, and the bypassable missing-attrs guard.
- **Docs and 020 wiring:** `PROJECT_CONTEXT.md` contains stale contract prose
  and unsourced result passages catalogued in spec D-7; Rule 11 applies.
  `ma_crossover_backtest.main()` and `logistic_baseline.main()` still require
  declared unadjusted-dollar data and currently stop on 020's named reason.
  Leave the MA script's data source to that separate scope.

No follow-on spec was created or numbered here.
