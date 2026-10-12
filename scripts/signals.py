"""Reusable trading signal generators."""

import zlib

import numpy as np
import pandas as pd


def sma_crossover_signal(
    prices: pd.DataFrame, short_window: int = 10, long_window: int = 30
) -> pd.DataFrame:
    """Add tradeable next-open SMA crossover signals to one ticker's prices."""
    if short_window >= long_window:
        raise ValueError(
            "short_window must be smaller than long_window; "
            f"got {short_window} and {long_window}."
        )

    # Work on a copy so the caller's frame is never modified as a side effect.
    # A function that both returns a frame and rewrites its argument is easy to
    # misuse once more than one signal is generated from the same prices.
    prices = prices.copy()

    prices["Short_SMA"] = prices["Close"].rolling(short_window).mean()
    prices["Long_SMA"] = prices["Close"].rolling(long_window).mean()

    # The comparison uses today's completed closing price and yesterday's
    # completed averages. It therefore identifies a crossover only after the
    # close that caused it is known. The first valid long average cannot exist
    # until long_window observations have accumulated.
    prices["Crosses_Above"] = (prices["Short_SMA"] > prices["Long_SMA"]) & (
        prices["Short_SMA"].shift(1) <= prices["Long_SMA"].shift(1)
    )
    prices["Crosses_Below"] = (prices["Short_SMA"] < prices["Long_SMA"]) & (
        prices["Short_SMA"].shift(1) >= prices["Long_SMA"].shift(1)
    )

    # A close-based signal cannot be filled at that same close without using
    # information that was only known at the end of the bar. Shifting the
    # signals by one row means we trade at the next day's Open instead.
    prices["Buy_Next_Open"] = prices["Crosses_Above"].shift(1, fill_value=False)
    prices["Sell_Next_Open"] = prices["Crosses_Below"].shift(1, fill_value=False)
    return prices


def buy_and_hold_signal(prices: pd.DataFrame) -> pd.DataFrame:
    """Add next-open signals for buying once at the start and never selling.

    The entry decision is taken on the first row and, like every other signal
    here, shifted forward one bar — so the fill lands on row 1's open rather
    than on a bar whose price the decision would have had to see. No exit
    signal is ever produced. The harness marks a still-open position at the
    final close; a closed round trip exists only when the accounting caller
    passes `liquidate=True` (spec 019 C5). Either way, end of data is an
    accounting decision, and emitting an explicit sell here would put that
    bookkeeping into the signal layer, where it does not belong.

    A frame with fewer than two rows has no bar to shift the entry onto, so it
    yields no signals rather than an error — "not enough history to trade yet"
    is a normal outcome, the same one the SMA warm-up period produces.
    """
    prices = prices.copy()

    decision = pd.Series(False, index=prices.index, dtype=bool)
    if not prices.empty:
        decision.iloc[0] = True

    prices["Buy_Next_Open"] = decision.shift(1, fill_value=False)
    prices["Sell_Next_Open"] = pd.Series(False, index=prices.index, dtype=bool)
    return prices


