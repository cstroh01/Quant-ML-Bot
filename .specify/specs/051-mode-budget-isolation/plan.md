# Plan: 051

Module: `scripts/mode_config.py` (pure; no network, no credential values). Tests: `tests/test_051_*.py`.
Units (each ≤300 added+removed lines incl. tests and evidence, contracts red first):
- **U1** profiles, defaults, isolation, arming validation (FR-001/002/003/009).
- **U2** budget sizing boundary: budget/daily cap/fractional/minimum/settled cash (FR-004/005/007/008),
  a pure function consumed by `paper_targets.order_deltas` callers; never imports broker code.
- **U3** ownership/exposure: bot-owned lots vs external holdings (FR-006), aggregate exposure input for 054.
- **U4** (`exec/`, reviewed lane) paper loop loads a profile; namespaced state/log; fakes prove the
  adapter receives only its profile's refs. Drafted by an agent only on Camden's per-change instruction.
