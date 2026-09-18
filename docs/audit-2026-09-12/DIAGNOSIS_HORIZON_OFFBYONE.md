# Diagnosis — the "+1" in the third return value of `build_target`

Scope: read-only diagnosis. No `.py` file was modified; no `git` command was run.
Spec citations are line numbers in `.specify/specs/019-funded-ledger-and-timing/spec.md`.

## Verdict

**No single conflation line in `scripts/targets.py`.** `build_target` (`scripts/targets.py:131`)
returns `horizon + 1` deliberately and correctly: spec `:51` states that the third
return value is `label_availability_span = h + 1`, "never a horizon". The module
docstring (`targets.py:4-9`) and the return docs (`targets.py:107-115`) say the same.
The tail-null count is also correct: spec `:48` makes the final `h+1` labels unobservable,
which is what `Open.shift(-(horizon+1))` at `targets.py:66` produces.

So the `+1` is where it belongs. What is wrong is everything around it:

1. **Naming, not arithmetic.** `scripts/features.py:116,119,125,187-188` still calls the
   value it receives `label_horizon` and stores it in `frame.attrs["label_horizon"]`.
   `scripts/estimators.py:278-280` reads that key and compares it against a caller's
   purge/embargo. The number is right; the slot name has not migrated, which is what
   makes every caller *look* like it is violating spec `:52`. It is not: `label_horizon`
   in `walk_forward_splits` (`scripts/walk_forward_cv.py:27,93-97`) is the purge width,
   not the target horizon, so feeding it `h+1` sizes a purge of `h+1` rows (spec `:55`)
   and does **not** build an `(h+1)`-session target.
2. **Two production callers never migrated** — see (b) below. Those are real, not test rot.
3. **A second, separate 019 change is tangled into the same failures**: the target moved
   from close-to-close to executable open-to-open, `log(Open[t+h+1]/Open[t+1])`
   (spec `:40,:46`). Several `test_targets.py` failures are caused by that, not by the span.

**Lookahead risk: none from the span itself.** The direction is conservative — the declared
span (`h+1`) is one row *wider* than the purge `walk_forward_cv.py:98` needs (spec `:55`
says so explicitly), and `estimators.py:279` refuses anything *shorter*. A caller cannot
end up with a purge sized off too small a number through this path. The live risk is the
opposite: callers that hardcode `1` now hard-fail instead of silently under-purging, which
is the check working.

## Classification per failing test

(a) = test encodes the OLD pre-019 contract, update it. (b) = property still true, new code wrong — flagged, not fixed.

### `tests/test_targets.py` — span (spec `:48`, `:51-52`)

| Test | Class | Stale because |
|---|---|---|
| `TestBuildTargetContract::test_the_returned_horizon_is_what_was_asked_for:247` | (a) | `:51` — third value is `h+1`, not `h` |
| `TestBuildTargetContract::test_direction_is_a_classification_task:239` | (a) | `:51` |
| `TestBuildTargetContract::test_return_is_a_regression_task:245` | (a) | `:51` |
| `TestBoundaries::test_exactly_the_last_horizon_rows_are_null:170` | (a) | `:48` — final **h+1** labels unobservable |
| `TestDirectionLabel::test_dtype_is_nullable_so_the_tail_cannot_become_false:66` | (a) | `:48` (asserts exactly 3 nulls at h=3) |
| `TestBoundaries::test_over_long_horizon_yields_an_empty_feature_frame:192` | (a) | `:51` (expects `horizon == 300`) |

### `tests/test_targets.py` — open-to-open price basis (spec `:40`, `:46`)

| Test | Class | Stale because |
|---|---|---|
| `TestDirectionLabel::test_label_at_t_compares_against_close_at_t_plus_horizon:48` | (a) | `:46` — endpoints are `Open[t+1]`/`Open[t+h+1]`, not closes. The observed "Close[t] vs Close[t+2]" is really the open-basis label read through a `Open = Close + 1` fixture |
| `TestForwardLogReturnLabel::test_value_is_the_log_ratio_over_the_horizon:77` | (a) | `:46` |
| `TestForwardLogReturnLabel::test_non_positive_close_is_nan:101` | (a) | `:48` — the "both endpoints finite and > 0" property still holds (`targets.py:90-91`); the fixture zeroes `Close`, which is no longer an endpoint. Fixture update only |
| `TestOffByOne::test_perturbing_the_bar_at_the_horizon_does_change_it:138` | (a) | `:46` — perturbs `Close`; must perturb `Open` |
| `TestValidation::test_missing_close_column_raises:227` | (a) | `:46` — the required column is now `Open` (`targets.py:58-59`); as written the frame *has* `Open`, so nothing raises |
| `TestGapCase::test_label_spans_rows_not_calendar_days:267` | (a) | `:46` + `:57-58` — the positional-shift property is still true, the close-based expectations are not |

