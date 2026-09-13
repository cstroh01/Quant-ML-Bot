"""Risk and performance reporting derived from a completed trade log.

This is a reporting layer that sits *below* execution, not beside it: it
reads what the backtest harness produced — a trade log — together with the
price frame that produced it, and re-expresses the pair as a per-bar equity
series. It imports neither `signals` nor `backtest_harness`, and it knows
nothing about how a signal was made or how a fill was decided (Rule 8).

Initial capital is phase initial, before the first fill. Close-series metrics
carry it in attrs; peak position -1 denotes that pre-trade anchor without
inventing a calendar session. Unfunded legacy logs are rejected.
"""

import numpy as np
import pandas as pd

from constants import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR

EQUITY_CURVE_COLUMNS = ["Date", "Position", "Bar P&L", "Equity"]

# Attribution must reconcile with the trade log to this tolerance. Tighter
# than any real cost effect, loose enough for float64 accumulation over a
# few thousand bars.
RECONCILIATION_TOLERANCE = 1e-9


def validate_costs(commission_per_trade: float, slippage_bps: float) -> None:
    """Validate the cash execution cost domain before any event."""
    if not np.isfinite(commission_per_trade) or commission_per_trade < 0:
        raise ValueError("commission_per_trade must be finite and >= 0")
    if not np.isfinite(slippage_bps) or not 0 <= slippage_bps < 10000:
        raise ValueError("slippage_bps must be finite and in [0, 10000)")


def _validate_prices(prices: pd.DataFrame) -> None:
    """Reject price frames that would silently produce a wrong curve.

    The date-to-position map below is built with `.loc`, and `.loc` against a
    duplicated label returns *every* match rather than raising. A long frame
    straight out of `download_market_data` is sorted by Ticker then Date and
    so has duplicate dates for a multi-ticker universe — slicing one ticker
    out and forgetting `reset_index(drop=True)` is the realistic way to get
    here, which is why this is a guard and not a comment.
    """
    missing = [name for name in ("Date", "Close") if name not in prices.columns]
    if missing:
        raise ValueError(f"prices is missing required columns: {missing}")
    if prices.empty:
        raise ValueError("prices must contain at least one bar.")
    dates = prices["Date"]
    if dates.duplicated().any():
        raise ValueError("prices['Date'] must be unique; found duplicate dates.")
    if not dates.is_monotonic_increasing:
        raise ValueError("prices['Date'] must be sorted ascending.")


