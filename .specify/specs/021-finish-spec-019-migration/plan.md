# Implementation Plan: Finish the Spec 019 Migration (Consumer Side)

**Branch**: `021-finish-spec-019-migration` | **Date**: 2026-09-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `.specify/specs/021-finish-spec-019-migration/spec.md`

**Artifacts**: [research.md](research.md), with the per-test inventory in R-1 ·
[data-model.md](data-model.md) · [contracts/consumer-interfaces.md](contracts/consumer-interfaces.md) ·
[quickstart.md](quickstart.md) · `tasks.md` (next phase)

## Summary

Move every consumer of the spec 019 library contract onto that contract,
without editing the library.

**The five changes are really seven** (C1–C7). The two additions come from
harness input validation (C6) and the metrics schema (C7).

**The work.**

- **Production:** 4 files:
  - `signals.py`;
  - `ma_crossover_backtest.py`;
  - `logistic_baseline.py`, its reporting hunks only;
  - `feature_diagnostics.py`.
- **Tests:** 10 files, 107 failing tests. One more test that would pass
  vacuously once C1 is fixed is caught by the same work.
- **Residual:** 21 failures stay red, each with a named owner: the two frozen
  files' tests, and 018 T024's tearsheet.

**Approach.** Six lanes with exclusive file ownership, A–E and G, plus a
fixture freeze that lets A–E run concurrently. Each lane is one PR of at most
400 lines. Lane G waits for D-2 sign-off.

**D-1: the `label_horizon` rename is deferred** to a follow-on. Every migrated
call site passes the span through a variable, so the follow-on becomes a pure
rename with no value changes.

## Technical Context

**Language/Version**: Python 3.13.14 (the interpreter in the 2026-09-14 and
2026-09-18 runs).

**Primary Dependencies**: pandas, numpy, scikit-learn, scipy (runtime);
pytest 9.1.1 (dev). **No new dependency** (Rule 6).

**Storage**: N/A. 021 writes no data. Test fixtures are synthetic and
in-memory.

**Testing**: `python -m pytest tests` is the only gate (CLAUDE.md →
Conventions → Tests). Focused runs are for development. Red evidence uses
`tests/mutation_support_019.killed`.

**Target Platform**: The developer's Windows machine (Git Bash / PowerShell)
and the GitHub Actions `test` job. Nothing is platform-specific.

**Project Type**: A research library plus runnable scripts. The FastAPI
terminal is read-only, and 021 touches only one of its tests.

**Performance Goals**: N/A. The full suite ran in about 110–140 s at baseline,
and 021 must not add a test that downloads or runs longer than the existing
process-pool tests.

**Constraints**:

- No `git` (Rule 10).
- No edits to the library modules.
- No edits to `feature_set_comparison.py` or `multi_ticker_comparison.py`.
- No edits to `routes/backtest.py`, `requirements*.txt` or
  `docs/PROJECT_CONTEXT.md`.
- Shared test fixtures are frozen (FR-020).
- ≤ 400 changed lines per PR.

**Scale/Scope**: 128 failing test functions triaged; 107 in scope.
Estimated about 700 changed lines across 6 PRs.

**Unknowns**: none remain. Every open question is resolved in research.md, and
D-2 is a sign-off, not an unknown.

## Constitution Check

*GATE: must pass before Phase 0. Re-checked after Phase 1 at the end of this
file.*

| Rule | How 021 complies | Status |
|---|---|---|
| 1. Point-in-time | No feature or label computation changes. Migrated target tests re-derive expectations by hand from `Open` (FR-005). Label perturbation tests perturb `Open` (FR-006). The re-armed `TestOffByOne` pair must not regress (research R-10). | PASS |
| 2. Purged, embargoed CV | Every migrated CV call site takes purge and embargo from the label's own span (FR-003, FR-004). Embargo ≥ span everywhere. No CV metric is reported. | PASS |
| 3. Costs mandatory | No costless path is added. D-3 applies commission and slippage to the terminal exit on all three report rows. | PASS |
| 4. Two baselines | The `random_signal` fix *restores* the random baseline, which under 019 fails on every seed of the sawtooth fixture. D-3 keeps buy-and-hold meaningful. No strategy result is reported (SC-007). | PASS, and a repair |
| 5. Tests on time code | `random_signal` indexes rows, so off-by-one, boundary and gap tests ship with its fix, in the same PR (research R-4). `diagnose`'s mask is on feature values, not time. | PASS, with an obligation on lane B |
| 6. Dependencies | None added. | PASS |
| 7. `exec/` | Not touched. It does not exist yet. | PASS |
| 8. Layer separation | `random_signal` stays in the signal layer. Capital and `liquidate` are passed by the orchestration script into the harness, so no layer learns another's internals. `feature_diagnostics` stays a diagnostic over the signal layer. No boundary is crossed. | PASS |
| 9. Merge gate | Six PRs ≤ 400 lines, each with a one-paragraph mechanism statement (Lanes). D-1 keeps value changes and name changes in separate PRs, so each line changes for one reason. | PASS |
| 10. VCS human-owned | The plan and tasks never instruct `git`. Line budgets are measured by `diff -u` against file snapshots. Camden commits. | PASS |
| 11. No unsourced figures | 021 renders no result. The capital constant printed in reports is an input assumption, like commission. `PROJECT_CONTEXT.md` is left alone so its pre-019 figures do not trigger regeneration inside 021 (D-7). | PASS |
| 12. No green without red | Every gate touched has a planted defect and a control (research R-10). Two new gates are added: the `random_signal` same-row guard and the diagnostics non-finite refusal. One vacuous pass is closed (FR-012). | PASS |

