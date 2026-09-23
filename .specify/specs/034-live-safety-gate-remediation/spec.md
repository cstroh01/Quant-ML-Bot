# Feature Specification: Live-Safety-Gate Remediation

**Feature**: `034-live-safety-gate-remediation`
**Status**: Draft specification only; no code changes made yet.
**Priority**: P0 — spec 032 (`scripts/live_safety_gate.py`) is a hard capital
gate (Project Instructions v2.1 §6) and is not yet safe to wire to a broker.
**Scope**: Fixes and closes four defects found by Antigravity's 2026-09-22
read-only audit of spec 032 against its own spec.md, all confirmed by direct
reading of `scripts/live_safety_gate.py` during this session. This spec does
NOT touch `reports/api/routes/capital_gate.py` — that file is owned by spec
033's Gate 3 work this same window. See "Router split" below.

## Problem

Spec 032 built a 1,233-line safety-gate module with careful atomic-transaction
discipline (`BEGIN IMMEDIATE` around every state mutation) and a real evidence
log, but four defects mean it cannot yet do its one job — deny exposure when
it should. In order of how they can hurt Camden:

1. **Unwired (REQ-001 violation).** `grep -rl "live_safety_gate" scripts/
   reports/` returns only the module and its own tests. No execution
   gateway, broker adapter, or API route imports `LiveSafetyGate` anywhere in
   the repo. Every one of spec 032's careful checks is currently inert —
   exactly the Knight Capital failure mode (control existed, wasn't in the
   path) that spec 032's own research cites.
2. **Kill/rolling-halt deadlock.** `reset_kill` refuses while
   `state["rolling_halt_active"]` is true (`live_safety_gate.py:~935`).
   `reset_rolling_halt` refuses while `state["kill_latched"]` is true
   (`~992`). If both latch in the same incident — plausible, since a
   drawdown breach is a common trigger for an operator to also hit the kill
   switch — **neither can ever be cleared**, including via
   `broker_disable_independently_verified=True`, which only bypasses the
   `kill_confirmed` check, not the cross-latch check. Confirmed by direct
   read, not just cited from the audit.
3. **Pending-sell netting defect.** `_worst_case_exposure`
   (`live_safety_gate.py:680-706`) computes
   `qty = position + pending.get(name, 0.0)` — it nets a *pending, unfilled*
   sell into the exposure calculation as though it has already executed.
   A buy evaluated while an earlier sell is still working sees artificially
   reduced gross/instrument notional, and can be allowed at a size that
   would breach `max_gross_pct`/`max_position_pct` if the sell is later
   cancelled, partially filled, or rejected by the broker. REQ-004 requires
   pending orders to count toward worst-case exposure; this makes a pending
   sell count *against* it instead.
4. **Divide-by-zero / unguarded equity in the sizing check.**
   `live_safety_gate.py:655-660`:
   `exposure["instrument_notional"] / equity >= self._config.max_position_pct`
   — `equity = snapshot.equity` is used directly with no floor check. At
   `equity <= 0` (a real state — a blown account, or a broker snapshot
   during a margin call) this raises `ZeroDivisionError` (equity == 0) or
   silently flips the sign of the comparison (equity < 0), either of which
   means the one path that most needs to hard-deny instead crashes or
   passes. REQ-005 requires dynamic equity sizing; it does not currently
   specify a floor.

None of these are subtle model bugs — they are exactly the class of defect
this project's constitution treats as more severe than a lookahead bug in a
signal, because they sit on the capital-preservation path, not the
alpha-generation path.

## Router split (decided 2026-09-22, binding on this spec)

`reports/api/routes/capital_gate.py` is a **read-only status cockpit** (5
hardcoded `CapitalGateItem` rows, no control actions) and is being wired for
Gate 3 (DSR/PBO) by spec 033 this same window. This spec adds a **new** file,
`reports/api/routes/safety.py`, owning Gate 5's *operational* endpoints:

- `POST /api/safety/kill` → `LiveSafetyGate.request_kill`
- `POST /api/safety/kill/confirm` → `LiveSafetyGate.confirm_kill`
- `POST /api/safety/kill/reset` → `LiveSafetyGate.reset_kill`
- `POST /api/safety/halt/rolling/reset` → `LiveSafetyGate.reset_rolling_halt`
- `GET /api/safety/status` → `LiveSafetyGate.status`

