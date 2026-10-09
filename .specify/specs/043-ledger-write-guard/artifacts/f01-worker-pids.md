# 043 T037 / F01: independent spawned-worker PID evidence

Windows CI run 37885161890 failed at `tests/test_043_enablement.py::test_enabled_e4_records_in_actual_spawned_workers`: the shared PID file contained a blank record (int('') raised). The remaining 1445 tests passed. This repair gives each actual worker its own PID file rather than ignoring malformed evidence. Existing E4 enablement/ledger assertions are retained.

Synthetic harness evidence only. EXAMPLE — NOT A RESULT. No research computation, recording guard, event schema, production ledger, broker code or dependency changes.

## Isolated Windows checks

Base d649f88a41f4af1d5c37c16618eaa877d1b0fadc; immutable archive SHA-256 c4643bcf65b1a4052cf21dde00ece695f6cc6a313d8b5b803344bf5ad3717a11. Python 3.13.14. Child environment excludes inherited recording enablement and credentials; SPEC043_REAL_ROOT points to the protected real checkout. Commands execute in the archive, never the real checkout.

- `python -B -m pytest tests/test_043_worker_pids.py tests/test_043_enablement.py -p no:cacheprovider`: 13 passed.
- `python -B -m pytest tests -p no:cacheprovider`: 1454 passed, 0 failed/errors, two dependency deprecation warnings (536.12 seconds). New tests: six; base contains the two #94 contracts.
- Whole copied/production docs/trials manifests unchanged. All other original Git blobs unchanged; mutation edits restored before the full suite.

## Rule 12, assertion-specific red proofs

Both mutations run only the six new tests in the isolated copy; neither is counted from collection/import errors.

| Planted defect | Intended failure | Result |
|---|---|---|
| Replace the per-PID file producer with the old shared append producer | Exact actual-child PID assertion in test_two_actual_processes_each_leave_exact_pid_evidence; valid round-trip assertion | 2 failed, 4 passed |
| Replace malformed-record ValueError with continue | test_malformed_or_mismatched_record_is_never_silently_ignored for empty/non-PID content: DID NOT RAISE | 2 failed, 4 passed |

Unchanged controls: two actual Python workers each report their own PID independently on stdout, the PID files match both exactly, and the parent's PID is absent. The test compares Python PIDs rather than Windows venv launcher PIDs. Valid records round-trip; negative and filename-mismatched records refuse.

Tested source SHA-256:
- tests/ledger_guard_child.py: 2cab030d3ddb21274b8ac98b1ac15a7fc8c015441890e324e0a5a1c8f1bab1db
- tests/test_043_worker_pids.py: a16514c9a9340b020752f2f93ce16afba27c2bad9f14e8fc49600da26f7a416f

CI on the proposed head and its integration with current main remains a separate merge check. No strategy metrics.
