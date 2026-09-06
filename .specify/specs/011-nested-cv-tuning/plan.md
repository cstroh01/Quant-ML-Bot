# Implementation Plan — 011 Nested, Leakage-Safe Hyperparameter Tuning

**Spec**: `.specify/specs/011-nested-cv-tuning/spec.md`

---

## Scope

- `scripts/model_cv.py` — **new**. `inner_splits_over` + `score_fold` +
  `tune_on_fold` + `nested_walk_forward` (FR-001 – FR-008)
- `tests/test_model_cv.py` — **new** (FR-012)

Explicitly **not** touched: `estimators.py` (spec 010 owns the registry and
its grids — this spec searches a grid, it does not author one),
`walk_forward_cv.py`, `logistic_baseline.py`, `features.py`, `targets.py`,
`signals.py`, `backtest_harness.py`.

**No new dependency** (FR-010). `log_loss` and `mean_squared_error` come from
the scikit-learn already imported at `estimators.py:28`.

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 1 — Point-in-time correctness | Inherited, not re-established: this module never constructs a column. It consumes a frame `features.build_features` already made causal. |
| 2 — Purge/embargo | The whole subject of the spec. The inner splitter reuses `walk_forward_splits` on a sub-frame rather than restating the rule; the argument that reuse is *conservative* across a hole is in **Design** below, and both directions of it are tested. |
| 3 — Costs | Not applicable: this module produces predictions, not P&L. No return, Sharpe, or P&L figure is computed anywhere in it. |
| 4 — Baselines | Not yet. Grading a tuned model against buy-and-hold and a random signal is spec 013's runner. |
| 5 — Tests | 45 tests, plus a 7-defect mutation check. Everything that indexes or aligns on a timestamp — the inner splitter, the back-map, the fold loop — ships with tests in this PR. |
| 6 — Dependencies | None added. The Rule 6 line for the PR is that there is no line: no package is added. |
| 8 — Layer separation | `model_cv.py` imports `walk_forward_cv`, `estimators`, numpy, pandas, and `sklearn.metrics` — asserted by AST import-set comparison, not by convention or a source grep. |
| 9 — The merge gate | Two files. The one genuinely subtle piece is the sub-frame back-map and why holes make it conservative rather than leaky; that argument is below and is the thing to check twice. |
| 10 — Version control | No `git` run at all. This was a local session, not the Actions lane, so the amended Rule 10 exception does not apply here. Camden commits. |

---

## Design

### The sub-frame, and why holes make it conservative

`walk_forward_splits` yields `train_indices` sorted but not gapless: after
spec 006, each earlier fold's embargo gap punches a hole in every later
fold's training positions. The tempting inner split — slice the frame up to
the outer test window — re-admits exactly those rows, which is a Rule 2
violation the *tuner* introduces on top of a splitter that was just fixed.

So `inner_splits_over` builds `features.iloc[outer_train_indices]`, runs the
real splitter on it, and maps back with `outer_train_indices[inner_index]`. A
row absent from `outer_train_indices` is absent from the sub-frame, so it
cannot be selected on — the guarantee is structural, not a check.

The reviewer's first objection is that the purge and embargo are now measured
in sub-frame rows, which are not real bars. That is true, and it errs in the
safe direction: across a hole, `E` sub-frame rows span *at least* `E` real
bars, never fewer. Both the purge and the embargo therefore over-cover and
never under-cover. `test_separation_across_a_hole_is_at_least_the_label_horizon`
measures that separation in real positions rather than trusting the argument.

### Validation is eager, not deferred to the first `next()`

`inner_splits_over` is a plain function that validates and then returns an
inner generator, rather than being a generator itself. A generator would
defer the strictly-increasing check to the first iteration, so a caller that
built the array wrongly would learn about it inside a loop body rather than
at the call site. That distinction is invisible in the signature and easy to
undo by adding a `yield`, so it has its own test.

### `score_fold` owns the sign convention

The spec's first draft let the caller supply a scorer. Dropped, and rightly:
comparing candidates requires a direction, and leaving the direction to the
caller means every caller re-derives it. A sign error here is silent — it
selects the *worst* candidate on every fold and still reports a plausible
number — so lower-is-better is stated in the docstring, tested in both
directions for both tasks, and mutation-checked.

`labels=[0, 1]` is passed to `log_loss` explicitly. Without it the label set
is inferred from `y_true`, and a validation fold that happens to be all one
class is scored on a different scale from every other fold — which makes the
mean across inner folds meaningless rather than merely wrong-looking.

### `_predict_for_scoring` reads the class, not the column

Classification scores need P(class 1), and `predict_proba`'s columns are
ordered by `model.classes_`. The code locates class 1 in that list instead of
indexing column 1. This looked like defensive nicety until the mutation check
proved otherwise — see **Test defect found**, below.

### The fallback is `default_params`, never `grid[0]`

An outer fold whose training data supports no inner fold falls back to the
registry's declared default with `tuned=False`. Spec 010 already asserts
`default_params` is a member of its own grid, so the fallback lands on a
configuration that is declared and exercised. `grid[0]` would land on
whichever point sorts first — `C=0.01` for logistic — on exactly the early
folds where the fallback fires most, which is the worst place to run an
untested configuration.

