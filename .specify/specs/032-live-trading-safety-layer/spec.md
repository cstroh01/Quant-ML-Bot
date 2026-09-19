# Feature Specification: Live-Trading Safety Layer

**Feature**: `032-live-trading-safety-layer`  
**Status**: Draft specification only; no live-trading code exists yet.  
**Priority**: P0 — hard capital gate before real-money trading.  
**Scope**: One-operator Quant-ML-Bot account, initially assumed to be a cash,
long-only US-equity account. Margin, shorting, derivatives, multiple accounts,
and multiple independent strategies require explicit extension of this spec.

## Problem

Quant-ML-Bot has a research-side position-sizing and loss-cap module, but that
module is not a live safety boundary. It observes periodic equity values, is
not wired into broker order submission, loses its halt latch when reconstructed,
and cannot guarantee protection from intraday loss, overnight gaps, stale data,
failed exits, or uncertain order acknowledgements. The project audit therefore
correctly treats it as insufficient for capital deployment.

The live layer needs an independent execution-side authority that remains
correct when the signal, accounting, data, process, or operator is wrong. Every
order that could add exposure must pass it immediately before submission. A
missing configuration, stale broker state, unknown order outcome, failed
cancellation, or unconfirmed broker control must deny new exposure rather than
fall through to a best guess.

This is a capital gate, not a dashboard feature. A green display, a local
boolean, or a successful API request is not evidence that the broker is safe.

## Requirements

### Non-negotiable requirements

- **REQ-001 — Independent authority.** The safety layer MUST sit in the order
  gateway/execution boundary, after strategy intent and before the broker. A
  strategy MUST NOT be able to bypass it by submitting directly to a broker
  adapter, using a second process, or restarting the strategy.

- **REQ-002 — Hard deny semantics.** The only permissive result is an explicit
  `ALLOW` containing the broker snapshot, configuration version, reservations,
  and checks that produced it. `UNKNOWN`, stale, missing, malformed, or
  contradictory inputs MUST produce `DENY`.

- **REQ-003 — Broker-authoritative state.** Position quantities, open orders,
  fills, buying power, and account equity MUST come from a fresh broker
  snapshot plus durable local reconciliation state. Local target weights and
  predicted positions are not exposure.

- **REQ-004 — Pending orders count.** Working, partially filled, and
  submission-uncertain orders MUST count toward worst-case exposure until their
  broker state is terminal and reconciled. A second order MUST NOT pass merely
  because the first order has not filled yet.

- **REQ-005 — Dynamic equity sizing.** All percentage limits MUST be evaluated
  against current, cash-flow-adjusted broker account equity. No fixed-dollar
  live limit may be used as a substitute for an equity-relative limit.

- **REQ-006 — Durable state.** Loss halts, kill state, configuration version,
  high-water marks, and unresolved order intents MUST survive process restart.
  A restart MUST never clear a protective state.

- **REQ-007 — Order lifecycle proof.** Submission timeout, disconnect after
  submission, partial fill, duplicate event, and cancellation timeout MUST enter
  reconciliation. The system MUST query by durable client order ID and
  executions before retrying; it MUST never infer “not submitted” from a
  network timeout.

- **REQ-008 — Explicit action classes.** `BLOCK_NEW`, `CANCEL_RISK_ADDING`,
  `REDUCE_ONLY`, `FLATTEN`, and `KILL_LATCHED` MUST be separate states or
  commands. A loss halt or kill MUST NOT silently imply liquidation.

- **REQ-009 — No unapproved defaults.** The system MUST refuse live trading
  when Camden has not approved the percentage limits, rolling window,
  freshness policy, account/session boundary, and reset authority. The values
  in the existing research module — including 25% per-name, 100% gross, and
  2%/4%/5% loss recommendations — are not live defaults; they were not
  calibrated on a funded equity curve and were based on close observations.

- **REQ-010 — Evidence trail.** Every allow, deny, trigger, cancellation,
  broker acknowledgement, reconciliation result, reset, and operator command
  MUST be append-only logged with account, timestamp, configuration version,
  reason, broker order IDs, and resulting exposure.

### Gate evaluation order

For every order intent, the gateway MUST evaluate in this order:

1. Load and validate the durable kill/loss/reconciliation state.
2. Fetch a fresh broker snapshot and reconcile positions, open orders, fills,
   cash, equity, and external cash flows.
