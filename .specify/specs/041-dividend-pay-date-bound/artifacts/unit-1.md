# Spec 041 Unit 1 evidence

Run: `spec041-unit1-20260928T205954-0400`, 2026-09-28, Windows,
Python 3.14.6, pytest 9.1.1. Source: pytest console and read-only PowerShell
artifact measurements from this unit. No strategy performance result is reported.

## Runs

| ID | Command | Observed result |
|---|---|---|
| B1 | `python -m pytest tests` | 903 passed / 0 failed; exit 0; 363.11s |
| R1 | `python -m pytest tests/test_041_pay_date_bound.py tests/test_020_unadjusted_price_data.py -q --tb=short` | 21 passed / 47 failed; exit 1; 9.05s |
| R2 | `python -m pytest tests/test_041_pay_date_bound.py -q --tb=short` | 6 passed / 47 failed; exit 1; 3.27s |
| C1 | `python -m pytest tests --collect-only -q` | 956 collected; exit 0; 3.48s |

R1 preceded a correction to the ex-date timezone error text in the new test.
R2 verified the final test file. Both runs failed only the 46 v2 table cases
(unsupported manifest version) and the offline flow (dividend payment date missing).
All 15 existing Spec 020 tests passed in R1. No production implementation changed.
The full suite was executed before edits; C1 verifies collection, not execution.

## Trial artifact integrity

Every before/after measurement below matched this complete state:

- `docs/trials/trials.jsonl`: 174 lines; SHA-256 `1bb5dbfe90c9df370c65910650ade15dd9d0e0366d011e09baf303975275f30f`.
- `docs/trials/trials.head.json`: records 174; SHA-256 `f83b1b9be5a608d444d61496899d25139eb56184fd924acd030e61347d22d764`.
- `docs/trials/returns/`: absent.

| Run | Before (America/New_York) | After (America/New_York) | All three unchanged |
|---|---|---|---|
| B1 | 2026-09-28T20:59:54.0972528-04:00 | 2026-09-28T21:06:13.7516481-04:00 | yes |
| R1 | 2026-09-28T21:07:43.9704732-04:00 | 2026-09-28T21:08:00.8963068-04:00 | yes |
| R2 | 2026-09-28T21:08:20.4303372-04:00 | 2026-09-28T21:08:31.3608409-04:00 | yes |
| C1 | 2026-09-28T21:08:53.8556411-04:00 | 2026-09-28T21:09:20.0677958-04:00 | yes |

## Pinned Spec 019 files

Both whole-file SHA-256 values were unchanged in this unit:

- `tests/test_019_prices.py`: `b7cc6cc48fe409e1e1cfdce96eb6c98ad25b960cb7da89aaa8ead74e361ec706`.
- `tests/test_019_conventions.py`: `05669610855dc98297ff79d0d242bc07f0066bf334d3b7720dbc40624a5b157f`.

Fourteen production/protected test files were hash-compared, with zero changes.
T005 onward, including mutation controls and a fully green post-implementation
suite, remains pending. This unit stops after T004.

