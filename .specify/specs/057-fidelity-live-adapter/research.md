# 057 U0: dependency audit of candidate Fidelity libraries (2026-10-07)

Offline source reading only. No credentials, no Fidelity request, no account access.
Downloaded from PyPI into a scratch directory; nothing added to `requirements*.txt`.

| | `fidelity-trader-api` 0.2.2 | `fidelity-api` 0.0.17 |
|---|---|---|
| Wheel SHA-256 | `f5a94056bd9a055ba88482ffcc7dc17013de9871b852b4d9b0dc55352506dd15` | `4d6e3cb4ab905e2ab966b7e8f139c5557bc09dbb4e68b7384e27369c2dc3f27f` |
| Source | github.com/brownjosiah/fidelity-trader-api | github.com/kennyboy106/fidelity-api |
| Mechanism | HTTP client (httpx) for Trader+ endpoints, reverse-engineered | Playwright browser automation of fidelity.com |
| Size | ~10.5k lines | ~1.6k lines |
| Runtime deps | httpx, pydantic (boto3 optional) | playwright, playwright-sm, pyotp |
| Login | `login(username, password, totp_secret)` | browser form + pyotp TOTP |
| Network destinations in source | Fidelity domains only (`*.fidelity.com`) plus Fidelity's embedded research vendors (`fidelity.apps.livevol.com`, `fidelity-widgets.financial.com`) used only by research modules | `digital.fidelity.com` only |
| Telemetry / third-party upload | none found | none found |
| Equity preview/place | yes: `preview_order` returns `confNum`; `place_order(order, conf_num)` | yes (UI flow) |
| Order status read | yes (`orders/status.py`) | positions/summary pages |

## Findings that bind the adapter (U1)

1. **Retries can duplicate orders.** `RetryTransport` replays any request, POSTs included, on
   timeouts and 5xx. Default `max_retries=0`; the adapter MUST construct clients with
   `max_retries=0` and never enable retries for preview/place/cancel (FR-006).
2. **Margin by default.** `EquityOrderRequest.acct_type_code` defaults to `"M"` (margin). The adapter
   MUST set `"C"` (cash) on every order; D-3 forbids margin.
3. **No client order id.** Fidelity orders carry a `confNum` from preview, not a caller id. The
   adapter maps the bot's deterministic client id (055) to the preview `confNum` and persists that
   mapping BEFORE `place_order`; reconciliation reads status by `confNum`.
4. **Credential repr.** The library's `Credentials` dataclass has a default `repr` that prints the
   password. The adapter never constructs or logs it; it passes values straight from secrets.
5. **CLI prints cookie counts** (`cli/_auth.py`); the adapter never imports `cli`.

## Recommendation (quant-ml-genius, D-2)
Adopt `fidelity-trader-api==0.2.2` pinned by the hash above, imported only inside
`exec/fidelity_live.py`, behind the broker interface so it can be replaced. Keep `fidelity-api`
(Playwright) as the documented fallback. Re-audit on every version bump. Risk accepted by Camden
(SCOPE-V1 §10); this audit does not make the integration authorized by Fidelity.

## Q136 — offline capability audit (2026-10-15)

Authority: Camden's Task 6, 2026-10-15 10:33 CT. Source-only audit; no Fidelity
request, library import, credential access, browser launch, account session, or
LIVE arming. Repository comparison is pinned to public main
`589e8068a5d77372cc397925a1657ecb0d47271b`.

Both wheels were downloaded without dependencies or installation from PyPI and
their SHA-256 hashes matched the U0 pins above. The retained evidence directory
is `Task6-Fidelity-20261015` in Camden's private Quant Project Claude folder:
raw wheels, extracted source, per-file hashes (`source-manifest.json`), the
AST I/O/URL inventory (`static-scan.json`), and `fake-reproductions.json`.
Wheel source line numbers below refer to those exact distributions, not GitHub HEAD.

