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

### Amendment — 2026-10-15 (Camden, D-4..D-7 approved in chat)
- D-4 Primary SDK only (fidelity-trader-api==0.2.2). Playwright fallback dropped: stealth-by-default
  (FR-005), no settled-cash read, no order status by id. On SDK breakage: halt; Camden trades manually.
- D-5 Session tokens stay memory-only (FR-004 unchanged). Never import or call cli/_session or any
  save/load path. One login (with TOTP) per run; at most one run per trading day.
- D-6 The SDK's status-1201 TOTP step answered with the configured seed is EXPECTED, not a challenge.
  The wrapper must observe it (record `totp_step: true` in run evidence). Any other non-1200 status,
  AuthenticationError, CSRFTokenError, 401/403, login redirect, or unknown auth payload = latched halt.
- D-7 The SDK's built-in Trader+ client headers are accepted as inherent to D-1. Headers are static:
  never modified, randomized, rotated or extended by our code. Recorded as risk, not compliance.

### Dedicated-account amendment (Camden, 2026-10-15, codex-task6c-dedicated-account.md)
The dedicated $200 cash bot account alone is in scope (Camden, 2026-10-17; settled cash only). Every account-sensitive request filters exactly that
account; a missing/swapped filter or foreign account in any response halts. Evidence records its SHA-256
fingerprint only. Broker sleeve quantities must equal the bot ledger exactly; sweep is cash; foreign
symbols/mismatches latch and alert. No manual baseline. Budget is min($200, settled_amt); profiles above $200 are refused before login. Fractional share quantities are floored to .001 both before and after daily-cap sizing; minimum order notional $1. coreBalance
is recorded separately. Unsettled deposits produce a normal refusal, not an error or latched halt.

### Host/credentials amendment (Camden, 2026-10-15, Task 6d)
Windows laptop first, dedicated Linux runner later. The exact live_fidelity credential_refs and
LibraryBroker account reference are FIDELITY_LIVE_USERNAME, FIDELITY_LIVE_PASSWORD,
FIDELITY_LIVE_TOTP, FIDELITY_LIVE_ACCOUNT. Q140 follows Q135: Windows Credential Manager
(service qmb-fidelity-live) or Linux environment, child env only, no parent mutation or disclosure.
Q138 provides both dispatch-only self-hosted variants; no installation or session is authorized here.

## 4. Rule 12 mutants (fakes only; no real Fidelity call in tests)
Place succeeds without arming; order bypasses the gate; credential appears in a log/exception;
timeout releases a reservation; security challenge ignored instead of halting; second session opened in one run.

## 5. Acceptance
Fakes-only suite green with mutants killed; dependency audit recorded; Camden's line-by-line review;
a supervised preview-only session against his real account (no order); LIVE activation only after §5.

### Fingerprint amendment (Camden, 2026-10-15, Task 8)
Q135 supersedes the earlier four-name and plain-SHA fingerprint text: exactly FIDELITY_LIVE_USERNAME, FIDELITY_LIVE_PASSWORD, FIDELITY_LIVE_TOTP, FIDELITY_LIVE_ACCOUNT, FIDELITY_LIVE_FP_KEY; FP_KEY is exactly 64 lowercase hex characters and fingerprints are HMAC-SHA256 keyed by its 32 decoded bytes, never plain SHA-256.
