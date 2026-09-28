# Implementation Plan: Dividend pay date as a declared conservative bound

**Branch**: `041-dividend-pay-date-bound` (human-owned) | **Date**: 2026-09-27
**Spec**: [spec.md](spec.md)
**Precondition**: spec 036 merged. 041 and 036 both edit `scripts/data.py` and never run concurrently.

## Summary

Implement spec 036 D-7 option C1 in the data layer. It adds one named lag constant
(value: unbounded), a version-2 manifest that declares the pay-date policy, and a
per-dividend `Dividend_Pay_Date_Basis` marker. The marker is carried on disk, in
the loaded frame, and on the harness dividend event. The validator is relaxed in
exactly one cell of its rule table. Harness and metrics arithmetic are unchanged.

## Technical Context

**Language/Version**: Python ≥ 3.12 (pinned NumPy floor).
**Primary Dependencies**: existing pins only. No additions.
**Storage**: `data/cache/unadjusted/` bundles (gitignored); spec-local evidence in `artifacts/`.
**Testing**: `python -m pytest tests`, offline; in-memory mutants via `tests/mutation_support_019.py`.
**Constraints**: no Git; no network in tests; no change to `exec/`, `live_safety_gate.py` or `portfolio_risk.py`.
**Scale/Scope**: `data.py`, one field and one event column in `backtest_harness.py`,
and the 036 provenance renderer. Expected PR size: 250–400 lines, including tests.

## Constitution Check

| Rule | How this spec satisfies it |
|---|---|
| 1 Point-in-time | The bound errs late. `Cash_t` never includes a dividend that arrives after `t`. The M1 mutant (early/ex-date pay) is planted and killed |
| 5 Time tests | Boundary cases: a dividend on the final session, same-day split plus dividend, re-entry inside the ex→pay window |
| 8 Layers | Resolution happens in `data.py`. The harness only records the basis it was handed; its arithmetic does not change |
| 11 Provenance | A bound is never written into the vendor date column on disk. Basis travels with every date. A finite lag cannot exist without a citation |
| 12 Red proof | Mutants M1–M3 plus the M4 configuration assertion, each with a green control |
| 14 | Unchanged and still owed. `capital_gate_eligible` stays `False` |
| 16 Limitations | FR-007's line on every 036 FR-008 surface |
| 6 / 7 / 9 / 10 | No dependency; no `exec/`; Camden's merge gate; no Git |

## Project Structure (files touched)

```text
scripts/data.py                 constants, policy derivation, snapshot field, validator,
                                manifest v2, loader resolution, attrs
scripts/backtest_harness.py     Pay_Date_Basis on dividend events (recording only)
<036 provenance renderer>       FR-007 line (file named by 036's merged implementation)
tests/test_041_pay_date_bound.py    all new tests (SC-002 to SC-007)
.specify/specs/041-dividend-pay-date-bound/artifacts/aapl-bundle.txt   SC-001 evidence
```

## Design notes

1. **Why the marker lives on disk, not only in the loader.** The loader could
   derive "bound" from "null on disk + policy". But then the actions CSV, which is
   the hashed artifact a reviewer opens, would carry no per-row statement. The
   explicit column makes the row self-describing, and the manifest hash covers it.
2. **Why `UNBOUNDED_PAY_DATE` is a far sentinel, not "day after the final
   session".** A plausible-looking real date invites being read as data. The
   sentinel is unmistakable, and it stays later than every row if a caller slices
   the frame. The harness compares `date <= row.Date` only, so no arithmetic
   touches it. `metrics.equity_curve` replays the same resolved date from the
   source frame, so reconciliation holds.
3. **Why the snapshot default is `"sourced"`.** It is the strict value. A future
   adapter that forgets to declare a policy gets today's fail-closed behavior, not
   a silent relaxation.
4. **Version 1 stays loadable and strict.** The existing spec 020 synthetic-bundle
   tests keep passing unchanged. No version-1 bundle exists in `data/cache/`
   (verified 2026-09-27: the directory does not exist).

## Execution

1. Re-read 036's merged `data.py` and renderer. Update line references in `tasks.md` if they moved.
2. Write the FR-004 table test and the M1–M3 oracles. Observe them fail against the unmodified code (red first).
3. Implement FR-001 to FR-005. Then FR-003's harness field, then FR-007.
4. Run the focused tests, then the mutants, then the full suite.
5. Camden runs SC-001 once, online; save the evidence.

## Complexity Tracking

No constitutional exception is requested.