Source prefixes: **SDK** = `fidelity_trader_api-0.2.2-py3-none-any/`;
**PW** = `fidelity_api-0.0.17-py3-none-any/`. These are the wheel extraction roots.
Short SDK paths (`auth/`, `models/`, `cli/`, etc.) resolve under
`SDK/fidelity_trader/`; short PW `fidelity.py` resolves to `PW/fidelity/fidelity.py`.

### Capability findings

| Question | fidelity-trader-api 0.2.2 | fidelity-api 0.0.17 fallback |
|---|---|---|
| 1. Cross-process persistence | CLI `save_session` writes cookie names/values plus creation time as plaintext JSON, reloads into the shared cookie jar, and sets `_authenticated=True`. Windows path `%APPDATA%/ft/session.json`; Unix `~/.config/ft/session.json`. Only Unix gets chmod 0600, after writing. No encryption or local expiry enforcement; original cookie domain/path/expiry metadata are not retained. SDK client itself has no equivalent public save/load method. Sources: SDK `fidelity_trader/cli/_session.py:22-97`, `cli/_config.py:7-18`. | Default `save_state=True`; restores Playwright storage state from `<profile_path>/Fidelity.json` or `Fidelity_<title>.json`, writes plaintext JSON at initialization/save/close, with no encryption or explicit restrictive permissions. Sources: PW `fidelity/fidelity.py:56-71,90-116,520-541`. Neither library proves a saved session will remain accepted across trading days. |
| Expiry | The wheel documents approximately 30 minutes of inactivity and exposes keep-alive; this is an upstream claim, **UNVERIFIED against Fidelity**. Keep-alive treats any successful HTTP response as alive; its documentation says 200 while implementation accepts any 2xx. The client follows redirects, so it does not establish that the final page still represents an authenticated session. Logout clears auth/CSRF in memory. SDK `auth/session_keepalive.py:10-38`, `auth/session.py:201-211`, `_http.py:67-71`. | No explicit age/expiry policy in storage save/load. Login still navigates to sign-in and attempts credentials; saved state is not a guarantee of avoiding login/TOTP. PW `fidelity.py:548-680`. |
| 2. Fractional shares | **Representable in source:** `EquityOrderRequest.qty: float` and preview/place bodies forward it unchanged. No integer validator or rounding found. CLI buy/sell arguments are separately integer typed. SDK `models/equity_order.py:33-98`; `cli/_orders.py:242,259`. Broker acceptance, instrument eligibility, increments and minimums remain **UNVERIFIED**. | `transaction(quantity: float)` fills `str(quantity)` in Quantity and checks preview text; no integer cast on this path. Source-level representation only, not proof the broker accepts a fraction. PW `fidelity.py:770-802,938-940,1017-1038`. |
| Dollar-based path | `qty_type_code` is an unrestricted string, default `S` (shares), forwarded to the payload. No documented/implemented dollar-order code or dollar-specific method was found; inventing a code is not justified. SDK `models/equity_order.py:45-61,80-85`. | Audited transaction path selects Quantity, not Dollars. No dollar-order path found. PW `fidelity.py:938-940`. |
| 3. Trader+ entitlement | Wheel METADATA:186 requires Trader+ access. `has_atp_access` checks an ATP entitlement, but login does not enforce it. Its context-initialization response is ignored and exceptions swallowed. Explicit `security_context.get_context()` raises HTTP errors and returns entitlement/error fields; exact missing-entitlement broker behavior is **UNVERIFIED**. SDK `client.py:105-125`, `auth/security_context.py:19-26`, `models/security_context.py:33-69`. | Uses the retail website; no Trader+-specific entitlement check or typed denial handling found in its callable methods. Unsupported UI/auth paths fall into generic errors/false returns. This does not establish retail entitlement or account eligibility. PW `fidelity.py:548-680,770-810,973-1042`. |
| 4. Challenge handling | Only session status 1201 is explicitly recognized as 2FA; with a supplied seed/code it is answered internally. Other auth failures become `AuthenticationError`; no native `SecurityChallenge` exists. Full mapping below. SDK `auth/session.py:83-141`, `exceptions.py:1-23`. | TOTP, SMS, push-alternate and remembered-device UI are recognized, but failures are mostly converted into tuples/False rather than a typed challenge. Full mapping below. PW `fidelity.py:603-728`. |
| 5. Order status | `get_order_status()` returns parsed `OrderDetail` records. Confirmation is `order.id_detail.conf_num`; code/description are `order.status_detail.status_code/status_desc`. Both status fields are unrestricted optional strings: the wheel contains no exhaustive status enum or live-response fixture. Exact broker status vocabulary is **UNVERIFIED**, and cannot be inferred from type annotations. SDK `orders/status.py:13-51`, `models/order.py:24-39,116-125,153-182`. | No order-status lookup by confirmation/client id, terminal-status enum, cancel/status reconciliation interface, or preview confirmation-number result found. `transaction` returns success/error, not an order identity/status. PW `fidelity.py:770-802,1017-1042`; full method inventory in `static-scan.json`. |
| 6. Settled cash / buying power | **Source capability exists:** `client.balances.get_balances(accounts)` requests cash/buying-power details; response provides per-account recent/intraday/close snapshots, optional `cash_detail.settled_amt` (`settledAmt`) and `buying_power_detail.cash`, with an as-of field. Missing, nonfinite, stale or wrong-account values must refuse; buying power must never substitute for settled cash. SDK `portfolio/balances.py:11-74`, `models/balance.py:45-65,67-103,316-355`; parsing may yield None (`models/_parsers.py:7-21`). | **No explicit settled-cash or buying-power read found.** Optional withdrawal balance is scraped from the transfer-page dropdown/table and stored as `withdrawal_balance`; absent values become 0. This is not source evidence of settled cash. PW `fidelity.py:127-216,398-456,484-500`. Fallback cannot currently satisfy the $100 settled-cash cap. |

