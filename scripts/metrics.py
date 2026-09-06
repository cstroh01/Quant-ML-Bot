"""Risk and performance reporting derived from a completed trade log.

This is a reporting layer that sits *below* execution, not beside it: it
reads what the backtest harness produced — a trade log — together with the
price frame that produced it, and re-expresses the pair as a per-bar equity
series. It imports neither `signals` nor `backtest_harness`, and it knows
nothing about how a signal was made or how a fill was decided (Rule 8).

The arithmetic is pinned to the harness's own P&L expression. For a trade
entered at bar ``e`` and exited at bar ``x``, with the log's recorded (already
slipped) fill prices ``E`` and ``X`` and commission ``c`` per fill:

    bar e            :  Close[e]  - E          - c
    bars i in (e, x) :  Close[i]  - Close[i-1]
    bar x            :  X         - Close[x-1] - c
    bars not held    :  0

That telescopes to exactly ``X - E - 2c``, which is `run_backtest`'s `P&L`
term for term. `equity_curve` asserting that identity is what makes an
off-by-one in this module impossible to miss.
"""

import numpy as np
import pandas as pd

from constants import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR

EQUITY_CURVE_COLUMNS = ["Date", "Position", "Bar P&L", "Equity"]

# Attribution must reconcile with the trade log to this tolerance. Tighter
# than any real cost effect, loose enough for float64 accumulation over a
# few thousand bars.
RECONCILIATION_TOLERANCE = 1e-9


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
    if not prices.index.equals(pd.RangeIndex(len(prices))):
        raise ValueError(
            "prices must carry a 0-based RangeIndex; call reset_index(drop=True)."
        )

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

    `starting_capital` defaults to the first bar's `Close`. A one-share book
    has no capital base of its own, so every percentage figure downstream
    depends on a stated denominator; the value used is recorded in the
    returned frame's `attrs`.

    Raises:
        ValueError: for a malformed price frame (see `_validate_prices`), a
            trade date absent from `prices`, or a reconciliation failure
            against the trade log's own P&L.
    """
    _validate_prices(prices)
    if commission_per_trade < 0:
        raise ValueError(
            f"commission_per_trade must be >= 0; got {commission_per_trade}"
        )
    if slippage_bps < 0:
        raise ValueError(f"slippage_bps must be >= 0; got {slippage_bps}")

    closes = prices["Close"].to_numpy(dtype=float)
    n_bars = len(prices)
    bar_pnl = np.zeros(n_bars, dtype=float)
    position = np.zeros(n_bars, dtype=int)

    # Date -> position. Uniqueness was just validated, so this map is 1:1.
    position_of_date = pd.Series(np.arange(n_bars), index=prices["Date"])

    # `iterrows` rather than `itertuples`: the log's column names contain
    # spaces and an ampersand, which itertuples silently renames positionally.
    for _, trade in trade_log.iterrows():
        try:
            entry_pos = int(position_of_date.loc[trade["Entry Date"]])
            exit_pos = int(position_of_date.loc[trade["Exit Date"]])
        except KeyError as error:
            raise ValueError(
                f"trade date {error.args[0]!r} is not present in prices['Date']."
            ) from error

        entry_price = float(trade["Entry Price"])
        exit_price = float(trade["Exit Price"])

        if entry_pos == exit_pos:
            # Same-bar round trip. Reachable when Buy_Next_Open fires on the
            # final row: the harness enters there and its end-of-data block
            # exits on that same bar. The whole round trip lands on one bar.
            bar_pnl[entry_pos] += (
                exit_price - entry_price - 2 * commission_per_trade
            )
            continue

        # Entry bar: bought at the open, carried to this bar's close.
        bar_pnl[entry_pos] += closes[entry_pos] - entry_price - commission_per_trade
        # Held bars: plain close-to-close marks.
        for bar in range(entry_pos + 1, exit_pos):
            bar_pnl[bar] += closes[bar] - closes[bar - 1]
        # Exit bar: carried from the previous close to the exit fill.
        bar_pnl[exit_pos] += exit_price - closes[exit_pos - 1] - commission_per_trade

        # Shares held at the close: on from the entry bar up to, but not
        # including, the bar the position was closed on.
        position[entry_pos:exit_pos] = 1

    if not trade_log.empty:
        expected = float(trade_log["P&L"].sum())
        actual = float(bar_pnl.sum())
        if abs(actual - expected) > RECONCILIATION_TOLERANCE:
            raise ValueError(
                "per-bar attribution does not reconcile with the trade log: "
                f"bars sum to {actual!r}, trade log sums to {expected!r}."
            )

    capital_base = (
        float(closes[0]) if starting_capital is None else float(starting_capital)
    )

    curve = pd.DataFrame(
        {
            "Date": prices["Date"].to_numpy(),
            "Position": position,
            "Bar P&L": bar_pnl,
            # Anchored at the capital base *before* bar 0's P&L is added, so a
            # drawdown beginning on the first bar is visible rather than
            # silently ignored — the same point `return_stats`'
            # `cumulative_price_index` makes about anchoring at the first close.
            "Equity": capital_base + np.cumsum(bar_pnl),
        }
    )
    curve.attrs["capital_base"] = capital_base
    curve.attrs["commission_per_trade"] = float(commission_per_trade)
    curve.attrs["slippage_bps"] = float(slippage_bps)
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
    previous, current = values[:-1], values[1:]
    returns = np.full(current.shape, np.nan, dtype=float)
    defined = (previous > 0) & (current > 0)
    returns[defined] = np.log(current[defined] / previous[defined])
    return pd.Series(returns, index=equity.index[1:])


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
    annualized return so the ratio measures skill rather than having been
    invested.

    Returns `nan` — never `0.0` and never `inf` — when the ratio is
    undefined: fewer than two observations, zero variance (a flat curve, the
    expected outcome of a strategy that took no trades), or a NaN from an
    equity series that reached zero. `0.0` would read as a real, mediocre
    result; `inf` would read as an extraordinary one.
    """
    clean = returns.dropna()
    if len(clean) != len(returns) or len(clean) < 2:
        return float("nan")

    annualized_return = clean.mean() * periods_per_year
    annualized_volatility = clean.std() * np.sqrt(periods_per_year)
    if not np.isfinite(annualized_volatility) or annualized_volatility == 0:
        return float("nan")
    return float((annualized_return - risk_free_rate_annual) / annualized_volatility)


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

    running_max = np.maximum.accumulate(values)
    drawdown = values / running_max - 1.0
    trough_pos = int(np.argmin(drawdown))
    worst = float(drawdown[trough_pos])

    if worst == 0.0:
        return 0.0, 0, 0

    at_peak = np.flatnonzero(values[:trough_pos] == running_max[:trough_pos])
    peak_pos = int(at_peak[-1]) if at_peak.size else 0
    return worst, peak_pos, trough_pos


def performance_summary(
    prices: pd.DataFrame,
    trade_log: pd.DataFrame,
    *,
    commission_per_trade: float,
    slippage_bps: float,
    starting_capital: float | None = None,
) -> dict[str, float | int]:
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
