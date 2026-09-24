# Feature Specification: Finish the Spec 019 Migration (Consumer Side)

**Feature Branch**: `021-finish-spec-019-migration`

**Created**: 2026-09-18

**Status**: Consumer migration implemented locally; D-2 was approved by Camden
on 2026-09-18. Merged spec-021 PRs: none found in the GitHub PR list on
2026-09-23 (PR-A–PR-G are lane labels in the task record). Final full-suite
baseline: 12 failed, 840 passed, 9 errors; exactly 21 R-1 residual IDs.
SC-002 passes; T052's historical frozen-file digests remain open by Camden's
2026-09-23 direction; see
tasks.md Gate and HANDOFF.md. No `git` command was run.

**Input**: Camden, 2026-09-18: "Scope a spec that completes the consumer side of
spec 019. The library side is done and correct. Production call sites, test
fixtures and docs that still assume the old contract were never migrated.
`feature_set_comparison.py` and `multi_ticker_comparison.py` are frozen for
this spec. Decide whether the `label_horizon` → `label_availability_span`
rename is absorbed or deferred."

## Why this spec exists

Spec 019 changed the library contract (`backtest_harness.py`, `targets.py`,
`features.py`, `estimators.py`, `model_cv.py`, `metrics.py`, `ml_signal.py`),
and those modules now pass their own 019 suites. Their consumers were never
moved. The earlier triage attributed most of the suite's failures to five
contract changes. This spec confirms that attribution against the current
tree, corrects it where the tree disagrees, and scopes the migration.

