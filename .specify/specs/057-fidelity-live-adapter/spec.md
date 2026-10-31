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
  Superseded 2026-10-23 by spec 064 amendment 002: daily deploy fraction 1.0.

### Amendment — 2026-10-15 (Camden, D-4..D-7 approved in chat)
- D-4 Primary SDK only (fidelity-trader-api==0.2.2). Playwright fallback dropped: stealth-by-default
  (FR-005), no settled-cash read, no order status by id. On SDK breakage: halt; Camden trades manually.
- D-4a (Camden, 2026-10-29, after the FR-013 record of private run 40888803539): the SDK's
  status-1201 step (D-6) turns the configured base32 seed into a code with `import pyotp`, which
  is not among the SDK's declared dependencies, so the hash-locked host never had it and the SDK
  raised AuthenticationError before any TOTP request. `pyotp==2.10.0` is added to
  `requirements-fidelity-host.txt` with its wheel hash. It is the only addition: no SDK, wrapper
  or guard change, and no other source of a TOTP code.
- D-5 Session tokens stay memory-only (FR-004 unchanged). Never import or call cli/_session or any
  save/load path. One login (with TOTP) per run; at most one run per trading day.
- D-5a (Camden, 2026-10-30, answering "Do you approve amending D-5 for up to two login probes?":
  "Yes, build the probe"): up to two extra supervised logins in total, started by Camden, for
  entitlement diagnosis only, through `exec/fidelity_login_probe.py` and the dispatch-only
  `ops/workflows/fidelity-login-probe.yml`. Login with every LibraryBroker guard and the
  entitlement check, then only if that passes read settled cash and positions of the dedicated
  account. No preview or place path and no arming. The cap counts persisted records, with a marker
  pushed before login. It refuses on KILL, refuses unless HALTED exists (so D-6 and FR-005 still
  hold: the profile is already latched, and a failed probe alerts Camden), and never writes HALTED,
  `attempts/` or `preview-sessions/`. Its record is not preview evidence. D-5 is otherwise unchanged.
- D-6 The SDK's status-1201 TOTP step answered with the configured seed is EXPECTED, not a challenge.
  The wrapper must observe it (record `totp_step: true` in run evidence). Any other non-1200 status,
  AuthenticationError, CSRFTokenError, 401/403, login redirect, or unknown auth payload = latched halt.
- D-6a (Camden, 2026-10-28, after the FR-013 record of private run 40703286171): Fidelity
  permanently moved its login page on or before 2026-10-26. Exactly one redirect is accepted:
  the SDK's pre-credential page load whose URL before the query is exactly
  `https://digital.fidelity.com/prgw/digital/login/atp`, answered `308` with a target that is
  exactly `https://digital.fidelity.com/prgw/digital/signin/atp` plus the identical query (no
  port, userinfo, `;params`, fragment or other spelling), before any request to
  `ecaap.fidelity.com`. A missing marker refuses. Every other login redirect, and any redirect
  at all from the moved page, remains a latched halt (D-6).
- D-7 The SDK's built-in Trader+ client headers are accepted as inherent to D-1. Headers are static:
  never modified, randomized, rotated or extended by our code. Recorded as risk, not compliance.
- D-8 (Camden, 2026-10-29, after an offline dress rehearsal of the merged pin): safety-gate
  price marks built in `exec/live_loop.py` take broker prices for non-cash symbols only. A core
  money-market row (`_CASH_SYMBOLS`) is never a gate position, so its price fed only the
  observation digest, where a missing `lastPrice` became `float(None)` and a latched halt.
  Sleeve marks stay last close x (1 + GAP_ALLOWANCE); ownership, the foreign-symbol halt and
  every other guard are unchanged.
- D-9 (Camden, 2026-10-30, after the FR-013 record of private run 41069466690): the full login
  succeeded and `context/security` answered 200, but the wrapper refused with `Fidelity
  entitlement refused`, and the record could not say whether the ATP entitlement was absent, had
  another name or value, or `errors` was non-empty. The redacted FR-013 login facts gain one
  optional `entitlement` entry read from that response: top-level key names, each entitlement's
  display, classification and a value reduced to true/false/other, and the error count with key
  names and short code/type/status values. A label that is not short plain text, or holds three
  consecutive digits, is `*`. Internal system ids, persona values and error messages are never
  recorded. Diagnostic only: the entitlement refusal itself is unchanged and is not loosened.
