# Feature Specification: Position Sizing and Portfolio Risk Layer

**Feature Branch**: `017-position-sizing-risk`

**Created**: 2026-09-11

**Revised**: 2026-09-11 — clarified; see *Clarifications* below.

**Status**: Implemented 2026-09-12 — not through the Merge Gate (Rule 9)

**Input**: User description: "Position sizing and portfolio-level risk layer
(per docs/PROJECT_CONTEXT.md and this project's constitution). Requirements:
(1) position sizing via volatility targeting or fractional-Kelly, sized off
each signal's confidence and the asset's realized/predicted volatility —
never full Kelly; (2) correlation-aware allocation across the 5-ticker
universe (AAPL, MSFT, GOOGL, NVDA, AMZN) so correlated names don't act as one
concentrated bet; (3) a daily/weekly drawdown and loss cap enforced in code
that halts new entries automatically."

**Owns / must not know about** (per CLAUDE.md's module table): a new
`scripts/portfolio_risk.py`, a **risk layer** that sits between the signal
layer and execution.

| Owns | Must not know about |
|---|---|
| How much of the book each signal gets | How a signal was produced |
| How correlated positions share one risk budget | How a fill is priced or a trade is booked |
| When new entries are halted | P&L arithmetic |

It **reads** two numbers that accounting produces — the book's equity at each
session close, and the current holdings expressed as weights — and never
computes either.

---

## Background

**Why this spec, why now.** Spec 012's Background named it: *"The one-share
position size is the root cause … fixing that is an execution-layer change
under Rule 8, recorded as the natural follow-up and deliberately not smuggled
in here."* Every script in the repo still trades exactly one share of one
ticker. The roadmap is backtest → paper trading → small live capital, and a
book with no sizing rule and no loss cap is not something paper trading can
meaningfully exercise.

Three separate failures, one per user story:

1. **Sizing.** One share of NVDA and one share of AAPL are not the same bet.
   The size of a position has to depend on how volatile the asset is and how
   strongly the signal believes in it.
2. **Correlation.** `docs/PROJECT_CONTEXT.md` already recorded AAPL and GOOGL
   bottoming on the same day (2025-04-08) — a market-wide shock hits every
   name in this universe at once. Five full-size positions in five mega-cap
   tech names are not five bets. They are one tech bet, taken five times.
3. **Loss caps.** Nothing in the repo stops trading after a bad day or a bad
   week. A cap that lives in a human's head is not a cap.

### Where this sits relative to Rule 8

The constitution: *"The signal layer knows nothing about fills, position
sizing, or P&L."* So sizing is **not** signal-layer work. It is not accounting
either — this module never books a trade or prices a fill. It is a decision
layer that consumes one output from each side:

- From the signal layer: a per-ticker confidence.
- From accounting: equity at each close, and current holdings as weights.

That is a dependency on the **shape** of two numbers, not on anyone's code.
No import in either direction, the same "shared shape, not shared code"
coupling spec 012 recorded between `ml_signal.py` and the harness. Rule 8 asks
a PR that reaches across layers to state why; this paragraph is that
statement.

### What this spec does not do

- **It does not wire into `backtest_harness.run_backtest`.** The harness is
  one-share, one-instrument, long-only, and has no concept of a weight. A
  weight-based multi-asset execution path is an execution-layer change and
  needs its own spec. This spec ships the risk layer and its tests, the same
  call spec 012 made about end-to-end wiring.
- **It reports no return, Sharpe, or P&L.** Rules 3 and 4 therefore have no
  metric to attach to. The first spec that runs this layer through a costed
  backtest owes both baselines.
- **It does not implement Kelly sizing.** See Q1 below.

---

## Clarifications

### Session 2026-09-11

Resolved by the implementing agent against the constitution's existing
conventions, per the run instructions and CLAUDE.md (*"the answer belongs in
the spec, where the next agent can also read it"*). Each answer carries its
reasoning so Camden can overturn it by editing this section, not by
reconstructing a chat.

- Q: Which sizing rule — volatility targeting or fractional Kelly — and if
  Kelly, which fraction is the ceiling? → A: **Volatility targeting only.**
  `weight = confidence × target_volatility / volatility`. No Kelly code path
  exists, so "never full Kelly" holds by construction rather than by a
  parameter check someone can raise.

  **Why.** Kelly sizes off an *expected return*, and this repo does not have
  a validated one. Worked with this repo's own numbers: spec 014's best
  classifier is 52.99% accurate on AAPL; AAPL's daily σ is about 181 bps
  (spec 012). The binary Kelly fraction is `(2p − 1)/σ_daily = 0.0598 / 0.0181
  = 3.3×` the book. Half Kelly is still 1.65× — leverage, from a screening
  result on one ticker that spec 005 showed does not yet beat a majority-class
  baseline. That is CLAUDE.md's *"an unusually high Sharpe is a bug report"*
  in sizing form: Kelly turns an unproven edge directly into leverage, and its
  size scales linearly with the error in that edge. The regression path is
  worse: continuous Kelly on a log-return forecast carries a `+σ²/2` term that
  holds a position even at zero predicted edge — the opposite of "sized off
  confidence." Volatility targeting needs only `σ`, which clusters and is
  estimable point-in-time (`docs/PROJECT_CONTEXT.md`: MSFT 21-day vol 10%–58%).
  A Kelly path belongs in a later spec, after spec 013 produces calibrated
  evidence, with a fraction ceiling of at most one half stated in that spec.

- Q: Is a "week" the calendar trading week or a rolling five-session window,
  and how long does a halt last? → A: **The calendar week** (ISO, Monday to
  Sunday) of the session label. A **weekly** halt latches from the breaching
  session through the last session of that week. A **daily** halt covers only
  the breaching session's decision. A halt is a property of the session whose
  close makes the decision (executed at the next open).

  **Why.** A rolling window never resets: one bad Tuesday slides forward day
  by day, so "when does trading resume" has no fixed answer — which fails
  Rule 9 on its face. The calendar week is how a broker statement reports, and
  it gives the halt a definite end. It latches because an un-latched halt
  switches off on a one-day bounce and puts the book back in the market in the
  middle of the week that breached it. Daily granularity: a decision at `t`'s
  close executes at `t+1`'s open, so a daily halt that expired at `t`'s close
  would never block anything; covering the decision made at `t`'s close is the
  only reading under which it does something.

- Q: Does "halts new entries" also block *increasing* a position that is
  already open? → A: **Yes.** Under a halt, each ticker's target is
  `min(target, current)`. Opening and adding are blocked; reducing and exiting
  are not. `current` is the holding **as accounting reports it at that close**
  (drifted weight), not the previous target.

  **Why.** Read literally, "new entries" leaves a loophole: hold 0.1% of a
  name and scale it to the cap during a halt. What the cap exists to stop is
  *added risk*, and adding to a position is added risk. Exits stay allowed
  because a halt that traps the book in its losing positions increases risk
  instead of capping it. Drifted weight, not previous target: after a price
  drop a position's weight is below its old target, and "topping back up" to
  that target is buying.

- Q: What does "confidence" mean, and which volatility estimate is used? → A:
  **Confidence is a conviction in `[0, 1]`** — 0 is no position, 1 is full
  conviction; missing reads as 0; outside `[0, 1]` raises. **Volatility is the
  realized** standard deviation of daily log returns over a trailing **63
  session** window, annualized by `sqrt(252)`. Correlation uses a trailing
  **63 session** window of the same returns. Sizing takes volatility as an
  input, so a forecast can replace the realized estimate later without
  changing sizing.

  **Why.** A conviction in `[0, 1]` is estimator-agnostic — a classifier's
  probability, a predicted return, and spec 012's entry mask can all be mapped
  onto it — and the mapping is a signal-layer choice (spec 012 FR-012 made the
  same call for predictions). Missing reads as flat, matching spec 005 and 012.
  63 sessions is one quarter: a shorter window reacts faster to volatility
  clustering but re-sizes on noise, and every re-size is turnover that Rule 3
  will charge for. Correlation's sampling error at 63 sessions and `ρ = 0.6`
  is about `(1 − ρ²)/sqrt(63) ≈ 0.08`, tight enough to act on, and a longer
  window would average away the sell-off correlation spike — the moment this
  adjustment exists for. Both windows are still required parameters, never
  defaults (the repo's convention for decision parameters); the values here
  are the recommended configuration.

- Q: What are the book-level caps and loss limits, and in what order are the
  steps applied? → A: Recommended configuration below; the order is fixed:
  **standalone weight → per-name cap → correlation adjustment → gross cap →
  halt.** Loss boundaries are **inclusive** (reaching a limit exactly halts).
  Gross exposure may not exceed 1.0 — **no leverage**, enforced by validation.

  | Parameter | Value | Reasoning |
  |---|---|---|
  | `target_volatility` | 0.10 | 10% annualized per position at full conviction. At AAPL's 28.7% vol that is a 35% standalone weight, which the per-name cap then binds. |
  | `max_weight` | 0.25 | No single name above a quarter of the book. |
  | `max_gross` | 1.00 | A cash account heading to small live capital. Above 1.0 raises. |
  | `volatility_window` / `correlation_window` | 63 / 63 | See the previous answer. |
  | `daily_loss_limit` | 0.02 | About 3σ daily at a 10–12% book vol — fires on tail days, not ordinary noise. |
  | `weekly_loss_limit` | 0.04 | About 2.5σ weekly. |
  | `weekly_drawdown_limit` | 0.05 | From the week's high-water mark, so a week that rallies and gives it back is caught before it is a loss. |

  **Why cap before correlation.** Three perfectly correlated names, each with
  a standalone weight of 1.0: cap first gives 0.25 each, then divided by an
  overlap of 3 is 0.083 each — 0.25 combined, one capped bet. Correlation
  first gives 0.333 each, then capped to 0.25 each — 0.75 combined, three
  capped bets. The second order silently undoes story 2. **Why inclusive.**
  A loss limit that must be *exceeded* lets a book sit exactly at its cap and
  keep adding; at a limit, the conservative side is the halted side. (Spec
  012's *entry* boundary is strict for the mirror-image reason: the
  conservative side of an entry is not entering.) **Why the halt last.** It is
  the only step allowed the final word on adding risk; anything after it could
  undo it.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Each position is sized off conviction and volatility (Priority: P1)

As the project owner, I need each ticker's position sized from how confident
its signal is and how volatile the asset is, so a volatile name and a calm
name carry comparable risk instead of comparable share counts.

**Why this priority**: Without it there is no position size at all, and
stories 2 and 3 have nothing to adjust or halt.

**Independent Test**: Feed hand-built confidences and volatilities for a
single session; assert every weight equals the stated formula, computed
independently in the test.

**Acceptance Scenarios**:

1. **Given** two names with equal confidence and volatilities of 20% and 40%,
   **When** they are sized, **Then** the 40% name's weight is exactly half the
   20% name's.
2. **Given** a confidence of zero, or a missing confidence, **When** that name
   is sized, **Then** its weight is exactly zero.
3. **Given** a volatility low enough that the formula implies a weight above
   the per-name cap, **When** it is sized, **Then** the weight equals the cap.
4. **Given** realized volatility at session `t`, **When** any close after `t`
   is changed by any factor, **Then** the volatility at `t` is bit-identical.
5. **Given** the module, **When** any configuration is built, **Then** the
   only sizing rule available is volatility targeting — there is no Kelly
   fraction to set, full or otherwise.

---

### User Story 2 - Correlated names share one risk budget (Priority: P1)

As the project owner, I need positions in correlated names to be scaled down
together, so a cluster of names that move as one is sized as one bet rather
than several.

**Why this priority**: This universe is five mega-cap tech names. Without it,
story 1's per-name sizing quietly builds a concentrated sector bet.

**Independent Test**: Hand a correlation matrix and standalone weights to the
allocation step; assert the adjusted weights exactly.

**Acceptance Scenarios**:

1. **Given** two names with perfectly correlated returns and equal standalone
   weights `x`, **When** they are allocated together, **Then** each gets
   `x/2` — combined, one bet of size `x`.
2. **Given** two names with zero correlation, **When** they are allocated,
   **Then** neither weight changes.
3. **Given** two negatively correlated names, **When** they are allocated,
   **Then** neither weight *increases*. A hedge earns no extra size in a
   long-only book.
4. **Given** the five-ticker universe where AAPL, MSFT, and GOOGL move
   near-identically and NVDA and AMZN move independently, **When** all five
   are held at full conviction, **Then** the three correlated names' combined
   weight is approximately one standalone weight, and NVDA's and AMZN's
   weights are approximately unchanged.
5. **Given** `k` equal-size positions with equal volatility and common
   pairwise correlation `ρ ≥ 0`, **When** they are allocated, **Then** the
   book's ex-ante volatility equals one position's standalone volatility times
   `sqrt(k / (1 + (k-1)ρ))` — exactly one bet's worth at `ρ = 1`.
6. **Given** three perfectly correlated names whose standalone weights all
   exceed the per-name cap, **When** they are allocated, **Then** their
   combined weight is one cap, not three.

---

### User Story 3 - Loss caps halt new entries automatically (Priority: P1)

As the project owner, I need a daily loss cap and weekly loss and drawdown
caps enforced in code, so a bad day or week stops new risk from being added
without anyone having to notice.

**Why this priority**: This is the control that has to exist before paper
trading, and it is the one a human is least reliable at enforcing mid-loss.

**Independent Test**: Feed a hand-built equity series with a known breach;
assert exactly which sessions are halted and why.

**Acceptance Scenarios**:

1. **Given** a session whose loss against the previous close reaches the
   daily limit, **When** that session closes, **Then** the decision made at
   that close is halted, and the next session's decision is not (absent a new
   breach).
2. **Given** a weekly loss that reaches the weekly limit on a Wednesday,
   **When** equity recovers on Thursday, **Then** Thursday's and Friday's
   decisions are still halted, and the next week's first decision is not.
3. **Given** a week that rises and then falls back from its intra-week peak
   by the weekly drawdown limit, **When** that session closes, **Then** its
   decision is halted even though the week is not yet a loss.
4. **Given** a halted decision, **When** targets are computed, **Then** no
   position is opened or increased, and existing positions can still be
   reduced or closed.
5. **Given** the halt state at session `t`, **When** equity after `t` is
   changed by any amount, **Then** the halt state at `t` is unchanged.
6. **Given** a Monday that gaps down from Friday's close, **When** Monday
   closes, **Then** the weekly loss is measured from Friday's close — the gap
   is inside the new week's loss, not lost between two weeks.

---

### Edge Cases

- **First session**: there is no previous close, so no daily loss can be
  measured and none is reported as a breach. The first week's anchor is the
  first observed equity.
- **Warm-up**: before a full volatility or correlation window exists, a name
  cannot be sized, so its weight is zero — never a guessed size.
- **Zero or missing volatility**: weight zero. A zero volatility would divide
  into an infinite weight, which the per-name cap would silently turn into a
  maximum-size position — the worst possible direction to fail.
- **Missing bar for one ticker** (halt, data gap): returns across the gap are
  missing, not stitched into a multi-day return labelled as one day. That
  name stays unsized until a full window of real returns exists again.
- **Holiday week** (four sessions): still one week.
- **Year boundary**: a week spanning 31 December and 2 January is one week
  (ISO year-week, not calendar-year-week).
- **A missing session in the equity series**: the daily loss is measured
  against the previous *observed* close. A whole missing week simply means the
  next observed week anchors to the last observed close.
- **Timezone-aware or non-midnight session labels**: rejected. CLAUDE.md
  *Conventions → Timestamps* makes a session label naive and
  midnight-normalized; comparing it to an aware one is the silent one-bar
  shift Rule 5 exists to catch.
- **Non-positive or missing equity**: rejected. A return on a non-positive
  book is undefined, and a missing close would turn a real loss into a skipped
  one.
- **Sessions out of order or repeated** in the equity stream: rejected.
- **Tickers that do not line up** across confidence, prices, and holdings:
  rejected, the same reasoning as spec 012's misaligned-hurdle check.
- **An undefined correlation between two active names**: rejected rather than
  guessed at in either direction.
- **Every name flat**: an all-zero target, not an error.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** *(sizing)*: The module MUST compute a per-ticker standalone
  weight `confidence × target_volatility / volatility` at one session, then
  cap it at `max_weight`. Missing or zero confidence, and missing or zero
  volatility, MUST give exactly zero. Confidence outside `[0, 1]` and
  negative volatility MUST raise.
- **FR-002** *(never full Kelly)*: Volatility targeting MUST be the only
  sizing rule. The module MUST NOT contain a Kelly sizing path; adding one is
  a new spec (see Clarifications, Q1).
- **FR-003** *(volatility, Rule 1)*: Realized volatility at session `t` MUST be
  the sample standard deviation of the last `volatility_window` daily log
  returns ending at `t`, annualized by `sqrt(252)`, and MUST be missing unless
  all of those returns exist. It MUST use only closes at or before `t`.
- **FR-004** *(correlation, Rule 1)*: Pairwise correlation at session `t` MUST
  use only the last `correlation_window` daily log returns ending at `t`.
- **FR-005** *(correlation-aware allocation)*: Each active position's weight
  MUST be divided by its overlap — the sum over all *active* positions `j`
  (itself included) of `max(ρ_ij, 0)`. Inactive positions MUST NOT count. The
  adjustment MUST never increase any weight.
- **FR-006** *(order)*: Steps MUST apply in the order standalone weight →
  per-name cap → correlation adjustment → gross cap → halt.
- **FR-007** *(book-level cap)*: If total gross weight exceeds `max_gross`,
  every weight MUST be scaled by the same factor to meet it. `max_gross` MUST
  be at most 1.0.
- **FR-008** *(loss caps)*: A guard MUST consume the book's equity at each
  session close and report, per session: daily return against the previous
  observed close; weekly return against the last close of the previous week;
  weekly drawdown against the week's running high-water mark (anchor
  included); a flag per breached cap; and whether that session's decision is
  halted. Breaches MUST be inclusive of the limit. At daily granularity a
  daily drawdown is the daily loss, so one daily limit covers both.
- **FR-009** *(halt duration)*: A daily breach MUST halt that session's
  decision only. A weekly loss or weekly drawdown breach MUST halt every
  decision from the breaching session through the last session of the same
  ISO week, regardless of later recovery.
- **FR-010** *(halt enforcement)*: Under a halt each ticker's target MUST be
  `min(target, current)`, where `current` is the reported holding at that
  close. Reductions and exits MUST remain possible.
- **FR-011** *(point-in-time halt)*: The halt state at session `t` MUST depend
  only on equity at or before `t`. A streaming guard fed one session at a time
  and a whole-series evaluation MUST agree exactly, and the whole-series
  evaluation MUST be implemented by running the streaming guard, not as a
  second implementation.
- **FR-012** *(one decision, composed)*: One function MUST produce a session's
  final target weights from prices, confidences, current holdings, the halt
  state, and the configuration, and MUST truncate the price history at that
  session before computing anything from it. It MUST also return each
  intermediate step (standalone, capped, overlap, adjusted, gross-scaled,
  final) so the mechanism can be inspected, not just its result.
- **FR-013** *(Rule 8)*: `portfolio_risk.py` MUST NOT import
  `backtest_harness`, `metrics`, `signals`, `ml_signal`, `estimators`,
  `model_cv`, `logistic_baseline`, `ma_crossover_backtest`,
  `multi_ticker_comparison`, or `data`. It MUST NOT compute a fill, a trade,
  or P&L.
- **FR-014** *(Rule 6)*: No new dependency.
- **FR-015** *(timestamps)*: Every session index MUST be timezone-naive,
  midnight-normalized, unique, and strictly increasing, or the call MUST
  raise.
- **FR-016** *(validation)*: Every limit, window, and cap MUST be validated on
  construction: `0 < target_volatility`, `0 < max_weight ≤ max_gross ≤ 1`,
  `volatility_window ≥ 2`, `correlation_window ≥ 3`, and each loss limit in
  `(0, 1)`. Out-of-domain values MUST raise rather than be clipped.
- **FR-017** *(universe-agnostic)*: The module MUST work for any set of
  tickers and MUST NOT hard-code the five-ticker universe; the tests MUST
  exercise it on exactly that universe.
- **FR-018** *(Rule 5 and mutation coverage)*: Tests MUST cover the
  off-by-one, boundary, and gap cases for every time-indexed computation, and
  a mutation check MUST show each defect named in SC-008 fails the suite.

### Key Entities

- **Confidence**: a per-ticker conviction in `[0, 1]` for one session, from
  the signal layer. Produced upstream; consumed here.
- **Volatility**: annualized standard deviation of a ticker's daily log
  returns over a trailing window.
- **Standalone weight**: the fraction of the book one position would get on
  its own, before correlation is considered.
- **Overlap**: for one active position, the sum of its non-negative
  correlations with every active position, itself included. At least one.
- **Target weight**: the final fraction of the book to hold, after sizing,
  correlation, the book-level cap, and any halt.
- **Equity**: the book's value at a session close, reported by accounting.
- **Halt state**: per session, whether that session's decision may add risk,
  and which cap stopped it.
- **Risk configuration**: the validated set of parameters in the Q5 table.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For hand-built inputs, every standalone weight matches the
  formula computed independently in the test to within `1e-12`, and doubling
  a volatility halves its weight.
- **SC-002**: Changing any close after session `t` by any factor leaves
  volatility, correlation, and the final target weights at `t` bit-identical.
- **SC-003**: Two perfectly correlated names at standalone weight `x` receive
  `x/2` each; zero correlation leaves weights unchanged; negative correlation
  never increases them.
- **SC-004**: On a synthetic five-ticker universe with a three-name correlated
  cluster, the cluster's combined weight is within 5% of one standalone
  weight, and each independent name keeps at least 90% of its standalone
  weight.
- **SC-005**: For `k` equal positions at common correlation `ρ ∈ {0, 0.3,
  0.6, 1}`, ex-ante book volatility matches `σ·sqrt(k/(1+(k-1)ρ))` to within
  `1e-12`.
- **SC-006**: A breach reaching a limit exactly halts; a loss one
  representable step smaller does not. A weekly halt stays on for the rest of
  its week after equity recovers, and is off at the next week's first
  session.
- **SC-007**: Under a halt, no ticker's target weight exceeds its current
  weight, and a ticker whose signal goes flat is still taken to zero.
- **SC-008**: A mutation check fails the suite for each injected defect: the
  per-name cap applied after the correlation step; negative correlations not
  clipped; inactive names counted in the overlap; variance used in place of
  volatility; a volatility window that reads one bar ahead; a strict instead
  of inclusive loss boundary; a weekly halt that un-latches on recovery; a
  weekly anchor taken from the week's first close instead of the prior week's
  last close; a halt that only blocks opening from flat; a halt that also
  blocks exits; a missing confidence treated as full conviction; a zero
  volatility sized at the per-name cap.
- **SC-009**: The full test suite passes with no network access and no new
  dependency.

---

## Assumptions

- **Universe**: AAPL, MSFT, GOOGL, NVDA, AMZN, as settled in spec 013
  (`multi_ticker_comparison.TICKER_UNIVERSE`). This module does not import
  that constant (FR-013); the tests do.
- **Long-only.** The harness goes flat rather than short (spec 002), and this
  layer matches: no target weight is ever negative.
- **Daily bars, decisions at the close.** A decision made at session `t`'s
  close is executed at `t+1`'s open, matching Rule 1's "signals shift
  forward; fills happen at the next bar's open."
- **Accounting is someone else's.** Equity and current holdings are inputs.
  In a backtest they come from a future weight-based harness; in paper or
  live trading, from the broker. Tests that need a feedback loop do their own
  small mark-to-market inside the test — the same way `test_ml_signal.py`
  imports the harness while `ml_signal.py` does not.
- **Where confidence comes from is out of scope.** Mapping a classifier's
  output, a predicted return, or spec 012's entry mask into a confidence is a
  signal-layer decision for the wiring spec that follows.
- **No all-time drawdown kill switch.** The request names daily and weekly
  caps. A book-lifetime maximum-drawdown stop that needs a human to reset is a
  common pre-live control and is recorded as an open question, not added
  silently.
