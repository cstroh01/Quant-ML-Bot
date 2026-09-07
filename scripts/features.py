"""Causal feature construction, parameterized by target, horizon, and scale.

This began as `logistic_baseline.build_features` (`:36-55`) with its two
hardcoded assumptions lifted into arguments: the window sizes, and the target
(spec 009). Spec 014 lifts a third — whether the features are price *levels*
or scale-free ratios. It remains a separate module rather than an edit to
that function because `logistic_baseline.py`'s output is the committed
control result Phase 3 measures against, and spec 005 ruled deliberately in
favour of leaving it alone.

Signal layer (Rule 8): imports `signals` and `targets`, nothing else from the
project, and never `backtest_harness`.
"""

import numpy as np
import pandas as pd

from signals import sma_crossover_signal
from targets import LABEL_COLUMN, build_target

# The five columns `logistic_baseline.FEATURE_COLUMNS` lists, in its order.
# Restated rather than imported because importing that module pulls
# scikit-learn in for a list of five strings; `test_targets.py` asserts the
# two lists are equal so the duplication cannot drift.
#
# Three of these are price levels, which spec 014 identified as two distinct
# defects rather than one. They are *non-stationary*: a fold trained on $50
# bars predicts $200 bars by extrapolating outside its own training support.
# And `Short_SMA`/`Long_SMA` are ~0.97 collinear, which is what made ridge
# ill-conditioned. Kept here as the control set, not as the default.
LEVEL_FEATURE_COLUMNS = [
    "Log_Return",
    "Rolling_Volatility",
    "Short_SMA",
    "Long_SMA",
    "Volume",
]

# The default. Every column is a ratio of same-row quantities, so the whole
# vector is invariant to the units of price and volume — which is what makes
# a fold's training support cover its test window, and what makes a single
# `alpha`/`C` mean the same thing on every column.
#
# `SMA_Spread` and `Close_To_Short` are the two halves of a decomposition,
# not two looks at the same thing. Because
# `Close/Long == (Close/Short) * (Short/Long)`, "price against its long
# average" is *already* carried by the pair; measuring it directly as a third
# quantity would re-measure the sum of the other two. Splitting it into the
# fast leg (price against the short average) and the slow leg (short against
# long) is what breaks the collinearity rather than merely rescaling it —
# scaling is a diagonal transform and cannot change a correlation.
#
# Measured on the spec 014 fixture: `Close/Long - 1` against `SMA_Spread`
# correlates 0.865, and `Close/Short - 1` against it correlates 0.325.
SCALE_FREE_FEATURE_COLUMNS = [
    "Log_Return",
    "Rolling_Volatility",
    "SMA_Spread",
    "Close_To_Short",
    "Rel_Volume",
]

FEATURE_SETS: dict[str, list[str]] = {
    "levels": LEVEL_FEATURE_COLUMNS,
    "scale_free": SCALE_FREE_FEATURE_COLUMNS,
}

DEFAULT_FEATURE_SET = "scale_free"

# The three columns spec 014 adds. Always computed, whichever set is
# selected, so one frame can be diagnosed under both without being rebuilt —
# `feature_diagnostics.py` and `feature_set_comparison.py` both rely on this.
DERIVED_RATIO_COLUMNS = ["SMA_Spread", "Close_To_Short", "Rel_Volume"]

DEFAULT_SHORT_WINDOW = 10
DEFAULT_LONG_WINDOW = 30
DEFAULT_VOLATILITY_WINDOW = 10


def feature_columns(feature_set: str = DEFAULT_FEATURE_SET) -> list[str]:
    """The column names belonging to one registered feature set.

    Returns a copy, so a caller that sorts or appends cannot mutate the
    module-level list every other caller reads.

    There is deliberately no module-level `FEATURE_COLUMNS` any more. The name
    used to mean the level set and would now mean the scale-free one; leaving
    it in place would change what existing code computed without changing what
    it says, which is the exact failure mode this spec exists to correct.

    Raises:
        ValueError: for an unregistered set. There is no default fallback, for
            the reason `estimators.get_spec` gives: silently substituting a
            feature set for the one a caller asked for produces a result
            attributed to the wrong thing.
    """
    try:
        return list(FEATURE_SETS[feature_set])
    except KeyError:
        raise ValueError(
            f"unknown feature_set {feature_set!r}; registered sets are "
            f"{sorted(FEATURE_SETS)}"
        ) from None


