---

description: "Task list for spec 017 — position sizing and portfolio risk layer"
---

# Tasks: Position Sizing and Portfolio Risk Layer

**Input**: Design documents from `.specify/specs/017-position-sizing-risk/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/portfolio-risk-module.md, quickstart.md

**Tests**: Required. The constitution (Rules 1 and 5) and spec FR-018 make
them part of the deliverable, and SC-008 requires a mutation check. Tests are
written before the code they cover and are confirmed failing first.

**Organization**: Grouped by user story. All three stories are P1; they are
ordered by dependency (sizing produces the weights correlation adjusts; the
halt clamps the result). The composing function and the end-to-end halt test
come after all three.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3 — maps to spec.md's user stories
- Only two source files change: `scripts/portfolio_risk.py` and
  `tests/test_portfolio_risk.py`. Tasks touching the same file run in order.

---

## Phase 1: Setup

**Purpose**: Baseline and skeletons.

- [X] T001 Record the baseline: run `./venv/Scripts/python.exe -m unittest discover -s tests` from the repo root before any change and note the count (expected 416, OK) — **416 tests, OK, 138.6 s.**
- [X] T002 Create `tests/test_portfolio_risk.py` with its module docstring, imports, and shared helpers (`sessions`, `panel_from_returns`, `hadamard`, `random_panel`, `config`, `LIMITS`)
- [X] T003 Confirm the new test module fails to import before `scripts/portfolio_risk.py` exists (TDD red) — **Recorded honestly: this check was not valid as run.** It was invoked as `python -m unittest tests.test_portfolio_risk`, which does not put `tests/` on `sys.path`, so it failed on `import context` — before it ever reached the missing module. The same invocation error surfaced on the first green attempt and was corrected to `discover -s tests -p test_portfolio_risk.py` (the repo's own convention; `quickstart.md` was fixed too). The evidence that these tests fail against broken code is T030's mutation check, not this task.

---

## Phase 2: Foundational (blocking)

**Purpose**: Configuration, validation, and returns — everything the three stories share.

- [X] T004 [P] Write `SessionIndexValidationTests`, `LogReturnTests`, `RiskConfigValidationTests`, `ModuleBoundaryTests` in `tests/test_portfolio_risk.py`
- [X] T005 Create `scripts/portfolio_risk.py` with the module docstring and exactly the import set `__future__, dataclasses, numpy, pandas, constants` (FR-013)
- [X] T006 Implement `RiskConfig` and `RECOMMENDED_CONFIG` with `__post_init__` validation (FR-016) in `scripts/portfolio_risk.py`
- [X] T007 Implement `_validate_sessions`, `_session_label`, `_validate_panel`, `_aligned` (FR-015, label alignment) in `scripts/portfolio_risk.py`
- [X] T008 Implement `log_returns` (positional, gap-aware) in `scripts/portfolio_risk.py`

**Checkpoint**: foundational tests pass.

---

## Phase 3: User Story 1 — sized off conviction and volatility (P1) 🎯 MVP

**Goal**: A standalone weight per ticker from confidence and realized volatility; no Kelly path.

**Independent Test**: `VolatilityTargetSizingTests` and `RealizedVolatilityTests` pass on hand-built inputs with no other story implemented.

### Tests for User Story 1

- [X] T009 [P] [US1] Write `RealizedVolatilityTests` (independent recomputation, first valid row is exactly `window`, std-not-variance, future perturbation bit-identical + control, missing-bar re-warm) in `tests/test_portfolio_risk.py`
- [X] T010 [P] [US1] Write `VolatilityTargetSizingTests` (literal expected weights, halving, zero/missing confidence and volatility, range checks, label alignment) and `NoKellyPathTests` (FR-002, by AST) in `tests/test_portfolio_risk.py`

### Implementation for User Story 1

- [X] T011 [US1] Implement `realized_volatility` (trailing, `ddof=1`, `sqrt(252)`, full window or missing) in `scripts/portfolio_risk.py`
- [X] T012 [US1] Implement `volatility_target_weights` (uncapped; missing → 0; non-positive vol → 0) in `scripts/portfolio_risk.py`

**Checkpoint**: US1 tests pass.

---

## Phase 4: User Story 2 — correlated names share one risk budget (P1)

**Goal**: Overlap division and the book-level gross cap.

**Independent Test**: `CorrelationAdjustmentTests`, `ExAnteVolatilityTests`, `GrossCapTests` pass on hand-built correlation matrices.

### Tests for User Story 2

- [X] T013 [P] [US2] Write `TrailingCorrelationTests` (vs `numpy.corrcoef`, short history, exactly one window, future perturbation + control, missing bar, exact 0 and 1 from Hadamard patterns) in `tests/test_portfolio_risk.py`
- [X] T014 [P] [US2] Write `CorrelationAdjustmentTests` (`ρ=1` halves, `ρ=0` unchanged, `ρ<0` unchanged, inactive not counted, never increases over seeded random matrices, diagonal rounding, undefined-correlation raise) and `ExAnteVolatilityTests` (SC-005) in `tests/test_portfolio_risk.py`
- [X] T015 [P] [US2] Write `GrossCapTests` (unchanged below, proportional above, sum equals cap) in `tests/test_portfolio_risk.py`

### Implementation for User Story 2

- [X] T016 [US2] Implement `trailing_correlation` (truncate at session first) in `scripts/portfolio_risk.py`
- [X] T017 [US2] Implement `position_overlap` and `correlation_adjusted_weights` (diagonal forced to 1, clip to `[0, 1]`, active-only) in `scripts/portfolio_risk.py`
- [X] T018 [US2] Implement `apply_gross_cap` in `scripts/portfolio_risk.py`

**Checkpoint**: US1 and US2 tests pass.

---

## Phase 5: User Story 3 — loss caps halt new entries automatically (P1)

**Goal**: The streaming guard, its whole-series view, and the halt clamp.

**Independent Test**: `LossCapGuardTests`, `LossCapHistoryTests`, `EntryHaltTests` pass on hand-built equity paths and weight vectors.

### Tests for User Story 3

- [X] T019 [P] [US3] Write `EntryHaltTests` (open and add blocked; reduce and exit allowed; validation) in `tests/test_portfolio_risk.py`
- [X] T020 [P] [US3] Write `LossCapGuardTests` (first session; daily one-session halt; inclusive boundary exact and one ulp inside, daily and weekly; weekly latch; weekly drawdown; anchor inside the high-water mark; Monday gap; holiday week; ISO year boundary; missing week; ordering, equity, session and limit validation; rejected observation leaves state unchanged) in `tests/test_portfolio_risk.py` — **Extended:** an exact-boundary test for the weekly *drawdown* cap was added after the first draft, so a strict-boundary defect on that cap has a test to fail too (T030 mutant "strict weekly drawdown boundary").
- [X] T021 [P] [US3] Write `LossCapHistoryTests` (streaming equals history; future perturbation + control; empty series) in `tests/test_portfolio_risk.py`

### Implementation for User Story 3

- [X] T022 [US3] Implement `apply_entry_halt` in `scripts/portfolio_risk.py`
- [X] T023 [US3] Implement `LossCapStatus` and `LossCapGuard` (validate before mutating; transition per data-model.md) in `scripts/portfolio_risk.py`
- [X] T024 [US3] Implement `loss_cap_history` by running one fresh guard (no second implementation) in `scripts/portfolio_risk.py`

**Checkpoint**: all three stories pass independently.

---

## Phase 6: Composition and end-to-end

**Purpose**: The one-call decision, and proof the stories work together.

- [X] T025 [P] Write `TargetWeightsCompositionTests` (per-step columns and attrs; future perturbation bit-identical + control; warm-up flat; boundary at exactly one window; correlation window longer than volatility window; missing bar; all flat; label order; invariants; halted path) in `tests/test_portfolio_risk.py`
- [X] T026 [P] Write `CapOrderingTests` (US2 #6) and `FiveTickerUniverseTests` (SC-004 on `multi_ticker_comparison.TICKER_UNIVERSE`) in `tests/test_portfolio_risk.py` — **Corrected before the first run:** one control assertion compared the cluster's summed standalone weight against three times its own mean, which is true by arithmetic and so tested nothing. It now compares against the cluster's *post-adjustment* total.
- [X] T027 [P] Write `AutomaticHaltIntegrationTests` (single-name crash in a synthetic loop halts entries with no manual flag; nothing grows while halted; the crashed name still exits; entries resume the next week) in `tests/test_portfolio_risk.py`
- [X] T028 Implement `target_weights` (truncate → estimate → sizeable mask → standalone → cap → overlap → gross → halt) in `scripts/portfolio_risk.py`

**Checkpoint**: `test_portfolio_risk.py` passes in full — **125 tests, OK, 1.6 s**, first run after the invocation fix.

---

## Phase 7: Evidence and polish

- [X] T029 Run the full suite; record the count, confirm no network and no new dependency (SC-009) — **541 tests, OK, 160.8 s** (416 baseline + 125 new). No network: every new test builds its data in memory. No new dependency: `requirements.txt` untouched; the module imports only `numpy`, `pandas`, `dataclasses`, and `constants`.
- [X] T030 Mutation check (SC-008): run every mutant from a scratchpad runner against `tests/test_portfolio_risk.py`, with an unmutated control; hash `scripts/portfolio_risk.py` before and after; record the table here

  Each mutant was a *copy* of the module placed ahead of `scripts/` on
  `sys.path` in a fresh interpreter; the repo file was never edited. SHA-256
  before and after: `a6b9818d…0914`, identical. No `git` (Rule 10).

  **Control (no mutation): 125 run, 0 failed. Survivors: none (21 of 21 caught).**

  | # | Injected defect | SC-008? | Test methods failed |
  |---|---|---|---|
  | 1 | per-name cap applied after the correlation step | yes | 2 |
  | 2 | negative correlations not clipped | yes | 4 |
  | 3 | inactive names counted in the overlap | yes | 4 |
  | 4 | variance used in place of volatility | yes | 3 |
  | 5 | volatility window reads one bar ahead | yes | 18 |
  | 6 | strict daily loss boundary | yes | **1** |
  | 7 | strict weekly loss boundary | yes | **1** |
  | 8 | strict weekly drawdown boundary | yes | **1** |
  | 9 | weekly halt un-latches on recovery | yes | 3 |
  | 10 | weekly anchor = this week's first close | yes | 8 |
  | 11 | halt only blocks opening from flat | yes | 3 |
  | 12 | halt also blocks exits (freezes the book) | yes | 4 |
  | 13 | missing confidence treated as full conviction | yes | **1** |
  | 14 | zero volatility sized (cap would bind) | yes | **1** |
  | 15 | overlap diagonal not forced to exactly 1 | extra | 2 |
  | 16 | weekly high-water mark excludes the anchor | extra | **1** |
  | 17 | daily return measured against the week anchor | extra | 5 |
  | 18 | correlation reads the untruncated panel (Rule 1 leak) | extra | 7 |
  | 19 | composition reads the untruncated panel (Rule 1 leak) | extra | 5 |
  | 20 | gross cap clips each name instead of scaling the book | extra | **1** |
  | 21 | timezone-aware session labels accepted | extra | **1** |

  **Thinnest margins, stated rather than smoothed over:** eight mutants are
  caught by exactly one test method. The three strict-boundary mutants are
  one-test by construction — only an exactly-representable boundary value can
  tell `<` from `<=`, and each cap has one such test. The other five (missing
  confidence, zero volatility, anchor in the high-water mark, gross-cap
  clipping, aware labels) each guard a single line with a single direct test;
  none is exercised a second time through `target_weights`, because the
  composition's own "sizeable" mask would hide two of them there. A reviewer
  should read those five tests as the only thing standing between the line
  and its defect.

  #8 is caught only because an exact-boundary test for the weekly drawdown
  cap was added during T020. Before it, every drawdown test sat well away
  from its limit (−5.29%, −5.1% against 5%), so by inspection that mutant had
  nothing to fail against. This was reasoned from the tests, not demonstrated
  by running the mutant without the new test.
- [X] T031 Real-data sizing diagnostic on the cached ten-year universe (`data/cache/AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv`): overlap and gross exposure at full conviction — no return, Sharpe, or P&L

  Read straight from the CSV (no network path), 2,514 sessions 2016-09-06 → 2026-09-04, 2,451 sized. `RECOMMENDED_CONFIG`, all five names at confidence 1.0, starting flat, no halt.

  | Measure | p10 | median | p90 |
  |---|---|---|---|
  | mean overlap per held name | 2.20 | **3.24** | 4.02 |
  | gross after per-name cap | — | 1.22 | — |
  | gross after overlap step | 0.27 | **0.38** | 0.57 |
  | share of exposure the overlap step removes | — | **69%** | 75% |

  - Max overlap 4.48 (2020-05-20); 4.44 in the window around 2020-03-16; 3.71 around 2025-04-08 — the correlation spike in market-wide sell-offs is visible, and those are the sessions the adjustment cuts hardest.
  - Gross cap never bound (0 sessions): the overlap step alone keeps a full-conviction book well under 1.0.
  - Last session (2026-09-04): median pairwise correlation 0.15 — a low-correlation regime. Targets AAPL 0.218, NVDA 0.177, MSFT 0.117, GOOGL 0.115, AMZN 0.099; gross 0.73.
  - **Flag, not a fix:** removing a median 69% of full-conviction exposure is aggressive. It is what the rule says (five names behaving like ~1.5 independent bets), but whether overlap division should be softened — e.g. toward portfolio-vol scaling — is Camden's call once a costed backtest exists. Recorded as an open question.
- [X] T032 Run quickstart §3 (the halt example) and confirm its stated output — **Matches:** 09-09 halted (daily −3.54%, weekly −4.5%); 09-10 and 09-11 recover and stay halted on the weekly latch.
- [X] T033 [P] Add a spec 017 section to `docs/PROJECT_CONTEXT.md` — **Written in the night run** (top of the file, above spec 015); ticked on resumption. Two flags added on resumption (T035).
- [X] T034 [P] Write `NIGHT_RUN_SUMMARY.md` at the repo root: what was built, open questions, final test count — **Written in the night run**; the run ended right after writing it, before ticking T033/T034. A *Resumption* section was added on 2026-09-12.
- [X] T035 Resumption re-verification (added 2026-09-12, second session; no `git`)

  The night run left every deliverable on disk but no transcript, and its
  mutation runner lived in a scratchpad that no longer exists. So its two
  headline claims were re-checked rather than carried forward:

  - **Full suite:** 541 collected, `OK`, 160.9 s — matches T029.
  - **Mutation check, rebuilt from T030's table** (re-implemented from the
    descriptions, not byte-identical to the night's mutants): control 125
    run, 0 failed; **21 of 21 caught**; module SHA-256 `a6b9818d…0914`
    before and after, the same hash T030 recorded. The same eight mutants
    are caught by exactly one test (#6, #7, #8, #13, #14, #16, #20, #21).
    Counts for the others differ from T030 because this runner counted
    failing test IDs including subtests, not methods.
  - **Two findings from `docs/audit-2026-09-12/probes.py` reproduced** (a
    separate audit, not this spec's work), recorded as open questions in
    `NIGHT_RUN_SUMMARY.md` rather than fixed, because each is a spec change:
    a dust-size position halves its correlated neighbours (FR-005 counts
    held names by presence, not size), and a freshly constructed guard
    forgets a mid-week latch (replaying equity through `loss_cap_history`
    rebuilds it correctly).
  - Stale text fixed: checklist note (FR-011 → FR-013; clarification markers
    resolved), plan's mutant count, spec status.

---

## Dependencies & Execution Order

### Phase dependencies

- Phase 1 → Phase 2 → Phases 3, 4, 5 → Phase 6 → Phase 7.
- Phase 4's `position_overlap` does not need Phase 3's code, but its tests
  build weights by hand, so US2 can be verified without US1.
- Phase 5 needs only Phase 2.
- Phase 6 needs all of 3, 4, 5.

### Within each story

Tests first, confirmed failing; then implementation; then the checkpoint.

### Parallel opportunities

Every test-writing task is `[P]` with respect to the module file, but all
test tasks share `tests/test_portfolio_risk.py` and all implementation tasks
share `scripts/portfolio_risk.py`, so within a single agent they run in
sequence. `T033` and `T034` touch different files and are genuinely parallel.

---

## Parallel Example: User Story 3

```text
Task: "Write EntryHaltTests in tests/test_portfolio_risk.py"
Task: "Write LossCapGuardTests in tests/test_portfolio_risk.py"
Task: "Write LossCapHistoryTests in tests/test_portfolio_risk.py"
# then, in order, in scripts/portfolio_risk.py:
Task: "Implement apply_entry_halt"
Task: "Implement LossCapStatus and LossCapGuard"
Task: "Implement loss_cap_history"
```

---

## Implementation Strategy

### MVP first

Phase 1 + 2 + 3 gives a sized book with no correlation awareness and no
halt. It is testable alone, but it is **not** safe to use alone: US2 exists
because US1 by itself builds a concentrated sector bet in this universe.

### Incremental delivery

1. Setup + Foundational.
2. US1 → sizing verified.
3. US2 → correlation and gross cap verified.
4. US3 → halt verified.
5. Composition + integration → the three verified together.
6. Evidence: suite, mutations, real-data diagnostic, docs.

---

## Notes

- No `git`, including read-only commands (Rule 10). Restores and "did the
  file change" questions are answered by hashing, not by version control.
- No task here computes a return, Sharpe, or P&L.
