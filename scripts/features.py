"""Causal feature construction, parameterized by target and horizon.

This is `logistic_baseline.build_features` (`:36-55`) with its two hardcoded
assumptions lifted into arguments: the window sizes, and the target. It is a
new module rather than an edit to that function because
`logistic_baseline.py`'s output is the committed control result Phase 3
measures against, and spec 005 ruled deliberately in favour of leaving it
alone.

Signal layer (Rule 8): imports `signals` and `targets`, nothing else from the
project, and never `backtest_harness`.
"""

import numpy as np
import pandas as pd

from signals import sma_crossover_signal
from targets import LABEL_COLUMN, build_target

# The same five columns `logistic_baseline.FEATURE_COLUMNS` lists. Restated
# rather than imported because importing that module pulls scikit-learn in
# for a list of five strings; `test_targets.py` asserts the two lists are
# equal so the duplication cannot drift.
#
# These are price *levels*, not ratios, which is a real weakness for a linear
# model and a blocker for any pooled cross-sectional model. Making them
# scale-free is its own change with its own effect on results, deliberately
# not bundled with a new target (spec 009 Assumptions).
FEATURE_COLUMNS = [
    "Log_Return",
    "Rolling_Volatility",
    "Short_SMA",
    "Long_SMA",
    "Volume",
]

DEFAULT_SHORT_WINDOW = 10
DEFAULT_LONG_WINDOW = 30
DEFAULT_VOLATILITY_WINDOW = 10


def build_features(
    prices: pd.DataFrame,
    *,
    target_kind: str,
    label_horizon: int,
    short_window: int = DEFAULT_SHORT_WINDOW,
    long_window: int = DEFAULT_LONG_WINDOW,
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW,
) -> tuple[pd.DataFrame, str, int]:
    """Build causal features and the selected label.

    Returns `(frame, task, label_horizon)`. The frame carries the input's
    columns plus the SMA/crossover columns, `Log_Return`,
    `Rolling_Volatility`, and `Label`, with warm-up rows and rows lacking an
    observable label removed, on a 0-based `RangeIndex`.

    `task` and `label_horizon` are passed straight through from
    `targets.build_target` so a caller can hand the same horizon to
    `walk_forward_splits` — the label and its purge must be sized in the same
    units, and the surest way to guarantee that is to never write the number
    twice.

    Every feature is computed from data at or before its own row (Rule 1):
    the SMAs and the rolling volatility are trailing windows, and
    `Log_Return` is a backward difference. `Label` is the only column that
    looks forward, and it is excluded from `FEATURE_COLUMNS` by construction.
    """
    features = sma_crossover_signal(prices, short_window, long_window)
    features["Log_Return"] = np.log(features["Close"] / features["Close"].shift(1))
    features["Rolling_Volatility"] = (
        features["Log_Return"].rolling(volatility_window).std()
    )

    # The label is the prediction target only. It is never a feature — see
    # FEATURE_COLUMNS above, which this column is deliberately absent from.
    label, task, horizon = build_target(
        features, kind=target_kind, horizon=label_horizon
    )
    features[LABEL_COLUMN] = label

    # Drop the SMA/volatility warm-up rows, then any row whose features or
    # label are not fully observable — which removes the final `horizon`
    # rows, whose label reaches past the end of the data. Same sequence as
    # logistic_baseline.build_features:51-55.
    frame = (
        features.iloc[long_window:]
        .dropna(subset=FEATURE_COLUMNS + [LABEL_COLUMN])
        .reset_index(drop=True)
    )
    return frame, task, horizon
