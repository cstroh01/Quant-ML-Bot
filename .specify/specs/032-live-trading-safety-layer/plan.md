# Implementation Plan: Live-Trading Safety Layer

**Branch**: `032-live-trading-safety-layer` | **Date**: 2026-09-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`.specify/specs/032-live-trading-safety-layer/spec.md`, driven by the
Capital Gate requirement in the project instructions: "A live-trading safety
layer exists and is tested: max position size, max daily loss / drawdown
circuit breaker, and a manual kill switch. Non-negotiable before any capital
gate progress."

## Reference failure mode

Spec 032's Problem section names Knight Capital as the precedent this layer
exists to make structurally impossible, and the request that produced this
plan asked for the citation to live here. On 2012-08-01, Knight Capital
Group deployed new trading software to eight production servers but missed
one; the eighth server kept running dead code from a retired feature
(`Power Peg`) that had been repurposed for a new flag. When the new
software went live, orders on that server were routed into the dead code
path, which had no independent check on order size, rate, or cumulative
exposure before it reached the market. In 45 minutes it sent millions of
erroneous orders and accumulated a $7 billion unwanted position, realizing
a $460 million loss that forced the firm's sale days later. The SEC's
order against Knight (Release No. 70694, 2013-10-16) found violations of
Rule 15c3-5 -- the same market-access rule spec 032's Design section 1
and its Practice/precedent subsection cite for the position/gross cap here.

The mechanism that failed was not "a bad model" or "a bad signal." It was
the absence of an independent, broker-aware layer sitting between "the
system decided to send an order" and "an order reached the exchange" --
one that would have rejected the order flow on size or rate grounds
regardless of what the (broken) code upstream of it believed it was doing.
That is exactly this module's job description, restated: sit after the
strategy's decision, before the broker, and refuse to trust that decision.

## Summary

A new module, `scripts/live_safety_gate.py`, and its tests,
`tests/test_live_safety_gate.py`. It is the execution-side authority spec
032's Problem section calls for: independent of the signal layer, of spec
017's `portfolio_risk.py`, and of the broker adapter, sitting strictly
between a sizing decision and a broker call. It implements:

- **Max position / gross size** (Design section 1): equity-relative,
  inclusive boundaries, current position plus every non-terminal reservation
  plus the candidate order, atomically checked and reserved.
- **Daily loss / rolling drawdown circuit breaker** (Design section 2): a
  streaming breaker that updates on every trusted observation, halts adds
  while permitting reductions, and matches the spec's asymmetric reset
  rules (daily resets on the next trading day; rolling latches until an
  operator resets it).
- **Manual kill switch** (Design section 3): a durable latch requested
  first and checked before every order, with the confirmation-state
  vocabulary the spec's Confirmation contract defines
  (`REQUESTED`/`LOCAL_BLOCKED`/`BROKER_CANCEL_PENDING`/
  `BROKER_DISABLED_CONFIRMED`/`RECONCILING`/`KILL_CONFIRMED`/
  `BROKER_DISABLE_UNVERIFIED`).
- **Durable state** (REQ-006) in a SQLite file, not Python attributes --
  the kill latch, both halts, the configuration version, and every
  non-terminal order reservation survive a process restart because they
  are read back from disk, not reconstructed in memory.
- **An evidence trail** (REQ-010): every allow, deny, kill event, reset, and
  configuration change is appended to an `evidence_log` table with a
  timestamp and full context.

What it deliberately does not implement is scoped out below under
**Open work**, most importantly: no broker adapter, no network call, and
no credential of any kind (Rule 7) -- this module is the decision engine an
`exec/` adapter calls, not the adapter itself.

## Reconciling spec 032 against the cited research report