3. Deny if any snapshot, limit, clock, or broker status is unknown or stale.
4. Evaluate the manual kill switch and loss/drawdown circuit breaker.
5. Compute worst-case post-order per-position and portfolio exposure, including
   all reservations and the candidate order.
6. Atomically reserve the exposure and submit with a unique client order ID.
7. Confirm broker acknowledgement and reconcile the resulting state. An
   uncertain result remains halted for new exposure until resolved.

The order of these assertions is part of the safety contract. A passing size
calculation cannot override a kill latch or stale-state halt.

## Design

### 1. Max position size and portfolio size

#### Control objective

Prevent one order, one position, or the sum of all positions and working orders
from consuming more than an equity-relative risk budget. The control is a
pre-trade rejection, not an after-the-fact warning.

#### Equity and exposure definitions

Let:

- `E_t` = broker-confirmed net liquidation/account equity at the decision
  instant, adjusted so external deposits and withdrawals are not mistaken for
  trading P&L;
- `q_i` = broker-confirmed signed quantity of instrument `i`;
- `p_i^worst` = conservative executable price used for the exposure check;
- `o_i^reserved` = the worst-case quantity from all non-terminal working or
  submission-uncertain orders for `i`, including the candidate order;
- `N_i = abs(q_i + o_i^reserved) × p_i^worst` = worst-case position notional;
- `G = sum_i N_i` = worst-case gross portfolio notional.

For an initial long-only cash deployment, `p_i^worst` MUST be the broker or
market-data adapter's conservative executable estimate, not an old local mark.
If the adapter cannot produce a valid estimate, the order is denied. The
extension to short or leveraged positions must define borrow, margin, and
liquidation exposure separately; it cannot reuse this formula by assumption.

The two hard assertions are:

```text
N_i / E_t <= MAX_POSITION_PCT
G   / E_t <= MAX_GROSS_PCT
```

The boundary is inclusive: equality is a denial. `E_t <= 0`, missing equity,
or an unresolved external cash-flow adjustment is a denial. The percentage
configuration is mandatory and versioned; there is no fixed-dollar fallback.

#### Execution behavior

- The check applies to entries, adds, amendments that increase exposure, and
  any concurrent order batch.
- A reduce-only or exit order may lower exposure, but it still requires a
  reconciled broker snapshot and a valid order lifecycle.
- The reservation and submission decision MUST be atomic from the gateway's
  perspective. Two individually acceptable orders must not jointly cross a
  limit because they were checked concurrently.
- The check MUST aggregate positions across the whole account, not just the
  strategy's local book. If more than one strategy can trade the account,
  their exposures share the same cap.
- A broker rejection, partial fill, or cancellation race MUST trigger a fresh
  reconciliation before another exposure-increasing order is allowed.

#### Practice/precedent

This follows the market-access risk-control pattern in SEC Rule 15c3-5:
orders are rejected when they would exceed pre-set capital/credit thresholds,
including aggregate exposure, and erroneous orders are rejected using order
size parameters. It also follows FIA's market-access recommendations, which
describe hard pre-trade limits at multiple aggregation levels, including order
size and position size.

The precedent supports the mechanism, not a universal percentage. The SEC
explicitly treats the threshold amount as a documented business judgment based
on the firm's financial condition, trading pattern, and risk tolerance. Camden
must choose `MAX_POSITION_PCT` and `MAX_GROSS_PCT`; this spec deliberately does
not invent them. A reasonable launch discussion is “no leverage and a
quarter-book single-name cap,” but that is a proposal for approval, not an
accepted gate value.

#### Required acceptance evidence

The implementation is not capital-gate eligible until an independent replay
shows that:

- changing account equity changes the permissible notional proportionally;
- fixed-dollar caps cannot be configured or silently substituted;
- current positions plus every working order are included;
- two concurrent orders cannot jointly exceed either cap;
- exact-boundary orders are rejected;
- reductions remain possible during a loss halt or kill state; and
- stale, missing, contradictory, or non-positive equity denies exposure.

### 2. Daily loss / rolling drawdown circuit breaker

#### Control objective

Automatically stop adding risk when the account has lost too much in the
current trading day or has fallen too far from a recent equity high. This is a
trigger for a halt, not a promise that the account cannot lose more: gaps,
slippage, market closure, failed exits, and broker outages can exceed any
threshold.

