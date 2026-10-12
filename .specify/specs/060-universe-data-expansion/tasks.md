# Tasks: 060 — expanded ETF universe and free-data additions

Every code unit: red tests first; a Rule 12 driver with a clean control; at most 600 changed lines;
the full suite; ledger hashes before and after. **HUMAN GATE** = Camden acts. Queue ids in brackets.

- [ ] T001 `research.md`: verification record per §4 candidate (terms page, limits, coverage), each
  with source URL and date (Rule 11). Report only.
- [ ] T002 Universe builder and v1 list format (FR-001) [Q113].
- [ ] T003 Massive adapter, offline (FR-002) [Q114].
- [ ] T004 FRED/ALFRED and Treasury adapters, offline (FR-003) [Q115].
- [ ] T005 Reconciliation wiring (FR-004).
- [ ] T006 **HUMAN GATE — keys.** Camden adds the Massive, FRED and any new keys as secrets in the
  private repo and on his PC.
- [ ] T007 Bounded fetch (Codex lane) building `docs/universe/etf_universe_v1.csv` and manifests.
- [ ] T008 Rule 12 driver for §6 mutants.