def build_features(
    prices: pd.DataFrame,
    *,
    target_kind: str,
    label_horizon: int,
    short_window: int = DEFAULT_SHORT_WINDOW,
    long_window: int = DEFAULT_LONG_WINDOW,
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW,
    feature_set: str = DEFAULT_FEATURE_SET,
    volume_window: int | None = None,
) -> tuple[pd.DataFrame, str, int]:
    """Build causal features and the selected label.

    Returns `(frame, task, label_horizon)`. The frame carries the input's
    columns plus the SMA/crossover columns, `Log_Return`,
    `Rolling_Volatility`, the three ratio columns, and `Label`, with warm-up
    rows and rows lacking an observable label removed, on a 0-based
    `RangeIndex`. Call `feature_columns(feature_set)` for the names a model
    should actually be handed.

    `task` and `label_horizon` are passed straight through from
    `targets.build_target` so a caller can hand the same horizon to
    `walk_forward_splits` — the label and its purge must be sized in the same
    units, and the surest way to guarantee that is to never write the number
    twice.

    `feature_set` selects which columns the row-completeness drop is judged
    against, and nothing else: all columns are computed either way. Judging
    the drop against the *selected* set is what keeps `feature_set="levels"`
    reproducing `logistic_baseline.build_features` row for row — dropping on
    the union would discard the extra volume warm-up rows there too, and move
    the committed control result.

    `volume_window` defaults to `long_window`. Every feature is computed from
    data at or before its own row (Rule 1): the SMAs, the rolling volatility
    and the volume mean are trailing windows, and `Log_Return` is a backward
    difference. The three ratios divide same-row quantities, so they add no
    new time dependency. `Label` is the only column that looks forward, and it
    is excluded from every feature set by construction.

    Raises:
        ValueError: for an unregistered `feature_set`, or a `volume_window`
            below 1.
    """
    columns = feature_columns(feature_set)

    if volume_window is None:
        volume_window = long_window
    if volume_window < 1:
        raise ValueError(f"volume_window must be >= 1; got {volume_window}")

    features = sma_crossover_signal(prices, short_window, long_window)
    features["Log_Return"] = np.log(features["Close"] / features["Close"].shift(1))
    features["Rolling_Volatility"] = (
        features["Log_Return"].rolling(volatility_window).std()
    )

    # The scale-free three. Each is a ratio of two same-row quantities, minus
    # one where a "distance from parity" reading is the natural one.
    features["SMA_Spread"] = features["Short_SMA"] / features["Long_SMA"] - 1.0
    features["Close_To_Short"] = features["Close"] / features["Short_SMA"] - 1.0
    features["Rel_Volume"] = (
        features["Volume"] / features["Volume"].rolling(volume_window).mean()
    )

    # A halted ticker gives a zero rolling volume, and a zero denominator
    # gives an infinity that no estimator errors on and every estimator is
    # wrecked by. Send it to NaN so the drop below removes the row, which is
    # the honest reading: the feature is not defined there.
    for column in DERIVED_RATIO_COLUMNS:
        features[column] = features[column].replace([np.inf, -np.inf], np.nan)

    # The label is the prediction target only. It is never a feature — see
    # FEATURE_SETS above, which this column is deliberately absent from.
    label, task, horizon = build_target(
        features, kind=target_kind, horizon=label_horizon
    )
    features[LABEL_COLUMN] = label

    # Drop the SMA/volatility warm-up rows, then any row whose *selected*
    # features or label are not fully observable — which removes the final
    # `horizon` rows, whose label reaches past the end of the data. Same
    # sequence as logistic_baseline.build_features:51-55. A `volume_window`
    # longer than `long_window` needs no wider slice here: its warm-up is a
    # leading run of NaN, which the drop removes.
    frame = (
        features.iloc[long_window:]
        .dropna(subset=columns + [LABEL_COLUMN])
        .reset_index(drop=True)
    )
    return frame, task, horizon
