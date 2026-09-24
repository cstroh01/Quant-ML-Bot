---

description: "Task list: wire funded-ledger callers to the unadjusted pipeline"
---

# Tasks: Wire Funded-Ledger Callers to the Unadjusted Pipeline

**Spec number**: NNN, a placeholder. **Camden assigns it** (the 021 T055
convention). Rename the directory when it is assigned. No test file name
carries the number, so the rename touches only this directory.

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/cli-and-api.md](contracts/cli-and-api.md),
[quickstart.md](quickstart.md)

**Tests are required.** Rule 5 (time), Rule 12 (red before green), FR-009 and
FR-011 all demand them. In each story, write the tests first, watch them fail,
then implement.

**No `git`.** No task runs it. Camden commits.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (a different file, and no dependency on an incomplete task)
- **[D-3]**: drop this task if Camden rejects spec D-3

---

## Phase 0: Gate (blocks everything)

- [ ] T001 Camden signs off on spec D-1 through D-7 (D-7 is recorded here but implemented under spec 020 or the Norgate-adapter spec) and assigns the spec number. Record each answer in the **Status** line of `.specify/specs/NNN-unadjusted-caller-wiring/spec.md`, and rename the directory. Also record a pointer to this spec in the "020 wiring" bullet of spec 021's T055 handoff (`.specify/specs/021-finish-spec-019-migration/tasks.md`). If D-3 is accepted, mark 018 T024 "superseded by NNN" in `.specify/specs/018-terminal-truthfulness/tasks.md`. **Camden's call; an agent does not do this.**

## Phase 1: Setup

