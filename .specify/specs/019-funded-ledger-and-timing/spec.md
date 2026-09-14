# 019 — Funded ledger and timing

Authority: audit 2026-09-12 work order 2; the user authorizes this handwritten
spec and six sequential review units without git or Spec Kit commands.

## Frozen decisions

- One instrument, long-only cash account; integer entry quantity, no margin,
  shorts, leverage, external flows, pending orders or financing. Immediate
  next-open orders reserve and consume their full notional plus fee atomically.
  Insufficient cash rejects the order and records the rejection. No resizing.
- Explicit starting capital is required before the first open; no price-derived
  default may choose funding using later information. Initial equity exists
  BEFORE the first event, identified as phase `initial`, not a fake prior day.
- Timing, execution, and target availability: defined normatively in [Timing and price contract (normative)](#timing-and-price-contract-normative).
- Action-spanning price-ratio labels are unavailable; they are not total-payoff
  labels. Split/dividend-aware return-index features chain forward causally.
- Labels are outcomes, never predictors. Known-label training masks apply
  AFTER calendar splits. Inference retains every source session and index.
  A missing prediction means flat at that decision; its exit shifts one session.
- The h-session label is a forecast horizon, not a claim that hysteresis holds
  exactly h sessions. Variable-duration policy returns require separate replay.
- End of batch is not an exit decision. Open positions are marked. Optional
  terminal liquidation is explicitly requested and identified in the ledger.
- Cash accounting, price basis, and corporate actions: defined normatively in [Timing and price contract (normative)](#timing-and-price-contract-normative).
- Research log predictions plus a hurdle are NOT expected dollar utility
  (audit 25). No profitability claim or new trading strategy is authorized here.

## Timing and price contract (normative)

This section is the single authoritative specification of timing, execution, target availability, accounting, and price conventions for spec 019.

### Instants

| Instant | Timing / Index | Description |
|---|---|---|
| `feature_available_at` | After session $t$'s close | Point-in-time features computed solely from information available at or before session $t$ close. |
| `decision_at` | After session $t$'s close | Model prediction and trading decision evaluated after session $t$ close, prior to session $t+1$ open. |
| `entry_at` | $\text{Open}[t+1]$ | Execution of next-open entry order; reserves and consumes cash notional and entry fee atomically. |
| `exit_at` | $\text{Open}[t+h+1]$ | Execution of exit order for forecast horizon $h$; receives proceeds and pays exit fee atomically. |
| `label_available_at` | $\text{Open}[t+h+1]$ | Target label outcome is observable only once the session $t+h+1$ open price is published. |

### Targets and cross-validation

- **Target formulations:**
  - Forward log return target: $\log(\text{Open}[t+h+1] / \text{Open}[t+1])$, observable at exit open.
  - Direction target: $(\text{return} > 0)$ mapped to integer class, with flat ($0.0$ return) as class 0.
  - Both endpoints must be finite and strictly positive ($> 0$). The final $h+1$ labels of a dataset are unobservable and emitted as missing (`NaN` / `<NA>`), never fabricated downward or imputed.
  - Labels spanning corporate actions (split or dividend) are unavailable (`NaN`), not misleading price ratios. Total-payoff targets across actions are deferred to future work.
- **Span, not horizon (Correction 1, R-10):**
  - `build_target` returns `(label, task, label_availability_span)` where the third return value is `label_availability_span = h + 1`, never a horizon.
  - Span = $h + 1$; callers must never pass this returned span back as `horizon` (which would erroneously generate an $(h+1)$-session target). The availability span is handed back strictly to size purge and embargo intervals.
- **Purge and embargo convention (Correction 2, R-02):**
  - Purge and minimum embargo span is $h + 1$ rows.
  - $h + 1$ rows is a chosen convention, not a mathematical derivation: it is one row more conservative than `walk_forward_cv.py:98` requires (`t < test_start - label_horizon` with purge $h$ keeps up to $\text{Open}[\text{test\_start}]$, which is known before the decision at that session's close). $h + 1$ is chosen to provide a deliberate safety margin across fold boundaries. Cross-validation refuses any purge/embargo span shorter than feature-frame metadata declares.
- **Positional shifts and session gaps (Correction 3, R-19):**
  - Targets shift by row ($\text{Open.shift}(-1)$ and $\text{Open.shift}(-(h+1))$).
  - Positional behavior: if a session is absent from the dataset (such as an unscheduled market halt, holiday, or missing bar), $\text{Open}[t+1]$ is the next observed open, and the label silently spans more calendar time without a trace. Enforcing a complete calendar belongs to finding 16 (`AUDIT.md:77`, work order 3).
- **Calendar preservation and inference:**
  - Preserve source sessions and index. Filter training and validation sets strictly after chronological calendar splitting; inference does not require a known outcome. Multi-asset callers must split by ticker; CV and target paths reject mixed tickers.
- **Audit closure status for finding 23 (Correction 7, R-08):**
  - Calendar-preserving features (Finding 23, `AUDIT.md:93`): Status is **library-closed; consumer open (API rundown)**. Core feature creation and CV masks preserve source sessions without row deletion, but the consumer API rundown remains open pending consumer test updates.

### Accounting

- **Account model:**
  - Cash account: single instrument, long-only, integer entry quantity. No margin, shorting, leverage, external cash flows, pending orders, or financing.
  - Capital must be declared explicitly before the first open; no price-derived default may choose funding using later information.
  - Immediate next-open orders reserve and consume their full notional plus fee atomically. Insufficient cash rejects the order and records the rejection; rejected orders incur no fee. No resizing.
  - `Buying_Power` is Cash. `Reserved_Cash` is 0.0 because there are no pending unfilled orders or financing.
- **Marking vs. liquidation:**
  - End of batch is not an exit decision. No automatic final-row flatten. Default accounting marks open positions at session close; optional `liquidate=True` records an explicit terminal-close liquidation and charges its fee.
- **Fixed-horizon policy constraint (Correction 5, R-15):**
  - A decision at $t$ with horizon $h$ opens at $\text{Open}[t+1]$ and closes at $\text{Open}[t+h+1]$; no early exit, no extension.
  - Under fixed-horizon execution, each trade's pre-cost log return identically equals its entry decision's label ($\log(\text{Exit Price} / \text{Entry Price}) = \text{Label}_t$).
  - Hysteresis is permitted only at $h = 1$ (where each held session is a one-session position whose payoff is that session's label, and continuing incurs no new round trip). Hysteresis for $h > 1$ is prohibited.
  - Variable-duration policy returns and optimal stopping are deferred to work order 5 as their own spec with multi-horizon labels and in-fold policy selection (`AUDIT.md:97, 233`).
- **Audit closure status for finding 01 (Correction 7, R-08):**
  - Funded ledger (Finding 01, `AUDIT.md:45`): Status is **library-closed; consumer open (018 T024)**. Core ledger accounting and metrics reconciliation hold at the library boundary, but tearsheet routes (`reports/api/routes/backtest.py`) that consume account returns remain open until replaced.

### Prices and corporate actions

- **Price basis declaration (Correction 6, R-04):**
  - `price_basis='unadjusted_dollars'` is a declaration against accident, not a proof against forgery. Its only non-test writer will be spec 020's loader (020 `spec.md:115`).
  - Never apply this tag to old adjusted caches to bypass the boundary.
  - `execution_price_frame` validates OHLCV bounds and corporate action validity, and derives `Research_Close` and `Research_Volume` forward causally without rewriting earlier research values.
- **Stock splits:**
  - Split factor is new shares per old share (1.0 for no action), executed before session open.
  - Share holdings scale by the split factor; per-share price scales inversely. Split fractions are retained; broker cash-in-lieu is unmodeled.
- **Dividends and payment dates (Correction 4, R-03):**
  - Dividend is dollars per post-split share. Entitlement occurs before ex-date opening trades: shares held before ex-date open accrue a dividend receivable.
  - Receivables contribute to `Equity` ($\text{Equity} = \text{Cash} + \text{Quantity} \times \text{Price} + \text{Receivable}$), but never contribute to `Buying_Power`.
  - Cash credit occurs only on the declared payment session (or first observed session thereafter), at which point `Receivable` transfers to `Cash`.
  - Payment date basis: If a payment session is not sourced from the vendor, a declared upper-bound session is used, and $\text{Pay\_Date\_Basis} \in \{\text{sourced}, \text{bound}\}$ is recorded on the dividend event. A later pay date can only delay cash conversion and reject more orders, never admit an unaffordable order (Rule 1-safe). Spec 020 supplies the bound per ticker from primary filings.

### Session labels and phases

- Daily dates are naive session labels (e.g. `YYYY-MM-DD`).
- Phase distinguishes `initial`, `open`, and `close`. These are chronological event sequence phases within and across sessions, not broker execution timestamps. Midnight is not treated as an execution instant.
- Initial capital exists before the first market event, identified as phase `initial` with initial peak position -1 and no invented previous trading day.
- Corporate action fractions are retained; broker cash-in-lieu, tax withholding, and settlement delays (e.g. T+1) are unmodeled in this bounded cash-account profile.

## Acceptance

Hand-calculated event balances; $100 rejects a $201.10 entry (AUDIT.md:45); pre-trade $100
through [95,95,90] draws down 10% (AUDIT.md:47); corrupt fills/costs fail; overnight-only
pre-entry movement earns nothing; latest feature row survives; prefix/future
perturbation invariance; split and paid dividend reconcile; per-review-unit
red evidence and isolated mutation controls. Synthetic data only.

## Scope disagreements and limits

The derived plan omits 25 from 3.2 and assigns it only to 3.5; audit work order
2 includes 22–25 (and work order 5 also includes 25). Keep 25 in this review;
do not claim its economic estimand problem solved by changing timestamps.
The plan proposes specs 022–025 and target/data before ledger; this run's user
instead assigns spec 019 and ledger-first dependency order. Audit does not
mandate those proposed numbers or that internal order. Findings 03–04 are
work-order-1 prerequisites, not a plan/audit disagreement.

Full portfolio risk, order recovery, dataset provenance storage, empirical
utility calibration and dependent-data inference remain separate milestones.