#### Measurement

The breaker uses broker-marked account equity, including realized and
unrealized P&L, commissions, fees, and financing applicable to the account.
It MUST update on every trusted account/fill/mark observation during trading,
not only at the daily close.

External deposits and withdrawals are ledger events, not trading gains or
losses. The equity series used by the breaker is therefore cash-flow-adjusted.

For the official broker trading-day boundary:

```text
daily_loss_t = (E_t - E_day_start) / E_day_start
daily_breach = daily_loss_t <= -DAILY_LOSS_PCT
```

For a configurable rolling window of `W` trading sessions:

```text
H_t              = max(E over the current rolling W-session window)
rolling_drawdown = E_t / H_t - 1
rolling_breach   = rolling_drawdown <= -ROLLING_DRAWDOWN_PCT
```

Both boundaries are inclusive. The official broker/session calendar and
timezone, including daylight-saving transitions, define the day; the laptop's
local clock does not.

#### Trigger action

On either breach, the account enters `LOSS_HALT` with an immutable reason and
the triggering equity evidence. The gateway MUST:

1. reject new positions and all increases to existing positions;
2. cancel resting orders that could add exposure, then confirm their terminal
   states;
3. continue to permit only reconciled reduce-only and exit orders; and
4. keep the halt effective through restart and process replacement.

The base policy does **not** automatically close existing positions. That is a
deliberate boundary: the loss breaker limits additional risk, while forced
market liquidation is a separate action with its own price, liquidity, and
order-failure risk. A position may still lose more after the halt; the system
must report this honestly rather than call the threshold a guaranteed loss
limit. Automatic flattening, if desired, requires a separate Camden-approved
policy and a separate testable liquidation controller.

#### Reset behavior

- **Daily breach:** remains active for the rest of the official trading day.
  At the next trading day, it may reset automatically only after a fresh
  reconciliation, a new cash-flow-adjusted day-start equity, no kill latch,
  no rolling breach, and a healthy broker/order channel. Restarting during the
  same day never resets it.
- **Rolling breach:** latches until an authenticated operator reset after
  review. Reset is rejected if the current rolling drawdown still breaches the
  limit, if reconciliation is incomplete, or if the kill switch is active.
  The reset event records the operator, reason, current equity, and limit
  configuration. A reset does not erase the historical breach.
- **Unknown measurement:** a stale or contradictory equity stream enters
  `RECONCILIATION_HALT`, which has no automatic expiry.

The daily percentage, rolling percentage, and rolling window are Camden-owned
business decisions. The right values depend on strategy holding period,
volatility, liquidity, account size, tax/fee economics, and how much overnight
risk Camden is willing to retain. SEC/FIA precedent supports documented,
reviewed limits; it does not justify selecting a number from a generic blog or
from the research module's unvalidated defaults.

#### Practice/precedent

FIA market-access guidance describes post-trade limits such as daily loss
limits by instrument, asset class, or strategy, with automatic close-out or
reduction when breached. The design here uses the same hard, automated limit
but chooses the safer initial action for a small cash account: stop adding
risk, cancel risk-increasing orders, and leave liquidation as an explicit
reduce-only action. The choice is also consistent with exchange risk controls:
a circuit breaker stops order flow; it is not assumed to predict or prevent a
market gap.

#### Required acceptance evidence

The implementation is not capital-gate eligible until replay tests cover
intraday mark-to-market loss, overnight gaps, exact thresholds, deposits and
withdrawals, broker-day/timezone boundaries, rolling high-water marks,
recovery without premature reset, process restart, stale marks, and partial
cancellation. The test oracle must prove that a halt blocks adds but permits
reductions.

### 3. Manual kill switch

#### Control objective

Give the sole operator a durable, out-of-band way to stop Quant-ML-Bot's order
flow immediately when the system behaves unexpectedly or when the operator no
longer trusts the automated controls.

#### Invocation

The primary invocation is an authenticated local control command that first
writes a durable `KILL_LATCHED` record/flag, then signals the order gateway.
The gateway checks that latch before every order and on every heartbeat. A
watched flag file is a fallback invocation path for a dead or unhealthy
strategy process, but it is not the only control: a flag that nobody reads
cannot protect a broker account.

Where the broker or venue provides a firm/session kill or “cancel all and
disable order entry” control, the kill command MUST invoke it through an
out-of-band broker connection or credential. The local latch remains required
because the broker control cannot stop a local process from repeatedly trying
to submit after re-enablement.

