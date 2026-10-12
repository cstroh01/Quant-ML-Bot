"""Reusable execution, accounting, and reporting helpers."""

import numpy as np
import pandas as pd

from cost_model import MODEL, PERMITTED_VOLUME_BASES, CostConfig, CostUnavailable, estimate_fill_cost
from metrics import validate_costs

# The trade log's shape is fixed here so an empty result still has the same
# columns as a populated one. Downstream code can then treat "no trades" as a
# normal outcome instead of a special case.
TRADE_LOG_COLUMNS = ["Entry Date", "Entry Price", "Exit Date", "Exit Price", "P&L"]

REQUIRED_PRICE_COLUMNS = ("Date", "Open", "Close", "Buy_Next_Open", "Sell_Next_Open")

# Spec 046 D-3: flat bps survives only as a labelled unit-test/diagnostic mode, never as a fallback.
FLAT_LABEL = "not reportable (Rule 13)"
# Per-fill Rule 13 evidence columns (FR-005); empty on non-fill events and flat fills.
NO_DETAIL = dict(Half_Spread=np.nan, Impact=np.nan, Cost_As_Of=pd.NaT, Cost_Quantity=np.nan, Cost_ADV=np.nan,
                 Cost_Sigma=np.nan, Cost_Window_Start=pd.NaT, Cost_Volume_Basis=None, Cost_Spread_Handling=None)


