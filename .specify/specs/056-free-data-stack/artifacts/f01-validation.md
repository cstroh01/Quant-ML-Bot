# 056 F01: session-label calendar checks, fail-closed close comparison, (start, end) fact periods

Source: Codex cross-review 2026-10-08 (CROSS-REVIEW-MAIN.md, private folder), 056 P1 findings at
`scripts/data_sources.py` L49 (completed_session not checked against a calendar), L89 (infinite
closes / NaN tolerance hid mismatches), L101 (`facts_as_of` keyed on `end` only). Synthetic only.
EXAMPLE — NOT A RESULT.

## Red (main 2c72c9a, new tests in test_056_checks.py / test_056_manifest.py)
```
FAILED tests/test_056_checks.py::test_invalid_tolerance_refuses[nan]
FAILED tests/test_056_checks.py::test_invalid_tolerance_refuses[inf]
FAILED tests/test_056_checks.py::test_invalid_tolerance_refuses[-1.0]
FAILED tests/test_056_checks.py::test_facts_with_the_same_end_but_different_start_are_separate_periods
FAILED tests/test_056_checks.py::test_both_sources_infinite_is_a_mismatch_not_agreement
FAILED tests/test_056_manifest.py::test_session_label_must_be_a_completed_nyse_session[2026-10-10-fetched_at0]
FAILED tests/test_056_manifest.py::test_session_label_must_be_a_completed_nyse_session[2026-10-08-fetched_at1]
FAILED tests/test_056_manifest.py::test_session_label_must_be_a_completed_nyse_session[2026-10-07-fetched_at2]
FAILED tests/test_056_manifest.py::test_calendar_dated_sources_allow_non_sessions_but_never_the_future
9 failed, 29 passed in 0.36s
```
(Single-sided infinite/zero/negative closes were already reported; both-sides-infinite and NaN
tolerance were not.)

## Fixes (`scripts/data_sources.py`)
- `SourceManifest.label_calendar` (default `nyse_session`): the label must be an NYSE session whose
  16:00 ET close is at or before `fetched_at`. `calendar_date` (EDGAR, OpenFIGI, ALFRED, French) must
  not be after the fetch's New York date. Unknown calendars refuse.
- `_bars` refuses a payload containing any non-session label, not just a bad last label.
- `close_mismatches`: tolerance must be finite and ≥ 0; a missing, non-finite or non-positive close on
  either side is a mismatch.
- `facts_as_of` keys on (end, start): quarter and year-to-date durations sharing an end, and instants,
  stay separate. The U4b1 per-start workaround in `CompanyFacts.as_of` still holds and is now redundant.

## Not in this unit
- Spec 056 §3 FR-007 still cites Codex's private draft for the M01–M23 acceptance matrix; inlining it
  needs that file (private folder), not available to this cloud session.
- Pending decisions unchanged: EDGAR 16:00–17:30 acceptance visibility, acceptance-time zone,
  snapshot_hash provenance, FR-003 license-note field, ALFRED vintage lag, single-process SEC rate.

## Rule 12
`python tests/mutation/run_056_validation_mutants.py` → 8/8 killed.
