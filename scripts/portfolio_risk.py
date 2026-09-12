"""Size each position, share risk across correlated names, and halt on losses.

Every script in this repo trades one share of one ticker. Spec 012 named that
as the root cause of its own "declines nearly every trade" finding and left
the fix for later; this module is the decision half of that fix. At one
session close, for a book of several tickers, it answers three questions:

1. **How big?** Volatility targeting: `confidence x target_volatility /
   volatility`, capped per name, so a calm name and a volatile one carry
   comparable *risk* rather than comparable share counts. There is no Kelly
   path. Kelly sizes off an expected return this repo has not validated, and
   its size moves one-for-one with that estimate's error -- on spec 014's best
   AAPL classifier, half Kelly is 1.65x leverage (spec 017, Clarifications Q1).
2. **How much of that is the same bet?** Each active weight is divided by its
   *overlap*: the sum of its non-negative correlations with every active
   name, itself included. `k` perfectly correlated names become one bet split
   `k` ways; an uncorrelated name is untouched; a negative correlation earns
   no extra size.
3. **May the book add risk at all?** `LossCapGuard` reads equity at each close.
   A daily loss at its limit halts that close's decision; a weekly loss or
   drawdown at its limit halts every decision for the rest of that ISO week.
   A halted decision may shrink or exit a position, never open or grow one.

**The order is load-bearing:** standalone -> per-name cap -> overlap -> gross
cap -> halt. Capping after the overlap step would let three correlated names
each reach the cap, which quietly undoes step 2 (spec 017, research R4).

**Layer (Rule 8).** This sits between signal and execution. It consumes a
confidence from the signal layer and two numbers accounting produces --
equity at each close, and current holdings as weights -- and imports none of
those modules. It never prices a fill, books a trade, or computes P&L.

**Point in time (Rule 1).** Every value at session `t` is computed from data
at or before `t`. The functions that take a price panel truncate it at the
session before computing anything, so a leak would need code below that line
to reach back for the untruncated frame.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from constants import TRADING_DAYS_PER_YEAR

# A correlation estimate may overshoot |1| by float noise; beyond this it is a
# caller's bug, not rounding.
CORRELATION_TOLERANCE = 1e-9


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _is_real(value: object) -> bool:
    # bool is an int subclass; `max_gross=True` is a typo, not a 1.0.
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(
        value, (bool, np.bool_)
    )


def _require_positive_finite(name: str, value: object) -> float:
    if not _is_real(value):
        raise TypeError(f"{name} must be a real number; got {type(value).__name__}")
    number = float(value)
    if not np.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be positive and finite; got {value}")
    return number


def _require_window(name: str, value: object, *, minimum: int) -> int:
    if not isinstance(value, (int, np.integer)) or isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an int; got {type(value).__name__}")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}; got {value}")
    return int(value)


def _require_loss_limit(name: str, value: object) -> float:
    if not _is_real(value):
        raise TypeError(f"{name} must be a real number; got {type(value).__name__}")
    number = float(value)
    # Written as a positive range check so NaN fails it and raises too.
    if not 0.0 < number < 1.0:
        raise ValueError(f"{name} must be strictly between 0 and 1; got {value}")
    return number


def _require_bool(name: str, value: object) -> bool:
    if not isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a bool; got {type(value).__name__}")
    return bool(value)


def _validate_sessions(index: pd.Index, *, what: str) -> None:
    """Reject any index that is not naive, midnight, unique, and ascending.

    CLAUDE.md makes a daily bar's label a *session*, not an instant: naive and
    midnight-normalized. An aware label compared against a naive one is the
    silent one-bar shift Rule 5 exists to catch, so it raises here rather than
    being coerced into agreement.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError(f"{what} must be indexed by session labels (a DatetimeIndex).")
    if index.tz is not None:
        raise ValueError(f"{what} session labels must be timezone-naive; got tz={index.tz}.")
    if not (index == index.normalize()).all():
        raise ValueError(f"{what} session labels must be midnight-normalized.")
    if index.has_duplicates:
        raise ValueError(f"{what} session labels must be unique.")
    if not index.is_monotonic_increasing:
        raise ValueError(f"{what} session labels must be sorted ascending.")


