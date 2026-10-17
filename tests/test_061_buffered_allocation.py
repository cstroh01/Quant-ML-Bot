"""061: EXAMPLE — NOT A RESULT. Synthetic prices and injected ledgers only."""
import numpy as np
import pandas as pd
import pytest
from context import SCRIPTS_DIR

from buffered_allocation import buffered_weights
from signals import ALLOCATION_SLEEVES


def prices():
    dates = pd.to_datetime(["2023-01-30", "2023-01-31", "2023-02-01", "2023-02-03",
                            "2023-02-28", "2023-03-01"])
    return pd.DataFrame({t: (20 + i) * np.exp(np.arange(6) * 0.001 * (i + 1))
                         for i, t in enumerate(ALLOCATION_SLEEVES)}, index=dates)


def test_buffered_weights_are_equal_not_a1_and_reserve_applied_once():
    book = buffered_weights(prices())
    assert list(book.index) == list(pd.to_datetime(["2023-02-01", "2023-03-01"]))
    assert np.allclose(book.to_numpy(), 0.11625), "061 EQUAL: rejects A1 and unbuffered B-BH"
    assert np.allclose(book.sum(axis=1), 0.93), "061 RESERVE: apply seven percent exactly once"


def test_future_change_does_not_change_past_and_gap_is_not_a_rebalance():
    closes = prices()
    before = buffered_weights(closes)
    closes.loc["2023-02-03":, "SPY"] *= 5
    closes.loc["2023-02-03":, "SPY"] = np.nan
    after = buffered_weights(closes)
    pd.testing.assert_series_equal(before.loc["2023-02-01"], after.loc["2023-02-01"])
    assert pd.Timestamp("2023-02-03") not in after.index, "061 MONTHLY: no daily retargeting"
    assert pd.Timestamp("2023-01-30") not in after.index, "061 FIRST: opener unknown"


def test_missing_close_reweights_only_available_sleeves_and_empty_month_is_cash():
    closes = prices()
    closes.loc["2023-02-01", "SPY"] = np.nan
    closes.loc["2023-03-01"] = np.nan
    book = buffered_weights(closes)
    assert book.loc["2023-02-01", "SPY"] == 0
    assert np.allclose(book.loc["2023-02-01"].drop("SPY"), 0.93 / 7)
    assert book.loc["2023-03-01"].sum() == 0


@pytest.mark.parametrize("kind", ["aware", "duplicate", "reversed"])
def test_invalid_sessions_refuse(kind):
    closes = prices()
    if kind == "aware":
        closes.index = closes.index.tz_localize("America/New_York")
    elif kind == "duplicate":
        closes = pd.concat([closes, closes.iloc[[-1]]])
    else:
        closes = closes.iloc[::-1]
    with pytest.raises(ValueError):
        buffered_weights(closes)