Do not edit `capital_gate.py` in this spec. If Gate 5's *status row* should
eventually read live state from `safety.py`'s data, that is a follow-on spec,
not this one — do not scope-creep into it.

## Requirements

- **REQ-034-001 — Wire the gate into the order path (closes REQ-001).**
  Every code path capable of submitting a new or exposure-increasing order
  MUST call `LiveSafetyGate.evaluate_order` first, and MUST treat any
  non-`ALLOW` outcome as a hard stop, not a warning. Since no broker adapter
  exists yet in this repo, this requirement is satisfied by: (a) a minimal
  `scripts/order_gateway.py` seam that every future broker adapter is
  required to call through (single chokepoint, per module-boundary table),
  and (b) an AST/static check (mirroring the project's existing AST-suite
  pattern) that fails CI if any future module imports a broker client
  without also importing `LiveSafetyGate` in the same module. Do not build a
  real broker adapter in this spec — no broker is chosen yet. The chokepoint
  and the CI guard are what "wired" means until one exists.

- **REQ-034-002 — Break the kill/rolling-halt deadlock.** Define an explicit
  precedence: the kill switch is the outer latch. `reset_rolling_halt` MUST
  be reachable while `kill_latched` is true (a rolling halt clearing does not
  itself resume trading — the kill latch still blocks `evaluate_order`
  independently), so an operator can always clear the inner (rolling) latch
  first, then clear the outer (kill) latch, in that order, with no state
  requiring the other to clear first. Add a same-transaction regression test
  that latches both, asserts `reset_kill` is refused before
  `reset_rolling_halt` runs (documents old behavior as the failing case),
  then asserts the fixed order succeeds. `reset_kill`'s existing
  cross-checks against `reconciliation_halt` are unaffected.

- **REQ-034-003 — Fix pending-order netting direction.** Worst-case exposure
  MUST count a pending sell at its **pre-fill** quantity for gross/position
  sizing purposes (i.e., do not subtract an unfilled sell's quantity from
  current position when computing worst-case notional), while still
  reserving against double-submission of the same order via the existing
  `pending_orders` table. A pending buy continues to add to worst-case
  exposure as today. Add a test: current position 100 shares, one pending
  sell order for -50 unfilled, evaluate a new buy sized to be allowed only
  if the sell is assumed filled — assert `DENY`.

- **REQ-034-004 — Floor equity before any division.** Any check that divides
  by `snapshot.equity` (currently `max_position_pct`, `max_gross_pct`) MUST
  treat `equity <= 0` as an unconditional `DENY` with a distinct reason code
  (e.g. `DENY_NONPOSITIVE_EQUITY`) evaluated before the division, never a
  `ZeroDivisionError` and never a sign-flipped pass. Add both an
  `equity == 0` and an `equity < 0` regression test.

- **REQ-034-005 — Router split.** `reports/api/routes/safety.py` implements
  the five endpoints listed above, each a thin wrapper over the
  corresponding `LiveSafetyGate` method with FastAPI request/response models
  in `reports/api/schemas.py` (new models, additive only — do not modify
  existing `CapitalGateItem`/`CapitalGateStatusResponse`). `capital_gate.py`
  is untouched by this spec; if `git diff` shows any change to it, that is a
  spec violation, not a merge nit.

## Non-goals

- No broker adapter, no real order execution, no credentials or `exec/`
  work — flagged per CLAUDE.md, not built here.
- No change to position-sizing math in `scripts/portfolio_risk.py`.
- No change to `capital_gate.py` (see Router split).
- No attempt to fix the HAC bandwidth defect logged 2026-09-14
  (`metrics.py:343-344`) — separate, unverified-as-fixed, track it as its
  own follow-up (see session notes), not folded in here to keep this PR
  reviewable.

## Acceptance

All four defects above have a red-then-green regression test in
`tests/test_live_safety_gate.py` (or a new `tests/test_safety_router.py` for
REQ-034-005), the full suite (`python -m pytest tests`) shows no new
failures relative to the current baseline (817 passed / 18 failed / 9 errors
as of the spec-033 Phase 7 checkpoint — diff against that baseline the same
way the 2026-09-14 019-blast-radius churn was diffed, not against a fresh
zero), and `git diff --stat -- reports/api/routes/capital_gate.py` is empty.
PR description follows CLAUDE.md's five-point requirement in full.