#### State and action

`KILL_LATCHED` means:

- all local strategy and order-gateway submissions are denied;
- all resting orders are cancelled, with terminal-state confirmation required;
- broker/venue order entry is disabled at the firm/session/account scope when
  the selected broker supports that control;
- any fills racing with cancellation are reconciled before the result is
  declared safe; and
- the latch survives restart and cannot be cleared by the strategy process.

The kill switch stops order flow and cancels orders; it does **not** silently
liquidate existing positions. If Camden wants an emergency flatten, that is a
separate, explicit, reduce-only command after a fresh position snapshot. This
prevents “kill” from turning a control intended to stop a runaway system into
an unreviewed burst of market liquidation orders.

#### Confirmation contract

The operator-facing result MUST distinguish `REQUESTED`, `LOCAL_BLOCKED`,
`BROKER_CANCEL_PENDING`, `BROKER_DISABLED_CONFIRMED`, `RECONCILING`, and
`KILL_CONFIRMED`. `KILL_CONFIRMED` requires all of the following:

1. The durable local latch is present and every local order path reports the
   account blocked.
2. A fresh broker query shows no working order, or every prior working order
   has a terminal cancellation/fill/rejection state.
3. The broker/venue kill or order-entry-disable state is positively confirmed
   when that capability exists. An HTTP/API success response alone is not
   enough.
4. Any fills created during cancellation have been reconciled into the
   account position and equity snapshot.
5. If the broker exposes no disable-status query, the result is
   `BROKER_DISABLE_UNVERIFIED`, not `KILL_CONFIRMED`; the local system remains
   latched and the operator must verify the broker side through an independent
   channel.

The broker-side semantics are modeled on CME Globex Kill Switch behavior:
working orders are cancelled and new order entry is prohibited, while the
control does not claim to liquidate existing positions. FIA guidance further
recommends source-level cancel-all, separate access for a runaway-algorithm
scenario, and formal conformance testing. Quant-ML-Bot should test the actual
selected broker's semantics rather than assume that all “cancel all” APIs mean
the same thing.

#### Recovery

`KILL_LATCHED` has no timer. Re-enablement requires an authenticated operator
command, a fresh reconciliation, no active loss/drawdown/reconciliation halt,
and a recorded reason. If the broker-side kill cannot be positively cleared,
the local system stays halted. A restart is not recovery.

## Failure modes to test against

The following are capital-gate tests, not optional hardening:

| Failure or adversarial case | Required safe result |
|---|---|
| Equity grows or shrinks while the same percentage limits remain configured | Permitted notional changes with equity; no stale dollar cap is used. |
| Candidate order reaches either cap exactly | Reject; boundaries are inclusive. |
| Two simultaneous orders each pass alone but exceed the portfolio cap together | Atomic reservation rejects the aggregate excess. |
| Existing position plus a working order plus a new order | All worst-case exposure is counted. |
| Partial fill, duplicate fill event, out-of-order event, or cancel/fill race | Reconcile by durable order ID; deny new exposure until resolved. |
| Network timeout immediately after broker submission | Query broker/executions; never blind-retry. |
| Missing, stale, non-positive, or contradictory broker equity/positions | `RECONCILIATION_HALT`; no new order. |
| Deposit or withdrawal near a loss threshold | Cash flow is excluded from trading loss; event is logged. |
| Intraday mark-to-market loss breaches daily limit | Cancel risk-increasing orders, block adds, permit reductions; do not claim guaranteed loss containment. |
| Overnight gap crosses the daily threshold before the next observation | Halt on the next trusted observation; document that the threshold can be exceeded by the gap. |
| Equity recovers after a daily breach during the same day | Remain halted until the next official day. |
| Rolling drawdown recovers, or old high-water-mark data rolls out of the window | Reset requires the specified operator/reconciliation path; no accidental auto-resume. |
| Process crashes after a breach, kill, or accepted submission | Restart restores latch, reservations, and unresolved intent. |
| Day boundary, holiday, timezone, or daylight-saving transition | Use the broker calendar/session definition; no laptop-clock reset. |
| Kill command arrives during order submission | Durable latch wins; cancellation and fill reconciliation continue until terminal. |
| Strategy restarts after kill | Every order path remains denied. |
| Broker cancel-all request returns success but orders remain working | Poll and reconcile; status is not confirmed. |
| Broker has no kill-status endpoint | Report `BROKER_DISABLE_UNVERIFIED`; remain locally latched. |
| Broker-side kill is active but the local flag is removed | Local control restores/retains the latch from broker state and denies orders. |
| Operator attempts reset while a limit is still breached | Reject reset; preserve the latch and evidence. |
| Order is reduced-only during a halt or kill | Allow only after fresh reconciliation and broker order-type verification. |
| Configuration omits a limit, uses an invalid percentage, or changes mid-session | Deny live trading; require versioned approved configuration and explicit restart/review. |
| Broker snapshot is valid for one strategy but another process trades the same account | Account-level aggregation catches the exposure, or the account is not eligible for live use. |
| Local process believes it is flat while broker reports a position | `RECONCILIATION_HALT`; no new exposure. |
| Clock drift makes an observation appear fresh | Use broker/server timestamp and a bounded clock-skew rule; otherwise halt. |
| Kill cancellation itself fails because the broker is unreachable | Keep local latch, raise urgent operator alert, and require independent broker-side action; never report success. |

