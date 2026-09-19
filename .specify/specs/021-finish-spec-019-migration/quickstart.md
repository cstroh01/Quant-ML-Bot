# Quickstart: Validating Spec 021

These are runnable checks that prove the migration landed. They use no `git`
(Rule 10), no network, and no market data. Every command runs from the
repository root.

## 0. Prerequisites

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
```

- **The concurrent cost_utils lane has landed or been abandoned** (D-6).
  Camden confirms this. Lane A does not start before it.
- **D-2 is signed off in spec.md** before lane G starts. The other lanes don't
  need it.

## 1. Re-baseline before any edit (T001)

```bash
python -m pytest tests -q --tb=no --junitxml=<scratch>/baseline.xml
```

**Expected:** within a few tests of 156 failed / 558 passed / 9 errors, with
128 unique failing test functions (spec.md → Baseline).

**If it differs:**

1. Diff the failing IDs against research R-1.
2. Record every addition or removal and its cause in `tasks.md` → Evidence.
3. Then start.

A new failure that is not in R-1 belongs to whoever introduced it, not to 021.

## 2. Snapshot for line budgets (per lane, before its first edit)

Copy every file the lane owns to `<scratch>/snap-<lane>/`, keeping relative
paths. After the edits:

```bash
diff -u <scratch>/snap-B/scripts/signals.py scripts/signals.py | grep -c '^[+-][^+-]'
```

**Expected:** each PR's sum over its files is ≤ 400 (SC-005). This is the
measurement method spec 018's tasks used.

## 3. Focused runs per lane

| Lane | Command | Expected |
|---|---|---|
| A | `python -m pytest tests/test_backtest_harness.py tests/test_metrics.py tests/test_ml_signal.py` | all pass |
| B | `python -m pytest tests/test_signals.py tests/test_ma_crossover_backtest.py tests/test_logistic_baseline.py` | all pass |
| C | `python -m pytest tests/test_targets.py` | all pass except `TestEquivalenceWithLogisticBaseline` (2), until lane G |
| D | `python -m pytest tests/test_feature_scaling.py tests/test_reports_api.py -k "not backtest_tearsheet"` | all pass |
| E | `python -m pytest tests/test_estimators.py tests/test_model_cv.py` | all pass except `test_model_cv.py::TestEquivalenceWithLogisticBaseline` (4), until lane G |
| G | the two equivalence classes | all pass |

These focused runs are development aids. They are not the gate; step 5 is.

## 4. Structural checks

**SC-002: no literal purge or embargo in migrated code.**

```bash
grep -nE "(label_horizon|embargo_bars)=[0-9]" \
  tests/test_estimators.py tests/test_model_cv.py tests/test_feature_scaling.py \
  tests/test_targets.py tests/test_ml_signal.py
```

**Expected:** only lines that carry an exemption comment (research R-9).
Every other hit is a defect.

**SC-004: a random baseline that actually runs.**

```bash
python -m pytest tests/test_ma_crossover_backtest.py -k "baseline or random or stated_once" -v
```

**Expected:** these tests pass:

- the count-first guard (20 summaries);
- trade count equals the requested count;
- buy-and-hold has 1 closed trade;
- capital, commission, slippage and policy each appear exactly once.

**FR-019: no forbidden file touched.** For every file in this list, confirm
that the lane's snapshot diff never included it:

- the library modules;
- `feature_set_comparison.py` and `multi_ticker_comparison.py`;
- `routes/backtest.py`;
- `requirements*.txt`;
- `docs/PROJECT_CONTEXT.md`.

## 5. The gate: full suite against the residual list (SC-001)

```bash
python -m pytest tests -q --tb=no --junitxml=<scratch>/final.xml
```

**Expected:** the set of failing test IDs in `final.xml` equals the 21 IDs
under "Residual" in research R-1. There are no errors outside that set.

Extracting the failing IDs from the XML is a few lines of standard-library
`xml.etree`. Any failing ID outside the residual list fails the gate. An
entry that leaves the residual list is fine, but record which owner landed it.

**SC-006: no silent deletion.**

```bash
python -m pytest tests --collect-only -q | tail -1
```

**Expected:** ≥ the baseline's collected count, minus the retirements listed in
D-2 and plus the new Rule 5 and Rule 12 tests.

## 6. Red evidence (Rule 12, SC-003)

For each gate in research R-10:

1. Plant the listed defect in an **in-memory copy**, using
   `tests/mutation_support_019.killed(...)`. That is the 019 precedent: patch
   temporarily, never overwrite source.
2. Run the gate. **Expected:** it fails, and the message names the offending
   row, column or field.
3. Run the unmutated control. **Expected:** it passes.
4. Paste the command and both outcomes into `tasks.md` → Evidence, under the
   lane's PR.

## 7. What 021 does *not* make runnable

`python scripts/ma_crossover_backtest.py` and `python scripts/logistic_baseline.py`
still stop, and that is expected. Both read `data/cache/`, and download if the
cache is cold, so they are not part of the offline gate above. They now stop on 020's named reason, "funded
ledger requires declared unadjusted dollar prices", instead of 019's
"starting_capital is required". Running them end to end needs spec 020's
loader wired in, which is out of scope. Do not "fix" this by declaring
`price_basis` in production code (FR-013; 019 R-04).
