# Implementation Plan: Nominal price reconstruction

**Branch**: `044-nominal-price-reconstruction` (human-owned) | **Date**: 2026-09-30, revised for R1–R11
**Spec**: [spec.md](spec.md) | **Review**: [artifacts/review-codex.md](artifacts/review-codex.md)
**Precondition**: spec 041's production tasks are merged. 044 never runs at the same time as 041 or
043, because all three edit `scripts/data.py`.

## Summary

The yfinance adapter receives split-adjusted OHLC and wrongly calls it nominal. `data.py` gains
one pure function that multiplies each row by the product of strictly later split ratios. Those
ratios come from a single open-ended provider response, whose horizon is checked against an as-of
clock and whose factor events are all validated first. Only then does the adapter slice to the
window and hand the result to the **unchanged** split oracle. The dividend and volume treatment is
chosen by a registered probe, P-1. Unverified volume is marked and blocked from the cost model. An
independent, cited split table catches an omitted split inside its coverage interval.

## Technical context

**Language**: Python ≥ 3.12. **Dependencies**: existing pins only.
**Storage**: bundles in `data/cache/unadjusted/`; P-1 raw rows in `data/cache/spec044_p1/`. Both
are gitignored. Committed evidence lives in `artifacts/`.
**Testing**: `python -m pytest tests`, offline. Mutants go through `tests/mutation_support_019.py::killed`.
**Constraints**: no Git, no network in tests, no `docs/trials/**`, and no `exec/`.
**Review units**: **a hard cap of 300 lines, added plus removed, per unit, including evidence and
task-status edits**, measured without Git against pre-unit copies (tasks.md standing rules). A
unit that would exceed the cap is split, never waived.

## Constitution check

| Rule | How it is satisfied |
|---|---|
| 1 Point-in-time | The conditional argument (spec §2): a complete, current, validated factor, plus the P-1 conventions. T-PIT uses a fixed window with a growing response and perturbed future values. M2 is killed |
| 5 Time tests | The spec §3 edge table, the FR-002 horizon and coverage cases, and FR-014 DST alignment |
| 8 Layers | `data.py` only, plus one loader attrs line (FR-010). No caller or harness change |
| 11 Provenance | P-1 records versions, input hashes, a raw-row hash and ledger hashes. The split table cites primary filings row by row |
| 12 Red proof | M1–M6 with green controls, using message-matched oracles only. The probe's `--self-check` does the same for the probe's own gates |
| 14 Corporate actions | FR-006 over the common coverage interval. Events after `verified_through` are disclosed |
| 16 Limitations | The FR-007 labels, a volume-basis line, and unreconciled-event lines, printed by the existing CLI loop |
| 6/7/9/10 | No dependency, no `exec/`, Camden's merge gate, no Git |

## Files touched

```
scripts/data.py                              FR-001/002/004/005/007/011–014, FR-006 constant; one loader attrs line (FR-010)
tests/test_044_nominal_reconstruction.py     new, in parts across Units 2, 3, 6 and 7
tests/test_041_pay_date_bound.py             FR-009 migration (Unit 1)
tests/test_020_unadjusted_price_data.py      FR-009 migration (Unit 1)
.specify/specs/044-.../artifacts/            p1_probe.py + p1_rules.py, the two CSV inputs, .gitignore, p1-determination.txt,
                                             split-table-crosscheck.md, baseline.txt, sc-001-rerun.txt
```

## Units (tasks.md holds the detail; each unit ≤ 300 measured lines and stops for review)

| Unit | Content | Who |
|---|---|---|
| 0 | Probe review in two parts; inputs; `--self-check` and the run; recording P-1's selections; the cross-check by a second lane | Camden, plus the D-5 lanes |
| 1 | FR-009 fixture migration and seams. Actual red or green recorded per test | agent |
| 2 | Contracts A: exact reconstruction, edges, FR-011, FR-002 horizon and coverage, FR-014 | agent |
| 3 | Contracts B: T-PIT, the quantized residual, dividend, volume, same-day, labels, the SC-002 twin | agent |
| 4 | Implementation: pure function, validation, clock and horizon, coverage, slicing | agent |
| 5 | Implementation: conventions, labels, the loader attrs line | agent |
| 6 | Mutation wiring and kill evidence (M1–M4, M6) | agent |
| 7 | FR-006: tests first, then the constant, comparison and M5 (split in two if over the cap) | agent |
| 8 | SC-001 re-run, suite count, unit-size table | Camden |

Units 4–6 run with no reference-table check. That is acceptable because no bundle is published
until SC-001 in Unit 8.

## Design notes

- **Factor computation.** Validate first (FR-011). Then take a reverse cumulative product of the
  ratios over sessions, divided by each row's own ratio, so the split-day row is excluded. The
  computation is O(n).
- **Slicing happens after reconstruction.** Reconstructing after slicing is M2. T-PIT asserts this
  behaviorally, at the adapter boundary.
- **Horizon.** `trading_days` with an injected clock. The as-of instant is localized to New York
  explicitly at that boundary, and session labels never pass through UTC.
- **Expected values.** Hand-written literals on exactly representable fixtures, never computed by the
  helper under test. The quantized case asserts a documented bound, not an identity (R8).
- **Rounding.** None (D-1).

## Risks

- **P-1 STOP on dividends (Q-P3).** The spec stops. AAPL SC-001 cannot pass without a dividend
  treatment.
- **Scarce pre-split filed ranges (Q-P1).** If no qualifying quarter precedes two splits, Q-P1 is a STOP.
- **Volume inconclusive (Q-P4).** Bundles still ship, marked `provider_unverified`. Any future
  cost-model consumer must refuse them (FR-005).
- **Probe horizon counts weekdays.** An extra holiday can cause a false STOP, and the run is simply
  repeated on the next session.
- **A basket split after `verified_through`.** It is disclosed, not caught. Re-verifying moves
  `verified_through`.
