"""Expanding-window walk-forward cross-validation for market data."""

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
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield positional train/test indices for expanding calendar-time windows."""
    if date_column not in data.columns:
        raise ValueError(f"DataFrame must contain a {date_column!r} column.")
    if initial_train_months <= 0 or test_months <= 0:
        raise ValueError("Window sizes must be positive numbers of months.")
    if data.empty:
        return

    dates = pd.to_datetime(data[date_column], errors="coerce")
    if dates.isna().any():
        raise ValueError(f"The {date_column!r} column must contain valid dates.")
    if not dates.is_monotonic_increasing:
        raise ValueError(f"The {date_column!r} column must be sorted ascending.")

    train_end = dates.iloc[0] + pd.DateOffset(months=initial_train_months)
    final_date = dates.iloc[-1]

    while train_end <= final_date:
        test_end = train_end + pd.DateOffset(months=test_months)
        train_mask = dates < train_end
        test_mask = (dates >= train_end) & (dates < test_end)
        test_indices = np.flatnonzero(test_mask.to_numpy())

        if test_indices.size:
            yield np.flatnonzero(train_mask.to_numpy()), test_indices

        train_end = test_end


def main():
    market_data = download_market_data([TICKER])
    prices = market_data[market_data["Ticker"] == TICKER]
    prices = prices.sort_values("Date").reset_index(drop=True)

    for fold, (train_indices, test_indices) in enumerate(
        walk_forward_splits(prices), start=1
    ):
        print(
            f"Fold {fold}: train rows = {len(train_indices)}, "
            f"test rows = {len(test_indices)}"
        )


if __name__ == "__main__":
    main()