### Challenge-to-SecurityChallenge mapping required by our wrapper

These are all challenge-specific branches found in the audited auth paths; they
are not an exhaustive catalog of responses Fidelity can return. Unknown prompts,
redirects, malformed payloads and account warnings must fail closed; no challenge
may be solved or bypassed by a new agent implementation.

| Surface / source | Library behavior | Required wrapper handling |
|---|---|---|
| SDK password status !=1200; `auth/session.py:89-94` | Raises AuthenticationError containing broker message. | Halt with redacted SecurityChallenge/auth-failure classification; do not copy raw message into evidence or retry login automatically. |
| SDK session 1201 without TOTP; `auth/session.py:107-113` | Raises AuthenticationError requesting extra verification. | SecurityChallenge and latched halt. |
| SDK session 1201 with TOTP; `auth/session.py:115-133` | Submits TOTP internally and retries session creation; may return success without exposing that a challenge occurred. | Current FR-005 requires a decision about expected initial TOTP versus an extra challenge; do not silently call this challenge-free evidence. The present wrapper has no observation hook for the intermediate 1201. |
| SDK TOTP response !=1200 or final session !=1200; `auth/session.py:124-138` | Raises AuthenticationError containing response message. | SecurityChallenge and halt; redact before persistence. |
| SDK invalid TOTP input; `auth/session.py:143-161` | AuthenticationError includes inner exception text. | Halt as credential/authentication failure with fixed safe output; never persist inner text. |
| SDK CSRF endpoint non-200/missing token; `auth/session.py:177-190` | Raises CSRFTokenError. | Halt as session/security failure; no automatic re-login. |
| SDK context initialization; `client.py:117-123` | HTTP response not checked; exceptions swallowed. | Explicitly inspect context and required entitlement; unknown/security/error payload must halt rather than count a clean session. |
| SDK preview/status/balances non-2xx; `orders/equity.py:38-41`, `orders/status.py:49-51`, `portfolio/balances.py:72-74` | Generic HTTPStatusError. 2xx error/missing data can parse into empty optional fields. | Identify auth/security responses before generic redaction; halt on 401/403, login redirects/security HTML or unsafe unknown response. Missing conf_num/cash/order identity must refuse. Ordinary preview rejection needs a separate safe recorded result, not fabricated success. |
| SDK keep-alive / background refresh; `auth/session_keepalive.py:31-38`, `auth/auto_refresh.py:105-120` | Returns False or logs warning and continues after errors. | Do not use these paths to hide a failed session. Surface failure and halt; no background refresh adopted here. |
| PW expected TOTP heading plus seed; `fidelity.py:609-644` | Automatically generates/fills a TOTP; may tick remembered-device checkbox. Returns (True,True). | Same expected-TOTP decision as SDK; do not label unseen intermediate prompts challenge-free. No new device-verification bypass. |
| PW missing TOTP for authenticator-only prompt; `fidelity.py:646-652,677-680` | Raises internally, catches/prints traceback, returns (False,False). | Convert failure into SecurityChallenge/halt with sanitized output. Never treat a nonempty tuple as truthy success. |
| PW push/alternate/SMS; `fidelity.py:654-668` | Clicks alternate method, requests SMS, returns (True,False). | Detect incomplete authentication and halt; no automated SMS/push completion. |
| PW unknown auth page/timeout; `fidelity.py:670-680` | Generic error or timeout, prints, returns (False,False). | SecurityChallenge/unsafe-auth halt; no retry or clean-session count. |
| PW login_2FA; `fidelity.py:682-728` | Can remember device; returns True/False and prints raw exceptions. | Not an autonomous challenge-handling route; fail closed on any False/unknown return. |
| PW order critical popup/red inline alert/preview mismatch; `fidelity.py:973-1023` | Returns (False,error text), with generic messages on unrecognized popup. | Classify known security/account-warning text as SecurityChallenge; unknown warning/error blocks the session, no raw text persistence. |