- [ ] T002 Run `python -m pytest tests -q` from the repo root. Paste the failing test IDs and the pass/fail counts into [Evidence → Baseline](#baseline) below. This is the SC-006 reference.
- [ ] T003 Create `tests/unadjusted_fixtures.py`. This is a helper, **not** a test-module name, so the collection guard accepts it. It provides:
  - `StubSource`: an adapter shaped like `SyntheticSource` in `tests/test_020_unadjusted_price_data.py:50-70`;
  - `session_prices(ticker, start, end, closes)`: dates come from `data.trading_days(start, end)` (research R-5: the bundle validator requires a complete session calendar);
  - `publish_bundle(root, ticker, prices, actions=None) -> Path`: calls `data.cache_unadjusted_market_data(..., created_by_revision="unadjusted-wiring-synthetic", cache_dir=root)`.

  Include one ready-made series: at least 60 sessions, with a 2:1 split near the middle, and nominal `Close` exactly halving on the ex-date so that `_validate_split_discontinuities` passes.

## Phase 2: Foundational — the `data.py` entry point (blocks US1 and US2)

**Contract:** [contracts §3](contracts/cli-and-api.md#3-scriptsdatapy-public-additions) and [data-model](data-model.md).

- [ ] T004 [P] Write the resolver and loader tests in `tests/test_unadjusted_caller_wiring.py`. Each one must fail before T005. Cases:
  - (a) the cache directory is absent, giving `missing`;
  - (b) the directory is empty, giving `missing`;
  - (c) two `AAPL_*` bundles, giving `ambiguous`, with both paths in `check`, sorted;
  - (d) bundles for `A` and `AA`: resolving `A` returns only `A`'s manifest;
  - (e) the ticker `../x`, giving `invalid`, with no filesystem access (assert via a `cache_dir` that does not exist *and* a patched `Path.iterdir` that raises);
  - (f) lowercase `aapl` resolves `AAPL`;
  - (g) a byte flipped in the data CSV after publishing: `load_unadjusted_for_ticker` raises `invalid`, and `check` contains `"data file hash check failed"`;
  - (h) a valid bundle: the returned frame has `attrs["price_basis"] == "unadjusted_dollars"` and a `source_manifest_sha256`;
  - (i) `isinstance(err, LookupError)` and `not isinstance(err, ValueError)`.
- [ ] T005 Implement `UnadjustedDataUnavailable`, `resolve_unadjusted_manifest` and `load_unadjusted_for_ticker` in `scripts/data.py`, beside `load_unadjusted_market_data`.
  - Follow research R-2 (exact-stem regex) and R-3: wrap only the loader call, and chain with `from error`.
  - Edit no existing function in `data.py`.
  - Docstrings state the guarantees: no network access, no writes, no fallback.

**Checkpoint:** T004 is green. `test_020_unadjusted_price_data.py` and `test_data.py` are unchanged and still pass.

---

## Phase 3: User Story 1 — The Phase 0 crossover runs on declared dollars or says why not (P1) 🎯 MVP

**Goal:** `ma_crossover_backtest.main()` funds only on a validated bundle. With no bundle, it exits nonzero with the named message and leaves no side effects.

**Independent test:** `python -m pytest tests/test_unadjusted_caller_wiring.py -k "cli or signal"`.

### Tests (write first; each must fail before T010–T012)

- [ ] T006 [P] [US1] Signal-basis test in `tests/test_unadjusted_caller_wiring.py`.
  - Use the T003 split series with a `short_window`/`long_window` pair chosen so the nominal halving *would* cross the SMAs.
  - Assert that `research_close_signal` emits no `Sell_Next_Open` on the session after the split.
  - Control: `sma_crossover_signal` on the nominal frame does emit one. Both assertions live in the same test, so the fixture provably exercises the case.
  - Also assert the returned frame keeps the nominal `Close` and `Open` and the `price_basis` attr.
- [ ] T007 [P] [US1] CLI unavailable tests in `tests/test_unadjusted_caller_wiring.py`. Call `ma_crossover_backtest.main([], cache_dir=<empty tmp>)` and assert that:
  - it raises `UnadjustedDataUnavailable` and its `str` contains `"AAPL"` and `"unavailable"`;
  - `data.download_market_data` is never called (patched to raise);
  - `ma_crossover_backtest.cache_path` is never called (patched to a spy);
  - the injected synthetic trial ledger file is byte-identical before and after (research R-7).

  Add a subprocess case: `python scripts/ma_crossover_backtest.py`, with its data directory redirected, exits with 1 and prints the message to stderr. If redirecting the default directory in a subprocess proves impractical, cover the `__main__` conversion with a unit test of the small wrapper function instead, and record the substitution in Evidence.
- [ ] T008 [P] [US1] CLI success test in `tests/test_unadjusted_caller_wiring.py`.
  - Use one synthetic AAPL bundle in tmp, and patch `ma_crossover_backtest.cache_path` to point into tmp.
  - Spy on `ma_crossover_backtest.run_backtest`: every call's `prices.attrs["price_basis"] == "unadjusted_dollars"`, and every call's `source_manifest_sha256` is equal.
  - stdout contains `source_name`, `capital_gate_eligible` and every `source_limitations` string (FR-008).
  - `--manifest <path>` bypasses the resolver: it succeeds even with a second, ambiguous bundle present.
- [ ] T009 [P] [US1] Static test in `tests/test_unadjusted_caller_wiring.py`. Parse `scripts/ma_crossover_backtest.py` with `ast` and assert that no `download_market_data` name or import appears anywhere in it (SC-003).

### Implementation

- [ ] T010 [US1] Add `research_close_signal(nominal, short_window, long_window)` to `scripts/ma_crossover_backtest.py`, per research R-4 and contracts §4. It calls `data.execution_price_frame` and `signals.sma_crossover_signal`. It leaves `signals.py` untouched.
- [ ] T011 [US1] Rewrite `main()` in `scripts/ma_crossover_backtest.py` as `main(argv=None, *, cache_dir=UNADJUSTED_CACHE_DIR)`:
  - an `argparse` option `--manifest`;
  - `load_unadjusted_for_ticker(TICKER, cache_dir, manifest_path=...)` **before** `research_attempt` (D-5);
  - then `research_close_signal`.
  - Remove the `download_market_data` import at `:13`.
  - Print the provenance header (data-model, "Provenance").
  - The `if __name__ == "__main__":` block catches `UnadjustedDataUnavailable` and raises `SystemExit(str(error))`.
  - Keep `baseline_results` and `mean_holding_bars` signatures unchanged (021 contracts §1).
- [ ] T012 [US1] Fix the figure in `scripts/ma_crossover_backtest.py` `main()` (FR-010). The current single panel labels nominal prices "Adjusted close" and "Adjusted price (USD)".
  - **Top panel:** `Research_Close` with `Short_SMA_Research` and `Long_SMA_Research`, labelled "Causal total-return index (research units)".
  - **Bottom panel:** nominal `Open`, with buy and sell markers at fill sessions, labelled "Nominal price (USD)".
  - Keep the existing comment explaining why markers sit on the Open.
  - Update the module docstring: it now needs a spec 020 bundle.

**Checkpoint:** T006–T009 are green. `tests/test_ma_crossover_backtest.py` still passes unchanged: it never calls `main()` (`:3`).

---

## Phase 4: User Story 2 — The tearsheet reports *unavailable* instead of crashing (P1) [D-3]

**Goal:** `GET /api/backtest/tearsheet` returns 503 with the documented detail when no bundle is usable, and 200 with provenance on a valid one.

**Independent test:** `python -m pytest tests/test_reports_api.py -v`.

**Depends on:** Phase 2, plus T010 (it imports `research_close_signal`). Ship it as PR-2, after PR-1 has merged.

### Tests (write first)

- [ ] T013 [P] [US2] [D-3] In `tests/test_reports_api.py`, remove the hand stamp `self.panel.attrs["price_basis"] = "unadjusted_dollars"` at `:28` (research R-5). In `test_backtest_tearsheet`, publish one synthetic AAPL bundle via `tests/unadjusted_fixtures.publish_bundle` into `<fixture cache dir>/unadjusted/`. Keep the existing assertions. Add these:
  - the seven new fields from contracts §2 are present;
  - `capital_gate_eligible is False`;
  - `source_manifest_sha256` matches the published manifest.

  Check that the `fixture_client` helper exposes its cache directory. If it does not, extend the helper minimally and note that in Evidence.
- [ ] T014 [P] [US2] [D-3] Add three tests to `tests/test_reports_api.py` — `test_tearsheet_503_missing`, `test_tearsheet_503_ambiguous` and `test_tearsheet_503_invalid` (a tampered hash). Each asserts `status_code == 503` and the full detail shape from contracts §2. Add a fourth for `ticker=../x`, asserting a 503 with `reason == "invalid"`.

### Implementation

- [ ] T015 [US2] [D-3] Add the seven provenance and account fields to `BacktestTearsheetResponse` in `reports/api/schemas.py`. Leave `services/api.ts` unchanged: the fields are additive.
- [ ] T016 [US2] [D-3] Rewrite the data path in `reports/api/routes/backtest.py`:
  - replace `get_cached_ticker_data` with `load_unadjusted_for_ticker(ticker, cache_dir / "unadjusted")`, called before `research_attempt`;
  - map `UnadjustedDataUnavailable` to `HTTPException(status_code=503, detail={...})`, per contracts §2;
  - build the signal with `research_close_signal`;
  - pass `starting_capital=STARTING_CAPITAL` and `liquidate=LIQUIDATE_AT_END`, imported from `ma_crossover_backtest`, to `run_backtest`, `baseline_results`, `equity_curve` and `performance_summary`;
  - populate the new response fields from the frame's attrs;
  - remove the `get_cached_ticker_data` import. Leave `routes/data.py` untouched.

**Checkpoint:** T013–T014 are green. The other `test_reports_api` tests are unchanged and pass.

---

## Phase 5: User Story 3 — No funded path can reach adjusted prices (P2)

**Goal:** prove that the invariant can go red (Rule 12).

- [ ] T017 [US3] Create `tests/mutation/run_unadjusted_wiring_mutants.py`, modelled on `tests/mutation/run_spec_018_mutants.py`. Its rules:
  - copy the tree to a temp directory, and apply one mutant per run;
  - run the focused pytest selection for that mutant, and require a nonzero exit;
  - run an unmutated control, and require exit 0;
  - hash the source before and after, and require them to be identical.

  Its mutants are the rows of research R-6. Drop the two `[D-3]` rows if D-3 was rejected.
- [ ] T018 [US3] Run T017. Record each mutant as KILLED or SURVIVED, plus the control result, in [Evidence → Mutants](#mutants). A survivor blocks the merge until its test is strengthened.

---

## Phase 6: Polish and gate

- [ ] T019 [P] Update `.specify/specs/NNN-unadjusted-caller-wiring/quickstart.md` if any test name or command changed during implementation.
- [ ] T020 Run `python -m pytest tests`. Compare against the T002 baseline, and record the diff in [Evidence → Gate](#gate). The only permitted changes are: `test_backtest_tearsheet` moves from error to pass (if D-3 was accepted), and new tests pass (SC-006).
- [ ] T021 Run the quickstart §6 manual smoke test against the real, empty `data/cache/unadjusted/`. Record the stderr line and the exit code. Confirm `docs/trials/trials.jsonl` has the same line count before and after (SC-001).
- [ ] T022 Draft the PR description(s), per CLAUDE.md:
  - the spec number;
  - what changed and why it is correct;
  - "no metrics reported: real data is unavailable (B-1); synthetic P&L is a test oracle" (SC-005);
  - "no new dependencies".

  Name B-1 and F-1 explicitly as open. **Do not open the PR or run `git`.** Hand the text to Camden.
- [ ] T023 Update the **Status** line in `spec.md`: implemented tasks, the PR(s), and the residual items (B-1 → spec 020 Q1; F-1 → Rule 14 follow-on; D-4 → `logistic_baseline.py` after 021 D-2).

---

## Dependencies and execution order

```
T001 (Camden) → T002, T003 → T004 → T005 ─┬─→ US1: T006–T009 [P] → T010 → T011 → T012 ──┐
                                          │                                            ├─→ T017 → T018 → T019–T023
                                          └─→ US2 [D-3]: (needs T010) T013, T014 [P] → T015 → T016 ┘
```

- **PR-1** = T002–T012, plus the US1 half of T017/T018.
- **PR-2** = T013–T016, plus the D-3 half of T017/T018. It lands after PR-1.
- US3 depends on both stories, because its mutants target their code.

### Parallel opportunities

- T004 runs alongside T003 once the fixture API is agreed. Both are test-side.
- T006, T007, T008 and T009 touch distinct test functions in one file. Write
  them together, and run them red together.
- T013 and T014 together. T015 runs alongside the test tasks, since it only
  touches the schema file.

## Implementation strategy

1. **MVP = Phase 2 + US1 (PR-1).** It closes the gap the trial registry
   recorded. The CLI now names the unavailable state and stops logging errored
   trials for it.
2. **PR-2** turns the tearsheet's 500 into a documented 503, and closes 018
   T024.
3. **Afterwards, outside this spec:** once spec 020 Q1 names a payment-date
   source, a real AAPL bundle can be published, and this wiring runs green
   with no further code change. Rule 14 (F-1) must still be satisfied before
   any figure from it is reported.

---

## Evidence

### Baseline

(T002)

### Mutants

| Mutant (R-6) | Result | Test that killed it |
|---|---|---|

### Gate

| Criterion | Result |
|---|---|
| SC-001: CLI unavailable → nonzero, 0 files, 0 trial lines | |
| SC-002: tearsheet 503 on missing; 200 on synthetic bundle | |
| SC-003: 0 `download_market_data` references in in-scope files | |
| SC-004: every gate red + green | |
| SC-005: no metric quoted | |
| SC-006: no new failures vs. T002 | |
