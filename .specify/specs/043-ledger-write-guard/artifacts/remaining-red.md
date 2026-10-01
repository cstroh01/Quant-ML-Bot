# T012-T015 proof record

Runs on 2026-09-30 in full copies outside C:\GitHub, Python 3.13.14.
T012 incident-red: 1 failed; actual direct library call wrote 6 records and 3 sidecars.
Its child completed and verify() passed; the failure names the changed ledger paths.
T013 enabled-red: 1 failed; D-1 B flag is unimplemented (argparse exit 2).
This is the predicted red until T025, not a successful enabled control.
T014 root-red: 7 failed / 1 passed. Six missing-resolver cases await T021.
The relocated real registry resolves to marked/extra instead of marked; assertion names both.
The planted depth check detects that wrong path. Its unmutated control remains red until T022.
T015 tripwire-proof: 8 passed; unchanged control, append, sidecar addition,
head removal, finally-on-exception, manifest, environment, and copy-boundary checks.
The planted changes are confined to stand-in directories, not the real ledger.
Evidence: each run's .txt, -meta.json, -ledger.json; incident/enabled also -events.jsonl.
All real-ledger tripwires report equality. T020 and later are not started.