**Coverage hole worth flagging (not a failure):** `TestOffByOne::test_perturbing_the_bar_just_past_the_horizon_changes_nothing:126`
now **passes vacuously** — it perturbs `Close`, which no longer enters the label at all, so it
would pass against a label that read arbitrarily far into the future. It must be re-pointed at
`Open` in the same edit as its companion, or SC-004's anti-lookahead guard is gone.

### `tests/test_targets.py` — baseline equivalence (escalate before editing)

`TestEquivalenceWithLogisticBaseline::test_direction_label_matches_the_baseline_label:316`
and `::test_build_features_reproduces_the_baseline_frame:335` — **(a) by the letter of spec `:46`**
(`logistic_baseline` is the pre-019 `Close.shift(-1)` control; equivalence cannot survive a
deliberate change of price basis), **but do not edit them silently.** These are the tests that
pin the AAPL control quoted in `docs/PROJECT_CONTEXT.md`. Retiring them retires that control
number, which is Camden's call, not an agent's.

### `tests/test_estimators.py` — (a), spec `:55`

All failures raise `ValueError: purge/embargo shorter than label availability horizon` at
`scripts/estimators.py:280`. Every one passes a literal `embargo_bars=1` against a frame that
now declares span `2` (lines `201,222,245,287,302,346,362,380,398,423,446,465,487`). Spec `:55`:
"Purge and minimum embargo span is h + 1 rows … Cross-validation refuses any purge/embargo span
shorter than feature-frame metadata declares." The embargo literal is stale; the check is right.
Also `TestRegressionPath::test_task_and_horizon_come_through_from_build_features:336`
(`assertEqual(self.horizon, 1)`) — (a) per spec `:51`.

### `tests/test_model_cv.py` — mixed

- The purge/embargo `ValueError` failures (via `model_cv.py:439` and `:300`): **(a)**, spec `:55`,
  identical to the estimator cluster.
- `TestEquivalenceWithLogisticBaseline` — `test_single_point_grid_reproduces_the_baseline_element_for_element`,
  `test_null_placement_matches_too`, `test_one_outer_fit_per_fold_on_top_of_the_tuning_fits`,
  `test_the_fixture_discriminates_between_folds`: **not this issue.** They fail with
  `ValueError: Input X contains NaN` inside `scripts/logistic_baseline.py:159`, because
  `build_features` now preserves every source session instead of dropping warm-up rows
  (spec `:19`, `:60`). Spec `:62` already records this as finding 23, status
  **"library-closed; consumer open (API rundown)"** — these four *are* that open consumer.
  They belong to work order 3, not here.

### `tests/test_feature_set_comparison.py` — (b), NEW CODE is wrong

All 4 failures and all 9 errors trace to `scripts/feature_set_comparison.py:169` passing
`embargo_bars=EMBARGO_BARS` where `EMBARGO_BARS = 1` (`:107`), against a frame declaring span 2
(the traceback reports `horizon=2, embargo=1`). The tests assert process, seed and
serial/parallel-equivalence properties that are all still true; the *production* module never
migrated to spec `:55`. **Do not edit these tests.** `scripts/multi_ticker_comparison.py:78,246`
has the identical defect, and its reported `"embargo_bars"` metadata at `:299` would understate
the embargo in any metric it emits — a PR-requirement-3 reporting defect as well as a bug.

## Recommended fix approach (described, not implemented)

Do not touch `scripts/targets.py`; it already matches the normative section. The migration is a
naming pass plus two production constants. First, rename the third value end to end —
`build_features`'s third return and its `frame.attrs` key from `label_horizon` to
`label_availability_span` (`features.py:116,119,125,187-188`), and the `estimators.py:275-280`
parameters and error message to say *span* — so spec `:52`'s "never pass this back as horizon"
becomes checkable by reading a call site instead of by memory; rename `walk_forward_splits`'s
parameter in the same edit, since it is a purge width and its present name is what makes correct
calls look wrong. Second, fix the two (b) callers by deriving the embargo from the span the frame
declares rather than from a module constant, deleting `EMBARGO_BARS = 1` in both
`feature_set_comparison.py` and `multi_ticker_comparison.py` so the number cannot drift from the
label again. Third, update the (a) tests: the span cluster is mechanical (`h` → `h+1`), while the
open-basis cluster needs its fixtures re-pointed from `Close` to `Open` — including the now-vacuous
`test_perturbing_the_bar_just_past_the_horizon_changes_nothing`, which must be re-armed in the same
change as its companion. Leave the `logistic_baseline` equivalence tests and the finding-23 NaN
cluster for Camden to rule on; they retire a committed control result and belong in their own
reviewable change, not in this one.