def random_signal(
    prices: pd.DataFrame,
    n_trades: int,
    avg_holding_days: int,
    seed: int,
) -> pd.DataFrame:
    """Add next-open signals for `n_trades` randomly timed round trips.

    Each round trip is held for exactly `avg_holding_days` bars, and the trips
    never overlap — a new entry is never signalled while an earlier position is
    still open. Timing is the only random thing here: the function reads the
    frame's length and nothing else, so it cannot see a price and therefore
    cannot leak one.

    `seed` is required, not optional. Every draw goes through
    `numpy.random.default_rng(seed)`, so the same arguments always produce the
    same trade log and no call disturbs global random state.

    Consecutive trips keep a one-row gap: trip i+1 enters at least one row
    after trip i exits, so no row ever carries both flags. The spec 019
    harness refuses such a row, and a same-open sell-then-buy would be two
    costed fills with no change in position, a cost artifact rather than a
    baseline trade.

    Raises `ValueError` if the frame is too short to hold `n_trades` gapped
    trips of that length, i.e. has fewer than
    `n_trades * (avg_holding_days + 1) + 1` rows; the message names that
    bound. Silently returning fewer trades than asked for would quietly break
    the trade-frequency match that makes this a baseline rather than a
    different strategy.
    """
    if n_trades < 0:
        raise ValueError(f"n_trades must be >= 0; got {n_trades}")
    if avg_holding_days < 1:
        raise ValueError(f"avg_holding_days must be >= 1; got {avg_holding_days}")

    prices = prices.copy()
    n_bars = len(prices)

    buys = np.zeros(n_bars, dtype=bool)
    sells = np.zeros(n_bars, dtype=bool)

    # A strategy that never traded gets a baseline that never trades. Returning
    # early here is what keeps the capacity arithmetic below out of the
    # n_trades == 0 case, where it would divide the frame up for no trips.
    if n_trades == 0:
        prices["Buy_Next_Open"] = buys
        prices["Sell_Next_Open"] = sells
        return prices

    # Entries start at row 1 for the same reason the shifted signals above do:
    # row 0 is the first bar anyone could have looked at, so nothing is filled
    # on it. An entry at row i exits at row i + avg_holding_days, which must
    # still be inside the frame.
    first_entry_row = 1
    last_entry_row = n_bars - 1 - avg_holding_days
    n_candidate_rows = last_entry_row - first_entry_row + 1

    # Non-overlap and the one-row gap are imposed by construction rather than
    # checked afterwards. Draw n_trades distinct offsets from a range
    # shortened by the room every trip needs, sort them, then push the i-th
    # one forward by i * holding. Distinct sorted offsets differ by at least
    # 1, so consecutive entries end up at least holding + 1 rows apart: the
    # earlier trip exits, and the next one enters on a later row.
    spread = avg_holding_days
    n_offsets = n_candidate_rows - (n_trades - 1) * spread
    if n_candidate_rows < 1 or n_offsets < n_trades:
        raise ValueError(
            f"{n_bars} bars cannot hold {n_trades} non-overlapping trades of "
            f"{avg_holding_days} bars each with a one-row gap between them; "
            f"at least {n_trades * (avg_holding_days + 1) + 1} bars are needed."
        )

    rng = np.random.default_rng(seed)
    offsets = np.sort(rng.choice(n_offsets, size=n_trades, replace=False))
    entries = first_entry_row + offsets + np.arange(n_trades) * spread
    exits = entries + avg_holding_days

    buys[entries] = True
    sells[exits] = True

    prices["Buy_Next_Open"] = buys
    prices["Sell_Next_Open"] = sells
    return prices


# Spec 058 T011: the preregistered hypotheses H1-H8 as hold selections over a wide close panel.
MONTH_SESSIONS = 21
VOL_SESSIONS = 60
SAFE_ASSET = "SHY"
SECTOR_ETFS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")


def _observed(closes: pd.DataFrame, rows: int) -> pd.DataFrame:
    """True where all `rows` sessions ending at t have a close, so nothing precedes listing."""
    return closes.notna().astype(float).rolling(rows, min_periods=rows).sum().eq(rows)


def _past_return(closes: pd.DataFrame, start_lag: int, end_lag: int = 0) -> pd.DataFrame:
    return closes.shift(end_lag) / closes.shift(start_lag) - 1.0


def _top_k(score: pd.DataFrame, eligible: pd.DataFrame, k: int, *, highest: bool) -> pd.DataFrame:
    """The k best eligible scores per row (ties to the earlier column); none while fewer than k qualify."""
    ranked = score.where(eligible).rank(axis=1, ascending=not highest, method="first")
    enough = eligible.sum(axis=1) >= k
    return ((ranked <= k) & eligible).mul(enough, axis=0).astype(bool)


