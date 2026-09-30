# Spec 041 Unit 5b evidence

Date: 2026-09-29. Windows; Anaconda Python 3.14.6, pytest 9.1.1.
EXAMPLE — NOT A RESULT. Synthetic tests only; no network or real AAPL download.

## Scope delivered

- Completed T015 only. No separate T016 work was started or claimed.
- Wired SC-005 M1–M3 through the existing
  `tests/mutation_support_019.py::killed()` in-memory mutation helper.
- Strengthened M2 with a version-2 bundle whose manifest policy is `sourced`
  while its dividend row has basis `bound` and a null pay date.
- Confirmed all five M4 direct configuration cases raise before any bundle is
  written.
- Repaired the existing Spec 020 mutation driver for the FR-005 loader call.
  The unsafe replacement now carries the manifest pay-date policy and bound
  source into `_ValidatedUnadjustedBundle` and `_merge_actions_for_execution`.
  No third mutation harness was created.

## Unit diff

Changed-line counts are against the files read at this unit's start, without
using Git.

| File | Added | Removed |
|---|---:|---:|
| `tests/test_041_pay_date_bound.py` | 33 | 5 |
| `tests/mutation/run_mutation_check.py` | 8 | 2 |
| `.specify/specs/041-dividend-pay-date-bound/tasks.md` | 1 | 1 |
| `.specify/specs/041-dividend-pay-date-bound/artifacts/unit-5b.md` | 78 | 0 |

Total: **128 changed lines**, below the 400-line unit limit. Production files were not edited;
in particular, `scripts/data.py` and its mixed line endings are untouched.

## Verification

| Run | Result | Exit |
|---|---|---:|
| Focused 041 + 020 | 115 passed, 0 failed, 0 errors; 1 warning; 19.06s | 0 |
| Existing Spec 020 mutation driver | clean control passed; unsafe-loader mutant killed at `test_tampered_price_file_fails_hash_check` | 0 |
| `python -m pytest tests` | 1003 passed, 0 failed, 0 errors; 1 warning; 316.30s | 0 |

Focused command:
`python -m pytest tests/test_041_pay_date_bound.py tests/test_020_unadjusted_price_data.py -q`.
The focused count is Unit 5a's 112 plus three new M1–M3 mutation cases. The
full-suite count is the 1000-case baseline plus those same three cases.

The warning is the existing Starlette `httpx` deprecation warning. No test was
skipped, deselected, retried, or run in a second lane.

## Rule 12 mutant evidence

Each `killed()` case first ran its unmutated oracle successfully, compiled the
planted defect in memory, caught the oracle's `AssertionError`, restored the
module dictionary, and verified that the source-file digest did not change.

| Mutant | Planted defect | Red proof under the defect | Result |
|---|---|---|---|
| M1 — option B | Resolve `unbounded` to `action.Date` instead of `UNBOUNDED_PAY_DATE` | The dividend becomes cash early, the re-entry is admitted, and `events.count("rejected") == 1` fails | killed |
| M2 — validator pass-through | Remove the `pay_date_policy != "sourced"` condition from `null_pay_date_allowed` | The new sourced-policy / bound-basis / null-date bundle loads; `raises_containing(..., "dividend payment date missing")` raises its oracle `AssertionError` | killed |
| M3 — provenance laundering | Stamp every loaded dividend basis as `"sourced"` | The on-disk null bound row loads as sourced, so the exact `basis == "bound"` assertion fails | killed |
| M4 — uncited/nonpositive finite lag | Set lag to 5 with `None`, empty, or whitespace source; set lag to 0 or -1 with a test citation | All three uncited cases raise `requires a cited upper-bound source`; both nonpositive cases raise `must be a positive number of sessions`; output directory stays empty | raised in all 5 cases |
| Existing Spec 020 unsafe loader | Replace validated bundle loading with direct CSV reads and stamping | The mutant fails the named tampered-price hash oracle; the driver prints `KILLED` rather than `MUTATION SETUP FAILED` | killed |

## Protected artifacts

Verified immediately before and after the focused run, the mutation driver
(including both of its internal pytest subprocesses), and the single full-suite
run:

- `docs/trials/trials.jsonl`: 174 lines; SHA-256
  `1bb5dbfe90c9df370c65910650ade15dd9d0e0366d011e09baf303975275f30f`.
- `docs/trials/trials.head.json`: 174 records; SHA-256
  `f83b1b9be5a608d444d61496899d25139eb56184fd924acd030e61347d22d764`.
- `docs/trials/returns/`: absent before and after every run.

No Git command, network access, protected-file edit, direct backtest call, or
direct research call was performed.