This is not a rare path. With the module's default inner sizing, outer fold 1
has exactly `initial_train_months` of training data and cannot support a
six-month inner window, so it *always* falls back. The `tuned` flag in the
per-fold frame is what keeps that visible to a reader of the artifact rather
than hidden inside a mean.

### Inner window sizing reuses the outer defaults

`inner_initial_train_months` / `inner_test_months` default to
`walk_forward_cv`'s own `DEFAULT_INITIAL_TRAIN_MONTHS` / `DEFAULT_TEST_MONTHS`
rather than to a smaller number invented here. Picking, say, three months
would be this module deciding how many inner folds a caller wants, which the
spec's Assumptions explicitly place at the call site. A caller wanting more
inner folds shortens `inner_test_months`.

---

## Reviewability — the 011a / 011b split

`tasks.md` sets a split point at ~250 changed lines. The diff is larger than
that — `model_cv.py` is 483 lines and `test_model_cv.py` is 996, a large
share of both being docstrings and the reasons behind assertions — so the
split applies. The boundary is marked in the source by the
`Phase 2 — scoring and the tuning loop` comment:

- **011a** — everything above that comment: `_check_strictly_increasing`,
  `inner_splits_over`, `_inner_splits`, and test classes
  `TestStrictlyIncreasingAssertion`, `TestInnerSplitMembership`,
  `TestInnerSplitOrderingAndSeparation`, `TestContiguousEquivalence`,
  `TestModuleBoundaries`. This half depends on `walk_forward_cv` only and
  stands alone: it is the correctness argument of the whole spec, and it is
  where a reviewer's attention is worth the most.
- **011b** — `score_fold`, `_predict_for_scoring`, `tune_on_fold`,
  `nested_walk_forward`, and the remaining test classes.

Splitting is Camden's call at commit time, since Rule 10 puts staging in his
hands. Both halves are green independently; T010's isolation test is the one
task that sits in 011b rather than where `tasks.md` listed it, because
"the selection is unchanged" needs a selection to exist.

---

## Verification — as run

```powershell
./venv/Scripts/python.exe -m unittest discover -s tests
```

**Result: 255 tests, OK.** Suite was 210 after spec 010; 45 added here.

### Mutation check (T017)

Seven deliberate defects injected into `model_cv.py`, each run against the
full `test_model_cv.py`:

| Injected defect | Result |
|---|---|
| Prefix/range slice instead of the sub-frame (re-admits embargoed holes) | **FAILED** (13 failures) |
| Strictly-increasing assertion dropped | **FAILED** (4 failures) |
| `score_fold`'s sign flipped | **FAILED** (2 failures) |
| `labels=[0, 1]` dropped from `log_loss` | **FAILED** (2 errors) |
| Fallback returns `grid[0]` instead of `default_params` | **FAILED** (3 failures) |
| `predict_proba` read positionally instead of via `classes_` | **FAILED** (1 failure) |
| Tuner handed the whole frame instead of the fold's training positions | **FAILED** (3 failures) |

### Test defect found by that check, and fixed

The first mutation run caught six of seven. **`proba[:, 1]` instead of
`proba[:, classes.index(1)]` survived the entire suite**, because no fixture
produces a single-class inner training fold and `classes_` is `[0, 1]`
everywhere else — so the two expressions were indistinguishable to every test
in the file. The spec lists that fold as an edge case, so a green suite that
could not tell them apart was under-testing it.

Fixed with `TestPredictForScoring`: one test on a stub whose `classes_` is
ordered `[1, 0]` (which the positional read gets backwards), and one on a real
`hgb` fit to a single class. Writing the second turned up a fact worth
recording: **`LogisticRegression` refuses a single-class fit outright** —
`ValueError: This solver needs samples of at least 2 classes` — while
`HistGradientBoostingClassifier` fits happily with `classes_ == [0]` and still
returns a *two*-column `predict_proba`. So for logistic the edge case is a
raise, not a mis-score, and gradient boosting is the family that actually
reaches the branch.

That raise is pre-existing behaviour shared with `estimators.fit_predict_walk_forward`,
which calls `.fit` the same way, so it is left alone rather than caught and
converted here — flagging it (CLAUDE.md, *What to flag rather than fix*)
rather than deciding unilaterally that a single-class training fold should be
skipped, scored as a loss, or raised on.

### The equivalence test does not stand alone

Spec 010's plan recorded that a "fit once, reuse across folds" defect survived
an output-equality test against `logistic_baseline.walk_forward_predictions`,
because `_synthetic_features` pairs random features with alternating labels
and gives a model nothing to fit. FR-011's equivalence test would have
inherited exactly that weakness, so it does not use that fixture: it runs on a
learnable frame from `features.build_features` over a real price walk, guarded
by `test_the_fixture_discriminates_between_folds` (first and last outer fold
must fit different coefficients), and paired with
`test_one_outer_fit_per_fold_on_top_of_the_tuning_fits`, which counts
`build_estimator` calls and pins the budget at one fit per (grid point, inner
fold) plus one per outer fold. Output equality cannot supply that count, which
is the point.

### T019 — the observed cost of one `hgb` nested run

See **Cost, measured** below.

---

## Cost, measured (T019)

Recorded so spec 010's grid size can be revised against a real number rather
than a guess, per that spec's own Assumptions.

_(measurement pending — filled in below)_
