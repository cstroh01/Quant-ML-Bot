# Tasks 065 — Verified capital scaling (PROPOSAL)

All boxes start open. This packet adopts nothing; the $200 pilot stays until
`spec.md` §6 holds. Units marked **Camden-only** are never built, ticked or
merged by an agent. Each unit stays ≤600 added+removed lines and touches only
its listed files.

- [ ] T001 **Camden-only.** Record D-1..D-6 in `spec.md` §4 (managed fraction,
  hard ceiling, SafetyConfig version, deposit deployment, re-provisioning
  route, minimum operating authority).
  Files: `.specify/specs/065-verified-capital-scaling/spec.md`.
- [ ] T002 **Camden-only.** Separate governance PR, on Camden's explicit chat
  instruction, amending only `docs/SCOPE-V1.md` §11.3 item 7 so verified,
  attributable deposits may raise authority up to the adopted hard ceiling.
  Items 1–6 unchanged. Files: `docs/SCOPE-V1.md`.
- [ ] T003 **Camden-only.** Accept 064 T003 (settled flows reach
  `BrokerSnapshot.external_cash_flow`; cash net of commitments) and evidence,
  read-only, whether the Fidelity integration exposes transfer history. Until
  both hold, authority cannot exceed $200. Files: none in this packet.
- [ ] T004 Pure `capital_authority` module: `V = C − K + B`, `A = min(H, f × V)`,
  cash bridge with asymmetric quarantine (increase freezes, decrease reduces),
  `above_ceiling_usd`, `min_operating_authority_usd`, `stage_pro_rata`. Decimal
  only; no I/O or clock. Planted defects 1, 3, 4, 5, 7, 8 at unit level, each
  with a clean control.
  Files: `scripts/capital_authority.py`, `tests/test_065_capital_authority.py`.
- [ ] T005 Read-only `pending_outflow(journal)` accessor; existing journal
  behaviour byte-for-byte unchanged (existing 064 tests stay green). Planted
  defect: a pending inbound counted as outbound.
  Files: `scripts/cash_flow_journal.py`, `tests/test_065_journal_outflows.py`.
- [ ] T006 **Camden-only (protected).** Replace `MAX_LIVE_BUDGET_USD` with
  `MAX_LIVE_AUTHORITY_USD`; LIVE `ModeProfile` mandate fields with validation;
  daily cap based on authority; pro-rata staging in `bound_buys`. PAPER
  profiles unchanged. Camden line-by-line review and merge.
  Files: `scripts/mode_config.py`, `tests/test_065_mode_config_mandate.py`.
- [ ] T007 **Camden-only (Rule 7).** Wire authority into `exec/live_loop.py` on
  top of merged 064 T003: `A` replaces grant/equity, `unattributed_cash`
  refusal, `above_ceiling_usd`, disclosure. Scenarios S1–S10 through `run_once`
  with fakes; planted defects 1–9 against the real consumer.
  Files: `exec/live_loop.py`, `tests/test_065_live_scaling.py`.
- [ ] T008 **Camden-only; only if D-3 chooses a bump.** Change
  `ALLOCATION_SAFETY_CONFIG.version` with a written gate-store migration and
  the PAPER evidence consequence accepted first.
  Files: `exec/paper_loop.py`.
- [ ] T009 **Camden-only (credential handling).** Update the provisioning
  template pins to the adopted mandate (and, if D-5 chooses it, a reviewed
  profile-only mode). Fake runner only; no real `gh` call.
  Files: `scripts/fidelity_provision.py`, `tests/test_064_fidelity_provision.py`.
- [ ] T010 Acceptance record (exact head, suite counts, mutation receipts,
  ledger hashes) and the `capital_authority` row in the CLAUDE.md module table.
  Files: `docs/implementation/spec-065/acceptance.md`, `CLAUDE.md`.

After T001–T010: Camden personally deletes and re-provisions the secrets
(`spec.md` FR-007) and, separately, arms LIVE only once §11.3 items 1–6 hold.
Neither is a task here, and no checkbox substitutes for either.