def _session_label(session: object) -> pd.Timestamp:
    label = pd.Timestamp(session)
    if pd.isna(label):
        raise ValueError("session must be a session label, not NaT.")
    if label.tz is not None:
        raise ValueError(f"session must be timezone-naive; got tz={label.tz}.")
    if label != label.normalize():
        raise ValueError(f"session must be midnight-normalized; got {label}.")
    return label


def _validate_panel(closes: pd.DataFrame) -> None:
    if not isinstance(closes, pd.DataFrame):
        raise TypeError(f"closes must be a DataFrame; got {type(closes).__name__}")
    _validate_sessions(closes.index, what="closes")
    if closes.columns.has_duplicates:
        raise ValueError("closes must carry each ticker once.")


def _aligned(values: object, tickers: pd.Index, *, name: str) -> pd.Series:
    """`values` as a float series in `tickers` order, matched by label.

    By label, never by position: a confidence built in universe order and a
    panel pivoted into alphabetical order must still pair AAPL with AAPL. A
    different *set* of tickers raises, because a missing name read as NaN
    would size as flat and look like a decision.
    """
    series = pd.Series(values).astype("float64")
    if series.index.has_duplicates:
        raise ValueError(f"{name} must carry each ticker once.")
    if set(series.index) != set(tickers):
        raise ValueError(
            f"{name} must carry exactly the tickers {sorted(map(str, tickers))}; "
            f"got {sorted(map(str, series.index))}."
        )
    return series.reindex(tickers)


def _require_weights(values: np.ndarray, *, name: str) -> None:
    if np.any(~np.isfinite(values)) or np.any(values < 0):
        raise ValueError(f"{name} must be finite and non-negative for every ticker.")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RiskConfig:
    """Every parameter the risk layer decides with, validated once.

    No field has a default. `RECOMMENDED_CONFIG` holds the values spec 017
    records with their reasoning (Clarifications Q4, Q5); a caller passes it
    by name, so no number in a decision is one nobody chose.

    `max_gross <= 1` forbids leverage: this layer is built for a cash account
    heading to small live capital. `max_weight <= max_gross` because one name
    cannot be allowed more than the whole book. Out-of-domain values raise;
    nothing is clipped into range.
    """

    target_volatility: float
    max_weight: float
    max_gross: float
    volatility_window: int
    correlation_window: int
    daily_loss_limit: float
    weekly_loss_limit: float
    weekly_drawdown_limit: float

    def __post_init__(self) -> None:
        _require_positive_finite("target_volatility", self.target_volatility)
        max_gross = _require_positive_finite("max_gross", self.max_gross)
        if max_gross > 1.0:
            raise ValueError(f"max_gross must be <= 1.0 (no leverage); got {self.max_gross}")
        max_weight = _require_positive_finite("max_weight", self.max_weight)
        if max_weight > max_gross:
            raise ValueError(
                f"max_weight ({self.max_weight}) must not exceed max_gross ({self.max_gross})."
            )
        _require_window("volatility_window", self.volatility_window, minimum=2)
        _require_window("correlation_window", self.correlation_window, minimum=3)
        _require_loss_limit("daily_loss_limit", self.daily_loss_limit)
        _require_loss_limit("weekly_loss_limit", self.weekly_loss_limit)
        _require_loss_limit("weekly_drawdown_limit", self.weekly_drawdown_limit)


RECOMMENDED_CONFIG = RiskConfig(
    target_volatility=0.10,
    max_weight=0.25,
    max_gross=1.00,
    volatility_window=63,
    correlation_window=63,
    daily_loss_limit=0.02,
    weekly_loss_limit=0.04,
    weekly_drawdown_limit=0.05,
)


# ---------------------------------------------------------------------------
# Estimation
# ---------------------------------------------------------------------------


