# ADR 0002: Autonomous Operations — What May Run Unattended, and What May Not

## Status
Proposed (2026-09-29). Written by Claude Code and not yet reviewed. ADR 0001's
addendum records why an agent does not mark its own ADR accepted: this one
becomes `Accepted` only when Camden signs off. The hosting choice below is
explicitly **pending Camden**.

## Date
2026-09-29

## Scope and sourcing rule
This ADR records policy for v1.1 (paper trading) and for whatever follows the
capital gate. It holds no code and no credential. It records one set of risk
numbers, the v1 safety limits (Settled input 5), at Camden's direction. ADR 0001
places risk numbers in the private companion repository; see the flag there.

Every external claim cites a primary source from the [Sources](#sources)
table. Each source was fetched on 2026-09-29, and its URL and date are listed
there. A claim that could not be fetched from a primary source is marked
**UNVERIFIED** inline and is collected in the
[UNVERIFIED register](#unverified-register). The fetch tool returned
summarized text, so wording marked as quoted should be re-checked against the
live page before this ADR is accepted.

## Context
`docs/SCOPE-V1.md` §4 puts a broker paper adapter, a scheduled daily run, and
position reconciliation in v1.1. Once that loop exists, it has to run every
session without Camden at a keyboard, or the capital gate's paper clock (§5)
measures an operator's attendance rather than a system. Three rules pull
against "unattended":

- **Rule 7.** No autonomous agent *modifies* code that can place an order.
  Running reviewed code on a schedule is not modification, so this ADR does not
  conflict with Rule 7. It must also never become a path by which unreviewed
  code gets run.
- **Rule 15 and spec 033.** Every trial counts toward the Deflated Sharpe
  denominator. An unattended retrain that does not register its runs inflates
  every later DSR silently.
- **§5, the capital gate.** No real capital until every step passes, and "a
  deadline never relaxes a gate". Autonomy must not become the mechanism by
  which a step is skipped.

## Settled inputs (Camden; recorded here, not reopened)

1. **Free data only** (`SCOPE-V1.md` §2).
2. **Alpaca paper runs as an autonomous loop at v1.1.** Alpaca live comes only
   after the capital gate passes.
3. **Fidelity stays Camden's manual account.** The system holds no Fidelity
   credential, reads nothing from it, and places nothing in it. Consequence:
   positions there are invisible to `portfolio_risk` and `live_safety_gate`,
   so no correlation or exposure figure from this system covers Camden's total
   book.
4. **Scraping and IBKR are rejected.**
5. **Safety limits v1, `SafetyConfig.version = "2026-09-29-v1"`
   (Camden, 2026-09-29). Provisional pending paper reconciliation.** These are
   configuration values Camden chose. They are not results or measured figures.
   Percentages are fractions of equity.

   | `SafetyConfig` field | Value |
   |---|---|
   | `max_position_pct` | 0.10 |
   | `max_gross_pct` | 0.60 |
   | `daily_loss_pct` | 0.02 |
   | `rolling_drawdown_pct` | 0.08 |
   | `rolling_window_sessions` | 63 |
   | `max_snapshot_age_seconds` | 60 |
   | `max_clock_skew_seconds` | 5 |

   - The names are `SafetyConfig`'s own fields (`scripts/live_safety_gate.py`).
     `timezone` keeps its default, `America/New_York`. The set satisfies the
     class's own `max_position_pct <= max_gross_pct <= 1.0` check.
   - *Provisional* means the values are to be revisited once the paper loop's
     reconciliation evidence exists. It does not mean advisory: until changed,
     the gate enforces them exactly.
   - Any change is a Capital-layer act under a new version label. The gate
     refuses changed values under an unchanged version (`ConfigMismatchError`).
   - **Flagged, not resolved:** ADR 0001 and `SCOPE-V1.md` §3 item 6 place risk
     numbers only in the private companion repository. Recording them here puts
     them in the tree that will become public. Camden to confirm this is
     intended, or move them at the physical repo split.

## Proposal

### 1. Three autonomy layers

| Layer | What it covers | May run unattended? | Condition |
|---|---|---|---|
| **Operations** | fetch → signal → size → order → reconcile → monitor → report | **Yes** | Every order passes `live_safety_gate`. A halt or kill latches durably and is re-armed only by Camden. Code runs only from a reviewed, merged revision |
| **Research** | scheduled retrains, re-fits, re-evaluations | **Only if registered** | Every run, including errored and abandoned ones, is written to the trial ledger through `trial_runner`/`trial_registry` before its result is read. A run that cannot register does not run |
| **Capital** | going live, sizing up, changing any limit in `SafetyConfig` or the risk layer | **Never** | Human-gated at `SCOPE-V1.md` §5 steps 5–6: paper reconciled through a volatile regime, then a small, explicitly capped amount. Each step is signed off by Camden |

Boundary cases, resolved conservatively:

- A **retrained model replacing the one the paper loop trades** is a Research
  output entering Operations. This ADR proposes allowing it on paper only if
  the retrain is registered. Replacing the model on a *live* account is a
  Capital change. See Open question 3.
- A **halt clearing itself** is forbidden in every layer. The gate's latches
  are durable (spec 032 REQ-006) and are re-armed by a human.
- **Changing the schedule, the host, or the data source** is a reviewed code
  change, not an operational action.

### 2. Paper-to-live safety: never by configuration alone

Alpaca paper and live use separate credentials and a different base URL
(`https://paper-api.alpaca.markets` for paper) [S1]. Swapping two keys and a URL
is therefore enough to point the same loop at real money. This ADR requires
that such a swap **produces denied orders, not live orders**:

- **A durable, signed "gate-passed" marker.** It is a record, signed by Camden,
  that binds:
  - the specific live broker account identifier;
  - the capital cap for gate step 6;
  - hashes of the gate evidence (the spec 033 Gate 3 artifact and the paper
    reconciliation report);
  - the `SafetyConfig` version;
  - an issue date.

  It is stored durably beside the gate's SQLite state, not in an environment
  variable.
- **`live_safety_gate` verifies it.** It checks the signature against a public
  key pinned in reviewed code. Verification needs no network and no
  credential, so it stays inside the module's existing boundary (Rule 8; the
  module docstring's "no broker code, no credentials").
- **Fail closed on unknown accounts.** The broker-confirmed snapshot must carry
  the account identifier. An order is allowed only if that account is on a
  pinned list of paper accounts **or** matches a marker that verifies. Any
  other account, including a live account whose marker is missing, expired,
  revoked, or for a different account, is denied, and the kill latch is set.
- **Revocation latches.** Revoking or superseding the marker is itself a
  durable event. Sizing up means issuing a new marker, which is a Capital-layer
  act.
- **Required red proof (Rule 12), in the implementing spec:** plant a
  live-account snapshot with no marker, with a marker for a different account,
  with a tampered signature, and with an over-cap order. Each must be denied,
  and a valid paper snapshot must pass as the control.

This extends spec 032/034's gate. It is a design requirement for spec 039 (or a
successor), not an edit made by this ADR.

### 3. Secrets

- Broker keys live only in a vault (a cloud secret manager, or the host OS
  credential store) or in environment variables loaded from a gitignored
  `.env`. They never appear in the repository, in a spec, in a log line, in CI
  output, or in an agent's context (Rule 7; `CLAUDE.md` "Secrets").
- **There is no IP allowlist to fall back on.** A June 2026 community forum post
  asks Alpaca to enable IP allowlisting on API keys, noting the field "already
  exists in the Alpaca dashboard — it's just disabled". No Alpaca staff reply
  was visible when it was fetched [S2]. This is a user request, not
  staff-confirmed. Treat keys as usable from anywhere, so the kill switch and
  the vault carry the weight an allowlist would otherwise share.
- **A trading key is not demonstrably withdrawal-free.** The assumption that
  API keys cannot move money out is **UNVERIFIED**, and Alpaca's own reference
  contradicts it for crypto:
  - The Trading API, authenticated with the ordinary `APCA-API-KEY-ID` /
    `APCA-API-SECRET-KEY` headers, exposes `POST /v2/wallets/whitelists` to add
    a withdrawal address [S5].
  - It also exposes `POST /v2/wallets/transfers` to request a crypto withdrawal
    to a whitelisted address. A new whitelisted address must wait at least 24
    hours before use [S5][S6].
  - The transfer endpoint is marked deprecated in favour of the web app [S6].
    The dates 2026-07-09 (deprecated) and 2026-10-09 (sunset) were seen on the
    first fetch only. The whitelist endpoint shows no deprecation notice [S5].
  - Both reference pages show only the paper host. That a live key reaches the
    same endpoints is inferred, not shown (see the note under Sources).

  Required controls:
  - **(a)** The Operations loop reads `GET /v2/wallets/whitelists` every
    session. Any entry it did not expect raises an immediate alert and latches
    the kill; the 24-hour wait is the detection window.
  - **(b)** Camden asks Alpaca whether crypto and wallet permissions can be
    disabled on the account or on the key (**UNVERIFIED**).
- **Rotation.** Keys are rotated on a fixed cadence and after any suspected
  exposure. The cadence itself is a Capital-layer setting kept in the private
  repository.

### 4. Alert by exception

The loop reports nothing when a session is normal and alerts on anything else.
Alert triggers:

- the kill switch latched, or a reconciliation or loss/drawdown halt;
- broker state disagrees with the internal ledger;
- a data fetch fails or fails validation (for example
  `_validate_unadjusted_prices`);
- a trial-ledger write guard fires;
- an unexpected crypto whitelist entry (§3);
- a key approaching its rotation date;
- **a missed run.** A dead-man's switch fires when no success heartbeat arrives
  by a set time. It must run somewhere other than the host it watches.

**Residual human tasks, expected and named, not treated as failures:**

| Task | Cadence | Layer |
|---|---|---|
| Weekly review: gate evidence log, reconciliation diffs, alert history, model-decay monitor | Weekly | Operations |
| Key rotation, and checking the crypto whitelist is empty | Per cadence; after any suspected exposure | Operations / secrets |
| Re-arming the gate after a kill or halt, with a written reason | On event | Operations |
| Gate sign-offs: §5 step 5 (paper reconciled) and step 6 (issuing the signed marker) | Once each; again for every size-up | Capital |
| Approving any limit change, a model promotion to live, or a host change | On event | Capital |
| Reviewing and merging code the loop runs (Rules 7 and 9) | Per PR | — |

### 5. Disclosures that spec 039 must carry (Rule 16)

Per Alpaca's paper trading documentation [S1], paper trading does **not**
simulate the following:
- market impact;
- information leakage;
- slippage due to latency;
- order queue position;
- price improvement;
- regulatory fees;
- **dividends**.

Its fill model and data also differ from live trading:
- Orders fill only once they are marketable.
- Eligible orders "receive partial fills for a random size 10% of the time".
- Paper accounts "are only entitled to receive and make use of IEX market data".

Consequences that must appear on every paper-trading surface:

- **The Rule 13 square-root market-impact term is not validated by paper
  trading.** Paper has no impact at all, so any paper-versus-backtest cost
  comparison measures the spread term and fill mechanics only.
- **Dividend handling cannot be reconciled on paper.** Paper credits no
  dividends, so spec 041's receivable-to-cash path has no broker truth to
  compare against during the paper clock.
- **Fills are marketable-only, with random partial fills 10% of the time.**
  Partial-fill handling is exercised; queue behaviour and price improvement are
  not.
- **Paper market data is IEX-only**, not a consolidated feed [S1].

**Flag for Camden, not resolved here.** §5 step 5 asks for "execution reality
reconciled against backtest assumptions". Given the above, Alpaca paper can
reconcile order lifecycle and position state, but not impact, dividends, or
latency slippage. Whether step 5 is satisfiable on paper alone, or needs its
evidence narrowed or supplemented at the small-capital step, is a gate
question for Camden.

### 6. Spec 039 scope: the gate's process bootstrap

Spec 039 must include the **reviewed process bootstrap that constructs the
durable `LiveSafetyGate`**, in the reviewed lane under Rule 7:
- It opens the gate on its SQLite path with the `SafetyConfig` from Settled
  input 5.
- It injects the result where callers obtain it.
- It is the hook where §2's marker and account checks run.

Until the bootstrap exists, `get_safety_gate()` in
`reports/api/routes/safety.py` raises HTTP 503 ("live safety gate is not
configured"). Every route that depends on it, including the kill request,
therefore fails closed. During that period the broker-side kill (Hosting
options, below) is the only kill path that works.

## Hosting options

Hosting cost is **outside** the "free data only" constraint. That constraint
governs data sources, so a paid host does not violate it, but the cost is a
budget decision in its own right.

| | **A. Small always-on VM** (e.g. GCP e2-micro) | **B. Scheduled GitHub Actions job** (private companion repo) | **C. Camden's own always-on machine** (OS task scheduler) |
|---|---|---|---|
| **Cost** | GCP's free tier covers 1 non-preemptible e2-micro per month in `us-west1`, `us-central1` or `us-east1`, with 30 GB-months of standard disk and 1 GB of North America egress [S11]. Whether an external IPv4 address is billed was not fetched (**UNVERIFIED**) | Private repositories on GitHub Free get 2,000 included minutes a month. Beyond that, Linux 2-core runners cost $0.006 per minute. Public repositories on standard runners are free [S10] | No hosting fee; electricity and hardware already owned |
| **Durable-state fit** (the gate's SQLite, reservations, latches) | **Good.** A persistent disk holds the SQLite file across runs, as REQ-006 assumes | **Poor.** Each run starts on a fresh runner, so the kill latch set in one run is gone in the next unless it is kept in an external store, which brings a host back. Committing state back to the repository is not an option: Rule 10's Actions carve-out covers agents invoked from an issue or PR, pushing to their own branch, not a scheduled job writing to `main` | **Good.** Local disk, same as A |
| **Kill-switch reachability** | SSH or the cloud console from a phone. The broker-side kill (below) works regardless | The workflow can be disabled and a running job cancelled from the GitHub UI, but the *durable* gate latch cannot be set if no state persists. That leaves the broker-side kill as the only effective kill | Reachable only with remote access set up. Otherwise only the broker-side kill |
| **Failure modes** | Silent VM or agent death (needs the external dead-man's switch); OS patch reboots; one more cloud account to secure | The schedule "can be delayed during periods of high loads… some queued jobs may be dropped", with the start of every hour a high-load time; the minimum interval is 5 minutes; scheduled runs use "the latest commit on the default branch", so a merge changes what runs at the next tick; public-repository schedules are disabled after 60 days without activity [S9] | Power or ISP outages; OS updates rebooting mid-session; a laptop sleeping; the gate's state on a machine also used for everything else |

**Broker-side kill, independent of host.** The Trading API can cancel all open
orders (`DELETE /v2/orders`) [S12]. It can also liquidate all positions
(`DELETE /v2/positions`), with a `cancel_orders` option that cancels pending
orders first [S13]. A kill path that runs from anywhere with the keys, and does
not depend on the loop's host being alive, should exist whichever option is
chosen. Revoking keys from the Alpaca dashboard as a last resort is assumed
here but not verified from a primary source (**UNVERIFIED**).

## Decision
**Pending Camden.** Two things are required:
1. acceptance, amendment, or rejection of the Proposal (§§1–5);
2. a choice among hosting options A, B and C, or another option.

On this table, B fits the durable-state requirement poorly unless an external
store is added. That observation is not a decision.

## Consequences (if the Proposal is accepted)

### Positive
- The paper clock measures the system, not the operator's attendance.
- Moving from paper to live requires a signed human act the gate can verify.
  An edited configuration file cannot move real money.
- Unattended research cannot inflate the DSR denominator silently.
- Residual human work is named and bounded, so an alert means something is
  wrong, not that routine work was missed.

### Negative / tradeoffs
- The marker, signature verification, and account-identifier binding are new
  gate machinery. Each needs red proofs (Rule 12) and review in the `exec/`
  lane (Rule 7).
- An external dead-man's switch and alert channel are new dependencies. Each
  will need a Rule 6 justification.
- Paper evidence is structurally weaker than the §5 wording implies (§5 above).

## Open questions
1. Is §5 step 5 satisfiable on Alpaca paper, given no impact and no dividends?
2. Can Alpaca disable crypto and wallet permissions per account or per key?
   (**UNVERIFIED**; ask Alpaca.)
3. Does a registered retrain count as Operations on paper and Capital on live,
   as proposed, or is every model promotion Capital?
4. Which signing mechanism is used for the marker? It must not add an
   unjustified dependency (Rule 6).
5. What key-rotation cadence applies? It is a private-repository setting.

## Sources
All fetched 2026-09-29.

| # | Claim supported | URL | Page date / note |
|---|---|---|---|
| S1 | Paper does not simulate market impact, information leakage, latency slippage, queue position, price improvement, regulatory fees, or dividends; marketable-only fills; random partial fills 10% of the time; IEX-only data; separate paper credentials and base URL | https://docs.alpaca.markets/docs/paper-trading | undated doc page |
| S2 | Forum feature request for API-key IP allowlisting; no staff reply visible | https://forum.alpaca.markets/t/feature-request-api-key-ip-allowlisting/19087 | post dated 2026-06-10 |
| S3 | No minimum deposit for individual accounts | https://alpaca.markets/support/alpaca-minimum-deposit | page updated Dec 2022 |
| S4 | US-resident eligibility: 18+, SSN (not ITIN), US residential address in the 50 states or Puerto Rico, citizen / permanent resident / listed visa | https://alpaca.markets/support/requirements-alpaca-brokerage-account | page updated Oct 2023 |
| S5 | Trading API `POST /v2/wallets/whitelists`, key-header auth; 24-hour wait before use | https://docs.alpaca.markets/us/reference/createwhitelistedaddress | no deprecation notice shown |
| S6 | Trading API `POST /v2/wallets/transfers` crypto withdrawal, key-header auth; marked deprecated (dates 2026-07-09 / 2026-10-09 seen on first fetch only) | https://docs.alpaca.markets/us/reference/createcryptotransferforaccount | — |
| S7 | Customer agreement: consent to Alpaca's "Automated Systems"; no liability for "System Failure". No clause expressly permitting customer algorithms was found | https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf | v25 2026.06 |
| S8 | FINRA Regulatory Notice 26-10: replaces the pattern-day-trader designation and the $25,000 minimum equity with intraday margin standards; effective 2026-06-04; phase-in allowed to 2027-10-20 | https://www.finra.org/rules-guidance/notices/26-10 | published 2026-04-20 |
| S9 | Actions `schedule`: 5-minute minimum; delays and dropped jobs under load; runs the latest default-branch commit; public repos disabled after 60 days of inactivity | https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows | — |
| S10 | Actions billing: free for public repos on standard runners; 2,000 minutes a month for private repos on Free; Linux 2-core $0.006 per minute | https://docs.github.com/en/billing/concepts/product-billing/github-actions | — |
| S11 | GCP free tier: 1 e2-micro in us-west1, us-central1 or us-east1; 30 GB-months disk; 1 GB egress | https://docs.cloud.google.com/free/docs/free-cloud-features | — |
| S12 | `DELETE /v2/orders` cancels all open orders | https://docs.alpaca.markets/us/reference/deleteallorders-1 | — |
| S13 | `DELETE /v2/positions` liquidates all positions; `cancel_orders` option | https://docs.alpaca.markets/reference/deleteallopenpositions-1 | — |

**Re-fetch note (2026-09-29).** S5 and S6 were independently re-fetched on
2026-09-29, and both endpoints are confirmed.
- S5 is not deprecated.
- S6 is marked deprecated, but the 2026-07-09 and 2026-10-09 dates were not
  visible on re-fetch. Treat them as unconfirmed.
- Both pages show the paper-api host (`paper-api.alpaca.markets`), so exposure
  of a *live* key is inferred rather than shown.

Three items previously listed as unverified are now sourced and apply to live
accounts, not to v1.1 paper:
- **$0 minimum** [S3]. The page dates from Dec 2022, so re-check it before
  funding.
- **US-resident eligibility** [S4].
- **The FINRA notice replacing the PDT rule** [S8]. Members may phase it in
  until 2027-10-20, so whether Alpaca has adopted it is a separate, unverified
  question.

## UNVERIFIED register

| Item | Status |
|---|---|
| API keys cannot withdraw funds | **UNVERIFIED, and contradicted for crypto** by S5/S6. Nothing fetched covers fiat withdrawals by API key either way |
| Alpaca's terms expressly permit customer algorithmic trading | **UNVERIFIED.** The current customer agreement (S7) was fetched; no express permission clause was found. The Terms and Conditions PDF returned no extractable relevant text |
| The date Alpaca itself adopts FINRA 26-10's intraday margin standards | **UNVERIFIED.** S8 allows members until 2027-10-20 |
| Crypto and wallet permissions can be disabled per account or per key | **UNVERIFIED** |
| API keys can be revoked or regenerated from the dashboard as a kill of last resort | **UNVERIFIED** |
| Whether GCP bills the free-tier VM's external IPv4 address | **UNVERIFIED** |