## Open Questions for Camden

These are decisions the system owner must make; the spec intentionally does not
invent them:

1. What are the approved `MAX_POSITION_PCT` and `MAX_GROSS_PCT` values for the
   first live account? Is leverage permanently prohibited for v1?
2. What broker defines authoritative equity, positions, session boundaries,
   and cash-flow events? What is the maximum tolerated snapshot age before the
   gateway denies orders?
3. What are `DAILY_LOSS_PCT`, `ROLLING_DRAWDOWN_PCT`, and the rolling window
   `W`? Are they calibrated from funded/paper evidence, and who may change
   them?
4. Is the daily reset allowed automatically on the next broker session, or
   should every daily breach require operator review? The design currently
   permits automatic reset only after reconciliation and only when no stronger
   halt remains.
5. Should the rolling drawdown latch reset only by Camden, or by a second
   approval/dual-control step if the account later grows? The current design
   requires an authenticated operator reset but does not assume a second human.
6. Does Camden want any automatic flattening after a daily/rolling breach, or
   is the chosen v1 policy strictly “cancel risk-increasing orders, block adds,
   permit reductions”? The default in this spec is the latter.
7. Does the selected broker support firm/session/account kill, cancel-all,
   cancel-on-disconnect, order-entry status, and an independent control
   channel? Which credential/process is allowed to invoke it?
8. Is the initial deployment strictly one account, one process, one strategy,
   long-only US equities? If not, the aggregation and margin/short exposure
   model must be expanded before the capital gate can pass.
9. What is the operator's alert path when `KILL_CONFIRMED` cannot be proven —
   phone/SMS, desktop alert, or another channel — and what response-time
   assumption is acceptable for a one-operator desk?
10. What evidence package is required before Camden personally approves the
    first live order: paper-run duration, injected broker failures, replay
    coverage, independent review, and a documented rollback/flatten procedure?

## Precedents and source basis

- [SEC Rule 15c3-5 FAQ](https://www.sec.gov/files/faq-15c-5-risk-management-controls-bd.htm) — pre-set capital/credit thresholds, aggregate exposure, order-size controls, and the requirement to use business judgment and ongoing review for threshold selection.
- [FIA Market Access Risk Management Recommendations](https://www.fia.org/sites/default/files/2020-04/Market_Access-Best-Practices.pdf) — hard position/order limits, daily loss limits, automatic reduction/close-out examples, and a manual kill button that disables trading and cancels resting orders.
- [FIA Best Practices for Automated Trading Risk Controls and System Safeguards](https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf) — participant-side kill switches, broker/exchange backstops, and controls that cannot be overridden by the trading process.
- [CME Globex Kill Switch](https://www.cmegroup.com/tools-information/webhelp/globex-credit-controls/Content/Kill-Switch.html) — concrete venue precedent for cancelling working orders and prohibiting new order entry, with explicit operational semantics.
- [FIA MiFID II minimum-standard recommendations](https://www.fia.org/sites/default/files/2019-05/FIA-MiFID-II-Minimum-Standard-Recs-for-ETD-eTrading-vF.pdf) — source-level cancel-all, separate access for runaway algorithms, re-enable semantics, and conformance testing.