Current `LibraryBroker.login()` does not translate SDK AuthenticationError to our
SecurityChallenge. `FidelityLive.connect()` catches it as a generic BrokerError
without setting `_halted` (`exec/fidelity_live.py:105-116,199-200`). An inert-fake
reproduction confirmed BrokerError with `_halted=False`. This must be repaired in
the reviewed lane before a preview runner claims FR-005 compliance.

### Order status reconciliation finding

At the pinned main, `LibraryBroker.status()` reads `order.conf_num/status_code/
status_desc` directly (`exec/fidelity_live.py:222-227`). Those fields are nested
in this wheel. An inert fake with a real-model-shaped FILLED order returned None.
This is a P1 boundary-binding defect: known fills remain unresolved rather than
releasing reservations. Fix nesting before status normalization; do not broaden
terminal sets to hide this defect.

The repository currently recognizes terminal `FILLED`, `CANCELLED`, `CANCELED`,
`EXPIRED`, `REJECTED`; working `OPEN`, `ACCEPTED`, `PENDING`, `NEW`, `WORKING`,
`PARTIALLY_FILLED` (`exec/fidelity_reconcile.py:26-29`). It uppercases and joins
whitespace with underscores; any other non-None string is `unrecognized`, None is
`unknown`, and both block new decisions (`exec/fidelity_reconcile.py:49-73`).
The wheel accepts arbitrary status strings, so an exact finite list of broker
codes cannot be supplied from this offline evidence. No guessed code mapping is
authorized by this audit.

### Disk, network destinations, and secret-output inventory