def equity_curve(
    prices: pd.DataFrame,
    trade_log: pd.DataFrame,
    *,
    commission_per_trade: float,
    slippage_bps: float,
    starting_capital: float | None = None,
) -> pd.DataFrame:
    """Re-express a completed trade log as a per-bar equity series.

    Returns one row per price bar with `Date`, `Position` (shares held at
    that bar's *close*), `Bar P&L`, and `Equity`.

    `commission_per_trade` is required rather than inferred: the log's
    `Entry Price`/`Exit Price` are slipped fill prices and commission is
    subtracted from `P&L` separately, so a net P&L cannot be decomposed back
    into the costs that produced it. `slippage_bps` is not used in the
    arithmetic — the recorded fill prices already carry it — but is required
    and echoed so that no curve exists without the cost model that produced
    it on the record (Rule 3).

    Capital and costs must match the recorded funded run. Open positions
    contribute marked equity even when the closed-trade table is empty.
    Invalid event balances, transitions and chronology fail explicitly.
    """
    _validate_prices(prices)
    validate_costs(commission_per_trade, slippage_bps)
    ledger = trade_log.attrs.get("ledger")
    if ledger is None:
        raise ValueError("funded event ledger required; legacy P&L is not account equity")
    capital = trade_log.attrs["capital_base"]
    for key, value in (("commission_per_trade", commission_per_trade),
                       ("slippage_bps", slippage_bps)):
        if value != trade_log.attrs[key]:
            raise ValueError(f"{key} differs from the funded run")
    if starting_capital is not None and starting_capital != capital:
        raise ValueError("starting_capital differs from the funded run")
    numbers = ledger[["Cash", "Quantity", "Price", "Fee", "Equity", "Buying_Power", "Receivable"]]
    if not np.isfinite(numbers.to_numpy(dtype=float)).all():
        raise ValueError("nonfinite ledger event")
    if ((ledger.Cash < 0).any() or (ledger.Quantity < 0).any()
            or not np.array_equal(ledger.Event_ID, np.arange(len(ledger)))
            or not ledger.Date.is_monotonic_increasing):
        raise ValueError("invalid ledger balances, IDs or chronology")
    if not np.allclose(ledger.Equity, ledger.Cash + ledger.Quantity * ledger.Price + ledger.Receivable,
                       rtol=0, atol=RECONCILIATION_TOLERANCE):
        raise ValueError("cash plus positions does not reconcile")
    if not np.array_equal(ledger.Cash, ledger.Buying_Power):
        raise ValueError("buying power must equal cash")
    initial = ledger.iloc[0]
    if initial.Event != "initial" or initial.Equity != capital or initial.Quantity != 0:
        raise ValueError("invalid initial event")
    source = prices.set_index("Date")
    phase_rank = {"initial": -1, "open": 0, "close": 1}
    order = [(e.Date, phase_rank.get(e.Phase, -99)) for e in ledger.itertuples()]
    if order != sorted(order):
        raise ValueError("event phases out of order")
    cash, quantity, receivable = capital, 0., 0.
    entry_cost, income = 0., 0.
    expected_trades = []
    pending_payments, seen_actions = [], set()
    for event in ledger.iloc[1:].itertuples(index=False):
        phase = "close" if event.Event in ("mark", "liquidation") else "open"
        if (event.Phase != phase or event.Date not in source.index
                or event.Price != source.loc[event.Date, "Close" if phase == "close" else "Open"]):
            raise ValueError("event phase or quote differs from source")
        if event.Event not in ("buy", "sell", "liquidation", "split") and event.Quantity != quantity:
            raise ValueError("non-fill event changed share quantity")
        if event.Event in ("split", "dividend"):
            key = (event.Date, event.Event)
            if key in seen_actions:
                raise ValueError("duplicate corporate action")
            seen_actions.add(key)
        if event.Event == "buy":
            if quantity or event.Quantity <= 0:
                raise ValueError("overlapping or empty entry")
            entry_quantity = event.Quantity
            entry_date = event.Date
            entry_price = event.Price * (1 + slippage_bps / 10000)
            entry_cost = event.Quantity * entry_price + commission_per_trade
            income = 0.
            cash -= entry_cost
        elif event.Event in ("sell", "liquidation"):
            if quantity <= 0 or event.Quantity != 0:
                raise ValueError("invalid exit transition")
            exit_price = event.Price * (1 - slippage_bps / 10000)
            proceeds = quantity * exit_price - commission_per_trade
            cash += proceeds
            expected_trades.append((entry_date, entry_price, event.Date, exit_price,
                                    proceeds - entry_cost + income, quantity, entry_quantity, entry_cost, income))
        elif event.Event == "split":
            if (event.Action != source.loc[event.Date, "Split"]
                    or event.Action <= 0 or event.Quantity != quantity * event.Action):
                raise ValueError("invalid split quantity")
        elif event.Event == "dividend":
            if event.Action != quantity * source.loc[event.Date, "Dividend"]:
                raise ValueError("dividend amount differs from source")
            pending_payments.append((source.loc[event.Date, "Dividend_Pay_Date"], event.Action))
            income += event.Action
            receivable += event.Action
        elif event.Event == "payment":
            due = sum(amount for date, amount in pending_payments if date <= event.Date)
            if abs(due - event.Action) > RECONCILIATION_TOLERANCE:
                raise ValueError("payment differs from due entitlements")
            pending_payments = [(date, amount) for date, amount in pending_payments if date > event.Date]
            cash += event.Action
            receivable -= event.Action
        elif event.Event not in ("mark", "rejected") or event.Quantity != quantity:
            raise ValueError("invalid position transition")
        fee = commission_per_trade if event.Event in ("buy", "sell", "liquidation") else 0.
        if abs(cash - event.Cash) > RECONCILIATION_TOLERANCE or event.Fee != fee:
            raise ValueError("event cash or fee does not reconcile")
        if abs(receivable - event.Receivable) > RECONCILIATION_TOLERANCE or receivable < -RECONCILIATION_TOLERANCE:
            raise ValueError("dividend receivable does not reconcile")
        quantity = event.Quantity
    if not np.array_equal(trade_log.Trade_ID, np.arange(len(trade_log))):
        raise ValueError("invalid trade IDs")
    if len(expected_trades) != len(trade_log):
        raise ValueError("trade count differs from ledger exits")
    if not np.allclose(trade_log["Cumulative P&L"].to_numpy(dtype=float),
                       np.cumsum(trade_log["P&L"].to_numpy(dtype=float)), rtol=0,
                       atol=RECONCILIATION_TOLERANCE):
        raise ValueError("invalid cumulative trade P&L")
    for expected, (_, trade) in zip(expected_trades, trade_log.iterrows()):
        if (trade["Entry Date"] != expected[0] or trade["Exit Date"] != expected[2]
                or not np.allclose([trade[c] for c in ("Entry Price", "Exit Price", "P&L", "Quantity",
                                                      "Entry Quantity", "Entry Cost", "Dividend Income")],
                                   [expected[1], expected[3], *expected[4:]], rtol=0,
                                   atol=RECONCILIATION_TOLERANCE)):
            raise ValueError("trade record differs from funded events")
    marks = ledger[ledger.Event == "mark"]
    if not np.array_equal(marks.Date, prices.Date) or not np.array_equal(marks.Price, prices.Close):
        raise ValueError("ledger marks differ from source sessions/prices")
    closes = ledger[ledger.Phase == "close"].groupby("Date", sort=False).tail(1)
    equity = closes.Equity.to_numpy()
    curve = pd.DataFrame({"Date": closes.Date.to_numpy(),
                          "Position": closes.Quantity.to_numpy(),
                          "Bar P&L": np.diff(np.r_[capital, equity]), "Equity": equity})
    curve.attrs.update({k: trade_log.attrs[k] for k in
                        ("capital_base", "commission_per_trade", "slippage_bps", "liquidate")})
    return curve


