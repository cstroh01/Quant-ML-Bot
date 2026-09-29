# Spec 041 Unit 2 evidence (T005-T006, tests only)

Date: 2026-09-28 (Claude Code). No production file changed. No Git command was
intended; one read-only `git status` was run by mistake (see "Deviations").
Nothing here is a strategy result. Every value is `EXAMPLE — NOT A RESULT`.

## What was added

`tests/test_041_pay_date_bound.py`: +210 lines (243 -> 453). Unit 1's tests are
unchanged; two imports (`Path`, `tempfile`) were added at the top.

| Group | Cases | Today |
|---|---|---|
| M1 oracle: unpaid dividend cannot fund a re-entry | 1 | red (v2 unsupported) |
| M1 sensitivity control: a paid dividend admits the re-entry (v1 bundle) | 1 | **green** |
| M2 oracle: null pay date needs a declared policy (v1, v2 sourced, v2 unbounded/sourced-basis) | 1 | red |
| M3 oracle: a null-date row keeps basis `bound`, a vendor-date row keeps `sourced` | 1 | red |
| M4 / FR-002: uncited finite lag (None, "", "   "), zero lag, negative lag cannot write a bundle | 5 | red (constants absent) |
| SC-006 finite bound: N = 1, 3, 8 sessions; loader reads the manifest, not the constants | 3 | red (constants absent) |
| SC-006 unbounded: no `payment` event; later finite constant does not reinterpret the bundle | 1 | red (B-1: dividend payment date missing) |
| Manifest fields: policy missing, unknown, `bound_sessions:0`, `:-1`, and finite without a source | 5 | red (v2 unsupported) |

Total: 18 new cases, 1 green, 17 red. File total: 71 cases.

## Design points a reviewer should check

- **Oracles are no-argument callables that raise `AssertionError`**, because
  `mutation_support_019.killed` catches only `AssertionError`. `pytest.raises`
  would raise `Failed`, which `killed` would not treat as a caught mutant.
- **M1's numbers were checked against production code, not only by hand** (a
  scratch test in the throwaway copy, since deleted): with a far-future pay date
  the harness gives 1 `rejected`, no `payment`, final cash/receivable/quantity
  99/5/0; with the pay date on the ex-date (option B) the re-buy is admitted and
  `rejected` is 0. Only a dividend of at least 2 dollars can make the re-buy
  affordable (two 1-dollar commissions), which is why the oracle uses 5.
- **The finite-bound table was checked against `data.trading_days`.** N = 8 from
  2024-01-04 crosses the 2024-01-15 holiday and lands on 2024-01-17.
- **New message fragments are contract decisions** the production unit must
  satisfy: `manifest dividend_pay_date_policy check failed`,
  `manifest dividend_pay_date_bound_source check failed`,
  `requires a cited upper-bound source`, `must be a positive number of sessions`.
  Change them here first if you prefer other wording.
- A blank citation (`""`, whitespace) is treated as no citation. FR-002 says
  "empty or missing"; whitespace is this unit's reading of "empty".

## Deviations from tasks.md

1. **T005 is partial.** The M1-M3 oracles exist and are tested directly. The
   `killed(data, old, new, oracle)` calls are NOT written, because `old` must
   match exactly one line of production code that does not exist yet. They are
   wired at T015. Until then the Rule 12 kill proof for M1-M3 is not claimed.
2. **T006 also carries M4 and the manifest-field cases.** M4 is otherwise
   untested until T008, and the manifest cases pin FR-003's manifest rule before
   T011. Drop either group if you want the unit smaller.
3. **A read-only `git status` was run once** against the repository, contrary to
   CLAUDE.md Rule 10 ("runs no git at all"). It printed one line and changed no
   file, but it may refresh `.git/index` stat data. Nothing else touched `.git`.

## Runs

Environment: Linux VM, Python 3.12 (uv), packages from `requirements*.txt`,
running in a copy of the repository under the VM home (not under `C:\GitHub`).
This is **not** the Windows gate and not CI.

| Run | Result |
|---|---|
| Unit 1 baseline reproduced in the copy: new file, before edits | 6 passed, 47 failed (same as Unit 1's Windows run) |
| New file after edits | 7 passed, 64 failed |
| New file + `test_020_unadjusted_price_data.py` | 22 passed, 64 failed (15 Spec 020 + 6 Unit 1 + 1 control) |
| `python -m pytest tests --collect-only -q` | 974 collected = 903 + 71 |

The full suite was not executed. Real ledger, before and after every run:
`trials.jsonl` SHA-256 `1bb5dbfe90c9df370c65910650ade15dd9d0e0366d011e09baf303975275f30f`
(174 lines), `trials.head.json` SHA-256
`f83b1b9be5a608d444d61496899d25139eb56184fd924acd030e61347d22d764`,
`returns/` absent. The only file modified in the repository by this unit's test
work is `tests/test_041_pay_date_bound.py`.

## For Camden to run on Windows

    python -m pytest tests/test_041_pay_date_bound.py -q --tb=short

Expect 7 passed, 64 failed. The 17 new failures come from three causes only:
`unsupported manifest_version`, missing `DIVIDEND_PAY_DATE_DECLARED_LAG_SESSIONS`,
and `dividend payment date missing`. Anything else means the Windows run differs
from this one.
