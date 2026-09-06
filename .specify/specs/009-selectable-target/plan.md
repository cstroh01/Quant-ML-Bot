# Implementation Plan — 009 Selectable Prediction Target

**Spec**: `.specify/specs/009-selectable-target/spec.md`

---

## Scope

- `scripts/targets.py` — **new**. Label construction (FR-001 – FR-005)
- `scripts/features.py` — **new**. Parameterized feature builder
  (FR-006 – FR-008)
- `tests/test_targets.py` — **new** (FR-013)

Explicitly **not** touched: `scripts/logistic_baseline.py` (FR-011),
`walk_forward_cv.py`, `backtest_harness.py`, `signals.py`, `data.py`,
`metrics.py`.

**No new dependency.**

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 1 — Point-in-time correctness | The label is the only forward-looking column and is excluded from `FEATURE_COLUMNS` by construction. The nullable `Int64` dtype is load-bearing: a `bool` column cannot hold a null, so the unobservable tail would become `False` — a fabricated target, which improves results rather than crashing. `test_features_are_computable_from_the_past` perturbs future closes and asserts no feature moves. |
| 2 — Purge/embargo | Indirectly, and this is the main reason the spec exists first. `build_target` returns the horizon it used so a caller passes *one* number to both the label and `walk_forward_splits`. A 5-bar label under a 1-bar purge leaks silently and scores better. |
| 5 — Tests | Off-by-one both ways, boundaries (first row, last `h` rows, horizon ≥ frame length), gap case (positional not calendar), plus a mutation check. |
| 6 — Dependencies | None added. |
| 8 — Layer separation | Asserted by test, not by convention: `test_targets_imports_nothing_from_the_project` and `test_features_imports_only_signals_and_targets` parse each module's AST and compare the import set exactly. |
| 9 — The merge gate | Two small modules; the only subtle piece is the horizon handback, explained above. |
| 10 — Version control | No `git` run outside the Actions lane. |

---

## Design

### The horizon handback

`build_target` returns `(label, task, label_horizon)` rather than just a
label. The third element looks redundant — the caller passed it in — and is
the point of the module's shape.

`walk_forward_splits` sizes its purge from a `label_horizon` its caller
supplies, and deliberately refuses to guess one (`walk_forward_cv.py:26-28`).
Today `logistic_baseline.py` writes that number twice: `shift(-1)` at `:46`
and the literal `label_horizon=1` at `:65` and `:149`. They agree by
coincidence. Once the target is selectable, a caller who switches to a 5-bar
label and forgets to update the purge gets a Rule 2 violation that raises
nothing and improves the score. Handing the horizon back means the number is
written once and passed through.

`task` is derived from `kind` by lookup, not taken as a parameter — a
direction label is not a regression problem, and letting a caller assert
otherwise would only permit a mistake.

### `horizon=0` is rejected, not merely discouraged

The degenerate case is silent, not loud: a direction label becomes
`Close[t] > Close[t]`, which is `False` on every row, and a forward log
return becomes `log(1) == 0.0` everywhere. Both are perfectly well-formed
columns that no model can learn from and nothing complains about. Hence a
`ValueError`, and a test.

### Why a new module rather than editing `build_features` in place

`logistic_baseline.build_features` produces the control result quoted in
`docs/PROJECT_CONTEXT.md`, its behavior is pinned by
`tests/test_logistic_baseline.py`, and spec 005 already ruled in favour of
leaving that file alone. So the general path is built fresh and **proven
equivalent by test** instead: `test_build_features_reproduces_the_baseline_frame`
asserts frame equality on every shared column for
`target_kind="direction", label_horizon=1`. If that ever fails, a real
behavioural difference has been caught before it contaminates a comparison
table; while it passes, the old module is provably redundant and a later spec
may delete it.

### `FEATURE_COLUMNS` is restated, and the restatement is pinned

`features.py` defines its own list rather than importing
`logistic_baseline.FEATURE_COLUMNS`, because that import pulls scikit-learn in
for five strings. `test_feature_columns_match` asserts the two lists are
equal, so the duplication cannot drift.

The five columns are unchanged. They are price *levels* (`Short_SMA`,
`Long_SMA`, `Volume`), which is a genuine weakness for a linear model and a
hard blocker for any pooled cross-sectional model. Making them scale-free is
its own change with its own effect on results and does not belong in the same
PR as a new target.

### Labels are positional, matching the purge

`_future_close` uses `shift(-horizon)` — rows, not calendar days. This is the
same convention spec 003 chose for the purge (its FR-005), and the two *must*
match: if a label were sized in calendar days and the purge in rows, they
would disagree at every holiday, and the purge exists to cover exactly this
label. `TestGapCase` builds a frame with a five-calendar-day hole and asserts
the label spans one bar across it.

---

## Verification — as run

```powershell
./venv/Scripts/python.exe -m unittest discover -s tests
```

**Result: 180 tests, OK.** Suite was 152 after spec 008; 28 added here.

### Mutation check

Four deliberate defects injected into `targets.py`:

| Injected defect | Result |
|---|---|
| `shift(-horizon - 1)` — label reaches one bar too far | **FAILED** (15 failures) |
| `future >= prices["Close"]` — a flat close counts as up | **FAILED** (1 failure) |
| `if horizon < 0` — `horizon=0` no longer rejected | **FAILED** (2 failures) |
| `label[future.isna()] = pd.NA` removed — unobservable tail not nulled | **FAILED** (9 failures) |

### Two test defects found and fixed during the work

Recorded because both would have produced a green suite that proved less than
it appeared to:

1. **`test_perturbing_the_bar_at_the_horizon_does_change_it` was initially
   wrong.** It tripled `Close[t+h]` and asserted the label changed — but
   tripling an already-*up* bar leaves a direction label at `1`, so the
   assertion was invalid for one of the two builders and failed legitimately.
   Fixed by moving the future close to the far side of `Close[t]` based on
   what the label originally read, rather than merely scaling it.
2. **The module-boundary test grepped the source text** for
   `"backtest_harness"` and tripped on the docstring that documents the
   module *not* importing it. Replaced with an AST parse that compares the
   actual import set exactly — which is a stronger assertion than the
   substring check ever was.