def equity_log_returns(equity: pd.Series) -> pd.Series:
    """Bar-over-bar log returns of an equity series.

    Log returns, to match `return_stats.daily_log_returns` — the repository
    annualizes log returns everywhere, and mixing conventions would make two
    Sharpe ratios here incomparable.

    An equity series that touches zero or goes negative has no defined log
    return; those observations come back as NaN rather than -inf, and
    `sharpe_ratio` treats their presence as an undefined result.
    """
    values = equity.to_numpy(dtype=float)
    capital = equity.attrs.get("capital_base")
    if capital is not None:
        values = np.r_[capital, values]
    previous, current = values[:-1], values[1:]
    returns = np.full(current.shape, np.nan, dtype=float)
    defined = np.isfinite(previous) & np.isfinite(current) & (previous > 0) & (current > 0)
    returns[defined] = np.log(current[defined] / previous[defined])
    return pd.Series(returns, index=equity.index if capital is not None else equity.index[1:])


def sharpe_ratio(
    returns: pd.Series,
    *,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
    risk_free_rate_annual: float = RISK_FREE_RATE_ANNUAL,
) -> float:
    """Annualized Sharpe ratio of a per-bar return series.

    Uses the same arithmetic as `return_stats.annualize`: the mean scales
    with time and the standard deviation with its square root (pandas'
    default `ddof=1`), and the risk-free rate is subtracted from the
    annualized log return after converting the effective annual hurdle
    with log1p. This descriptive ratio is not evidence of skill. Cash earns
    zero in this model; the constant hurdle is a separate assumption.

    Returns `nan` — never `0.0` and never `inf` — when the ratio is
    undefined: fewer than two observations, zero variance (a flat curve, the
    expected outcome of a strategy that took no trades), or a NaN from an
    equity series that reached zero. `0.0` would read as a real, mediocre
    result; `inf` would read as an extraordinary one.
    """
    if not np.isfinite(risk_free_rate_annual) or risk_free_rate_annual <= -1:
        raise ValueError("annual effective risk-free rate must be finite and > -1")
    clean = returns.dropna()
    if len(clean) != len(returns) or len(clean) < 2:
        return float("nan")

    annualized_return = clean.mean() * periods_per_year
    annualized_volatility = clean.std() * np.sqrt(periods_per_year)
    if not np.isfinite(annualized_volatility) or annualized_volatility == 0:
        return float("nan")
    return float((annualized_return - np.log1p(risk_free_rate_annual)) / annualized_volatility)