def log_returns(closes: pd.DataFrame) -> pd.DataFrame:
    """Daily log returns, `ln(C[t] / C[t-1])` by row position.

    Row 0 is missing. A row is missing wherever its own close or the previous
    row's close is missing, so a gap is never stitched into a multi-session
    return labelled as one session. Row `t` reads rows `t` and `t-1` only.

    Log returns, matching `return_stats.daily_log_returns` and
    `features.Rolling_Volatility`, so this module's volatility and theirs are
    the same quantity.

    Raises:
        ValueError: a non-positive or infinite close, or an invalid session
            index.
    """
    _validate_panel(closes)
    values = closes.to_numpy(dtype=float)
    present = values[~np.isnan(values)]
    if np.any(~np.isfinite(present)) or np.any(present <= 0):
        raise ValueError("closes must be strictly positive and finite where present.")
    returns = np.full(values.shape, np.nan)
    if len(values) > 1:
        returns[1:] = np.log(values[1:] / values[:-1])
    return pd.DataFrame(returns, index=closes.index, columns=closes.columns)


def realized_volatility(
    closes: pd.DataFrame,
    *,
    window: int,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> pd.DataFrame:
    """Annualized realized volatility at every session.

    Row `t` is the sample standard deviation (`ddof=1`) of the `window` log
    returns ending at `t`, times `sqrt(periods_per_year)`. It is missing unless
    all `window` of those returns exist: a window with a hole in it is a
    smaller sample pretending to be a full one. The window is trailing and
    counted in sessions, not calendar days.

    Guarantee (Rule 1): row `t` is bit-identical under any change to any row
    after `t`.
    """
    window = _require_window("window", window, minimum=2)
    periods = _require_window("periods_per_year", periods_per_year, minimum=1)
    returns = log_returns(closes)
    daily = returns.rolling(window, min_periods=window).std(ddof=1)
    return daily * np.sqrt(periods)


def trailing_correlation(
    closes: pd.DataFrame, session: pd.Timestamp, *, window: int
) -> pd.DataFrame:
    """Pairwise correlation of the `window` log returns ending at `session`.

    A pair is missing unless both names have all `window` returns in that
    span; too little history is missing, never guessed. The result is always
    tickers x tickers, in `closes`' column order.

    Guarantee (Rule 1): bit-identical under any change to `closes` after
    `session`, because the panel is truncated before anything is computed.

    Raises:
        ValueError: `session` is not a session in `closes`, or an invalid
            session index.
    """
    window = _require_window("window", window, minimum=3)
    _validate_panel(closes)
    label = _session_label(session)
    if label not in closes.index:
        raise ValueError(f"session {label.date()} is not in the price panel.")
    past = closes.loc[:label]
    # window + 1 closes give exactly `window` returns once row 0 is dropped.
    returns = log_returns(past.iloc[-(window + 1) :]).iloc[1:]
    correlation = returns.corr(min_periods=window)
    return correlation.reindex(index=closes.columns, columns=closes.columns)


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------


def volatility_target_weights(
    confidence: pd.Series,
    volatility: pd.Series,
    *,
    target_volatility: float,
) -> pd.Series:
    """Standalone weight: `confidence x target_volatility / volatility`, uncapped.

    Confidence is a conviction in [0, 1]; missing reads as 0, matching spec
    005 and 012's "no model yet" semantics. A name with missing, zero, or
    infinite volatility gets exactly 0: a zero volatility would divide into an
    infinite weight that the per-name cap would silently turn into a
    maximum-size position -- the worst direction this could fail in.

    Returned on `confidence`'s index; `volatility` is matched by label.

    Raises:
        ValueError: confidence outside [0, 1], negative volatility, a
            non-positive target, or ticker sets that differ.
    """
    target = _require_positive_finite("target_volatility", target_volatility)
    raw = pd.Series(confidence).astype("float64")
    if raw.index.has_duplicates:
        raise ValueError("confidence must carry each ticker once.")
    tickers = raw.index
    vol = _aligned(volatility, tickers, name="volatility").to_numpy(dtype=float)

    raw_values = raw.to_numpy(dtype=float)
    known = ~np.isnan(raw_values)
    if np.any((raw_values[known] < 0) | (raw_values[known] > 1)):
        raise ValueError("confidence must lie in [0, 1].")
    if np.any(vol[~np.isnan(vol)] < 0):
        raise ValueError("volatility must be non-negative.")

    conviction = np.where(known, raw_values, 0.0)
    sizeable = (conviction > 0) & np.isfinite(vol) & (vol > 0)
    standalone = np.zeros(len(tickers))
    standalone[sizeable] = conviction[sizeable] * target / vol[sizeable]
    return pd.Series(standalone, index=tickers, name="Standalone")


def _aligned_matrix(correlation: pd.DataFrame, tickers: pd.Index) -> np.ndarray:
    if not isinstance(correlation, pd.DataFrame):
        raise TypeError(f"correlation must be a DataFrame; got {type(correlation).__name__}")
    if correlation.index.has_duplicates or correlation.columns.has_duplicates:
        raise ValueError("correlation must carry each ticker once on each axis.")
    wanted = set(tickers)
    if set(correlation.index) != wanted or set(correlation.columns) != wanted:
        raise ValueError(
            f"correlation must be indexed by exactly the tickers {sorted(map(str, tickers))}."
        )
    return correlation.reindex(index=tickers, columns=tickers).to_numpy(dtype=float)


def position_overlap(weights: pd.Series, correlation: pd.DataFrame) -> pd.Series:
    """How many copies of the same bet each held position is, correlation-weighted.

    For a held name `i` (weight > 0): the sum over held names `j` of
    `max(rho_ij, 0)`, with `rho_ii` taken as exactly 1. So the overlap is at
    least 1, is `k` for `k` perfectly correlated names, and is 1 for a name
    uncorrelated with everything held. A name that is not held is `NaN` and
    counts toward no one else's overlap: a position that is not held cannot
    concentrate the book.

    Negative correlations count as zero. In a long-only book a negatively
    correlated name is a partial hedge; crediting it with *extra* size would
    turn this adjustment into a source of leverage.

    Raises:
        ValueError: a missing correlation between two held names (sizing on an
            unknown correlation is a guess in one direction or the other), a
            correlation outside [-1, 1], weights that are negative or not
            finite, or ticker sets that differ.
    """
    held = pd.Series(weights).astype("float64")
    if held.index.has_duplicates:
        raise ValueError("weights must carry each ticker once.")
    tickers = held.index
    values = held.to_numpy(dtype=float)
    _require_weights(values, name="weights")
    matrix = _aligned_matrix(correlation, tickers)
    active = values > 0

    among_active = matrix[np.ix_(active, active)]
    if np.any(np.isnan(among_active)):
        raise ValueError("correlation is undefined between two held positions.")
    if np.any(np.abs(among_active) > 1.0 + CORRELATION_TOLERANCE):
        raise ValueError("correlations must lie in [-1, 1].")

    clipped = np.clip(matrix, 0.0, 1.0)
    # Self-overlap is 1 by definition, not by estimate. A pandas correlation
    # diagonal can come back one ulp below 1, which would put an isolated
    # name's overlap below 1 and *grow* its weight.
    np.fill_diagonal(clipped, 1.0)
    counted = clipped[:, active]
    overlap = np.full(len(values), np.nan)
    overlap[active] = counted[active].sum(axis=1)
    return pd.Series(overlap, index=tickers, name="Overlap")


def correlation_adjusted_weights(
    weights: pd.Series, correlation: pd.DataFrame
) -> pd.Series:
    """Each held weight divided by its overlap; names not held stay 0.

    Guarantees: no weight increases, since the overlap is at least 1. A
    cluster of `k` perfectly correlated names keeps the combined weight of one
    average member. For `k` equal positions with equal volatility at a common
    correlation `rho >= 0`, the book's ex-ante volatility is one position's
    times `sqrt(k / (1 + (k-1) rho))` -- one bet's worth per effective
    independent bet (spec 017, research R3).
    """
    overlap = position_overlap(weights, correlation)
    values = pd.Series(weights).astype("float64").to_numpy(dtype=float)
    active = values > 0
    adjusted = np.zeros(len(values))
    adjusted[active] = values[active] / overlap.to_numpy(dtype=float)[active]
    return pd.Series(adjusted, index=overlap.index, name="Adjusted")


def apply_gross_cap(weights: pd.Series, *, max_gross: float) -> pd.Series:
    """Scale the whole book down, proportionally, to at most `max_gross`.

    At or below the cap the weights come back unchanged. Above it every weight
    is multiplied by the same factor, so the relative sizing the correlation
    step produced survives the book-level limit. The capped sum equals
    `max_gross` to float precision, not bit-exactly.
    """
    cap = _require_positive_finite("max_gross", max_gross)
    if cap > 1.0:
        raise ValueError(f"max_gross must be <= 1.0 (no leverage); got {max_gross}")
    book = pd.Series(weights).astype("float64")
    values = book.to_numpy(dtype=float)
    _require_weights(values, name="weights")
    gross = float(values.sum())
    scaled = values * (cap / gross) if gross > cap else values.copy()
    return pd.Series(scaled, index=book.index, name="Gross_Scaled")


def apply_entry_halt(
    target: pd.Series, current: pd.Series, *, halted: bool
) -> pd.Series:
    """Under a halt, no position may be opened or grown; any may shrink or close.

    Not halted: `target` unchanged. Halted: `min(target, current)` per ticker.

    `current` is the holding accounting reports at the deciding close -- the
    *drifted* weight, not the previous target -- because after a price drop,
    returning to the old target is buying (spec 017, Clarifications Q3).

    Exits stay allowed on purpose. A halt that froze the book would trap it in
    the positions that produced the loss, which adds risk instead of capping
    it.

    Raises:
        TypeError: `halted` is not a bool.
        ValueError: a missing or negative holding or target, or ticker sets
            that differ.
    """
    is_halted = _require_bool("halted", halted)
    wanted = pd.Series(target).astype("float64")
    if wanted.index.has_duplicates:
        raise ValueError("target must carry each ticker once.")
    target_values = wanted.to_numpy(dtype=float)
    _require_weights(target_values, name="target")
    current_values = _aligned(current, wanted.index, name="current_weights").to_numpy(
        dtype=float
    )
    _require_weights(current_values, name="current_weights")

    if not is_halted:
        return pd.Series(target_values, index=wanted.index, name="Target")
    clamped = np.minimum(target_values, current_values)
    return pd.Series(clamped, index=wanted.index, name="Target")


def target_weights(
    closes: pd.DataFrame,
    confidence: pd.Series,
    current_weights: pd.Series,
    *,
    session: pd.Timestamp,
    config: RiskConfig,
    entries_halted: bool,
) -> pd.DataFrame:
    """One session's target weights, with every step on the record.

    Steps, in the only order that is correct (spec 017 FR-006):

    1. volatility and correlation from price history truncated at `session`;
    2. standalone weight (`volatility_target_weights`);
    3. per-name cap -- **before** the overlap step, or three correlated names
       each reach the cap and the book holds three capped bets, not one;
    4. overlap division (`correlation_adjusted_weights`);
    5. gross cap (`apply_gross_cap`);
    6. halt (`apply_entry_halt`) -- last, because it is the only step allowed
       the final word on added risk.

    A name is sizeable only if it has a positive, finite volatility *and* a
    complete correlation window; otherwise its weight is 0 and its
    `Volatility` is reported missing. Warm-up, a constant price, and a recent
    missing bar all land there and all mean the same thing: no full window,
    no position.

    `entries_halted` comes from `LossCapGuard.observe` at the same session.

    Returns one row per ticker, in `closes`' column order, with columns
    `Confidence, Volatility, Standalone, Capped, Overlap, Adjusted,
    Gross_Scaled, Current, Target`, and `attrs` recording `session` and
    `entries_halted`.

    Guarantee (Rule 1): the returned frame is bit-identical under any change
    to `closes` after `session`.
    """
    if not isinstance(config, RiskConfig):
        raise TypeError(f"config must be a RiskConfig; got {type(config).__name__}")
    is_halted = _require_bool("entries_halted", entries_halted)
    _validate_panel(closes)
    label = _session_label(session)
    if label not in closes.index:
        raise ValueError(f"session {label.date()} is not in the price panel.")

    # Everything below reads `history`, never `closes`.
    history = closes.loc[:label]
    tickers = closes.columns
    conviction = _aligned(confidence, tickers, name="confidence")
    current = _aligned(current_weights, tickers, name="current_weights")

    vol_window = config.volatility_window
    volatility = realized_volatility(
        history.iloc[-(vol_window + 1) :], window=vol_window
    ).iloc[-1]
    correlation = trailing_correlation(history, label, window=config.correlation_window)
    vol_values = volatility.to_numpy(dtype=float)
    sizeable = (
        np.isfinite(vol_values)
        & (vol_values > 0)
        & np.isfinite(np.diag(correlation.to_numpy(dtype=float)))
    )
    volatility = volatility.where(sizeable)

    standalone = volatility_target_weights(
        conviction, volatility, target_volatility=config.target_volatility
    )
    capped = standalone.clip(upper=config.max_weight)
    overlap = position_overlap(capped, correlation)
    adjusted = correlation_adjusted_weights(capped, correlation)
    scaled = apply_gross_cap(adjusted, max_gross=config.max_gross)
    target = apply_entry_halt(scaled, current, halted=is_halted)

    decision = pd.DataFrame(
        {
            "Confidence": conviction.fillna(0.0),
            "Volatility": volatility,
            "Standalone": standalone,
            "Capped": capped,
            "Overlap": overlap,
            "Adjusted": adjusted,
            "Gross_Scaled": scaled,
            "Current": current,
            "Target": target,
        },
        index=tickers,
    )
    decision.attrs["session"] = label
    decision.attrs["entries_halted"] = is_halted
    return decision


# ---------------------------------------------------------------------------
# Loss caps
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class LossCapStatus:
    """The guard's reading at one session close.

    `entries_halted` applies to the decision made at this close, which is
    executed at the next session's open.
    """

    session: pd.Timestamp
    equity: float
    daily_return: float
    weekly_return: float
    weekly_drawdown: float
    daily_breach: bool
    weekly_loss_breach: bool
    weekly_drawdown_breach: bool
    weekly_latched: bool
    entries_halted: bool


def _require_equity(equity: object) -> float:
    if not _is_real(equity):
        raise TypeError(f"equity must be a real number; got {type(equity).__name__}")
    value = float(equity)
    if not np.isfinite(value) or value <= 0:
        # A return on a non-positive book is undefined, and a missing close
        # would turn a real loss into a skipped one.
        raise ValueError(f"equity must be positive and finite; got {equity}")
    return value


class LossCapGuard:
    """Reads the book's equity at each close and decides whether it may add risk.

    Measures, per observed session:

    - **daily return** against the previous *observed* close. At daily
      granularity this is also the daily drawdown, so one limit covers both.
    - **weekly return** against the last close before the session's ISO week
      (Monday to Sunday). Anchoring there, not on this week's first close,
      keeps a Monday gap-down inside the new week's loss instead of between
      two weeks. The very first week anchors on the first observed equity.
    - **weekly drawdown** against the week's running high, anchor included, so
      a week that rallies and gives it back is caught before it is a loss.

    A breach is inclusive: reaching a limit exactly halts. A daily breach
    halts that session's decision only. A weekly loss or drawdown breach
    *latches* through the last session of that ISO week, however much equity
    recovers -- an un-latched halt switches off on a one-day bounce and puts
    the book back in the market in the week that breached (spec 017,
    Clarifications Q2). ISO weeks make a week spanning 31 December one week.

    Sessions must strictly increase. Every input is validated before any
    state changes, so a rejected observation leaves the guard as it was.
    """

    def __init__(
        self,
        *,
        daily_loss_limit: float,
        weekly_loss_limit: float,
        weekly_drawdown_limit: float,
    ) -> None:
        self.daily_loss_limit = _require_loss_limit("daily_loss_limit", daily_loss_limit)
        self.weekly_loss_limit = _require_loss_limit("weekly_loss_limit", weekly_loss_limit)
        self.weekly_drawdown_limit = _require_loss_limit(
            "weekly_drawdown_limit", weekly_drawdown_limit
        )
        self._last_session: pd.Timestamp | None = None
        self._last_equity: float | None = None
        self._week: tuple[int, int] | None = None
        self._week_anchor = float("nan")
        self._week_high = float("nan")
        self._weekly_latched = False

    @classmethod
    def from_config(cls, config: RiskConfig) -> LossCapGuard:
        return cls(
            daily_loss_limit=config.daily_loss_limit,
            weekly_loss_limit=config.weekly_loss_limit,
            weekly_drawdown_limit=config.weekly_drawdown_limit,
        )

    def observe(self, session: pd.Timestamp, equity: float) -> LossCapStatus:
        """Record one session close and return the halt state for its decision."""
        label = _session_label(session)
        if self._last_session is not None and label <= self._last_session:
            raise ValueError(
                f"sessions must strictly increase; got {label.date()} after "
                f"{self._last_session.date()}."
            )
        value = _require_equity(equity)

        # Nothing below raises, so the guard is never left half-updated.
        week = tuple(label.isocalendar())[:2]
        if week != self._week:
            anchor = self._last_equity if self._last_equity is not None else value
            self._week = week
            self._week_anchor = anchor
            self._week_high = anchor
            self._weekly_latched = False
        self._week_high = max(self._week_high, value)

        if self._last_equity is None:
            daily_return = float("nan")
        else:
            daily_return = value / self._last_equity - 1.0
        weekly_return = value / self._week_anchor - 1.0
        weekly_drawdown = value / self._week_high - 1.0

        # A NaN daily return (first session) compares False: no breach claimed
        # for a loss that cannot be measured.
        daily_breach = bool(daily_return <= -self.daily_loss_limit)
        weekly_loss_breach = bool(weekly_return <= -self.weekly_loss_limit)
        weekly_drawdown_breach = bool(weekly_drawdown <= -self.weekly_drawdown_limit)
        if weekly_loss_breach or weekly_drawdown_breach:
            self._weekly_latched = True
        entries_halted = daily_breach or self._weekly_latched

        self._last_session = label
        self._last_equity = value
        return LossCapStatus(
            session=label,
            equity=value,
            daily_return=daily_return,
            weekly_return=weekly_return,
            weekly_drawdown=weekly_drawdown,
            daily_breach=daily_breach,
            weekly_loss_breach=weekly_loss_breach,
            weekly_drawdown_breach=weekly_drawdown_breach,
            weekly_latched=self._weekly_latched,
            entries_halted=entries_halted,
        )


_STATUS_FIELDS = [field.name for field in dataclasses.fields(LossCapStatus)]


def loss_cap_history(
    equity: pd.Series,
    *,
    daily_loss_limit: float,
    weekly_loss_limit: float,
    weekly_drawdown_limit: float,
) -> pd.DataFrame:
    """The guard's reading at every session of an equity series.

    Built by running one fresh `LossCapGuard` over `equity` in order -- not a
    second implementation of the same rules, so the streaming guard and this
    view cannot disagree. One row per session, indexed by session.

    Guarantee (Rule 1): row `t` is identical under any change to equity after
    `t`.
    """
    series = pd.Series(equity)
    _validate_sessions(series.index, what="equity")
    guard = LossCapGuard(
        daily_loss_limit=daily_loss_limit,
        weekly_loss_limit=weekly_loss_limit,
        weekly_drawdown_limit=weekly_drawdown_limit,
    )
    rows = [
        dataclasses.asdict(guard.observe(session, value))
        for session, value in series.items()
    ]
    return pd.DataFrame(rows, columns=_STATUS_FIELDS).set_index("session")
