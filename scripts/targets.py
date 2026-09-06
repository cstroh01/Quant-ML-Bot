"""Prediction targets, and the horizons that define them.

A target is chosen by the caller, never assumed. Both public label functions
take an explicit `horizon`, and `build_target` hands that horizon back
alongside the label so a caller can pass the *same* number to
`walk_forward_splits` rather than restating a literal.

That handback is the point of this module's shape. `walk_forward_cv` purges
training rows whose label reaches into a test window, and it sizes the purge
from the `label_horizon` its caller supplies (`walk_forward_cv.py:26-28`). If
a label's horizon and the purge's horizon are two independently written
numbers, they can disagree — and a 5-bar label under a 1-bar purge leaks the
test window into training, raises nothing, and improves the reported score.
Today they agree only by coincidence: `logistic_baseline.py` hardcodes
`shift(-1)` at `:46` and the literal `label_horizon=1` at `:65` and `:149`.

Signal layer (Rule 8): numpy and pandas only. No estimator, no fold, no fill.
"""

import numpy as np
import pandas as pd

DIRECTION = "direction"
FORWARD_RETURN = "return"
TARGET_KINDS = (DIRECTION, FORWARD_RETURN)

CLASSIFICATION = "classification"
REGRESSION = "regression"

# Which estimator family each target implies. A caller does not get to pick
# the task independently of the target — a direction label is not a
# regression problem — so this is a lookup, not a parameter.
_TASK_FOR_KIND = {DIRECTION: CLASSIFICATION, FORWARD_RETURN: REGRESSION}

LABEL_COLUMN = "Label"


def _validate_horizon(horizon: int) -> None:
    """Reject horizons that produce a silently degenerate label.

    `horizon=0` is the dangerous one: a direction label becomes
    `Close[t] > Close[t]`, which is `False` on every row, and a forward log
    return becomes `log(1) == 0.0` everywhere. Both are perfectly valid
    columns that no model can learn anything from, and neither raises.
    """
    if not isinstance(horizon, (int, np.integer)) or isinstance(horizon, bool):
        raise TypeError(f"horizon must be an int; got {type(horizon).__name__}")
    if horizon < 1:
        raise ValueError(f"horizon must be >= 1; got {horizon}")


def _future_close(prices: pd.DataFrame, horizon: int) -> pd.Series:
    """`Close` shifted back by `horizon` **rows**, not calendar days.

    The positional convention matches the purge in `walk_forward_cv.py`
    (spec 003 FR-005). If a label were sized in calendar days and the purge
    in rows, the two would disagree across every holiday and halt — and the
    purge exists to cover exactly this label.
    """
    if "Close" not in prices.columns:
        raise ValueError("prices must contain a 'Close' column.")
    return prices["Close"].shift(-horizon)


def direction_label(prices: pd.DataFrame, *, horizon: int) -> pd.Series:
    """Whether the close `horizon` bars ahead is higher than this one.

    Returns a nullable `Int64` series: `1` for up, `0` for down-or-flat, and
    `<NA>` for the final `horizon` rows, whose future close does not exist
    yet.

    The dtype is deliberate. A plain `bool` or `int64` column cannot hold a
    null, so the unobservable tail would silently become `False`/`0` — a
    fabricated target, which is a lookahead bug that makes results look
    better rather than crashing (Rule 1).

    A flat close counts as down. That is arbitrary but must be stated: it is
    the same convention `logistic_baseline.build_features:47` uses, and
    changing it would move the committed AAPL control result.
    """
    _validate_horizon(horizon)
    future = _future_close(prices, horizon)
    label = (future > prices["Close"]).astype("Int64")
    label[future.isna()] = pd.NA
    return label.rename(LABEL_COLUMN)


def forward_log_return_label(prices: pd.DataFrame, *, horizon: int) -> pd.Series:
    """The log return over the next `horizon` bars.

    Returns a float series, `NaN` for the final `horizon` rows and anywhere
    either close is non-positive (where the log is undefined). Log rather
    than simple returns, to match `return_stats.daily_log_returns` and
    because log returns add across time.

    This is the target a cost-aware entry rule needs: a direction label can
    say "up" but cannot say whether "up" clears the round-trip cost of
    acting on it.
    """
    _validate_horizon(horizon)
    future = _future_close(prices, horizon)
    current = prices["Close"]

    future_values = future.to_numpy(dtype=float)
    current_values = current.to_numpy(dtype=float)
    label = np.full(len(prices), np.nan, dtype=float)
    defined = (future_values > 0) & (current_values > 0)
    label[defined] = np.log(future_values[defined] / current_values[defined])
    return pd.Series(label, index=prices.index, name=LABEL_COLUMN)


def build_target(
    prices: pd.DataFrame, *, kind: str, horizon: int
) -> tuple[pd.Series, str, int]:
    """Build the selected target and report what it implies.

    Returns `(label, task, label_horizon)`:

    - `label` — the target column.
    - `task` — `"classification"` or `"regression"`, derived from `kind`.
      This is what tells an estimator registry which model family applies.
    - `label_horizon` — the horizon that was used, handed back so the caller
      can pass the same value to `walk_forward_splits` instead of restating
      a literal that could drift from this one.

    Raises:
        ValueError: for an unknown `kind`. There is deliberately no default:
            silently falling back to a direction target would let a caller
            who meant to switch keep grading the old problem.
    """
    if kind not in TARGET_KINDS:
        raise ValueError(
            f"unknown target kind {kind!r}; valid kinds are {list(TARGET_KINDS)}"
        )

    builder = {
        DIRECTION: direction_label,
        FORWARD_RETURN: forward_log_return_label,
    }[kind]
    return builder(prices, horizon=horizon), _TASK_FOR_KIND[kind], horizon