def mean_log_return_se(returns: pd.Series, *, lags: int) -> float:
    """Bartlett/Newey-West standard error of the mean log return, per session.

    Fixed user-selected bandwidth; no independence claim or confidence badge.
    Calendar completeness and bandwidth sensitivity still need a run manifest.
    """
    values = returns.to_numpy(dtype=float)
    n = len(values)
    if isinstance(lags, bool) or not isinstance(lags, int) or lags < 0:
        raise ValueError("lags must be a nonnegative integer")
    if n < 2 or not np.isfinite(values).all() or lags >= n:
        return float("nan")
    centered = values - values.mean()
    variance = float(centered @ centered / n)
    for lag in range(1, lags + 1):
        covariance = float(centered[lag:] @ centered[:-lag] / n)
        variance += 2 * (1 - lag / (lags + 1)) * covariance
    return float(np.sqrt(max(0., variance) / n))


def max_drawdown(equity: pd.Series) -> tuple[float, int, int]:
    """Return `(max_drawdown, peak_position, trough_position)`.

    The drawdown is `equity / equity.cummax() - 1`, matching
    `return_stats.main`. The peak is the most recent high-water mark
    *strictly before* the trough, which is what makes the pair a real
    peak-to-trough decline rather than two unrelated bars.

    A curve that never declines returns `(0.0, 0, 0)`.
    """
    values = equity.to_numpy(dtype=float)
    if values.size == 0:
        return float("nan"), -1, -1

    anchored = "capital_base" in equity.attrs
    if anchored:
        values = np.r_[equity.attrs["capital_base"], values]
    if not np.isfinite(values).all() or values[0] <= 0:
        return float("nan"), -1, -1
    running_max = np.maximum.accumulate(values)
    drawdown = values / running_max - 1.0
    trough_pos = int(np.argmin(drawdown))
    worst = float(drawdown[trough_pos])

    if worst == 0.0:
        return 0.0, 0, 0

    at_peak = np.flatnonzero(values[:trough_pos] == running_max[:trough_pos])
    peak_pos = int(at_peak[-1]) if at_peak.size else 0
    return worst, peak_pos - int(anchored), trough_pos - int(anchored)


def performance_summary(
    prices: pd.DataFrame,
    trade_log: pd.DataFrame,
    *,
    commission_per_trade: float,
    slippage_bps: float,
    starting_capital: float | None = None,
) -> dict[str, float | int | str]:
    """Risk-adjusted summary of one backtest, as a flat printable dict.

    Every key is always present, including for an empty trade log — a
    strategy that took no trades is an expected outcome (a cost-aware entry
    rule may correctly decline every trade), and a formatter should not have
    to branch on it. Undefined ratios are `nan`; genuine zeros are `0.0`.

    The cost parameters and the capital base are echoed back so no figure
    here can be quoted without the assumptions that produced it (Rule 3).
    """
    curve = equity_curve(
        prices,
        trade_log,
        commission_per_trade=commission_per_trade,
        slippage_bps=slippage_bps,
        starting_capital=starting_capital,
    )
    returns = equity_log_returns(curve["Equity"])
    worst_drawdown, peak_pos, trough_pos = max_drawdown(curve["Equity"])
    capital_base = curve.attrs["capital_base"]
    total_pnl = float(curve["Bar P&L"].sum())

    return {
        "annualized_mean_log_return": float(returns.mean() * TRADING_DAYS_PER_YEAR)
            if np.isfinite(returns).all() else float("nan"),
        "cagr_252_sessions": float(np.expm1(returns.sum() * TRADING_DAYS_PER_YEAR / len(returns)))
            if np.isfinite(returns).all() else float("nan"),
        "mean_log_return_se_hac": mean_log_return_se(returns, lags=min(5, len(returns)-1)),
        "hac_lags": min(5, len(returns)-1),
        "cash_interest_rate_annual": 0.,
        "risk_free_rate_annual": RISK_FREE_RATE_ANNUAL,
        "interpretation": "research: log Sharpe and CAGR assume 252 complete sessions/year; fixed hurdle, zero cash interest",
        "liquidation": "terminal_close" if curve.attrs["liquidate"] else "mark_only",
        "total_trades": int(len(trade_log)),
        "total_pnl": total_pnl,
        "total_return": total_pnl / capital_base,
        "sharpe_ratio": sharpe_ratio(returns),
        "max_drawdown": worst_drawdown,
        "drawdown_peak_bar": peak_pos,
        "drawdown_trough_bar": trough_pos,
        "bars": int(len(curve)),
        "bars_in_market": int((curve["Position"] > 0).sum()),
        "capital_base": capital_base,
        "commission_per_trade": float(commission_per_trade),
        "slippage_bps": float(slippage_bps),
    }
