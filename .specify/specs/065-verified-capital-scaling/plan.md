# Plan 065 — Verified capital scaling (PROPOSAL)

Proposal only. Nothing here starts until Camden records D-1..D-7 in `spec.md` §4.
The $200 pilot stays in force throughout.

## Design

One new pure module owns authority, so the money path changes stay small and
reviewable:

- `scripts/capital_authority.py` (new; not a protected path). Inputs: settled
  cash, bot book (open orders, bot-owned quantities), last closes, journal
  result and pending outflows, previous acknowledged snapshot, mandate record.
  Outputs: `V`, `A`, `above_ceiling_usd`, cash-bridge residual, unmanaged cash `U`,
  and `stage_pro_rata(buys, cap_left)`. Decimal arithmetic, no I/O, no clock.
  It knows nothing about signals, fills or broker calls (Rule 8).
- `scripts/cash_flow_journal.py` gains one read-only accessor,
  `pending_outflow(journal)`. Existing semantics unchanged.
- `scripts/mode_config.py` (protected) holds the mandate fields, the renamed
  ceiling and the pro-rata cap base. Nothing else moves there.
- `exec/live_loop.py` (protected, Rule 7) calls `capital_authority` after
  reconciliation, sizes from `A`, bounds cash by
  `grant = max(0, min(C − U − K, A − B − R))`, relies on 064 T003a/T003b to apply
  settled flows to the breaker once, and adds the new refusal reasons and
  disclosure fields.
- `scripts/live_safety_gate.py` (protected) persists `U` and the bridge boundary
  in the T003a observation transaction (FR-002a; task T006b).

Data flow per run: reconcile → journal reconcile → cash bridge → `V`, `A` →
planner with `equity = A` → pro-rata stage → `bound_buys` → gateway. Monthly
cadence and ownership stay where they are (`scripts/paper_targets.py`,
`scripts/mode_config.py:279-298`).

## Units

| Task | Exclusive files | Owner | Depends on | Est. lines |
|---|---|---|---|---|
| T001 | `.specify/specs/065-verified-capital-scaling/spec.md` (§4 only) | **Camden-only** | packet merged | <20 |
| T002 | `docs/SCOPE-V1.md` (§11.3 item 7 only) | **Camden-only**, separate governance PR on his chat instruction | T001 | <20 |
| T003 | none in this repo: 064 T003 acceptance + read-only transfer-history check | **Camden-only** (protected / personal) | 064 T002 | — |
| T004 | `scripts/capital_authority.py`; `tests/test_065_capital_authority.py` | agent (Rule 9b) | T001 | ≤450 |
| T005 | `scripts/cash_flow_journal.py`; `tests/test_065_journal_outflows.py` | agent (Rule 9b) | T001 | ≤150 |
| T006b | `scripts/live_safety_gate.py`; `tests/test_065_gate_unmanaged.py` | **Camden-only** (protected) | T004 | ≤250 |
| T006 | `scripts/mode_config.py`; `tests/test_065_mode_config_mandate.py` | **Camden-only** (protected) | T004 | ≤350 |
| T007 | `exec/live_loop.py`; `tests/test_065_live_scaling.py` | **Camden-only** (Rule 7) | T003, T004, T005, T006, T006b | ≤600 |
| T008 | `exec/paper_loop.py` (`ALLOCATION_SAFETY_CONFIG.version` only) | **Camden-only**; only if D-3 says bump | T006 | <20 + migration note |
| T009 | `scripts/fidelity_provision.py`; `tests/test_064_fidelity_provision.py` | **Camden-only** (credential handling) | T006 | ≤250 |
| T010 | `docs/implementation/spec-065/acceptance.md`; `CLAUDE.md` (module table row) | agent (Rule 9b) | T004–T009 | ≤150 |

No two units share a file. T007 edits the same file as 064 T003, so it is
built on top of the merged 064 T003, never in parallel with it.

## Verification

- Each unit: focused tests red before the change, green after; each planted
  defect from `spec.md` FR-009 that the unit owns, in an isolated copy, turning
  its named test red; one clean control.
- T007 runs scenarios S1–S8, S8b, S8c and S9–S13 through `run_once` with a fake
  broker and fake journal; sockets blocked.
- Final: `python -m pytest tests` on the exact head, mutation drivers, CI. Ledger
  hashes before and after, unchanged.

## Risks

- **Feed capability.** If the Fidelity integration cannot read transfer history,
  a deposit can never be attributed: it lands in `U` (unmanaged) and `A` cannot rise.
  The spec then holds at $200 by construction. No workaround that infers deposits from
  balances is acceptable.
- **Fractional eligibility.** If any sleeve is not fractionable at Fidelity, the
  $200 end cannot hold all eight sleeves. The run halts instead of trading a
  different portfolio.
- **Version bump (D-3).** Bumping the shared config resets PAPER gate history and
  the §11.3 item 4 evidence; recommended against.
- **Re-provisioning (D-5).** With today's helper, all six secrets are deleted and
  re-entered personally. A mistake there blocks LIVE until redone; no automated
  retry exists by design.
