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


def _executable_endpoints(prices: pd.DataFrame, horizon: int) -> tuple[pd.Series, pd.Series]:
    """Entry next open, exit h sessions later; no cross-instrument shifts."""
    _validate_horizon(horizon)
    if "Open" not in prices:
        raise ValueError("prices must contain executable 'Open' prices")
    if "Ticker" in prices and prices.Ticker.nunique() != 1:
        raise ValueError("targets require one instrument")
    if "Date" in prices:
        dates = pd.to_datetime(prices.Date)
        if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
            raise ValueError("target sessions must be unique and ordered")
    return prices.Open.shift(-1), prices.Open.shift(-(horizon + 1))


def direction_label(prices: pd.DataFrame, *, horizon: int) -> pd.Series:
    """Direction of the executable open-to-open return; invalid endpoints unknown.

    Flat is class zero. Final h+1 rows are unobservable, never fabricated down.
    """
    returns = forward_log_return_label(prices, horizon=horizon)
    label = (returns > 0).astype("Int64")
    label[returns.isna()] = pd.NA
    return label.rename(LABEL_COLUMN)


def forward_log_return_label(prices: pd.DataFrame, *, horizon: int) -> pd.Series:
    """log(Open[t+h+1]/Open[t+1]), observed at the exit open.

    These future outcomes are legal only as targets. Expected log return is
    not expected dollar profit; changing timing does not solve audit 25.
    """
    current, future = _executable_endpoints(prices, horizon)
    future_values = future.to_numpy(dtype=float)
    current_values = current.to_numpy(dtype=float)
    label = np.full(len(prices), np.nan, dtype=float)
    defined = (np.isfinite(future_values) & np.isfinite(current_values)
               & (future_values > 0) & (current_values > 0))
    # A plain price ratio is not a total payoff across an action. Abstain;
    # corporate-action total-payoff labels require a separate target contract.
    action = prices.get("Split", pd.Series(1., index=prices.index)).ne(1)
    action |= prices.get("Dividend", pd.Series(0., index=prices.index)).ne(0)
    for offset in range(2, horizon + 2):
        defined &= ~action.shift(-offset, fill_value=False).to_numpy()
    label[defined] = np.log(future_values[defined]) - np.log(current_values[defined])
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
    return builder(prices, horizon=horizon), _TASK_FOR_KIND[kind], horizon + 1
