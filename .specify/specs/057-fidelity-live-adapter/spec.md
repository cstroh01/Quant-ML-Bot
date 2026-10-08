# Feature Specification: Fidelity LIVE execution adapter (unofficial, risk accepted)

**Spec number**: 057
**Created**: 2026-10-07
**Status**: Adopted under `docs/SCOPE-V1.md` §10. All code is `exec/` — Rule 7 reviewed lane: drafted
only on Camden's per-change instruction, merged only after his line-by-line read. LIVE stays locked
behind §5 and 051 arming.

## 1. Context
Fidelity offers no official retail trading API; SnapTrade's Fidelity link is read-only. Camden
requires LIVE execution at Fidelity and accepted in writing (2026-10-07) that an unofficial
integration may breach Fidelity's terms and risk account restriction. Fidelity has no paper mode.

## 2. Requirements
- **FR-001 Interface.** Implements the broker interface used by `order_gateway`: account summary,
  positions, settled cash, order preview, place, status by client id, cancel.
- **FR-002 Preview default.** Without an explicit LIVE arming record (051 FR-009) every call is
  preview-only; place/cancel refuse.
- **FR-003 Gate path.** Every order passes `order_gateway.submit_order` (034/032 gate) first.
- **FR-004 Credentials.** Username, password and TOTP seed resolve only from secrets named in the
  profile; never logged, printed, persisted or in exceptions. Session tokens live in memory only.
- **FR-005 Normal-customer behavior, no evasion.** Few orders per session, during market hours, from
  one session per run; no fingerprint spoofing, IP rotation, CAPTCHA solving or 2FA bypass. A login
  challenge, security prompt or account warning halts the profile and alerts Camden.
- **FR-006 Unknown is unknown.** Timeouts and unparseable responses leave reservations open (049 FR-006);
  reconciliation reads order status by the bot's client id before any new decision.
- **FR-007 Dependency vetting.** Any third-party Fidelity library is pinned by version and hash,
  source-audited for exfiltration/telemetry before adoption (Rule 6), and wrapped so it can be replaced.
- **FR-008 Positions read** feeds 054 as `read_holdings`.

## 3. Decisions
- **D-1 (Camden)** Fidelity is the LIVE executor; risk accepted.
- **D-2 (quant-ml-genius)** Evaluate in order: (a) an API-level client (e.g. the community
  `fidelity-trader-api` SDK) after source audit; (b) Playwright browser automation of Fidelity's
  site as fallback. Choose the one that returns order status by id and supports preview.
- **D-3 (Camden, at arming)** LIVE bot budget (a few hundred dollars), 0.20 daily deploy fraction.

## 4. Rule 12 mutants (fakes only; no real Fidelity call in tests)
Place succeeds without arming; order bypasses the gate; credential appears in a log/exception;
timeout releases a reservation; security challenge ignored instead of halting; second session opened in one run.

## 5. Acceptance
Fakes-only suite green with mutants killed; dependency audit recorded; Camden's line-by-line review;
a supervised preview-only session against his real account (no order); LIVE activation only after §5.