The task that produced this plan asked for spec 032's own REQ list to be
checked against numeric targets from a deep-research report
(`claude/research-solo-quant-edge-and-survival.md`, said to also live on
Camden's OneDrive) that suggests concrete values: target vol
`min(15%, 0.25-0.5 x deflated SR)`; de-risk at 10% drawdown; go flat at
~20% with human-only re-arm; 15c3-5-style pre-trade checks on size, rate,
duplicate, and price collar; broker reconciliation every cycle.

**That file does not exist in this repository**, under that path or any
similar one (checked by search, not just at the given path), and this
implementation session has no access to Camden's OneDrive. The reconciliation
the task asked for could not be performed against the actual document --
this is flagged rather than silently skipped, per CLAUDE.md's "what to flag
rather than fix." Camden should supply the report or its research numbers
directly if the reconciliation is still wanted.

What can be said without the document: spec 032 is explicit, in REQ-009 and
in every relevant Open Question, that it does **not** ship numeric defaults
and does not consider spec 017's own recommended numbers ("25% per-name,
100% gross, and 2%/4%/5% loss recommendations") valid live values, because
they were "not calibrated on a funded equity curve." A research report's
suggested numbers -- 10%/20% drawdown thresholds, a target-vol formula tied
to a deflated Sharpe ratio -- are exactly the same category of thing:
reasonable starting points for a discussion, not evidence calibrated on
this account's own funded history. This implementation follows spec 032's
instruction on this point precisely: `SafetyConfig` has no default for any
percentage, window, or tolerance (see `ConfigValidationTests` in the test
suite, which asserts every field is mandatory and that no dollar-based
field can even be expressed). Camden sets the real numbers before this gate
is used for anything, through `SafetyConfig(...)` at call time or
`SafetyGate.adopt_new_config(...)` for a later change -- never through a
constant this module ships.

The pre-trade check categories the report names (size, rate, duplicate,
price collar) map onto this implementation as follows: size -> the
position/gross cap; duplicate -> the `client_order_id` uniqueness
constraint (`DENY_DUPLICATE_ORDER`); price collar -> partially covered by
`DENY_PRICE_UNAVAILABLE` (an order is denied if no valid executable price
estimate exists) but a true collar (denying an order whose limit price is
implausibly far from the last trade) is not implemented -- flagged under
**Open work**. A per-order **rate** limit (orders per second/minute) is
**not implemented** and is also flagged under **Open work**; nothing in
spec 032's REQ list names one explicitly (its concern is cumulative
exposure, not order rate), but Knight Capital's own failure mode was as
much a rate/duplication runaway as a size one, so its absence is worth
Camden's attention specifically, independent of the missing report.

## An internal conflict in spec 032 itself, flagged rather than resolved

Spec 032's Kill Switch section states plainly: "all local strategy and
order-gateway submissions are denied" while `KILL_LATCHED`, with no
exception named. Its own Design section 1 "Required acceptance evidence"
list and its failure-mode table both say the opposite in places:
"reductions remain possible during a loss halt **or kill state**" and
"Order is reduced-only during a halt or kill -> Allow only after fresh
reconciliation and broker order-type verification."