| Library | Findings and file:line evidence |
|---|---|
| SDK disk | Session/config directory creation and plaintext session write/delete: `cli/_config.py:7-15`, `cli/_session.py:22-62`. Credential FileProvider reads a user-selected JSON path, not a write (`credentials.py:156-171`). No other direct file-write sites found in the wheel's Python AST scan; transitive dependency writes were not audited. |
| SDK network | Core hosts: digital, ecaap, dpservice, ecawsgateway, streaming-news.mds, fastquote under fidelity.com (`_http.py:6-7,29-32`); streaming MDDS `mdds-i-tc.fidelity.com` (`streaming/mdds.py:17`). Optional research explicitly exchanges a SAML assertion with **fidelity-widgets.financial.com**, then sends a token to **fidelity.apps.livevol.com**, both outside *.fidelity.com (`research/screener.py:20-25,35-77,105-108`). Optional AWS SecretsManager/SSM providers make non-Fidelity boto3 service calls (`credentials.py:49-130`). XML/W3C URL strings are namespaces, not HTTP destinations (`alerts/subscription.py:15-18`). HTTP follows redirects without a destination allowlist (`_http.py:44-45,67-71`); runtime redirect targets are unverified. None of these network paths was executed. |
| SDK output | Credentials dataclass includes password/TOTP in default repr (`credentials.py:35-39`). CLI outputs can contain account identities or complete JSON (`cli/_session.py:119-139`, `cli/_auth.py:74-98`, `cli/_output.py:94-104`). Retry logs request URLs (`retry.py:54-62,88-96`); refresh logs exception traceback (`auth/auto_refresh.py:117`). Authentication exceptions embed broker/inner messages (`auth/session.py:92-94,127-138,158-161`). No unconditional explicit username/password/token print found in the core client; this is not a guarantee that arbitrary exception messages or caller logging are secret-free. |
| SDK identity headers | Built-in headers identify as browser/ATP/Trader+ (`_http.py:9-15,34-40`). This conflicts with treating the library as inherently compliant with FR-005's no-spoofing constraint. A reviewed compliant transport decision is needed; no header or library code was changed here. |
| PW disk | Creates/writes unencrypted storage JSON and reloads it (`fidelity.py:90-116,520-541`); debug tracing captures screenshots/snapshots and writes a trace zip (`119-121,539-541`); downloads positions CSV to cwd then deletes it (`305-309,391`); downloads statements under ./Statements and creates directories (`1430-1436`). Browser-internal profile/cache writes and third-party dependencies were not audited. |
| PW network/output | Literal page navigation targets are digital.fidelity.com (`153,276,583,807-808,1066,1084,1150,1243,1359,1481`). Browser subresources and redirects are unrestricted and unknown offline. Raw exceptions/tracebacks are printed in auth paths (`673-680,722-728`); debug traces can capture sensitive page/input data. No unconditional direct password/TOTP print found, but there is no sanitizing boundary around error output. |
| PW no-evasion conflict | Imports playwright_stealth, creates StealthConfig, and unconditionally calls stealth_sync in driver setup (`fidelity.py:11,56-71,123-125`). Cannot adopt this fallback unchanged under FR-005. |

### Q136 disposition and downstream stop

- Primary SDK: fractional quantities and explicit settled-cash fields are present
  in source. Neither is a verified broker capability; no Fidelity probe is allowed.
- Fallback: no explicit settled-cash read found; withdrawal balance must not be
  substituted. **Task 6's stop condition is reached for the fallback design.**
- Persisting either library's cookies as supplied would also conflict with
  current FR-004 (session tokens memory-only). Do not persist them, even though
  the library exposes a plaintext persistence mechanism.
- Q135/Q137 must resolve the nested status binding, challenge-to-halt boundary,
  no-evasion transport constraint, and fail-closed cash freshness/account binding.
  These findings do not authorize edits to LIVE code or a changed security policy.
- Q135, Q137 and Q138 were not started after the required stop. No arming record,
  risk limit, workflow, broker account, credential or trial ledger was changed.
- Verification: two adapter defects reproduced with inert fakes and blocked
  sockets; no third-party runtime imports; 0 pytest suites and 0 mutation suites
  run (this unit is an audit/documentation change, not implementation acceptance).
  Static scan covered 102 wheel Python files. Local Rule 10 lane cannot publish
  a commit or PR; this research append is an uncommitted review unit, <=600 lines.

### Q136 addendum — revised Task 6 account facts (2026-10-15)

The local task file `codex-task6-fidelity.md` now includes Camden's 10:45 CT
account observations. Trader+ Web access, CASH account type, push-primary MFA,
manual fractional COST/VOO positions and SPAXX are **Camden-reported facts**, not
independently verified broker observations. No screenshot, holdings quantities,
credential value, live balance or Fidelity endpoint was accessed for this audit.

