# T003 measured baseline

Run: baseline-clean, 2026-09-30, Camden venv Python 3.13.14.
`python -m pytest tests`: exit 0; 1003 passed, 0 failed, 0 errors; 2 warnings.
Evidence: baseline-clean.txt, baseline-clean-meta.json, baseline-clean-ledger.json.
The full copy was outside C:\GitHub; all real ledger hashes match T002.
041 merge confirmation: Camden supplied bb16148d075aace16d52615a4397cc3a7b3b1965.
No version-control command was used to verify that statement.

The earlier setup attempt (baseline.txt / baseline-meta.json / baseline-ledger.json)
was 999 passed, 4 failed, 0 errors: injected GITHUB_SHA overrode source-identity fixtures.
Its four failures were test_source_identity_full_sha_no_subprocess [detached],
[loose], [packed], [missing], all in tests/test_033_trial_ledger.py.
Removing that injected variable produced the measured clean baseline above.
Both attempts left the real ledger identical. No source change was used to fix the run.