**Flag-rather-than-fix items** (CLAUDE.md), raised in spec.md and not
resolved here:

- the tension between the frozen `:367` crash and the request;
- the bypassable span guard;
- the unenforced "no hysteresis for h > 1" rule;
- `ma_crossover_backtest.baseline_results` getting a changed signature that
  018 T024 must adopt. It is a cross-spec interface, not a module-boundary
  crossing, and it is documented in contracts §1.

## Project Structure

### Documentation (this feature)

```text
.specify/specs/021-finish-spec-019-migration/
├── spec.md                          # what and why; decisions D-1 to D-7
├── plan.md                          # this file: lanes, PRs, sequencing
├── research.md                      # R-1 inventory (128 tests) and R-2 to R-12
├── data-model.md                    # the migration ledger's entities and states
├── quickstart.md                    # validation commands (no git, no network)
├── contracts/
│   └── consumer-interfaces.md       # baseline_results, format_comparison,
│                                    # random_signal, feature_diagnostics
├── checklists/
│   └── requirements.md              # spec quality checklist
└── tasks.md                         # /speckit-tasks output
```

### Source files touched

```text
scripts/
├── signals.py                 # B: random_signal spacing; buy_and_hold docstring
├── ma_crossover_backtest.py   # B: capital + liquidate constants and threading
├── logistic_baseline.py       # B: main(), _format_ml_comparison, cost constants; control functions frozen (D-2)
└── feature_diagnostics.py     # D: primitives refuse non-finite; diagnose masks

tests/
├── test_backtest_harness.py      # A
├── test_metrics.py               # A   (after the cost_utils lane lands)
├── test_ml_signal.py             # A   (after the cost_utils lane lands)
├── test_signals.py               # B
├── test_ma_crossover_backtest.py # B   (fixture region :22-42 frozen)
├── test_logistic_baseline.py     # B   (fixture region :19-35 frozen)
├── test_targets.py               # C, then G (TestEquivalenceWithLogisticBaseline only)
├── test_feature_scaling.py       # D
├── test_reports_api.py           # D   (test_ml_rundown hunk only; 018 T024 owns the rest)
├── test_estimators.py            # E
└── test_model_cv.py              # E, then G (TestEquivalenceWithLogisticBaseline only)
```

**Structure decision.** No new modules and no new directories. Every change is
in place, inside the files listed above.

## Lanes

**One file, one lane.** The one exception is sequential and flagged: lane G
re-enters two of C's and E's files after they merge. Lanes A–E share no file
and can run concurrently once their preconditions hold.

| Lane | Owns | Precondition | Delta mix | In-scope tests | Est. lines | PR |
|---|---|---|---|---|---:|---|
| **A: Ledger tests** | `test_backtest_harness.py`, `test_metrics.py`, `test_ml_signal.py` | The cost_utils lane has landed (D-6) | C1 ×34, C5 ×9, C6 ×3, C7, C3, C4-index, capital base | 41 | 130–200 | PR-A |
| **B: Accounting consumers** | `signals.py`, `ma_crossover_backtest.py`, `logistic_baseline.py` (reporting hunks only), `test_signals.py`, `test_ma_crossover_backtest.py`, `test_logistic_baseline.py` | D-3 and D-4 defaults accepted, or amended in spec.md | C1, C5, C6 including `random_signal` | 17, plus 1 would-be vacuous pass | 160–240 | PR-B |
| **C: Targets** | `test_targets.py`, except `TestEquivalenceWithLogisticBaseline` | none | C2 ×6, C3 ×5 | 11 | 80–130 | PR-C |
| **D: Features and diagnostics** | `feature_diagnostics.py`, `test_feature_scaling.py`, `test_reports_api.py` (`test_ml_rundown` hunk) | none | C4 ×13, C2 ×4, finding 23 | 17, plus 1 new assertion | 80–130 | PR-D |
| **E: CV consumers** | `test_estimators.py`, `test_model_cv.py`, except `TestEquivalenceWithLogisticBaseline` | none | C2 ×15, C4 ×2 (second layer) | 15 | 40–80 | PR-E |
| **G: Control re-anchoring** | `test_targets.py::TestEquivalenceWithLogisticBaseline`, `test_model_cv.py::TestEquivalenceWithLogisticBaseline`, and those two classes' docstrings and the `test_targets.py` module docstring | **D-2 signed off**, and PR-C and PR-E merged | D-2 | 6 | 60–120 | PR-G |

Totals: 107 in-scope tests (41 + 17 + 11 + 17 + 15 + 6); about 550–900
changed lines.

