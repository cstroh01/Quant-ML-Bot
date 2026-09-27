# Quant-ML-Bot

A quantitative trading **research framework**, built from scratch to the
standards a systematic desk would actually hold it to, on free data only.

The deliverable is the machinery, not the returns: point-in-time correctness,
purged and embargoed walk-forward cross-validation, false-discovery correction
over the project's entire trial history, cost modeling that includes spread and
market impact, an append-only trial ledger, and an execution safety layer with
durable halts and a kill switch.

> **Status: v1.0 in progress.** `docs/SCOPE-V1.md` holds the definition of done.
> No real capital has ever been deployed and none will be until the capital gate
> in that document passes in full. Nothing here is investment advice.

---

## What this is, and what it is not

**It is** an honest research harness. Every correctness property that silently
breaks a backtest is enforced by a test that has been observed failing, not by
review. The rules are written down in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md) and a pull
request that violates one is rejected regardless of its results.

**It is not** a profitable strategy, and it does not claim to be. It runs on a
static basket of five mega-cap survivors using free daily bars. That universe is
an accounting and machinery smoke test. Any performance figure it produces is
evidence that the plumbing is correct, not that an edge exists.

### Stated limitations

These are permanent properties of a free-data project, disclosed wherever a
result appears (constitution Rule 16):

| Limitation | Consequence |
|---|---|
| Static survivor basket (AAPL, MSFT, GOOGL, NVDA, AMZN), chosen as of 2026 | Survivorship bias. No delisted or distressed names in the history. |
| Corporate actions from a free tier, reconciled against one free second source at best | yfinance has documented split, dividend, and 100x pricing defects. Unreconciled actions are flagged, not assumed correct. |
| No point-in-time fundamentals | Features are price and volume only. |
| Daily bars | No intraday behavior, microstructure, or order-book information. |
| Costs are modeled, never calibrated against real fills | Half-spread plus square-root impact estimated from daily OHLC is an estimate. |

## Architecture

Three layers, independently correct and independently testable. The harness
knows nothing about how a signal was produced, which is what lets a model
replace a rule without touching execution.

| Layer | Module | Responsibility |
|---|---|---|
| Data | [`scripts/data.py`](scripts/data.py) | Fetch, validate, and cache unadjusted OHLCV plus separate corporate actions |
| Features | [`scripts/features.py`](scripts/features.py), [`scripts/targets.py`](scripts/targets.py) | Scale-free features and selectable prediction targets, computed point-in-time |
| Signal | [`scripts/signals.py`](scripts/signals.py), [`scripts/ml_signal.py`](scripts/ml_signal.py) | Decide *when* to trade, and nothing else |
| Validation | [`scripts/model_cv.py`](scripts/model_cv.py), [`scripts/walk_forward_cv.py`](scripts/walk_forward_cv.py) | Purged, embargoed walk-forward splits and nested tuning |
| Execution and accounting | [`scripts/backtest_harness.py`](scripts/backtest_harness.py) | Fills, a funded cash and position ledger, trades, P&L |
| Statistics | [`scripts/metrics.py`](scripts/metrics.py), [`scripts/selection_bias.py`](scripts/selection_bias.py) | Performance metrics with HAC standard errors, deflated Sharpe, CSCV/PBO |
| Trial ledger | [`scripts/trial_registry.py`](scripts/trial_registry.py), [`scripts/trial_runner.py`](scripts/trial_runner.py) | Append-only hash-chained record of every variant ever tried |
| Risk | [`scripts/portfolio_risk.py`](scripts/portfolio_risk.py) | Volatility-targeted sizing, correlation overlap, loss-cap halts |
| Safety | [`scripts/live_safety_gate.py`](scripts/live_safety_gate.py), [`scripts/order_gateway.py`](scripts/order_gateway.py) | Independent pre-order limits, durable circuit breakers, manual kill switch |

## The correctness properties it enforces

These are the reason the repository exists. Each is a rule in the constitution
with tests that fail when it is violated.

- **Point-in-time correctness (Rule 1).** For every row timestamped `t`, every
  value in it is computable from data that existed at or before `t`. No
  full-sample statistics, no backward fills, no scalers fit outside the fold. A
  signal is never filled at the close that produced it.
- **Purged, embargoed walk-forward CV only (Rule 2).** Random k-fold is banned.
  Observations whose label horizon overlaps the validation window are purged, and
  an embargo at least as long as the label horizon follows each window.
- **Costs are mandatory and non-flat (Rules 3, 13).** No gross mode. Slippage
  derives from a daily-OHLC half-spread estimate plus a square-root market-impact
  term; flat basis-point assumptions are invalid.
