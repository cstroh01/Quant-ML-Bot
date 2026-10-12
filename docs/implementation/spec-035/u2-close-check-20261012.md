# 035 T007/T008: U2 `Close` cross-check evidence

Cloud lane B, queue Q38, 2026-10-12. Linux evidence only; CI's test-windows is the Windows check.

- **Function:** `scripts/corporate_actions.py::cross_check_close(primary, second, coverage, *, close_tolerance)`,
  with `CLOSE_RELATIVE_TOLERANCE = 1e-3` (spec §8 D-2, recorded 2026-10-09). Relative difference is
  `|primary - second| / |second|`, inclusive; a non-finite `Close` refuses.
- **Contracts first (T007):** `tests/test_035_close_check.py` ran red before the implementation
  existed: 23 failed, 1 passed (the FR-009 socket-guard control), every failure
  `AttributeError` for the missing `cross_check_close` / `CLOSE_RELATIVE_TOLERANCE`.
- **Rule 12 field statement:** every refusal fixture perturbs `Close` only; `Open`, `High`, `Low`
  and `Volume` are identical across sources, because `Close` is the column a dividend-adjusted
  basis moves (FR-005, M1).
- **Planted defects (in memory via `tests/mutation_support_019.py::killed`, never committed):**

| Mutant | `old` → `new` | Oracle failure under the mutant | Control |
|---|---|---|---|
| Open-for-Close (T007) | `frame["Close"]` → `frame["Open"]` | `AssertionError: close cross-check did not refuse` on a 1% `Close`-only gap | identical bars pass |
| Primary-only sweep | `sorted(mine.keys() \| theirs.keys())` → `sorted(mine.keys())` | `AssertionError: close cross-check did not refuse` on a second-source-only session | identical bars pass |

- **Ledger:** `docs/trials/trials.jsonl` 174 lines, SHA-256
  `1bb5dbfe90c9df370c65910650ade15dd9d0e0366d011e09baf303975275f30f`; `trials.head.json` SHA-256
  `f83b1b9be5a608d444d61496899d25139eb56184fd924acd030e61347d22d764`; `docs/trials/returns/` absent.
  Unchanged before and after.
- **Review fix (fresh-context reviewer, P2):** a `+inf` second-source `Close` passed
  (`inf <= 1e-3 * inf`). Rows `inf` and `-inf` were added to the tolerance parametrization and ran
  red (2 failed), then an explicit `math.isfinite` guard made them green (49 passed across
  `test_035_close_check.py` and `test_035_reconcile.py`).
- **Full suite** (before the review fix, Python 3.12.3, `-n auto`): 1923 passed, 47 xfailed,
  0 failed, 0 errors, 1386 subtests passed.