def run_backtest(
    prices: pd.DataFrame,
    *,
    commission_per_trade: float = 0.0,
    slippage_bps: float = 0.0,
    starting_capital: float | None = None,
    shares: int = 1,
    liquidate: bool = False,
    cost_config: CostConfig | None = None,
) -> pd.DataFrame:
    """Fund already-shifted orders; return closed trades with an event ledger.

    With `cost_config`, every fill pays the spec 046 Rule 13 fraction for its own quantity
    (shares bought, or shares held at exit), estimated from bars through the session before
    the fill; terminal liquidation uses the preceding-session estimate. An order with no valid
    estimate is a `cost_refused` event, never a flat or zero-cost fill. Without it, flat
    `slippage_bps` runs as the labelled diagnostic `FLAT_LABEL`.

    Long-only, immediate fills, no borrowing or pending orders. Buying power
    equals cash. An unaffordable entry is recorded as rejected, never resized.
    Starting capital must be chosen explicitly before the first open.
    Open positions are marked unless terminal liquidation is requested.
    Dates identify sessions; Phase identifies initial/open/close events.
    """
    missing = [c for c in REQUIRED_PRICE_COLUMNS if c not in prices]
    if missing or prices.empty:
        raise ValueError(f"nonempty prices required; missing columns: {missing}")
    validate_costs(commission_per_trade, slippage_bps)
    if cost_config is not None:
        if not isinstance(cost_config, CostConfig) or slippage_bps != 0:
            raise ValueError("one cost model per run: a CostConfig with slippage_bps=0, or flat bps alone")
        if missing := [c for c in ("High", "Low", "Volume") if c not in prices]:
            raise ValueError(f"Rule 13 costs need full OHLCV; missing columns: {missing}")
        if prices.attrs.get("volume_basis") not in PERMITTED_VOLUME_BASES:
            raise ValueError(f"volume_basis {prices.attrs.get('volume_basis')!r} is not verified for Rule 13 costs")
    if prices.attrs.get("price_basis") != "unadjusted_dollars":
        raise ValueError("funded ledger requires declared unadjusted dollar prices")
    prices = prices.copy()
    for column, default in (("Split", 1.), ("Dividend", 0.), ("Dividend_Pay_Date", pd.NaT)):
        if column not in prices:
            prices[column] = default
    actions = prices[["Split", "Dividend"]].to_numpy(dtype=float)
    pay_dates = pd.to_datetime(prices.Dividend_Pay_Date)
    if (not np.isfinite(actions).all() or (prices.Split <= 0).any()
            or (prices.Dividend < 0).any() or pay_dates.dt.tz is not None
            or (prices.Dividend.gt(0) & (pay_dates.isna() | (pay_dates < prices.Date))).any()):
        raise ValueError("invalid split/dividend or missing payment session")
    prices["Dividend_Pay_Date"] = pay_dates
    # Spec 041 FR-003: record where each pay date came from, as handed in. A
    # frame that does not say is "unspecified", never inferred as "sourced".
    basis = prices.get("Dividend_Pay_Date_Basis")
    prices["Dividend_Pay_Date_Basis"] = ("unspecified" if basis is None else
                                         basis.astype(object).where(basis.notna(), "unspecified"))
    dates = pd.to_datetime(prices["Date"])
    if (dates.isna().any() or dates.duplicated().any()
            or not dates.is_monotonic_increasing or dates.dt.tz is not None
            or not dates.equals(dates.dt.normalize())):
        raise ValueError("Date must contain unique ordered naive session labels")
    if "Ticker" in prices and prices.Ticker.nunique() != 1:
        raise ValueError("one instrument per account simulation required")
    values = prices[["Open", "Close"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("prices must be finite and positive")
    for c in ("Buy_Next_Open", "Sell_Next_Open"):
        if not prices[c].map(lambda v: isinstance(v, (bool, np.bool_))).all():
            raise ValueError("signals must be exact booleans")
    if (prices.Buy_Next_Open & prices.Sell_Next_Open).any():
        raise ValueError("conflicting buy and sell signals")
    if (isinstance(shares, (bool, np.bool_)) or not isinstance(shares, (int, np.integer))
            or shares < 1):
        raise ValueError("shares must be a positive integer")
    if starting_capital is None:
        raise ValueError("starting_capital is required before the first open")
    cash = float(starting_capital)
    if not np.isfinite(cash) or cash <= 0:
        raise ValueError("starting_capital must be finite and positive")
    capital = cash
    quantity = 0.0
    entry = None
    receivable = 0.
    payments = []
    trades, events = [], []
    rate = slippage_bps / 10000.
    if cost_config is not None:
        history = prices.set_index(dates)[["Open", "High", "Low", "Close", "Volume"]]
        split_sessions = list(dates[prices.Split.to_numpy() != 1])

    def cost(i, units):
        """(fraction, breakdown) for a fill after session i - 1; CostUnavailable when none exists."""
        if cost_config is None:
            return rate, None
        if i < 1:
            raise CostUnavailable("warmup", "no session before the first fill")
        if i < len(prices) and prices.Split.iloc[i] != 1:  # applied at this open: Q is post-split, the window is not
            raise CostUnavailable("split_in_window", "split on the fill session")
        past = history.iloc[:i]
        past.attrs["volume_basis"] = prices.attrs["volume_basis"]
        est = estimate_fill_cost(past, as_of=dates.iloc[i - 1], quantity=float(units),
                                 config=cost_config, split_sessions=split_sessions)
        return est.total, dict(Half_Spread=est.half_spread, Impact=est.impact, Cost_As_Of=est.as_of,
                               Cost_Quantity=est.quantity, Cost_ADV=est.adv, Cost_Sigma=est.sigma,
                               Cost_Window_Start=est.window_start, Cost_Volume_Basis=est.volume_basis,
                               Cost_Spread_Handling=est.spread_handling)

    def record(date, phase, event, price, fee=0., action=0., basis=None, slippage=0.,
               fraction=0., detail=None, status=None):
        if not np.isfinite(cash + quantity * price + receivable):
            raise ValueError("nonfinite account equity")
        events.append(dict(Event_ID=len(events), Date=date, Phase=phase,
                           Event=event, Price=price, Fee=fee, Slippage=slippage, Cash=cash,
                           Buying_Power=cash, Reserved_Cash=0., Quantity=quantity,
                           Receivable=receivable, Action=action,
                           Equity=cash + quantity * price + receivable,
                           Pay_Date_Basis=basis, Cost_Fraction=fraction, Cost_Status=status,
                           **(detail or NO_DETAIL)))

    def sell(i, date, phase, quote, event):
        nonlocal cash, quantity, entry
        try:
            fraction, detail = cost(i, quantity)
        except CostUnavailable as refusal:
            record(date, phase, "cost_refused", quote, status=refusal.reason)
            return
        fill = quote * (1 - fraction)
        exit_slippage = quantity * (quote - fill)
        proceeds = quantity * fill - commission_per_trade
        if cash + proceeds < 0:
            raise ValueError("exit fee would require unauthorized borrowing")
        cash += proceeds
        trades.append({"Entry Date": entry[0], "Entry Price": entry[1],
                       "Exit Date": date, "Exit Price": fill,
                       "P&L": proceeds - entry[2] + entry[3], "Quantity": quantity,
                       "Entry Quantity": entry[4], "Entry Cost": entry[2],
                       "Dividend Income": entry[3]})
        quantity = 0.0
        entry = None
        record(date, phase, event, quote, commission_per_trade, slippage=exit_slippage,
               fraction=fraction, detail=detail)

    record(dates.iloc[0], "initial", "initial", values[0, 0])
    for i, row in enumerate(prices.itertuples(index=False)):
        due = sum(amount for date, amount in payments if date <= row.Date)
        if due:
            cash += due
            receivable -= due
            payments = [(date, amount) for date, amount in payments if date > row.Date]
            record(row.Date, "open", "payment", row.Open, action=due)
        if quantity and row.Split != 1:
            quantity *= row.Split
            record(row.Date, "open", "split", row.Open, action=row.Split)
        if quantity and row.Dividend:
            income = quantity * row.Dividend
            entry = (*entry[:3], entry[3] + income, entry[4])
            receivable += income
            payments.append((row.Dividend_Pay_Date, income))
            record(row.Date, "open", "dividend", row.Open, action=income,
                   basis=row.Dividend_Pay_Date_Basis)
            if row.Dividend_Pay_Date == row.Date:
                cash += income
                receivable -= income
                payments.pop()
                record(row.Date, "open", "payment", row.Open, action=income)
        if quantity and row.Sell_Next_Open:
            sell(i, row.Date, "open", row.Open, "sell")
        if not quantity and row.Buy_Next_Open:
            try:
                fraction, detail = cost(i, shares)
            except CostUnavailable as refusal:
                fraction = None
                record(row.Date, "open", "cost_refused", row.Open, status=refusal.reason)
            fill = row.Open * (1 + (fraction or 0.))
            required = shares * fill + commission_per_trade
            if not np.isfinite(required):
                raise ValueError("nonfinite order notional")
            if fraction is None:
                pass
            elif required > cash:
                record(row.Date, "open", "rejected", row.Open)
            else:
                cash -= required
                quantity = float(shares)
                entry = (row.Date, fill, required, 0., shares)
                record(row.Date, "open", "buy", row.Open, commission_per_trade,
                       slippage=shares * (fill - row.Open), fraction=fraction, detail=detail)
        record(row.Date, "close", "mark", row.Close)
    if quantity and liquidate:
        sell(len(prices) - 1, row.Date, "close", row.Close, "liquidation")
    liquidation_refused = bool(quantity and liquidate)
    log = pd.DataFrame(trades, columns=TRADE_LOG_COLUMNS + ["Quantity", "Entry Quantity", "Entry Cost", "Dividend Income"])
    log["Trade_ID"] = np.arange(len(log))
    log["P&L"] = log["P&L"].astype(float)
    log["Cumulative P&L"] = log["P&L"].cumsum()
    ledger = pd.DataFrame(events)
    fills = ledger.loc[ledger.Event.isin(["buy", "sell", "liquidation"])]
    log.attrs.update(ledger=ledger, capital_base=capital,
                     commission_total=float(fills["Fee"].sum()),
                     slippage_total=float(fills["Slippage"].sum()),
                     commission_per_trade=float(commission_per_trade),
                     slippage_bps=float(slippage_bps), liquidate=liquidate,
                     liquidation_refused=liquidation_refused,
                     cost_model=MODEL if cost_config is not None else "flat_bps",
                     cost_label=MODEL if cost_config is not None else FLAT_LABEL,
                     cost_config=cost_config.as_mapping() if cost_config is not None else None)
    return log


def summarize_trades(
    trade_log: pd.DataFrame,
    *,
    commission_per_trade: float = 0.0,
    slippage_bps: float = 0.0,
) -> dict[str, float | int]:
    """Return the summary values used by the backtest report.

    The cost parameters are echoed back exactly as given, not recovered from
    the trade log — a net P&L column cannot be decomposed back into the
    commission and slippage that produced it. Carrying them through means a
    printed or saved summary can never state a number without the cost
    assumptions behind it, which is what Rule 3 requires of a results artifact.
    """
    validate_costs(commission_per_trade, slippage_bps)
    if not np.isfinite(trade_log["P&L"].to_numpy(dtype=float)).all():
        raise ValueError("trade P&L must be finite")
    total_trades = len(trade_log)
    # Summing an empty column already yields 0.0, so no empty-case branch is
    # needed here. A trade that breaks exactly even counts as a loss, which is
    # the conservative reading of a win rate.
    total_pnl = float(trade_log["P&L"].sum())
    wins = int((trade_log["P&L"] > 0).sum())
    win_rate = (wins / total_trades * 100) if total_trades else 0.0
    return {
        "total_trades": total_trades,
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "commission_per_trade": float(commission_per_trade),
        "slippage_bps": float(slippage_bps),
    }
