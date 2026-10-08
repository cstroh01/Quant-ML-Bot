# Tasks: 051 mode and budget isolation

- [x] T001 U1 contracts: `tests/test_051_profiles.py` red (module absent / rules unenforced).
- [x] T002 U1 implement `scripts/mode_config.py` profiles, default PAPER, isolation, arming. Mutants: endpoint-only LIVE, shared paths, wrong fingerprint, expired arming.
- [x] T003 U2 contracts: `tests/test_051_sizing.py` (budget bound under inflated broker equity, daily cap, fractional/whole, min notional, settled cash).
- [x] T004 U2 implement sizing boundary in `mode_config.py`. Mutants: cap removed, budget from equity, unsettled cash spent, fractional when not allowed.
- [x] T005 U3 contracts + implement ownership/exposure. Mutant: external shares become sell intents.
- [ ] T006 Full suite + mutation evidence in `artifacts/`.
- [ ] T007 **Reviewed lane (`exec/`)**: wire profiles into `exec/paper_loop.py`; Camden reads every line.
- [ ] T008 **Human gate (Camden)**: create the second Alpaca paper account ($5,000) and add its keys as secrets.
- [ ] T009 Supervised small-profile PAPER run; record evidence.