def _momentum(closes: pd.DataFrame, months: int) -> pd.DataFrame:
    lag = MONTH_SESSIONS * months
    return _observed(closes, lag + 1) & (_past_return(closes, lag, MONTH_SESSIONS) > 0)


def _trend(closes: pd.DataFrame, sessions: int) -> pd.DataFrame:
    sma = closes.rolling(sessions, min_periods=sessions).mean()
    return _observed(closes, sessions) & (closes > sma)


def _cross_momentum(closes: pd.DataFrame, k: int) -> pd.DataFrame:
    lag = 12 * MONTH_SESSIONS
    return _top_k(_past_return(closes, lag, MONTH_SESSIONS), _observed(closes, lag + 1), k, highest=True)


def _risk_parity(closes: pd.DataFrame) -> pd.DataFrame:
    return _observed(closes, VOL_SESSIONS + 1)


def _dual_momentum(closes: pd.DataFrame, months: int) -> pd.DataFrame:
    if SAFE_ASSET not in closes.columns:
        raise ValueError(f"dual momentum needs {SAFE_ASSET} in the panel")
    lag = MONTH_SESSIONS * months
    eligible, total = _observed(closes, lag + 1), _past_return(closes, lag)
    risky = [ticker for ticker in closes.columns if ticker != SAFE_ASSET]
    winner = _top_k(total[risky], eligible[risky], 1, highest=True)
    beats = eligible[SAFE_ASSET] & (total[risky].where(winner).max(axis=1) > total[SAFE_ASSET])
    held = pd.DataFrame(False, index=closes.index, columns=closes.columns)
    held[risky] = winner.mul(beats, axis=0).astype(bool)
    held[SAFE_ASSET] = eligible[SAFE_ASSET] & ~beats
    return held


def _sector_pick(closes: pd.DataFrame, score_of, rows: int, k: int = 3) -> pd.DataFrame:
    missing = [ticker for ticker in SECTOR_ETFS if ticker not in closes.columns]
    if missing:
        raise ValueError(f"sector hypotheses need every sector ETF; missing {missing}")
    sectors = closes[list(SECTOR_ETFS)]
    picked = _top_k(score_of(sectors), _observed(sectors, rows), k, highest=False)
    return picked.reindex(columns=closes.columns, fill_value=False)


def _low_volatility(closes: pd.DataFrame) -> pd.DataFrame:
    realized = lambda s: np.log(s).diff().rolling(VOL_SESSIONS, min_periods=VOL_SESSIONS).std()  # noqa: E731
    return _sector_pick(closes, realized, VOL_SESSIONS + 1)


def _reversal(closes: pd.DataFrame) -> pd.DataFrame:
    return _sector_pick(closes, lambda s: _past_return(s, 5), 6)


HYPOTHESES = {
    "H1-3": lambda c: _momentum(c, 3), "H1-6": lambda c: _momentum(c, 6),
    "H1-12": lambda c: _momentum(c, 12), "H2-100": lambda c: _trend(c, 100),
    "H2-200": lambda c: _trend(c, 200), "H3-3": lambda c: _cross_momentum(c, 3),
    "H3-5": lambda c: _cross_momentum(c, 5), "H4": _risk_parity,
    "H5": lambda c: _risk_parity(c) & _momentum(c, 12),
    "H6-6": lambda c: _dual_momentum(c, 6), "H6-12": lambda c: _dual_momentum(c, 12),
    "H7": _low_volatility, "H8": _reversal,
}