| Added question | Offline finding and evidence | Design consequence |
|---|---|---|
| Push is primary; TOTP is offered | SDK has no push-primary selection, push approval or push polling flow. Password status !=1200 fails immediately. Session code 1201 triggers a TOTP POST if a seed/code is supplied, otherwise AuthenticationError; rejected TOTP or a final non-1200 session also raises. It does not inspect `authenticators` or callbacks to choose an MFA method. SDK `fidelity_trader/auth/session.py:83-141`; optional metadata exists separately in `models/auth.py:29-36`. | Do not claim the SDK waits for Fidelity Mobile or knows whether a push-primary account permits TOTP through this endpoint. That real-account behavior remains UNVERIFIED. Any extra challenge/unknown method must halt, without new push/SMS/device bypass. |
| Push-primary branch verification | Four inert-HTTP-fake cases passed: 1201 without TOTP fails; 1201 with accepted TOTP succeeds; rejected TOTP fails; unknown session status fails. The fake includes push-primary metadata, which is ignored by the extracted auth method. No HTTP/network request was made. Evidence: `push-primary-fake-checks.json`. | These are code-branch checks, not successful authentication or a clean preview session. No session may be counted toward the five-day gate. |
| Manual VOO overlaps a sleeve? | At main `589e8068a5d77372cc397925a1657ecb0d47271b`, `scripts/signals.py:403` declares exactly SPY, EFA, EEM, IEF, TLT, TIP, GLD, DBC. COST and VOO are not members. The holding importer recognizes SPAXX as cash (`scripts/holdings_import.py:26`). | No current COST/VOO sleeve collision. Preserve all manual quantities anyway; any future overlap must satisfy broker quantity = manual baseline + separate bot ledger. Never sell manual holdings to create the bot's budget. No actual baseline quantities have been supplied or inferred here. |
| Does core/sweep equal settled cash? | SDK exposes **separate** optional `core_balance` (`coreBalance`) and `settled_amt` (`settledAmt`) fields, plus held cash and money-market cash (`models/balance.py:45-65`). Timing and as-of fields are also separate (`316-355`). Source does not establish that these amounts are equal, fully available, or free of manual-order commitments for this account. | Do not use total account value, fractional manual positions, withdrawal balance, or proceeds from manual sales as settled bot cash. A later adapter must validate account identity, freshness and finite nonnegative core/settled fields and cap to the confirmed eligible cash with an absolute $100 ceiling. Missing or inconsistent fields refuse; no cash semantics were changed by this audit. |
| Fallback for push-primary account | PW recognizes a TOTP prompt, or clicks a push page's alternate method and requests SMS, returning (True,False); it does not implement autonomous push approval. Failures become (False,False)/False. PW `fidelity/fidelity.py:609-680,682-728`. | It remains ineligible unchanged: no explicit settled-cash read and default stealth behavior. Do not silently fall back to it. |

Q136's primary SDK findings remain source-level fractional representation plus
an explicit settled-cash field; actual endpoint/account acceptance remains
UNVERIFIED. The fallback still reaches the task's missing-settled-cash stop
condition. Q135 has not been opened or implemented. Q137/Q138 remain unstarted.
No PR, LIVE-code change, arming change or Fidelity request occurred. The original
two adapter defect reproductions remain documented; four additional MFA branch
checks passed. No pytest or mutation suite was run for this documentation unit.

### 2026-10-15 continuation authority
Camden approved D-4 through D-7 verbatim in chat and codex-task6b-continue.md.
The primary-only decision removes the fallback stop condition above. Historical
Q136 findings remain source-level evidence; actual broker acceptance is still UNVERIFIED.

Task 6c supersedes the historical account addendum: only the new dedicated $100
cash bot account is in scope. No manual baseline; exact bot-ledger reconciliation,
account-filter enforcement and separate settled_amt/coreBalance evidence are required.
