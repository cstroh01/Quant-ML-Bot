# Implementation Plan: Wire Funded-Ledger Callers to the Unadjusted Pipeline

**Branch**: none; Camden creates it | **Date**: 2026-09-23 | **Spec**: [spec.md](spec.md)
**Spec number**: NNN, a placeholder. **Camden assigns it.** See spec D-1.

**Input**: [spec.md](spec.md). The plan assumes D-1 through D-6 are accepted as
recommended. If D-3 is rejected, drop PR-2 and the tasks marked `[D-3]`. Nothing
else changes.

## Summary

Add one fail-closed, ticker-level entry point to `scripts/data.py`. It resolves
exactly one spec 020 manifest bundle and loads it. On a missing, ambiguous or
invalid bundle, it raises a single named error. Then route the two funded
callers through that entry point:

- **`ma_crossover_backtest.main()`**: on the error, a named message and a
  nonzero exit, with no files and no trial record.
- **`routes/backtest.py`**: on the error, HTTP 503. This absorbs 018 T024.

Signals are computed on the causal `Research_Close`. Fills stay on nominal
`Open`. Neither caller can reach `download_market_data` any longer.

## Technical Context

**Language/Version**: Python 3 (as the repository uses today)
**Primary Dependencies**: pandas, numpy, FastAPI (all existing). **No new dependency.**
**Storage**: `data/cache/unadjusted/` manifest bundles (spec 020), which are gitignored
**Testing**: `python -m pytest tests`, offline, with synthetic bundles published through `cache_unadjusted_market_data` and a stub adapter
**Target Platform**: local CLI and the local reports API
**Project Type**: single project (`scripts/` modules, `reports/api` routes)
**Performance Goals**: none new. Loading one bundle is O(rows)
**Constraints**: no network in tests; no adjusted-price fallback anywhere on a funded path; no edits to spec 020's validators
**Scale/Scope**: 2 production callers, 1 data-layer addition, and about 4 test files

## Constitution Check

*Gate: must pass before Phase 0. Re-checked after Phase 1.*

| Rule | How this plan complies | Status |
|---|---|---|
| 1. Point-in-time | Signals read `Research_Close`, which chains forward only (`data.py:447-486`). They never read adjusted history, which is rewritten backward. Signals are still shifted to the next open by `signals.py` | Pass |
| 2. Purged CV | Not touched. There is no model in either caller | N/A |
| 3. Costs | Both callers keep their explicit commission and slippage. The route passes them unchanged | Pass |
| 4. Two baselines | Strategy, buy-and-hold and random run on one bundle frame, with identical costs, capital and policy (FR-006). **No metric is quoted in the PR** (SC-005) | Pass |
| 5. Tests on time | The split-session test (US1 AS4) and the resolver/session tests ship with the change | Pass |
| 6. Dependencies | None added | Pass |
| 7. Execution | No `exec/` and no broker code | N/A |
| 8. Layer separation | The resolver and the error live in `data.py`, the module that owns cache I/O. `signals.py` is unchanged. The basis translation is in the caller. The harness is unchanged, and its guard stays as the last line of defense | Pass |
| 9. Merge gate | Two PRs, each small enough to explain line by line (budget ≤ 400 lines) | Pass |
| 10. VCS | This plan ran no `git`. Implementation also runs none outside the Actions lane | Pass |
| 11. Sourced figures | Every bundle-based output states its provenance (FR-008). The only numbers are test oracles | Pass |
| 12. Red before green | Each gate is paired with a mutant ([research R-6](research.md#r-6-mutants)) | Pass |
| 14. Corporate-action verification | **Not satisfied by this spec, and not claimed.** A yfinance bundle is `capital_gate_eligible=False`, and that status is printed. No real bundle exists yet (B-1) | Flagged (spec F-1) |
| 15. DSR gate | D-5 keeps data unavailability out of the trial count | Pass |

No violations. The Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
.specify/specs/NNN-unadjusted-caller-wiring/
├── spec.md
├── plan.md              # this file
├── research.md          # R-1 … R-7
├── data-model.md        # error type, resolver rules, frame lineage
├── quickstart.md        # offline validation
├── contracts/
│   └── cli-and-api.md   # CLI exit contract, 503 contract, data.py surface
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (files touched)

```text
scripts/
├── data.py                    # PR-1: + UnadjustedDataUnavailable, resolve_unadjusted_manifest,
│                              #        load_unadjusted_for_ticker. The 020 loader and validators are unchanged
└── ma_crossover_backtest.py   # PR-1: main() load path, research-close signal helper, exit contract, figure labels
reports/api/
├── routes/backtest.py         # PR-2 [D-3]: loader, 503, capital/policy, provenance
└── schemas.py                 # PR-2 [D-3]: + provenance fields on BacktestTearsheetResponse
tests/
├── unadjusted_fixtures.py             # PR-1: shared synthetic-bundle builder (not a test module name)
├── test_unadjusted_caller_wiring.py   # PR-1: resolver, CLI, signal basis, no-fallback scan
├── test_reports_api.py                # PR-2: tearsheet 200 on a bundle, plus 503 cases
└── mutation/run_unadjusted_wiring_mutants.py  # PR-1/PR-2 mutants
```

**Structure Decision**: two PRs.

- **PR-1** (data layer and CLI) stands alone. It lands first.
- **PR-2** (route) imports PR-1's entry point and its signal helper.

Test file names avoid the spec number, so renaming the directory to its number
later does not touch tests.

## PR budget

| PR | Files | Est. lines | Depends on |
|---|---|---|---|
| PR-1 | `data.py`, `ma_crossover_backtest.py`, 2 new test files, mutation driver | 250–350 | spec sign-off |
| PR-2 | `routes/backtest.py`, `schemas.py`, `test_reports_api.py`, mutation driver rows | 150–250 | PR-1 merged |

## Risks

- **The fixture stamp in `test_reports_api.py:28`.** It sets
  `panel.attrs["price_basis"] = "unadjusted_dollars"` by hand. That stamp is
  outside the blessed loader, and it does not survive the CSV write anyway. PR-2
  removes it and publishes a real synthetic bundle ([R-5](research.md#r-5-the-tearsheet-test-fixture)).
- **The frontend shows a raw `statusText` on a 503** (`services/api.ts:59`).
  That is readable but plain. Rendering the detail is UI work for spec 018 and
  is not done here.
- **B-1.** After merge, every real run is "unavailable". That is the intended
  honest state, but reviewers should expect it and not read it as a bug.

## Complexity Tracking

None.