def hypothesis_selection(config_id: str, closes: pd.DataFrame) -> pd.DataFrame:
    """Which tickers configuration `config_id` (spec 058 declaration) holds at each session's close.

    Guarantees: a boolean frame shaped like `closes`; the row for session t reads closes at or
    before t only, and is a decision to be filled at the open of t+1 by the portfolio layer. A
    ticker is never selected until every close its lookback needs exists (no backfill before
    listing, and a missing row inside the window deselects it). Ranked picks need k eligible
    tickers or select none; ties go to the earlier column. Weights and volatility targeting
    are sizing decisions and are not made here (Rule 8); `decision_sessions` says which rows
    rebalance.
    """
    if config_id not in HYPOTHESES:
        raise ValueError(f"unknown 058 configuration {config_id!r}; H9 and H10 combine these")
    index = closes.index
    if not isinstance(index, pd.DatetimeIndex) or index.tz is not None or index.has_duplicates \
            or not index.is_monotonic_increasing or closes.columns.has_duplicates:
        raise ValueError("closes needs naive, unique, ascending sessions and unique tickers")
    values = closes.to_numpy(float)
    if (values[~np.isnan(values)] <= 0).any() or np.isinf(values).any():
        raise ValueError("closes must be positive and finite where a row exists")
    return HYPOTHESES[config_id](closes.astype(float))


def decision_sessions(
    sessions: pd.DatetimeIndex, *, cadence: str, previous: pd.Timestamp | None = None
) -> np.ndarray:
    """Spec 058 §5 rebalance rows: True on the first session of each month or ISO week.

    `monthly` marks the first panel session of each calendar month (H1-H7, H9, H10, B-BH),
    `weekly` the first of each ISO week (H8). Row t is marked when its period differs from row
    t-1's, so it reads rows t-1 and t only. The first row is compared with `previous`, the
    session before it (a past date, so no lookahead); a fold or panel cut passes it so a true
    period opener is kept. Without `previous` the first row is never marked, since whether it
    opens its period is unknowable from the panel. Callers keep `book.loc[mask]`:
    `run_portfolio_backtest` trades only on rows its weights carry, so holdings drift between
    decisions instead of being re-targeted every session.
    """
    if not isinstance(sessions, pd.DatetimeIndex) or sessions.tz is not None \
            or sessions.has_duplicates or not sessions.is_monotonic_increasing:
        raise ValueError("sessions must be naive, unique and ascending")
    if previous is not None:
        previous = pd.Timestamp(previous)
        if previous.tz is not None or (len(sessions) and previous >= sessions[0]):
            raise ValueError("previous must be a naive session before the first row")
        sessions = pd.DatetimeIndex([previous]).append(sessions)
    if cadence == "monthly":
        period = np.asarray(sessions.year * 12 + sessions.month)
    elif cadence == "weekly":
        iso = sessions.isocalendar()
        period = iso["year"].to_numpy() * 100 + iso["week"].to_numpy()
    else:
        raise ValueError(f"cadence must be 'monthly' or 'weekly'; got {cadence!r}")
    opens = np.zeros(len(sessions), dtype=bool)
    opens[1:] = period[1:] != period[:-1]
    return opens[1:] if previous is not None else opens


# Spec 058 T013 B-RND: "seeded random long/flat per asset, monthly, same sizing and costs" (Rule 4).


def _validate_decision_panel(closes: pd.DataFrame, decision_mask) -> np.ndarray:
    index = closes.index
    if not isinstance(index, pd.DatetimeIndex) or index.tz is not None or index.has_duplicates \
            or not index.is_monotonic_increasing or closes.columns.has_duplicates:
        raise ValueError("closes needs naive, unique, ascending sessions and unique tickers")
    mask = np.asarray(decision_mask)
    if mask.dtype != bool or mask.shape != (len(index),):
        raise ValueError("decision_mask must be a boolean array with one entry per session")
    return mask


def _probability(name: str, value) -> float:
    if isinstance(value, bool) or not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]; got {value!r}")
    return float(value)


