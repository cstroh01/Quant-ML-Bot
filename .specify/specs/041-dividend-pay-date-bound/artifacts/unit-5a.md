# Spec 041 Unit 5a evidence

Date: 2026-09-29. Windows; Anaconda Python 3.14.6, pytest 9.1.1.
EXAMPLE — NOT A RESULT. Synthetic tests only; no real AAPL download.

## Delivered

- FR-005 records Camden's dated amendment: refuse every bundle reaching the
  sentinel, including v1. The sentinel remains 2262-04-11 at naive midnight.
- Writer rejects sourced snapshots missing the basis column with the existing
  "dividend pay-date basis missing or invalid" fragment. Three old fixtures now
  supply the column explicitly (null for splits, sourced for the dividend).
- Six requested guards plus the strict writer have planted-defect proofs using
  `tests/mutation_support_019.py::killed`; no new mutation harness.

## Unit diff

Compared with the files read at this unit's start, without Git.

| File | Added | Removed |
|---|---:|---:|
| `tests/test_020_unadjusted_price_data.py` | 2 | 0 |
| `.specify/specs/041-dividend-pay-date-bound/spec.md` | 6 | 1 |
| `tests/unadjusted_fixtures.py` | 1 | 0 |
| `tests/test_041_pay_date_bound.py` | 133 | 7 |
| `scripts/data.py` | 4 | 9 |
| `.specify/specs/041-dividend-pay-date-bound/tasks.md` | 15 | 2 |
| `artifacts/unit-5a.md` | 82 | 0 |

Total: **262 changed lines**.

Existing line endings preserved: data.py retains 420 CRLF lines (only LF lines
changed); the 041 test remains CRLF; other edited existing files remain LF.

## Verification

| Run | Result | Exit |
|---|---|---|
| Focused 041 + 020, first | 111 passed, 1 failed, 23.28s | 1 |
| Focused 041 + 020, corrected | 112 passed, 0 failed, 15.75s | 0 |
| `python -m pytest tests` | 1000 passed, 0 failed, 348.14s | 0 |

Focused command: `python -m pytest tests/test_041_pay_date_bound.py tests/test_020_unadjusted_price_data.py -q`.
The first failure was `test_writer_requires_explicit_sourced_basis`: the existing
isolation fixture populates tmp_path. The assertion now checks its own output
directory. No production failure was concealed. One existing Starlette warning.
Counts: 97 Spec 041 cases; 14 new this unit; full suite = 986 + 14 = 1000.

## Rule 12 evidence

All 13 mutation cases passed their clean control and caught an AssertionError
under the planted defect. Mutations compile in memory; source files are unchanged.

| Guard | Planted defect | Cases |
|---|---|---|
| Strict writer | Restore inferred sourced basis | 1 |
| Sentinel refusal | Change >= to > at equality | 3 (v1, v2 sourced, v2 unbounded) |
| Stray citation | Skip citation rejection | 2 (sourced, unbounded) |
| Snapshot policy | Bypass snapshot policy validation | 4 (unknown, uncited bound, both stray citations) |
| Validator policy | Skip unknown-policy rejection | 1 |
| Loopback exception | Allow every tuple address | 1 |
| CLI ledger isolation | Remove synthetic-root preflight | 1 |

Sentinel tests move the boundary onto the final session of a valid bundle and
also assert the real sentinel value. Network controls permit IPv4/IPv6 loopback;
a non-loopback address must fail before the fake connect runs. CLI controls unset
SPEC033_SYNTHETIC_ROOT; removing the preflight reaches an intercepted launch and
fails the oracle. Neither mutant opens a real connection or starts a script.

## Protected artifacts

Verified before and after all three pytest runs; one runner at a time:

- trials.jsonl: 174 lines; SHA-256 `1bb5dbfe90c9df370c65910650ade15dd9d0e0366d011e09baf303975275f30f`.
- trials.head.json: 174 records; SHA-256 `f83b1b9be5a608d444d61496899d25139eb56184fd924acd030e61347d22d764`.
- docs/trials/returns/: absent.
- test_019_prices.py: `b7cc6cc48fe409e1e1cfdce96eb6c98ad25b960cb7da89aaa8ead74e361ec706`.
- test_019_conventions.py: `05669610855dc98297ff79d0d242bc07f0066bf334d3b7720dbc40624a5b157f`.

No Git, protected-file edits, or research/backtest execution outside pytest.
tests/mutation/ remains untouched for Unit 5b. T015's M1-M3 work is pending;
rerun T017 after it. Camden's real AAPL check and Rule 14 remain manual.