**The five changes are really seven.** Reading every failure to its second
layer (see [Baseline](#baseline)) finds two more deltas (C6 and C7 below). Each
one breaks consumers on its own. One of them hides a production defect: under
019 the Rule 4 random baseline silently stops running.

## Baseline

This is the number this spec is measured against. Command:
`python -m pytest tests`, from the repository root.

| When (EDT) | Failed | Passed | Errors | Unique failing test functions |
|---|---:|---:|---:|---:|
| 2026-09-18 ~16:25, first triage run | 158 | 530 | 9 | 127 + 1 parent seen only via subtests |
| **2026-09-18 16:34:38, final run, tree stable during it** | **156** | **558** | **9** | **128** |

"Failed" counts unittest subtest failures separately. "Unique" counts test
functions, not subtests.

**Reconciling the two rows.** Between 16:29:52 and 16:30:39, a concurrent lane
changed the tree. It created `scripts/cost_utils.py`, `tests/test_cost_utils.py`
and `tests/test_return_stats.py`. It modified `metrics.py`, `ml_signal.py`,
`return_stats.py`, `test_019_conventions.py`, `test_metrics.py` and
`test_ml_signal.py`. Three effects follow, and they account for the whole
difference:

- Two tests turned green. `test_ml_signal.py::ModuleBoundaryTests::test_ml_signal_imports_only_numpy_and_pandas`
  had failed on `ml_signal` importing `metrics`; `validate_costs` moved to
  `cost_utils`. `test_metrics.py::TestSharpeConventions::test_matches_return_stats_annualization_arithmetic`
  also passes now.
- That makes 158 − 2 = 156 failed.
- Passed rose by those 2 plus 26 new cases, so 530 + 2 + 26 = 558.

This spec does not own that lane. Its file overlap is handled in
[D-6](#d-6--lane-ownership-and-overlap).

### Where the 128 unique failures fall

| Group | Tests | Owner |
|---|---:|---|
| In scope for 021 | 107 | This spec |
| `test_feature_set_comparison.py`: production file frozen | 12 | Follow-on ([D-5](#d-5--the-two-frozen-files)) |
| `test_multi_ticker_comparison.py`: production file frozen | 8 | Follow-on ([D-5](#d-5--the-two-frozen-files)) |
| `test_reports_api.py::TestReportsApi::test_backtest_tearsheet` | 1 | Spec 018 T024, which also needs 020's wiring |

## The contract deltas (C1–C7)

| ID | 019 change | Library site | What every consumer must now do |
|---|---|---|---|
| **C1** | `starting_capital` is required. The capital base is declared, never taken from a price. | `backtest_harness.py:68-72`; `metrics.py:85-86` | Pass capital explicitly on every `run_backtest` call. Expect equity to be anchored at the declared capital, never at the first close. |
| **C2** | The third return of `build_target` / `build_features` is the label availability span `h + 1`, not the horizon. | `targets.py:131`; `features.py:180-188`; the guard at `estimators.py:275-280` | Pass the returned span as both purge (`label_horizon=`) and `embargo_bars=`. Never write it as a literal. Never pass it back as `horizon=`. |
| **C3** | The label is `log(Open[t+h+1] / Open[t+1])` (direction is its sign), not close-to-close. | `targets.py:55-99` | Fixtures must carry `Open`. Expected values are re-derived from opens, and label perturbation tests perturb `Open`. |
| **C4** | No row is dropped. Warm-up and unknown-label rows stay, flagged by `Inference_Eligible` / `Train_Eligible`. Metrics keep the source index. | `features.py:185-188`; `estimators.py:275-285`; `metrics.py:28-47` | Mask after splitting and never `dropna` the frame first. Fits use train-eligible rows. Diagnostics use complete rows of the named set. |
| **C5** | End of batch is not an exit. Open positions are marked unless `liquidate=True`. The policy layer no longer forces a flat final bar. | `backtest_harness.py:142-144`; `ml_signal.py:181-182` | Reporting consumers choose `liquidate` explicitly, and identically for a strategy and its baselines. Tests assert the new semantics. |
| **C6** | The harness validates its inputs (019 units 1 and 5). | `backtest_harness.py:33-67` | See the list below this table. |
| **C7** | `performance_summary` carries more keys (019 unit 6). | `metrics.py:351-374` | Key-set assertions track the new schema. |

C6 in full. The harness now rejects:

- an empty frame;
- a non-finite or non-positive `Open` or `Close`;
- signals that are not exact booleans;
- a row carrying both `Buy_Next_Open` and `Sell_Next_Open`;
- a frame without `attrs["price_basis"] == "unadjusted_dollars"`.

What consumers must do about it: synthetic fixtures declare the basis and use
positive prices, and signal generators never emit a same-row sell and buy.

**C6 has a production consequence.** `signals.random_signal` spaces trips
exactly `avg_holding_days` apart (`signals.py:126-139`). So trip *i*'s exit and
trip *i+1*'s entry can land on the same row. The pre-019 harness sold and
re-bought on that open. The 019 harness raises "conflicting buy and sell
signals". The callers catch the error and print "random baseline not run":
`ma_crossover_backtest.baseline_results:88-99`, and `multi_ticker_comparison._baseline_rows:138-148`.
On the sawtooth fixture every seed fails, so Rule 4's second baseline is silently
absent. `test_ma_crossover_backtest.py::test_the_random_baseline_matches_the_strategys_trade_count`
fails today on C1. Once capital is added it **will pass vacuously**, because it
loops over an empty list. A probe that adds capital in-process confirms both.

## Scope

### In scope: production

Four files, plus one route that gets no code change. 019 changed none of
them. `signals.py` is a core module in CLAUDE.md's boundary table, and the
`random_signal` fix stays inside its "when to trade" responsibility (Rule 8).

| File | Change | Deltas |
|---|---|---|
| `scripts/signals.py` | `random_signal` never places an exit and an entry on the same row. Its capacity check and error message follow. The `buy_and_hold_signal` docstring (`:49-53`) says the harness *marks*; a closed round trip is the accounting caller's explicit `liquidate` choice. | C6, C5 |
| `scripts/ma_crossover_backtest.py` | Declares starting capital and an end-of-data policy beside the cost model. Passes both, identically, to the strategy and both baselines (`:81`, `:92`, `:186`). `baseline_results` takes both as required keyword arguments. `format_comparison` states each once. | C1, C5 |
| `scripts/logistic_baseline.py` | Reporting only: `main()` (`:297-347`), `_format_ml_comparison` (`:229-294`) and the cost-model constants (`:26-33`) gain capital and the end-of-data policy, as above. Every function that builds the control's frame, label, CV or signal is frozen ([D-2](#d-2--logistic_baselinepy-is-a-frozen-pre-019-control)): `build_features`, `evaluate_walk_forward`, `walk_forward_predictions`, `_signal_from_predictions` and `build_ml_signal`. | C1, C5 |
| `scripts/feature_diagnostics.py` | `diagnose` measures only rows where the named set's columns are all finite, and reports how many rows it used and how many it excluded. The measurement primitives (`standardized_matrix` and the three measures built on it) refuse non-finite input with a named error, instead of failing inside the SVD with "SVD did not converge" or returning `nan`. The stale "completeness drop" comment in `main()` (`:206-210`) is corrected. | C4 |
| `reports/api/routes/ml_rundown.py` | No code change. It already reports the final session under 019. A test pins that (see the tests table). | C4 (finding 23, consumer half) |

After 021, `ma_crossover_backtest.main()` and `logistic_baseline.main()` still
cannot run end to end. They stop failing on 019's "starting_capital is
required" and fail instead on 020's named reason, "funded ledger requires
declared unadjusted dollar prices". That is the merge order REVIEW_019 R-01
records. Wiring the 020 loader into these callers is not 021's job.

### In scope: tests (10 files, 107 failing tests)

The first-layer delta is the error a test raises today. Second-layer failures
surface once the first layer is fixed. They were found with in-process probes
from the session scratchpad; nothing was written to the repository. The
per-test table is in `plan.md` → *Research* → R-1.

| File | Failing | First layer | Second layer found |
|---|---:|---|---|
| `test_metrics.py` | 22 | C1 ×22 | C5 ×4; C1 capital-base semantics ×1 (`test_curve_is_flat_at_the_capital_base` expects the first close, 11.0); C7 ×1; C4 index ×1 (`test_non_range_index_raises` asserts a guard 019 removed) |
| `test_feature_scaling.py` | 17 | C4 ×13, C2 ×4 | none |
| `test_targets.py` | 13 | C2 ×6 (one also C4), C3 ×5, D-2 ×2 | none |
| `test_backtest_harness.py` | 12 | C1 ×12 | C5 ×2 |
| `test_model_cv.py` | 11 | C2 ×8, D-2/C4 ×3 | C4 ×2 (`TestTuneOnFoldIsolation._corrupted` casts `<NA>` labels to int) |
| `test_ma_crossover_backtest.py` | 11 | C1 ×10, C6 ×1 (a zero close in the fixture call) | C6 `random_signal` ×3; C5 ×1; one test that would pass vacuously once C1 is fixed |
| `test_estimators.py` | 8 | C2 ×8 | none |
| `test_ml_signal.py` | 7 | C5 ×3, C6 ×3 (no `price_basis`), C3 ×1 (fixture has no `Open`) | the C3 test also hard-codes a purge literal on a hand-built frame (FR-004) |
| `test_signals.py` | 5 | C1 ×2, C6 ×3 (empty frame; non-positive prices ×2) | C5 ×1 |
| `test_logistic_baseline.py` | 1 | C1 ×1 | none |
| `test_reports_api.py` | 0 | n/a | `test_ml_rundown` gains an assertion that `as_of_date` is the final cached session |

First-layer totals across the 107: C1 47, C2 26, C4 13, C6 7, C3 6, C5 3,
D-2 5 (2 label or frame equivalence, 3 NaN in the baseline's fit).

### The 11 production files carrying `label_horizon`

This list is confirmed against the tree by
`grep -rc label_horizon --include=*.py scripts reports`. The count of 11 is
right. The meanings differ, and that difference drives [D-1](#d-1--the-label_horizon-rename-is-deferred-to-a-follow-on-spec).

| File | Uses | What the name means there | 021 | Rename (D-1) |
|---|---:|---|---|---|
| `scripts/model_cv.py` | 11 | purge width | no edit | follow-on |
| `scripts/walk_forward_cv.py` | 9 | purge width; `main()` demo passes `1, 1` | no edit | follow-on |
| `scripts/multi_ticker_comparison.py` | 5 | holds the returned span | frozen | follow-on |
| `scripts/estimators.py` | 4 | purge width, plus a legacy `attrs` fallback read (`:278`) | no edit | follow-on |
| `scripts/feature_set_comparison.py` | 3 | holds the returned span | frozen | follow-on |
| `scripts/logistic_baseline.py` | 3 | purge = 1 for its own Close→Close label, which is consistent for a 1-bar close label | reporting hunks only | follow-on, after D-2 |
| `reports/api/routes/diagnostics.py` | 3 | forecast horizon `h` (a comment and two kwargs) | no edit; behavior already correct | follow-on |
| `scripts/features.py` | 2 | forecast horizon `h` (the `build_features` parameter) | no edit | follow-on |
| `scripts/targets.py` | 1 | a docstring cross-reference (`:18`) | no edit | follow-on |
| `scripts/feature_diagnostics.py` | 1 | forecast horizon `h` | C4 edit only | follow-on |
| `reports/api/routes/ml_rundown.py` | 1 | forecast horizon `h` | no edit | follow-on |

### Out of scope, and who owns it

| Item | Owner | Why not here |
|---|---|---|
| The `label_horizon` → `label_availability_span` rename, and its twin `build_features(label_horizon=)` → `horizon=` | Follow-on spec; proposed `022-purge-span-rename`, number assigned by Camden | [D-1](#d-1--the-label_horizon-rename-is-deferred-to-a-follow-on-spec) |
| `feature_set_comparison.py`, `multi_ticker_comparison.py` and their 20 failing tests | Follow-on spec(s) | Frozen by directive ([D-5](#d-5--the-two-frozen-files)) |
| `reports/api/routes/backtest.py` and `test_backtest_tearsheet` | Spec 018 T024 | Already assigned; T024 also depends on 020 |
| Wiring the 020 loader into production entry points (`download_market_data` still returns `research_adjusted`) | Spec 020 follow-up | A different contract, and not a 019 consumer change |
| Every library module listed under [Why this spec exists](#why-this-spec-exists) | None | 019 library side is declared done. 021 reads it and does not edit it. |
| `docs/PROJECT_CONTEXT.md` | Follow-on docs pass, together with Rule 11 regeneration | [D-7](#d-7--docsproject_contextmd-is-not-edited-here) |
| `scripts/scratch_*.py` | None | They build their own close-to-close labels and never call the 019 library. They are not consumers. |

### Flagged, not fixed

CLAUDE.md asks these to be raised rather than resolved.

1. **The span guard can be bypassed.** `estimators.model_row_masks` enforces
   purge ≥ span only when the frame carries `attrs["label_availability_span"]`.
   A frame built by hand without it takes whatever the caller passes.
   `test_ml_signal.py::EstimatorAgnosticTests` (`:716-752`) does exactly that
   with `label_horizon=1, embargo_bars=1` for an h = 1 label. Once its missing
   `Open` column is added, it will pass one row short of the project
   convention, and nothing will object. 021 closes this at call sites
   (FR-003, FR-004). Making the guard itself unbypassable is library work for
   the rename follow-on.
2. **"Hysteresis is prohibited for h > 1"** (019 `spec.md:76`) has no guard in
   code. `ml_signal.positions_from_predicted_return` never learns `h`.
3. **Two frozen files degrade Rule 4 today.** `multi_ticker_comparison._baseline_rows`
   catches the random-baseline error. 021's `random_signal` fix changes that
   file's behavior through its import, without editing it. Its tests stay red
   for their own reasons.

## Decisions

These are recorded here, not settled in chat, per CLAUDE.md. Camden can
overturn any of them at review. D-2 gates tasks and must be confirmed before
those tasks start.

### D-1 — The `label_horizon` rename is deferred to a follow-on spec

Decision: **deferred**. Not absorbed.

1. **The rename cannot happen without touching frozen files.**
   `feature_set_comparison.py:153-172` and `multi_ticker_comparison.py:234-250`
   call `build_features(label_horizon=)` and `nested_walk_forward(label_horizon=)`.
   A hard rename breaks both. A compatibility shim adds library surface to
   modules 019 declared done.
2. **Reviewability.** Many call sites change a *value* in 021: a literal 1
   becomes the returned span. Renaming the keyword on the same line would hide
   which lines changed meaning and which only changed spelling. Rule 9 needs
   Camden to see that difference.
3. **021 is consumer-only.** The rename edits signatures in five library
   modules and the 019 guard's message.

**Mitigation inside 021, so the deferral costs nothing.** Every migrated call
site takes its purge and embargo from the returned span, never from a literal
(FR-003, FR-004). The follow-on then renames names only. No value changes, so
nothing can drift in between. The follow-on should carry:

- the keyword rename in `walk_forward_cv`, `model_cv` and `estimators`;
- `build_features(label_horizon=)` → `horizon=`;
- removal of the legacy `attrs["label_horizon"]` fallback reads (`estimators.py:278`
  and the two frozen files);
- the stale library docstrings (`targets.py:11-18`, `features.py:125-129`);
- `walk_forward_cv.main()`'s `1, 1` demo;
- the unbypassable-guard item under Flagged, not fixed.

### D-2 — `logistic_baseline.py` is a frozen pre-019 control

**Gated: Camden confirms before T-gated tasks start.**

Recommendation: 021 does not change `logistic_baseline.py`'s label, frame or
CV. They define the committed Phase 2 control, and migrating them moves that
goalpost. Two equivalence classes pin the new path to the control. 019 broke
both on purpose. They are re-anchored rather than deleted:

- **`test_targets.py::TestEquivalenceWithLogisticBaseline`** (spec 009 SC-001/SC-002).
  - The level-feature equivalence stays: the five level columns, matched by
    `Date` on the baseline's retained rows.
  - Label equivalence is replaced by a *pinned divergence*. The test asserts
    that the baseline's label is `Close[t+1] > Close[t]` and the 019 label is
    `Open[t+2] > Open[t+1]`, with a hand-worked row where the two disagree.
    The divergence is then asserted, not silent.
  - The row-count equality becomes: the 019 frame has every source session,
    and the baseline has a strict subset of them.
- **`test_model_cv.py::TestEquivalenceWithLogisticBaseline`** (spec 011 T015 /
  SC-006). Its property is "tuning is the only source of divergence", and that
  is kept. The reference moves from `logistic_baseline.walk_forward_predictions`
  to `estimators.fit_predict_walk_forward`, the in-contract untuned loop, with
  the same single grid point and the same span.
  - The chain back to the control survives.
    `test_estimators.py::test_matches_logistic_baseline_element_for_element`
    (`:212`) still pins the untuned loop to `logistic_baseline` on
    label-agnostic synthetic frames, and it passes today.

**Considered and rejected for 021: migrating `logistic_baseline.py` to 019.**
That changes a committed control result. It needs its own spec, with Rule 4
baselines and the Rule 11 regeneration of `PROJECT_CONTEXT.md`'s AAPL figures.

### D-3 — End-of-data policy for reports is explicit terminal liquidation

Recommendation: `ma_crossover_backtest` and `logistic_baseline.main()` pass
`liquidate=True` to the strategy and to both baselines, identically. The report
states the policy once, beside the cost model.

Reasons:

- It reproduces the pre-019 closed-trade semantics, with costs on the final
  exit. That exit is now an explicit, ledger-identified event rather than an
  implicit one.
- It keeps buy-and-hold a meaningful baseline. Under mark-only, `summarize_trades`
  reports it as 0 trades and $0.
- Rule 4 requires the identical treatment across all three rows.

Rejected alternative: mark-only, with the tables switched to ledger-equity P&L.
That changes report columns, and it belongs with 018 T029 or work order 3.

### D-4 — Starting capital is a declared constant; Camden sets the value

- **Production.** One `STARTING_CAPITAL` constant beside the cost model in
  `ma_crossover_backtest.py`. `logistic_baseline.py` restates it, following the
  local-restatement precedent its cost model sets (`logistic_baseline.py:26-31`;
  `constants.py:5-8`). The plan proposes `10_000.0` as an *assumption*, printed
  in the report header like commission. It is not a result. The only existing
  capital figure (`constants.py`) is none, so this is a new parameter.
- **Tests.** Each test module declares one capital constant, large enough that
  no entry is rejected unless rejection is under test. Tests that assert
  equity compare against the constant symbolically, never against a literal.
  Tests that already pass an explicit capital, such as `test_metrics.py:230`
  with `100.0`, keep their value.
- No default is added to the harness. 019 forbids one.

### D-5 — The two frozen files

Per directive, 021 does not edit `feature_set_comparison.py` or
`multi_ticker_comparison.py` beyond Codex's embargo fix, which has already
landed. That has a stated consequence: **021 cannot make the suite fully
green.** Twenty failing tests stay on the residual list (SC-001).

**Tension in the request.** The request lists the `feature_set_comparison.py:367`
crash among call sites to update, and also freezes that file. The crash is
production code: `compare_classification` runs `labels.astype(int)` over
covered rows whose labels are unknown. So no test-side change fixes it without
hiding it. It is recorded, not scheduled.

Defects handed to the follow-on:

- **`feature_set_comparison.py`**: pairs predictions with `<NA>` labels in the
  final `h+1` covered sessions (`:180-189`, cast at `:367` and `:428`).
  Recommended fix: score only rows with a known label, and report how many
  covered rows could not be scored.
- **`multi_ticker_comparison.py`**:
  - `run_backtest` is called without capital or an end-of-data policy
    (`:133`, `:141`, `:269`).
  - `research_adjusted` data comes in at `:230`; that is the 020 wiring.
  - The random baseline error is caught at `:143-148`. 021's `random_signal`
    fix removes its cause.

**Rule 4 compliance blocker, not a known limitation.** Since spec 019
landed, `random_signal` put exit *i* and entry *i+1* on one row, the 019
harness rejected it, and both callers (`ma_crossover_backtest.baseline_results`
and `multi_ticker_comparison._baseline_rows`) caught the error and printed a
reason in place of the baseline. Every comparison table produced through
either path since 019 has therefore been missing its required random-signal
baseline, silently. 021 lane B fixes the cause in `signals.py` (not frozen;
Camden confirmed 2026-09-18) and restores the baseline for
`ma_crossover_backtest`. `multi_ticker_comparison.py` stays frozen, so its
tables do not get a Rule 4 baseline until the follow-on spec wires capital,
the end-of-data policy and 020 data through it. No table from that script
may be read as Rule 4 compliant before then. The follow-on is **not yet
numbered**: `TODO(spec-NNN, number assigned by Camden): frozen-file
follow-on — Rule 4 blocker`. The `feature_set_comparison.py:367` cast is a
separate defect (NaN-label scoring, not a baseline). It is also frozen and
also handed to that follow-on, and a test-side fix would only hide it.

### D-6 — Lane ownership and overlap

- **The concurrent cost_utils lane.** It touches `test_metrics.py`,
  `test_ml_signal.py`, `metrics.py`, `ml_signal.py` and `test_019_conventions.py`.
  021's lane that owns `test_metrics.py` and `test_ml_signal.py` starts only
  after that lane lands or is abandoned. 021 then re-baselines before editing.
- **Spec 018 T024** owns `routes/backtest.py` and `test_backtest_tearsheet`.
  021's only hunk in `test_reports_api.py` is in `test_ml_rundown`. That is a
  hunk-level split of one file, the same pattern 018 used for its A/B hunks.
- **The `baseline_results` signature (D-3, D-4)** is the interface T024 adopts
  when it reconciles the route. 021 does not edit the route.

### D-7 — `docs/PROJECT_CONTEXT.md` is not edited here

That document quotes results produced under the pre-019 contract:

- the spec 014 comparison table at `:262-275` (purge = 1, embargo = 1, a
  close-based label);
- the spec 005 AAPL run at `:441-446`.

Their source artifacts are gitignored caches that the current code cannot
reproduce. Rule 11 says any PR that touches that surface must regenerate or
remove those figures first. Regeneration needs the frozen follow-on and 020
data. So 021 leaves the file alone.

The stale present-tense contract statements are listed for the docs follow-on:

- `:349-357`: `(label, task, label_horizon)`, "matches the old label exactly";
- `:428`, `:482-483`: `label_horizon=1, embargo_bars=1`;
- `:631`: "the end-of-data close".

Docstrings and comments inside files 021 already edits are in scope (FR-017).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Every remaining red test has a name and an owner (Priority: P1)

Camden runs the full suite after 021 merges. Every failure left is on a short,
enumerated residual list, and each entry names the spec that owns it. There is
no unexplained red and no vacuous green.

**Why this priority**: A suite with 128 unexplained failures cannot gate
anything. Every later spec's "no regressions" claim depends on this one.

**Independent Test**: Run `python -m pytest tests`. Compare the failing IDs to
the residual list under SC-001.

**Acceptance Scenarios**:

1. **Given** 021 merged and the concurrent lane landed, **When** the full
   suite runs, **Then** the failing set equals the 21 residual IDs exactly.
   There are no errors outside it.
2. **Given** a test that loops over baseline summaries, **When** those
   summaries are empty, **Then** the test fails. It does not pass vacuously.

---

### User Story 2 — A reviewer can see that the purge came from the label (Priority: P1)

Camden reads any migrated CV call site. He can tell the purge and embargo
widths came from the label's own availability span, without remembering which
number means what.

**Why this priority**: The rename is deferred (D-1). This is what keeps the
deferral safe. A literal `1` at a call site is how the drift happened.

**Independent Test**: Grep the migrated files for integer literals passed as
`label_horizon=` or `embargo_bars=`. Only label-free splitter unit tests
(`test_walk_forward_cv.py`) may match, and each such hunk says why.

**Acceptance Scenarios**:

1. **Given** a frame from `build_features`, **When** a test runs CV on it,
   **Then** purge and embargo equal the returned span.
2. **Given** a test that builds a labelled frame by hand, **When** it runs CV,
   **Then** it takes the span from `build_target`'s third return.

---

### User Story 3 — The Phase 0 comparison has three real rows (Priority: P2)

Running `ma_crossover_backtest`'s comparison on synthetic data yields three
rows: the strategy, buy-and-hold, and a random baseline that actually ran for
every seed. All three share the same capital, costs and end-of-data policy,
and each of those is stated once.

**Why this priority**: Rule 4. Under 019 the random baseline currently fails
on every seed of the sawtooth fixture, and buy-and-hold would report $0.

**Independent Test**: `baseline_results` on the sawtooth fixture returns 20
random summaries, each with the requested trade count. Buy-and-hold reports one
closed trade, identified in the ledger as a liquidation.

**Acceptance Scenarios**:

1. **Given** any seed and a feasible trip count, **When** `random_signal`
   builds signals, **Then** no row has both flags. The harness accepts the
   frame.
2. **Given** the three runs, **When** the report prints, **Then** capital,
   commission, slippage and end-of-data policy each appear exactly once.

---

### User Story 4 — Migrated gates can still go red (Priority: P2)

Every test that acts as a gate keeps a red control in the same PR (Rule 12).
Gates here include anti-lookahead, leakage, isolation, the non-finite guard and
baseline infeasibility.

**Independent Test**: Each PR's evidence records the planted defect, the gate
failing on it, and the control passing.

**Acceptance Scenarios**:

1. **Given** the migrated scaler-leakage test, **When** the scaler is fitted on
   the whole frame, **Then** the test fails.
2. **Given** the migrated fold-isolation test, **When** outside-row corruption
   reaches the fit, **Then** the visibility control shows it.

---

### User Story 5 — Nothing in a touched file describes the old contract (Priority: P3)

Docstrings and comments in files 021 edits describe the 019 contract: marking
versus liquidation, eligibility masks, open-to-open labels and the span.

**Independent Test**: Review the touched files' docstrings against C1–C7.

### Edge Cases

- **A position still open on the final session.** Under mark-only, the trade
  log is empty and final equity is the marked close. Under liquidation, one
  trade exits at the final close and pays exit costs.
- **Capital below one share's cost.** The entry is rejected and recorded. No
  test may hit this by accident.
- **Zero-trade strategy.** Buy-and-hold under liquidation still reports one
  trade. The random baseline for zero trades is zero trades, not an error.
- **Random trips that exactly fill the frame.** The capacity check accounts for
  the one-row gap and names the bar count it needs.
- **Warm-up rows at the start** have NaN features: not inference-eligible, not
  train-eligible.
- **The final `h+1` rows** have valid features and unknown labels:
  inference-eligible, not train-eligible.
- **Zero-volume rows** give NaN, not inf, in `Rel_Volume`. They are ineligible
  under `scale_free` and still eligible under `levels`.
- **An over-long horizon** (300 on 60 rows): every row is kept, none is
  train-eligible, and the span is 301.
- **Hand-built frames with no span in `attrs`** bypass the library guard, so
  the call site must supply the span.
- **Empty price frame.** The harness refuses it with a named error. The signal
  layer produces no entry, and that "no trade" property is asserted there.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every production and test call to `run_backtest` MUST declare
  `starting_capital` explicitly. Nothing may add a default to the harness.
- **FR-002**: Tests that assert a capital base or flat equity MUST compare
  against the declared capital, never a price-derived figure.
- **FR-003**: Every migrated CV call site on a `build_features` frame MUST pass
  purge and embargo from the returned span, or from
  `frame.attrs["label_availability_span"]`. It MUST NOT pass an integer
  literal. Exempt: splitter unit tests on label-free frames, which state the
  exemption in a comment.
- **FR-004**: A test that builds a labelled frame by hand MUST obtain the span
  from `build_target` and pass it.
- **FR-005**: Target expectations MUST be re-derived by hand from `Open`
  endpoints, with the arithmetic in a comment. Values printed by the code under
  test MUST NOT be pasted in as expectations.
- **FR-006**: Label perturbation tests MUST perturb `Open` and state why that
  is the field the label reads (Rule 12). The re-armed `TestOffByOne` pair MUST
  NOT regress.
- **FR-007**: No consumer may drop rows from a `build_features` frame before
  splitting.
  - Fits use rows that are finite in features and label.
  - Inference uses rows finite in features.
  - `diagnose` uses complete rows of the named set and reports their count.
- **FR-008**: The zero-volume guard MUST be asserted as ineligibility (NaN, not
  inf), with `levels` as the control that keeps those rows eligible.
- **FR-009**: Reporting consumers MUST pass `liquidate` explicitly and
  identically to a strategy and its baselines, and state it once in the
  report.
  - A test about end-of-data exit either passes `liquidate=True` and asserts
    the ledger's liquidation event, or asserts mark-only semantics.
  - The test's own docstring says which.
- **FR-010**: Policy-layer tests MUST assert that the final bar keeps its
  decision. Ending a batch is not a decision.
- **FR-011**: `random_signal` MUST NOT place an exit and an entry on the same
  row. It MUST preserve:
  - the exact trade count;
  - the exact holding length;
  - non-overlap;
  - seeded determinism;
  - a named error when capacity is insufficient.
- **FR-012**: Tests that loop over random-baseline summaries MUST assert the
  expected count before looping.
- **FR-013**: Synthetic fixtures that feed the funded ledger MUST declare
  `price_basis="unadjusted_dollars"` and use strictly positive prices. No
  production code in 021 sets `price_basis`.
- **FR-014**: Empty-frame and non-positive-price refusals MUST be asserted as
  named errors. "No trade" is asserted at the signal layer.
- **FR-015**: The `performance_summary` key-set test MUST match 019 unit 6's
  keys. The non-`RangeIndex` test MUST assert that the index is preserved and
  that the curve matches a `RangeIndex` twin.
- **FR-016**: The D-2 re-anchoring MUST keep:
  - the level-feature equivalence;
  - a pinned label divergence;
  - the "tuning is the only divergence" property, against
    `fit_predict_walk_forward`.

  **Gated on D-2.**
- **FR-017**: Docstrings and comments in every file 021 edits MUST NOT describe
  pre-019 behavior.
- **FR-018**: `test_ml_rundown` MUST assert that `as_of_date` equals the final
  session in the fixture cache (finding 23, consumer half).
- **FR-019**: 021 MUST NOT edit:
  - the library modules listed under [Why this spec exists](#why-this-spec-exists);
  - `feature_set_comparison.py` or `multi_ticker_comparison.py`;
  - `routes/backtest.py`;
  - `requirements*.txt`;
  - `docs/PROJECT_CONTEXT.md`.
- **FR-020**: Shared test fixtures MUST NOT change signature or output in 021:
  - `test_backtest_harness.make_signalled_prices`;
  - `test_ma_crossover_backtest.{make_prices, sawtooth_prices, COSTS}`;
  - `test_logistic_baseline._synthetic_features`.

  Fixes go at call sites.

### Key Entities

- **Contract delta (C1–C7)**: one 019 behavior change. It has a library site
  and a consumer obligation.
- **Call site**: a production line or test that consumes a delta. It has one
  delta per failure layer, a lane, and a status.
- **Residual failure**: a failing test outside 021's scope. It has an ID, a
  cause and an owning spec.
- **Decision (D-1 to D-7)**: a scoping choice. It has a recommendation, the
  rejected alternative, and whether it gates tasks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After 021 and the concurrent lane land, `python -m pytest tests`
  fails on exactly these 21 tests and no others, with zero errors outside
  them:
  - `test_feature_set_comparison.py` (12):
    - `TestParentSideThreadPinning::test_the_orchestrator_leaves_this_process_unpinned`
    - `TestSynchronousPathCreatesNoProcesses` × 2
    - `TestSerialParallelEquivalence` × 9, as setup errors
  - `test_multi_ticker_comparison.py` (8): every currently failing test.
  - `test_reports_api.py::TestReportsApi::test_backtest_tearsheet` (1).

  The IDs are in `plan.md` R-1. If an owner fixes one first, the list shrinks.
  It never grows.
- **SC-002**: Zero integer literals are passed as `label_horizon=` or
  `embargo_bars=` in files 021 edits, outside exempted splitter hunks.
- **SC-003**: Every migrated gate test (US-4) has recorded red evidence against
  a planted defect, plus a passing control.
- **SC-004**: On the sawtooth fixture:
  - 20 of 20 random seeds run;
  - each seed has the requested trade count;
  - buy-and-hold reports 1 closed trade;
  - the report states capital, costs and end-of-data policy exactly once each.
- **SC-005**: Every PR changes at most 400 production and test lines. That is
  019's review budget.
- **SC-006**: No test is deleted without a named replacement in the same PR.
  The collected-test count does not fall by more than the retirements listed
  in D-2.
- **SC-007**: 021 reports no strategy metric. No Sharpe, P&L or accuracy figure
  is quoted in any 021 PR as a result, so constitution PR requirements 3 and 4
  are not triggered.

## Assumptions

- The 019 library is correct, as the request states. Where a consumer and the
  library disagree, the consumer moves. REVIEW_019 and
  `DIAGNOSIS_HORIZON_OFFBYONE.md` agree.
- The concurrent cost_utils lane lands before 021's lane A starts. If it is
  abandoned instead, lane A re-baselines and proceeds.
- Codex's embargo fix in the two frozen files is final for 021's purposes.
- `10_000.0` is a proposed capital assumption for the Phase 0 and Phase 2
  scripts (D-4). Changing it changes no closed-trade P&L at one share. It
  changes only the capital-relative metrics.
- Implementation re-runs the baseline first. The counts here describe the tree
  at 2026-09-18 16:34:38 EDT.
