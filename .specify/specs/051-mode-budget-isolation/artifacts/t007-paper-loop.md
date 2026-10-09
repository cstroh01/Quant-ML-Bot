# 051 T007 evidence, 2026-10-08 (Linux, Python 3.13)

Reviewed-lane change to `exec/paper_loop.py` (Rule 7: Camden reads every line).
`tests/test_051_paper_loop_profile.py`: 7 passed. `tests/test_049_paper_loop.py`: 23 passed (no-profile behavior unchanged).
Broker reports $1,000,000 equity and cash; a $5,000 profile with a 0.2 daily fraction plans against $5,000 and spends at most $1,000.

| Mutant | Result |
|---|---|
| budget ignored (size against broker equity) | killed (survived first; `test_targets_are_planned_against_the_bot_budget` added) |
| budget refusals dropped | killed |
| settled cash taken from equity | killed |
| bounded sizes not applied | killed |
| LIVE profile accepted | killed |
| state not namespaced | killed |
| profile name not recorded | killed |
| credentials from shared APCA names | killed |

Control (unmutated): 30 passed. `ops/workflows/paper-loop.yml` now passes `--profile/--profiles-file`
and gives each matrix leg only its own credential names; actionlint clean.