- **Two baselines per strategy (Rule 4).** Buy-and-hold and a matched-frequency
  random signal, same period, same costs, dispersion reported.
- **False-discovery correction (Rule 15).** Every strategy, feature set,
  threshold, horizon, and seed ever tried is recorded in a hash-chained ledger,
  and a Sharpe is not a result until it clears a deflated-Sharpe gate against
  that lifetime trial count.
- **No unsourced figures (Rule 11).** Every number rendered to a human carries
  its source artifact, run id, and date. Placeholder values are forbidden.
- **No green signal without proof it can go red (Rule 12).** Every gate ships
  with a planted, plausible defect that the gate is observed catching, plus a
  clean control.

## Setup

Python >= 3.12 is required by the current pins (NumPy requires >= 3.12; pandas and contourpy require >= 3.11); CI uses Python 3.12.

```bash
python -m venv venv
venv/Scripts/activate            # Windows;  source venv/bin/activate elsewhere
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## Running

Entry points are standalone and run from the project root:

```bash
python scripts/data_pipeline_sanity_check.py   # fetch, inspect, and plot one price series
python scripts/return_stats.py                 # volatility, skew, kurtosis, drawdown, Sharpe
python scripts/ma_crossover_backtest.py        # rule-based SMA crossover baseline
python scripts/logistic_baseline.py            # walk-forward logistic baseline
python scripts/multi_ticker_comparison.py      # the five-ticker panel comparison
```

## Tests

```bash
python -m pytest tests
```

Pytest is the single runner. The suite is offline by design — a test that
requires a download is not a test. Collection guards reject misplaced test files
and modules that collect zero cases, so a silently skipped suite fails loudly.

## Data and caching

The data layer fetches **unadjusted** OHLCV and keeps corporate actions as a
separate table, because a funded ledger must trade the dollar prices that
actually existed. Retrospectively adjusted prices are legal for research
features and are tagged `price_basis = "research_adjusted"`; the backtester
refuses to run on them.

Everything under `data/cache/` is regenerable output and is gitignored. Market
data is never committed.

### The timestamp convention

`Date` is a **timezone-naive, midnight-normalized** label denoting a trading
*session*, not an instant. A daily bar has no single moment to attach a zone to,
and every choice of one shifts the bar across a date boundary for some reader:
the same bar written as midnight Eastern and read as UTC lands on the previous
calendar day. Instants are always timezone-aware; a session label crossing into
instant-space is localized to `America/New_York` explicitly, by the code doing
the crossing. [`CLAUDE.md`](CLAUDE.md) is the statement of record.

### Calendar gaps are reported, never filled

`find_missing_bars` reports NYSE sessions with no bar, per ticker. It returns the
frame unmodified — a backward fill or interpolation would write a value into a
row that was not knowable at that row's timestamp, which Rule 1 forbids by name.
The NYSE calendar is computed from the exchange's own rules rather than taken
from pandas' `USFederalHolidayCalendar`, which describes the federal government
instead: it omits Good Friday and includes Columbus and Veterans Day, on which
the market is open.

## Repository layout

```
docs/SCOPE-V1.md            Scope, hard constraints, definition of done
docs/PROJECT_CONTEXT.md     Detailed current state and history
.specify/memory/            The constitution — non-negotiable rules
.specify/specs/             Numbered specs; the unit of work
scripts/                    Modules and runnable entry points
tests/                      Regression, mutation, and gate tests
reports/                    Report API and terminal UI
data/cache/                 Generated output (gitignored)
```

## Roadmap

**v1.0** — the complete research framework, publicly tagged: runnable
end-to-end on unadjusted free data, green from a clean clone, deflated-Sharpe
and PBO gates operational, safety layer complete.

**v1.1** — paper trading: a broker paper adapter under review-only control, the
safety gate in the live order path, a scheduled daily signal report, position
reconciliation, and model-decay monitoring. This starts the capital gate's
one-to-two-month paper clock.

**Beyond** — real capital only after every step of the capital gate in
[`docs/SCOPE-V1.md`](docs/SCOPE-V1.md) passes, starting from an amount sized by
the risk layer and explicitly capped. Deferred research directions, and the
condition that would justify each, are listed there too.

## Disclaimer

This is a quantitative research framework, not investment advice. It makes no
representation that any strategy in it is profitable. It is provided without
warranty. It is built on free data sources with documented limitations, listed
in [docs/SCOPE-V1.md](docs/SCOPE-V1.md). It is licensed under the MIT License;
see [LICENSE](LICENSE).