This implementation does not silently pick a side. `evaluate_order` --
the automated, strategy-facing entry point -- follows the stricter Kill
Switch section text and denies every order, reduce-only included, while
`KILL_LATCHED`. A second, separate entry point,
`evaluate_operator_override_reduce`, exists only for the case the Kill
Switch section itself names as the correct channel for this
("a separate, explicit, reduce-only command after a fresh position
snapshot") -- it requires an authenticated operator and a reason, accepts
only reduce-only orders, and is the sole path that can reduce exposure
during a kill or a loss/drawdown halt. See the module docstring in
`scripts/live_safety_gate.py` for the same reasoning in the code itself.
Camden should confirm or override this reading; it is a judgment call
about which of two contradictory sentences to trust, not a fact this
session could verify against a third source.

## Technical Context

**Language/Version**: Python 3.13 locally, matching the rest of the repo.
`from __future__ import annotations`, standard library only.

**Primary Dependencies**: `sqlite3`, `dataclasses`, `json`, `zoneinfo` --
all standard library. No new entry in `requirements.txt` (Rule 6): the
durable, transactional state this module needs is exactly what `sqlite3`
is for, and reaching for a new dependency (a task queue, a document store)
to get transactions would add a supply-chain liability the standard
library already resolves.

**Storage**: A SQLite file at a caller-supplied path (tests use a
throwaway file per test; a live deployment would point at something under
`data/live_safety/`, now gitignored). Not `data/cache/`: that directory is
documented as regenerable output, and this state is the opposite of
regenerable -- losing it silently re-permits trading, which is the exact
audit finding (05/06, spec 017's halt latch living only in memory) this
spec exists to close.

**Testing**: `unittest` via `python -m pytest tests`. No network. The
mutation tests reuse the existing `killed(module, old, new, oracle)`
technique (`tests/mutation_support_019.py`), copied into a spec-scoped
`tests/mutation_support_032.py` rather than imported across a spec
boundary, matching the repo's existing one-helper-per-spec pattern.

**Target Platform**: Local research workstation and GitHub Actions
(`ubuntu-latest`); developed and verified on Windows, which needs every
SQLite connection explicitly closed before its temp directory is removed
(`SafetyGate.close()`; test fixtures track and close every gate they open).

**Project Type**: A new library module, not wired into `exec/` (which does
not yet exist in this repository) or any broker adapter.

**Constraints**: Rule 7 (no autonomous agent writes execution code that can
place an order -- this module cannot place one, by construction, since it
never imports a network client or holds a credential). Rule 8 (imports
nothing from `data.py`, `signals.py`, `backtest_harness.py`, or
`portfolio_risk.py`). Rule 12 (every gate ships a planted-defect test).
REQ-009 (no numeric default anywhere in `SafetyConfig`).

**Scale/Scope**: One account, one process boundary per spec 032's own
declared v1 scope (cash, long-only, single account). Multi-process
aggregation against the *same* SQLite file is partially supported for
free (SQLite's file locking serializes concurrent writers), but is not
the same guarantee as a real multi-strategy broker-side aggregation and is
listed under **Open work**.

## Constitution check

| Rule | Bearing on this plan | Status |
|---|---|---|
| 1 -- Point-in-time | N/A to this module in the backtest sense (no historical row is computed here), but the daily/rolling breaker's own analogous guarantee -- session `t`'s halt state depends only on observations at or before `t` -- is tested directly (`RestartDurabilityTests`, `LossDrawdownBreakerTests`). | PASS |
| 2 -- Purged CV | No model, no cross-validation. | N/A |
| 3 -- Costs | No return, Sharpe, or P&L computed or reported. | N/A |
| 4 -- Baselines | No strategy proposed or modified. | N/A |
| 5 -- Time tests | `_trading_day` crosses instant-space into session-space explicitly at `America/New_York` per CLAUDE.md's convention (not silently UTC); day-boundary and intraday-recovery cases are tested (`test_daily_halt_survives_intraday_recovery_same_day`, `test_daily_halt_clears_the_next_trading_day`). | PASS |
| 6 -- Dependencies | None added; `sqlite3`/`dataclasses`/`json`/`zoneinfo` are standard library. | PASS |
| 7 -- Execution never autonomous | No network call, no credential, no broker adapter in this module. `BrokerKillQuery` is caller-supplied data, not a broker call this module makes. | PASS |
| 8 -- Layer separation | Imports nothing from `data`, `signals`, `backtest_harness`, or `portfolio_risk`. Sits strictly after a sizing decision (any producer of an `OrderIntent`) and strictly before a broker call (any consumer of a `GateDecision`). | PASS |
| 9 -- Merge gate | This plan and the module docstring together state what changed, why each check is ordered the way it is, and what a wrong boundary would break -- the explanation is the deliverable Camden reviews. | Pending Camden's review |
| 10 -- Version control | No `git` run by this session; files written and explained, per this document. | PASS |
| 11 -- No unsourced figures | No number in this plan is presented as a live result; the Knight Capital figures above are historical facts with their SEC source cited, not this repository's output. | PASS |
| 12 -- Proof a gate can fail | Five planted defects in `tests/test_live_safety_gate.py::MutationTests`, one per REQ-critical branch (inclusive boundary, kill-latch check, pending-order aggregation, reduce-only carve-out, durable-restart reload), each with a passing control and a caught mutant. | PASS |

## Project structure

### Documentation (this feature)

```text
.specify/specs/032-live-trading-safety-layer/
├── spec.md     # already existed; authoritative requirements
└── plan.md     # this file
```

No `research.md`/`data-model.md`/`quickstart.md`/`tasks.md` were generated
separately -- the research questions spec 032 itself raised (Open Questions
1-10) are Camden's numeric decisions, not open design questions this plan
resolves, and the data model is small enough to state inline below.

### Source code (repository root)

```text
scripts/
└── live_safety_gate.py        # new -- this spec's only production file

tests/
├── test_live_safety_gate.py   # new -- unit, integration, and Rule 12 tests
└── mutation_support_032.py    # new -- the killed() helper, spec-scoped
```

**Structure decision**: one new module under `scripts/`, matching the
repo's flat layout (beside `portfolio_risk.py`, not inside it). Explicitly
**not** touched, per the task's instruction and the module boundary table:
`scripts/data.py`, `scripts/signals.py`, `scripts/backtest_harness.py`,
`scripts/portfolio_risk.py`.

## Design

### Data model

```text
SafetyConfig       version, max_position_pct, max_gross_pct, daily_loss_pct,
                    rolling_drawdown_pct, rolling_window_sessions,
                    max_snapshot_age_seconds, max_clock_skew_seconds,
                    timezone -- every field mandatory except timezone
BrokerSnapshot      as_of (tz-aware instant), status, equity,
                    external_cash_flow, positions{instrument: qty},
                    prices{instrument: worst-case executable price}
OrderIntent         client_order_id, instrument, delta_quantity (signed)
GateDecision        outcome (ALLOW/DENY), reason, config_version, action,
                    checks{...}, reservation_id
BrokerKillQuery     working_orders_terminal, disable_status (True/False/None)
```

Durable state (SQLite): `kv_state` (kill latch, both halts, config version
and full config, day/rolling anchors), `pending_orders` (every reservation,
terminal or not), `evidence_log` (append-only).

### `evaluate_order`, in call order

Matches spec 032's "Gate evaluation order" section exactly:

```text
1. load durable state; deny on a config version/value mismatch
2. check snapshot freshness/status/clock-skew/equity validity
     -> on failure: latch RECONCILIATION_HALT (no auto-expiry), deny
3. update the loss/drawdown breaker (always, on every trusted snapshot)
4. deny if KILL_LATCHED
5. deny if RECONCILIATION_HALT is latched
6. deny SHORT_NOT_SUPPORTED if the candidate would go short
7. if halted (daily or rolling) and not reduce-only -> deny LOSS_HALT
8. if reduce-only -> reserve and ALLOW (exposure caps do not apply)
9. compute worst-case exposure (position + every non-terminal reservation
   + candidate, at the conservative price); deny on a missing price
10. deny MAX_POSITION_PCT_BREACH / MAX_GROSS_PCT_BREACH (inclusive)
11. reserve (unique client_order_id) and ALLOW
```

Every branch runs inside one SQLite `BEGIN IMMEDIATE` transaction, so two
concurrent calls -- two processes or two calls in a test -- serialize
rather than race, which is what makes "two orders that each pass alone
cannot jointly exceed a limit" true rather than merely intended
(`ExposureLimitTests::test_two_orders_that_each_pass_alone_cannot_jointly_exceed_gross`).

### The daily/rolling breaker's day-boundary semantics differ from spec 017's on purpose

Spec 017's `LossCapGuard` halts only "that session's decision" for a daily
breach -- fine for a script that runs once per session close. Spec 032's
account is watched continuously intraday, and its own text says a daily
breach "remains active for the rest of the official trading day" even if
equity recovers before the close. This implementation's daily halt
therefore latches for the rest of the trading day once triggered
(`test_daily_halt_survives_intraday_recovery_same_day`), clearing only
when the trading day (in `SafetyConfig.timezone`, per CLAUDE.md's
instant-to-session crossing rule) actually rolls over
(`test_daily_halt_clears_the_next_trading_day`). This is a deliberate
divergence from spec 017's semantics, required by spec 032's own text, not
an oversight.

### Tests -- what each class pins

| Class | Pins |
|---|---|
| `ConfigValidationTests` | REQ-009: every field mandatory, no dollar field expressible, domain edges |
| `ConfigDurabilityTests` | a config value change under the same version raises at construction; `adopt_new_config` is the only sanctioned path and is blocked during an active kill |
| `DataContractTests` | naive `as_of` rejected; zero-delta order rejected |
| `FreshnessTests` | stale/clock-skew/broker-status/non-positive-equity all deny and latch `RECONCILIATION_HALT`; no automatic expiry; explicit clear works |
| `ExposureLimitTests` | proportional scaling with equity; inclusive boundary exact-deny and one-step-under-allow; pending orders and existing positions both count; two orders cannot jointly exceed gross; missing price denies; reduce-only bypasses the cap; short denied; duplicate order id denied; terminal orders stop counting |
| `LossDrawdownBreakerTests` | daily breach blocks adds/permits reductions; survives intraday recovery; clears next day; cash flow excluded; rolling breach latches across days until an operator reset that itself checks for a live breach first |
| `KillSwitchTests` | request/confirm/reset state machine against every value in the Confirmation contract; automated path denies reduce-only during a kill; the operator override path is the only one that can reduce during a kill |
| `RestartDurabilityTests` | kill latch, pending reservations, and a rolling halt all survive a simulated process restart (a second `SafetyGate` opened on the same file) |
| `EvidenceTrailTests` | every allow and deny is logged |
| `MutationTests` (Rule 12) | five planted defects: inclusive-boundary flip, kill-latch bypass, pending-order aggregation dropped, reduce-only carve-out dropped, restart-reload of the kill latch dropped -- each with a passing control and a caught mutant |

61 tests, `python -m pytest tests/test_live_safety_gate.py -q`: all pass.
Full repository suite: see `docs/PROJECT_CONTEXT.md` for the run recorded
at merge time.

## Open work (flagged, not built here)

These are named explicitly so they are not mistaken for "done" by omission:

1. **No broker adapter.** This module makes no network call and holds no
   credential (Rule 7). Wiring a real broker's order submission, fill
   confirmation, and kill/cancel-all API to this gate's `evaluate_order`,
   `record_order_outcome`, and `confirm_kill` is `exec/`-lane work, through
   the reviewed lane, not an autonomous agent.
2. **No price collar.** `DENY_PRICE_UNAVAILABLE` denies an order with no
   valid price estimate, but nothing here checks that a *limit* price is
   plausible relative to the last trade (the research report's "15c3-5
   -style ... price collar" language, and part of what actually failed at
   Knight Capital). Worth adding once a broker adapter exists to supply a
   reference price.
3. **No per-order or per-time-window rate limit.** Spec 032's own REQ list
   does not name one (its concern is cumulative exposure), but this is
   exactly the second dimension of Knight Capital's failure and should not
   be skipped by default just because no REQ number covers it.
4. **The research report could not be reconciled.**
   `claude/research-solo-quant-edge-and-survival.md` does not exist in this
   repository; Camden should supply it (or the specific numbers) if the
   reconciliation this task asked for is still wanted.
5. **The kill-switch reduce-only conflict** (see above) is this session's
   reading of two contradictory sentences in spec 032, not a confirmed
   decision -- Camden should explicitly confirm or override it.
6. **Multi-process/multi-strategy aggregation is partial.** Two processes
   pointed at the same SQLite file get real atomicity for reservations
   (REQ-004's concern), but spec 032's Open Question 8 (is this strictly
   one account/one process/one strategy?) is unresolved, and nothing here
   aggregates exposure across *different* SQLite files or accounts.
7. **No numeric configuration exists yet.** By design (REQ-009) -- Camden's
   Open Questions 1-6 in spec 032 are still open, and this module will
   refuse to do anything useful without a `SafetyConfig` he has actually
   chosen.
