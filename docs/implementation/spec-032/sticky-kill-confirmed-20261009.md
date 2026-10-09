# Spec 032 audit defect 4 — sticky `kill_confirmed`

EXAMPLE — NOT A RESULT. Synthetic gate state only. Base: main `bfff9c6`.
Sources: `docs/cleanup-audit-2026-09-18/AUDIT.md:419` and `docs/HANDOFF-2026-09-25.md:442`.
SCOPE §3 item 4 names this as the one 032 defect that spec 034 did not cover.

## Defect
`confirm_kill` stored `kill_confirmed=True` and never cleared it. A later confirmation reporting any
of these left the stale True in place:
- working orders still open
- a broker not yet disabled
- an unknown disable status
- no evidence at all

`reset_kill` accepted that historical flag, so trading could resume on outdated broker evidence.

## Fix (`scripts/live_safety_gate.py`, `confirm_kill`)
Any non-confirming status now revokes a stored confirmation inside the same `BEGIN IMMEDIATE`
transaction. It writes `kill_confirmed=False` and logs `KILL_CONFIRMATION_REVOKED`.

Unchanged:
- Re-confirming with fresh broker evidence permits the reset again.
- The operator attestation path.
- Latch ordering.

## Evidence (Linux, Python 3.13.16)
- **Red:** the new `tests/test_032_kill_confirmed.py` ran against the unmodified gate with 2 failed and
  2 passed. The failure was `032 STICKY reset accepted a stale confirmation after working orders
  reopened`, plus the planted-defect test.
- **Green:** 4 passed. The existing safety tests also pass: `test_live_safety_gate`,
  `test_safety_router`, `test_order_gateway`.
- **Rule 12:** an in-memory mutant (`mutation_support_032.killed`) restores the pre-fix behavior. The
  sticky oracle fails against it, and the unmutated control passes.
- Full suite: 1737 passed, 1386 subtests passed, exit 0. Ledger `1bb5dbfe…` unchanged. Safety code: Rule 9a excludes it, so Camden merges.
