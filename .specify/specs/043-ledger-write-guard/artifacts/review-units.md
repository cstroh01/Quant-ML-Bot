# Review units: added plus removed lines

Counts include tests, docs, evidence and checkbox edits. No Git was used.
Each row is a sequential review unit; no row exceeds 400 lines.
Existing-file counts use byte-preserving snapshots and line comparison.
New files count every physical line; JSONL evidence uses one record per child run.
T002's previously accepted ledger-pre.json is excluded from this scope.
Other lanes' 041/044 docs and the concurrent existing-test change are excluded.

| Unit | Source/checklist lines | Artifact lines | Total |
|---|---:|---:|---:|
| T003 baseline, including setup failure evidence | 2 | 329 | 331 |
| T004 inventory | 6 | 33 | 39 |
| T010 copy support | 118 | 0 | 118 |
| T011 entry points and red proofs | 185 | 210 | 395 |
| T012 direct incident | 13 | 52 | 65 |
| T013 enabled control | 25 | 74 | 99 |
| T014 root gates | 96 | 88 | 184 |
| T015 tripwire proof | 89 | 61 | 150 |
| Final suite and scope report | 0 | 326 | 326 |

## File accounting

- T003: tasks checkbox; baseline.txt / baseline-meta.json / baseline-ledger.json;
  baseline-clean.txt / baseline-clean-meta.json / baseline-clean-ledger.json; baseline.md; session.json.
- T004: two replaced lines in spec.md (4 changed lines), tasks checkbox; inventory.md (33).
- T010: tests/ledger_copy_support.py (116 new), tasks checkbox (2).
- T011: tests/ledger_guard_child.py (157 new), tests/test_043_entry_points.py (26 new), checkbox (2);
  entry-red.txt / -meta.json / -ledger.json / -events.jsonl, entry-red.md;
  e5-red.txt / -meta.json / -ledger.json / -events.jsonl (210 artifact lines total).
- T012: tests/test_043_incident.py (7 new), copy helper (2 added / 2 removed), checkbox (2);
  incident-red.txt / -meta.json / -ledger.json / -events.jsonl (52).
- T013: tests/test_043_enabled_control.py (17 new), child helper (6 added), checkbox (2);
  enabled-red.txt / -meta.json / -ledger.json / -events.jsonl (74).
- T014: tests/test_043_project_root.py (94 new), checkbox (2); root-red.txt / -meta.json / -ledger.json (88).
- T015: tests/test_043_copy_support.py (87 new), checkbox (2);
  tripwire-proof.txt / -meta.json / -ledger.json and remaining-red.md (61).
- Final: phase1-full.txt (156), -meta.json (14), -ledger.json (23), -events.jsonl (7),
  phase1-summary.md (52), scope-audit.json (32), and this review-units.md (42).

Both existing Markdown files retain LF exactly. New files use LF.
No implementation file from T020 onward was created or edited.