- D-10 (Camden, 2026-10-30, "Yes, fix it first", after a read of the merged code; no real run has
  reached this step, so this is a plausible defect and not an observed one): `settled_cash` skipped
  any snapshot stamped later than `as_of`, and every caller takes `as_of` before login, so a balance
  stamped at request time would refuse after a clean login. The upper bound is now the later of
  `as_of` and a clock read after the balance response, plus 60 seconds for Fidelity's clock leading
  the runner. This loosens one guard: a stamp up to 60 seconds ahead of the runner now counts. A
  later stamp and another New York day still never count. One read becomes stricter: a snapshot
  stamped inside the new range with an invalid amount now refuses the whole read, where it used to
  be skipped before validation. A refused read adds an optional `cash_stamps` login fact: snapshot
  count, each stamp's type name and its whole-second offset from the bound's base, never an amount
  or account value.

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

### PC-independent preview orchestration (Camden, 2026-10-19)
Camden requires ordinary execution with his development PC powered off and asks
to wire hosted Alpaca and Fidelity operation. A future Pi is optional. The
existing Windows task does not satisfy this requirement. This extension admits
offline implementation and a dormant private-host template, not broker access,
credentials migration, scheduling, deployment-pin changes or LIVE activation.

- **FR-009 Portable host.** Add `scripts/fidelity_preview_host.py` outside the
  protected adapter. Python 3.12, no Windows paths/vault/sleep dependencies.
  Default check-only; explicit input-refresh and preview modes. Fixed child
  commands only; never accept submit, arming or arbitrary commands. Preserve
  the existing allocation-aware `exec/live_loop.py` preview path and every
  protected budget, account, ownership, cash and authentication guard.
- **FR-010 Preflight.** Before each child, require an exact reviewed source pin,
  an explicitly authorized current NYSE date, 09:35 inclusive to 12:00 exclusive
  Eastern, initialized durable private state, and no KILL/HALTED. Recheck the
  clock before login after input refresh. A missing state root is not an empty
  account. Existing daily leases and durable pre-login persistence remain
  authoritative; no automatic lease clearing or session retry.
- **FR-011 Credential boundary.** Input-refresh children receive no Fidelity
  credential references. Only the fixed preview launcher receives the five
  references through its environment. No credential reads in check mode, no
  parent environment mutation, no raw child output or exception payload in logs.
- **FR-012 Private template.** `ops/workflows/fidelity-preview.yml` is a dormant
  manual-only template for the private companion repository, never a public
  self-hosted runner. Require private main, an explicit enable variable and
  authorized session, immutable main-ancestor pin, shared state-write
  concurrency, durable pre-login/final persistence, private backup and failure
  notification. Credentials are step-scoped, never workflow inputs. Installation,
  host/credential acceptance, notification receipt and real sessions remain
  human gates. Templates and fake Windows-host tests prove neither Linux
  execution nor ARM/Pi compatibility. Authentication challenges still halt.
- **FR-013 Failure diagnostics (Camden, 2026-10-26).** The first hosted preview
  (private run 40337114980) halted in `connect` and recorded only
  `abort_kind: HaltProfile`, so its cause could not be determined. A failed
  session record adds `failure`: the stage reached (`preflight`, `broker`,
  `login`, `reconcile`, `settled_cash`, `holdings`, `ownership`, `csv`,
  `allocation`, `preview`); the exception type; its message only when the type
  is defined in `exec/` (fixed texts and type names), at most 200 characters;
  and the login diagnostic. That holds the first refusal raised by this
  adapter's own guards or the library exception's type name, whether status
  1201 was seen, and the latest 20 responses as host (`*.fidelity.com`, else
  `other`), method, HTTP status, integer Fidelity auth code (auth endpoints
  only) and path with the query dropped and every segment that holds a digit
  or exceeds 24 characters masked. No library message, header, cookie, body or
  query string is recorded, and the existing credential guard still blanks the
  record. Diagnostics change no guard, halt or retry; a clean record is
  unchanged.

Acceptance: offline boundary/gap/DST and credential/command contracts, planted
defects, full suite; then independent exact-head reviews. Human-reviewed private
installation and separately authorized real previews follow. The existing five
distinct-session/holdings and capital gates remain binding. PAPER schedule
activation still follows 055 G16; this extension enables no schedule.
