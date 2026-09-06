"""Expanding-window walk-forward cross-validation for market data.

The window genuinely expands: each fold trains on everything before its own
test window except the rows purged at the boundary and the embargo gaps left
behind by earlier folds. An embargo is a gap after a test window, not a
permanent exclusion of it — see `walk_forward_splits` and spec 006.
"""

from collections.abc import Iterator

import numpy as np
import pandas as pd

from data import download_market_data

TICKER = "AAPL"
DEFAULT_INITIAL_TRAIN_MONTHS = 6
DEFAULT_TEST_MONTHS = 1


def walk_forward_splits(
    data: pd.DataFrame,
    initial_train_months: int = DEFAULT_INITIAL_TRAIN_MONTHS,
    test_months: int = DEFAULT_TEST_MONTHS,
    date_column: str = "Date",
    *,
    label_horizon: int,
    embargo_bars: int,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield positional train/test indices for expanding calendar-time windows.

    ``label_horizon`` and ``embargo_bars`` are stated explicitly by the
    caller (Rule 1/8): this module has no knowledge of how a label is
    computed and must not guess another module's label horizon.

    For each fold, training rows whose label horizon would reach into that
    fold's test window are purged, and a cumulative ledger excludes every
    prior fold's embargo gap from all later folds' training data (Rule 2).

    The embargo is a **gap of ``embargo_bars`` rows immediately following
    each test window**, not a quarantine of the test window itself. A fold's
    test data is ordinary history to a later fold and re-enters its training
    set; only the gap stays excluded, permanently, for every subsequent
    fold. That is what makes the window expanding: fold ``k+1`` trains on
    everything fold ``k`` trained on, plus the period fold ``k`` tested on,
    minus the gaps.

    A gap lands inside the *next* fold's test window whenever test windows
    are adjacent, so it excludes nothing there; it begins removing training
    rows one fold later, once ``train_end`` has moved past it.

    Raises:
        ValueError: if ``embargo_bars < label_horizon`` (an embargo shorter
            than the label horizon cannot prevent the leak it exists to
            close), or for the pre-existing input validation below.
    """
    if date_column not in data.columns:
        raise ValueError(f"DataFrame must contain a {date_column!r} column.")
    if initial_train_months <= 0 or test_months <= 0:
        raise ValueError("Window sizes must be positive numbers of months.")
    if embargo_bars < label_horizon:
        raise ValueError(
            "embargo_bars must be >= label_horizon "
            f"(got embargo_bars={embargo_bars}, label_horizon={label_horizon})."
        )
    if data.empty:
        return

    dates = pd.to_datetime(data[date_column], errors="coerce")
    if dates.isna().any():
        raise ValueError(f"The {date_column!r} column must contain valid dates.")
    if not dates.is_monotonic_increasing:
        raise ValueError(f"The {date_column!r} column must be sorted ascending.")

    train_end = dates.iloc[0] + pd.DateOffset(months=initial_train_months)
    final_date = dates.iloc[-1]

    # Ledger of (gap_start, gap_end) *positional* ranges — one embargo gap
    # per fold, accumulated across the whole generator call and re-applied
    # in full to every subsequent fold's training indices. Each entry covers
    # only the bars after a test window, never the test window itself.
    embargoed_ranges: list[tuple[int, int]] = []

    while train_end <= final_date:
        test_end = train_end + pd.DateOffset(months=test_months)
        train_mask = dates < train_end
        test_mask = (dates >= train_end) & (dates < test_end)
        test_indices = np.flatnonzero(test_mask.to_numpy())

        if test_indices.size:
            train_indices = np.flatnonzero(train_mask.to_numpy())

            # Purge: drop training rows whose label horizon reaches into
            # this fold's test window.
            test_start_pos = int(test_indices.min())
            if label_horizon > 0:
                train_indices = train_indices[
                    train_indices < test_start_pos - label_horizon
                ]

            # Embargo: exclude every fold's embargo zone recorded so far
            # (this fold's own zone is appended below, after yielding).
            for start, end in embargoed_ranges:
                train_indices = train_indices[
                    (train_indices < start) | (train_indices >= end)
                ]

            if train_indices.size:
                yield train_indices, test_indices

            # Record the embargo *gap* — the bars immediately after this
            # test window — not the test window itself. Anchoring the range
            # at test_start_pos instead would make consecutive folds' ranges
            # tile without gaps, and their union would exclude the whole
            # expanding region from every later fold's training data. See
            # spec 006 Background for the measurement.
            test_end_pos = int(test_indices.max()) + 1
            embargoed_ranges.append((test_end_pos, test_end_pos + embargo_bars))

        train_end = test_end


def main():
    market_data = download_market_data([TICKER])
    prices = market_data[market_data["Ticker"] == TICKER]
    prices = prices.sort_values("Date").reset_index(drop=True)

    for fold, (train_indices, test_indices) in enumerate(
        walk_forward_splits(prices, label_horizon=1, embargo_bars=1), start=1
    ):
        print(
            f"Fold {fold}: train rows = {len(train_indices)}, "
            f"test rows = {len(test_indices)}"
        )


if __name__ == "__main__":
    main()