### What each PR must let Camden explain (Rule 9)

- **PR-A.**
  - The harness requires declared capital, so every test declares it.
  - End of data is marked, not sold: tests that meant "sold" now say
    `liquidate=True`, and tests that meant "held" assert the mark.
  - A capital base is the declared capital, never the first close.
- **PR-B.**
  - Reports fund all three rows identically and liquidate identically.
  - `random_signal` could put an exit and the next entry on one row. The 019
    harness rejects that, and callers swallowed the error, so Rule 4's random
    baseline had vanished. Trips now keep a one-row gap.
- **PR-C.** Labels read opens, not closes, and the span is `h+1`. Every
  expected value is re-derived by hand from opens.
- **PR-D.**
  - Frames now keep warm-up rows, so diagnostics measure complete rows and say
    how many.
  - The zero-volume guard is an eligibility flag, not a dropped row.
  - The rundown reports the true final session.
- **PR-E.** Purge and embargo come from the label's span, never a literal. The
  isolation test corrupts only rows whose labels exist.
- **PR-G.** The pre-019 control stays frozen. What used to be an equivalence
  with it becomes a pinned, hand-worked divergence. The tuner equivalence now
  anchors to the in-contract untuned loop, which is still pinned to the
  control on synthetic frames.

### Where exclusive ownership is not possible (flagged)

1. **Lane G re-enters `test_targets.py` and `test_model_cv.py`.** This is
   sequential by construction. G starts only after PR-C and PR-E merge, so no
   two open PRs ever hold hunks in the same file. The class boundaries are the
   split line.
2. **`test_reports_api.py` is shared with spec 018 T024.** 021 owns only
   `test_ml_rundown`, and T024 owns `test_backtest_tearsheet`. The split is by
   hunk, and PR-D must not touch any other test in that file. If T024 is open
   at the same time, the second of the two to land re-baselines that file.
3. **`test_metrics.py` and `test_ml_signal.py` overlap the concurrent
   cost_utils lane.** Lane A waits (D-6).
4. **Cross-lane fixture reads.** A reads B's fixtures, C reads B's, and E reads
   B's. They are made safe by the fixture freeze (FR-020; research R-11), not
   by ordering. Any lane that believes it must change a shared fixture stops
   and raises it. It does not edit the fixture.
5. **Cross-spec interface.** Lane B changes `baseline_results`, which
   `routes/backtest.py` (018 T024) calls. The shape is fixed in
   [contracts §1](contracts/consumer-interfaces.md#1-ma_crossover_backtestbaseline_results)
   so T024 can adopt it independently.
6. **A frozen file changes behavior without being edited.**
   `multi_ticker_comparison.py` imports `random_signal`. PR-B's description
   must say so (research R-4).

## Sequencing

```text
T001 re-baseline ─┬─▶ PR-B (lane B) ─────────────────────────────┐
                  ├─▶ PR-C (lane C) ──────────┐                  │
                  ├─▶ PR-D (lane D) ──────────┼──────────────────┤
                  ├─▶ PR-E (lane E) ──────────┤                  ├─▶ T-final: full suite = residual list
                  │                           ├─▶ PR-G (lane G) ─┤         (SC-001 … SC-007)
 D-2 sign-off ────┼───────────────────────────┘                  │
 cost_utils lands ┴─▶ PR-A (lane A) ─────────────────────────────┘
```

- **Merge order** is free among B, C, D and E. A waits for the concurrent lane
  and G waits for D-2. **Suggested review order: B first.** It carries the only
  production behavior change with Rule 4 consequences, and D-3 and D-4 are best
  confirmed on it before the test lanes lean on the same conventions.
- **Every PR re-runs the full suite**, not only its lane's files. The measure
  is that the failing set is monotonically non-increasing and never gains an ID
  outside R-1.

## PR description template (CLAUDE.md → Pull request requirements)

1. **Spec**: 021, lane X. The research R-1 rows this PR closes.
2. **What changed and why it is correct**: the lane's mechanism statement
   above, plus the red evidence for its gates (research R-10).
3. **Metrics**: none reported (SC-007). State that explicitly, so the absence
   of fold, purge, embargo and cost figures is deliberate.
4. **Strategy change**: none. PR-B changes how a *baseline* is constructed.
   State the distributional change: trips now keep a one-row gap. State that
   no baseline figure is quoted.
5. **Dependencies**: none.
6. **Line count**: `diff -u` against the lane's pre-edit snapshot, per file and
   summed.

## Complexity Tracking

No constitution violations to justify.

## Constitution Check: post-design re-evaluation

Re-checked after research.md, data-model.md, contracts/ and quickstart.md:
**all twelve still PASS.**

The design added three things, and each strengthens a rule rather than
bending one:

- a **Rule 12** gate: `feature_diagnostics` refusing non-finite input;
- a **Rule 5** set of tests for `random_signal`;
- a **Rule 4** repair: the random baseline runs again.

The one cross-spec interface change (`baseline_results`) is documented rather
than hidden. No unresolved clarifications remain.
