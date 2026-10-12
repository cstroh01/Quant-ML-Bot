# Spec 038 T022 — register and stamp mutation driver (2026-10-12)

Queue Q96. Commits `tests/mutation/run_038_register_stamp_mutants.py`, the driver #153 deferred for the
300-line cap, and ticks T020 and T021 (merged in #153) and T022. No source, test, `docs/trials/` or
`data/cache/` byte changed. Linux evidence only. No CI workflow runs `tests/mutation/run_*.py` drivers, so
the driver's Windows path has not been exercised anywhere.

- **Revision:** `origin/main` `3b54c5be74fcc000862fb8c1cea4fb63bdcda92e`. **Python:** 3.12.3 (Linux, fresh venv).
- **Command:** `python tests/mutation/run_038_register_stamp_mutants.py` → exit 0.
- **Shape:** as `run_058_t007_mutants.py`: each one-site mutant goes into an isolated copy (`driver_support`),
  an unchanged copy runs first as the control, a kill is a JUnit *failure* (never an error) whose message
  carries the witness, and the real sources and `docs/trials/` are checked byte-identical afterwards.

## Run

```
CONTROL green (unchanged copy, 24 collected)
KILLED   M1 dividend-bound item dropped -> 038 REGISTER drift
KILLED   M1-scope SCOPE copy gains a bullet -> 038 REGISTER drift
KILLED   M2 commit cached across calls -> 038 STAMP M2 stale commit
KILLED   M3 run date from the last bar -> 038 STAMP M3 run date
KILLED   M3b local zone instead of UTC -> 038 STAMP M3b local zone
KILLED   review: workspace hard-coded -> 038 STAMP workspace
KILLED   review: zone east of UTC -> 038 STAMP M3b midnight
KILLED   review: data_end after run accepted -> DID NOT RAISE
KILLED   review: register entries reordered -> 038 REGISTER drift
KILLED   review: naive clock accepted -> DID NOT RAISE
KILLED   review: Sharpe status reworded -> 038 REGISTER sharpe_status
11/11 killed; sources and docs/trials (6 files) byte-identical
```

M2 is planted with `GITHUB_SHA` cleared by the stamp tests' autouse fixture, so the commit comes from the
synthetic `.git` whose HEAD moves between calls. M3b is never skipped (SC-003). Where `time.tzset` is missing (Windows), the
test's own `TZ=America/New_York` case skips, so the driver runs the M3b child with `TZ=EST5EDT` in its
environment (a POSIX-format zone the C runtime's `localtime` reads on both platforms) and counts any
`038 STAMP M3b` failure as the kill, for example the UTC−5 evening clock. If the zone is not honoured, M3b
survives and the driver exits 1. That path was simulated on Linux (forced `HAS_TZSET = False`, and the TZ
test forced to skip): with `EST5EDT` M3b was killed (11/11, exit 0); with a zone that changes nothing
(`UTC0`) it printed `SURVIVED`, 10/11, exit 1. It has **not** run on real Windows. The two `DID NOT RAISE` mutants are pinned
to their own refusal case (`test_refusals[change4-ValueError]`, `[change0-ValueError]`), so a failure in
another refusal case cannot be counted as their kill.

## Rule 12 — the driver itself goes red

In a scratch copy of the tree, the M2 assertion in `tests/test_038_stamp.py` was weakened to
`line(second, "commit:").startswith("commit: ")` (a plausible "just check the line exists" edit). The driver
then printed `SURVIVED M2 commit cached across calls`, `10/11 killed` (first driver revision), and exited 1. The scratch copy was deleted; the committed test is unchanged.

The case pin was proven the same way: with the two pinned case names swapped in a scratch copy of the
driver, both `DID NOT RAISE` mutants printed `SURVIVED`, `9/11 killed`, exit 1.
