# Quant-ML-Bot

A from-scratch quantitative trading research project. The current state is
**Phase 0**: a deliberately simple, verifiable baseline — real market data, a
rule-based signal, and honest trade accounting — built before any machine
learning is introduced.

> **Not investment advice.** Nothing here is a production trading system. The
> backtest models no fees, no slippage, no borrowing costs, and a single share.
> A backtest simulates; it does not prove.

## Why it is built this way

A model layered on broken plumbing disguises bugs as bad predictions. So the
three layers that a trading system actually needs are kept separate from the
start, and each one is provably correct on its own before anything smarter
plugs into it:

| Layer | Module | Responsibility |
|---|---|---|
| Data | [scripts/data.py](scripts/data.py) | Download and cache split/dividend-adjusted OHLCV prices |
| Signal | [scripts/signals.py](scripts/signals.py) | Decide *when* to trade — and nothing else |
| Execution & accounting | [scripts/backtest_harness.py](scripts/backtest_harness.py) | Turn signals into fills, trades, and P&L |
| Charting | [scripts/plotting.py](scripts/plotting.py) | Headless figure setup and saving |

Because the harness knows nothing about *how* a signal was produced, an ML
model can later replace `signals.py` without any change to execution or
accounting.

### The lookahead rule

A crossover is only knowable at the close that caused it, so it cannot be
filled at that same close. Every signal is shifted forward one bar and traded
at the **next day's open**. This is the project's single most important
correctness property, and it is pinned by a regression test rather than left
to review — see `test_trade_signal_never_fires_on_the_bar_that_created_it` in
[tests/test_signals.py](tests/test_signals.py).

## Setup

```bash
python -m venv venv
venv/Scripts/activate        # Windows;  source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
```

## Running

Each script is a standalone entry point. Run them from the project root:

```bash
python scripts/data_pipeline_sanity_check.py   # download, inspect, plot one price series
python scripts/return_stats.py                 # volatility, skew, kurtosis, drawdown, Sharpe
python scripts/ma_crossover_backtest.py        # SMA crossover baseline backtest
```

| Script | What it produces |
|---|---|
| [data_pipeline_sanity_check.py](scripts/data_pipeline_sanity_check.py) | Shape, dtypes, missing-value counts, and a closing-price chart |
| [return_stats.py](scripts/return_stats.py) | Return summary table, annualized return and Sharpe, distribution plots vs. a normal reference |
| [ma_crossover_backtest.py](scripts/ma_crossover_backtest.py) | Trade log CSV, summary statistics, and an annotated price chart |

## Tests

No test dependencies and no network access required:

```bash
python -m unittest discover -s tests
```

## Data and caching

The first run downloads from Yahoo Finance via `yfinance` and writes a CSV to
`data/cache/`; later runs read that cache. Pass `force_refresh=True` to
`download_market_data` to re-download. Cache writes are atomic, so an
interrupted run leaves the previous good file intact.

Everything under `data/cache/` — CSVs, charts, trade logs — is generated
output and is gitignored. Deleting the directory costs nothing but a re-run.

## Repository layout

```
docs/PROJECT_CONTEXT.md   Roadmap, standing principles, and current state
scripts/                  Reusable modules and runnable entry points
tests/                    Regression tests for the signal and accounting layers
data/cache/               Generated output (gitignored)
```

## Roadmap

Backtest → paper trading → small live capital. Phases are sequenced by
dependency, and none is skipped because a backtest looked good.
[docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) tracks the detailed state.
