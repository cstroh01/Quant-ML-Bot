# Quickstart — 017 Position Sizing and Portfolio Risk Layer

How to prove this spec works. Commands are PowerShell from the repo root,
using the repo's own virtualenv.

---

## 1. The test suite (no network)

```powershell
./venv/Scripts/python.exe -m unittest discover -s tests
```

Expected: all tests pass. The spec's own tests alone:

```powershell
./venv/Scripts/python.exe -m unittest discover -s tests -p "test_portfolio_risk.py" -v
```

What to look for, by story:

| Story | Test classes |
|---|---|
| US1 sizing | `VolatilityTargetSizingTests`, `RealizedVolatilityTests`, `NoKellyPathTests` |
| US2 correlation | `CorrelationAdjustmentTests`, `ExAnteVolatilityTests`, `CapOrderingTests`, `FiveTickerUniverseTests` |
| US3 loss caps | `LossCapGuardTests`, `LossCapHistoryTests`, `EntryHaltTests`, `AutomaticHaltIntegrationTests` |
| Rules 1, 5, 8 | `PointInTime*`, `SessionIndexValidationTests`, `ModuleBoundaryTests` |

---

## 2. One decision, by hand

A sketch of the call shape on the real ten-year cache (no download if
`data/cache/AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv` exists):

```python
import sys; sys.path.insert(0, "scripts")
import pandas as pd
from data import download_market_data
from portfolio_risk import RECOMMENDED_CONFIG, target_weights

tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]
prices = download_market_data(tickers, period="10y")   # cache hit
closes = prices.pivot(index="Date", columns="Ticker", values="Close")

session = closes.index[-1]
decision = target_weights(
    closes,
    confidence=pd.Series(1.0, index=tickers),      # full conviction, all five
    current_weights=pd.Series(0.0, index=tickers), # starting flat
    session=session,
    config=RECOMMENDED_CONFIG,
    entries_halted=False,
)
print(decision.round(4))
```

Read the frame left to right: `Standalone` is story 1, `Overlap` and
`Adjusted` are story 2, `Target` is after the book cap and any halt.
Expected shape: `Overlap` well above 1 for every name (these five are
positively correlated), and `Target` summing to much less than
`5 × max_weight`.

---

## 3. A halt, by hand

```python
import pandas as pd
from portfolio_risk import loss_cap_history

sessions = pd.to_datetime(["2026-09-04", "2026-09-08", "2026-09-09",
                           "2026-09-10", "2026-09-11"])   # Mon 09-07 is Labor Day
equity = pd.Series([100.0, 99.0, 95.5, 99.5, 100.5], index=sessions)
print(loss_cap_history(equity, daily_loss_limit=0.02,
                       weekly_loss_limit=0.04, weekly_drawdown_limit=0.05))
```

Expected: 09-09 breaches the weekly loss cap (`95.5/100 − 1 = −4.5%`) and the
daily cap (`95.5/99 − 1 = −3.5%`). 09-10 and 09-11 recover but stay
`entries_halted = True` — the weekly halt is latched for the rest of that
week.

---

## 4. Mutation check

The mutation runner lives outside the repo (scratchpad), because it writes
mutant copies of the module. Its results are recorded in `tasks.md` (T030)
and `NIGHT_RUN_SUMMARY.md`. It never edits `scripts/portfolio_risk.py`: each
mutant is a separate copy placed ahead of `scripts/` on `sys.path` in a fresh
interpreter.

---

## 5. What this quickstart does not show

No return, Sharpe, or P&L. Nothing here runs through a costed backtest, so
Rules 3 and 4 have nothing to attach to. That is the next spec's job.
