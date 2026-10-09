# 052 T006 evidence, 2026-10-08 (Linux, Python 3.13.16)

EXAMPLE — NOT A RESULT. `tests/test_052_acceptance.py` builds one synthetic panel (9 instruments,
20 sessions from 2026-03-02) with a delisting, rename, 2:1 split, halt, stale bar, unsupported
class, future-dated listing and late-observed listing. No market data; no metric is reported.
Limitations (SCOPE-V1 §6) are unchanged: survivor basket, free-tier corporate actions, no PIT
fundamentals, daily bars, modeled costs. Real-data population is T007.

Green: 11 passed. Full suite: 1382 passed, 1386 subtests passed. `docs/trials` hash unchanged.
Driver: throwaway, outside the repo, on a copy of the tree; runs only `tests/test_052_acceptance.py`.
| Mutant | Result |
|---|---|
| control (unmutated, before and after) | pass |
| future constituent leaks into past snapshot | killed |
| late-observed fact leaks backward | killed |
| ticker change remapped to today's symbol | killed |
| delisted name dropped after delisting | killed |
| delisted name dropped from all history | killed |
| adjusted volume treated as nominal: basis check removed | killed |
| adjusted volume treated as nominal: nominal shares at latest close | killed |
| research eligibility reads rows after as_of | killed |
| cross-sectional fit uses future rows | killed |
| membership taken from the latest snapshot | killed |
| halt bypassed | killed |
| staleness bypassed | killed |
| unsupported instrument class permitted | killed |
| participation cap omitted | killed |
| broker minimum omitted | killed |
| exclusion reason suppressed: first research reason only | killed |
| exclusion reason suppressed: delisting reason not recorded | killed |