def random_selection(
    closes: pd.DataFrame, *, decision_mask, enter_probability: float, exit_probability: float,
    initial_probability: float, seed: int
) -> pd.DataFrame:
    """B-RND hold selection for one seed: a seeded long/flat chain per ticker on decision rows.

    Guarantees: a boolean frame shaped like `closes`. Each ticker's state changes only on
    decision rows: on the first it is long with `initial_probability`; afterwards a flat ticker
    enters with `enter_probability` and a long one exits with `exit_probability`, so the
    baseline matches a candidate's entries and exits (`matched_activity`), not only its
    exposure. Between decisions the state carries; a ticker with no close at t is never held,
    and nothing is held before the first decision row. Row t reads only the closes' presence at
    rows <= t and the seeded draws, never a price. Each ticker draws one uniform per decision row
    from its own stream, seeded by `seed` and the ticker name, so adding or reordering columns
    leaves its draws unchanged. Sizing and costs come from the candidates' portfolio layer.
    """
    mask = _validate_decision_panel(closes, decision_mask)
    enter_probability = _probability("enter_probability", enter_probability)
    exit_probability = _probability("exit_probability", exit_probability)
    initial_probability = _probability("initial_probability", initial_probability)
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise ValueError(f"seed must be an integer; got {seed!r}")
    present = closes.notna().to_numpy()
    held = np.zeros(present.shape, dtype=bool)
    for col, ticker in enumerate(closes.columns):
        draws = np.random.default_rng([int(seed), zlib.crc32(str(ticker).encode())]).random(int(mask.sum()))
        state, k = False, -1
        for row in range(len(mask)):
            if mask[row]:
                k += 1
                if k == 0:
                    state = draws[k] < initial_probability
                elif state:
                    state = draws[k] >= exit_probability
                else:
                    state = draws[k] < enter_probability
            held[row, col] = state and present[row, col]
    return pd.DataFrame(held, index=closes.index, columns=closes.columns)


def random_selections(closes: pd.DataFrame, *, decision_mask, seeds, **activity) -> dict[int, pd.DataFrame]:
    """`random_selection` for each of at least two distinct integer `seeds`, keyed by seed.

    `activity` is `matched_activity`'s result. Rule 4 reports the random baseline's dispersion
    across seeds, not one draw, so a single seed is refused.
    """
    seeds = list(seeds)
    if len(seeds) < 2 or len(set(seeds)) != len(seeds) or any(
            isinstance(s, bool) or not isinstance(s, (int, np.integer)) for s in seeds):
        raise ValueError("seeds must be at least two distinct integers")
    return {s: random_selection(closes, decision_mask=decision_mask, seed=s, **activity) for s in seeds}


def matched_activity(candidate: pd.DataFrame, closes: pd.DataFrame, *, decision_mask) -> dict[str, float]:
    """The candidate's decision-row activity, as B-RND's chain parameters (Rule 4 match).

    `initial_probability` is its exposure: names held / names with a close, over decision rows.
    Between consecutive decision rows where a name has a close at both, `exit_probability` is
    exits / names held before and `enter_probability` is entries / names flat before; with no
    such opportunity the rate is 0. Rows between decisions are not decisions and are ignored.
    The rates are calibration constants of the whole `candidate` passed in, so a caller fits
    them on the research window only. A candidate holding a name with no close is refused.
    """
    mask = _validate_decision_panel(closes, decision_mask)
    if not candidate.index.equals(closes.index) or not candidate.columns.equals(closes.columns) \
            or not (candidate.dtypes == bool).all():
        raise ValueError("candidate must be a boolean selection shaped like closes")
    held = candidate.to_numpy()[mask]
    eligible = closes.notna().to_numpy()[mask]
    if (held & ~eligible).any():
        raise ValueError("candidate holds a ticker with no close on a decision row")
    if eligible.sum() == 0:
        raise ValueError("no eligible ticker on any decision row")
    both = eligible[1:] & eligible[:-1]
    was_long, was_flat = both & held[:-1], both & ~held[:-1]
    rate = lambda moved, base: float(moved.sum() / base.sum()) if base.sum() else 0.0
    return {"enter_probability": rate(was_flat & held[1:], was_flat),
            "exit_probability": rate(was_long & ~held[1:], was_long),
            "initial_probability": float(held.sum() / eligible.sum())}
