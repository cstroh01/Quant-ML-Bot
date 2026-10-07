"""049 T012 / Q22 synthetic diagnostics: EXAMPLE -- NOT A RESULT."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401
import data
from scripts import paper_monitor
from mutation_support_019 import killed


def panel():
    sessions = data.trading_days(date(2024, 1, 2), date(2024, 6, 1))[:36]
    values = 100. + np.arange(36) / 10
    values[30] = 1.  # t=29 long, then next session drops enough to flip t=30.
    return pd.DataFrame({"A": values}, index=pd.DatetimeIndex(sessions))


def run(prices=None, window=3):
    return paper_monitor.monitor(panel() if prices is None else prices,
                                 source="synthetic://Q22", window=window)


def test_state_and_next_return_are_separate_with_provenance():
    prices = panel()
    before = prices.copy(deep=True)
    result = run(prices)
    row = result.loc[(prices.index[29], "A")]
    assert row.Confidence == 1.0
    assert row.Outcome_Session == prices.index[30]
    assert row.Next_Return == pytest.approx(1 / 102.9 - 1)
    assert row.Hit == 0.0
    assert result.Coin_Flip_Baseline.eq(0.5).all()
    assert result.attrs["source"] == "synthetic://Q22"
    assert len(result.attrs["input_sha256"]) == 64
    assert "diagnostic, not a result" in result.attrs["disclosure"]
    assert "t+1" in result.attrs["availability"]
    pd.testing.assert_frame_equal(prices, before)


def test_future_change_cannot_change_already_matured_diagnostics():
    prices = panel()
    changed = prices.copy()
    changed.iloc[33:] *= 100
    left, right = run(prices), run(changed)
    pd.testing.assert_frame_equal(left.loc[:prices.index[31]], right.loc[:prices.index[31]])
    assert left.loc[(prices.index[32], "A"), "Confidence"] == right.loc[(prices.index[32], "A"), "Confidence"]


def test_window_counts_completed_sessions_and_last_outcome_is_unknown():
    result = run()
    hit = result.xs("A", level="Ticker").Hit
    expected = hit.rolling(3, min_periods=3).mean()
    pd.testing.assert_series_equal(result.xs("A", level="Ticker").Rolling_Hit_Rate,
                                   expected, check_names=False)
    assert result.xs("A", level="Ticker").Rolling_Hit_Rate.iloc[:2].isna().all()
    assert pd.isna(result.iloc[-1].Outcome_Session)
    assert pd.isna(result.iloc[-1].Hit)
    assert pd.isna(result.iloc[-1].Rolling_Hit_Rate)
    assert result.xs("A", level="Ticker").index.equals(panel().index)


def test_zero_move_and_missing_close_are_not_directional_hits():
    prices = panel()
    prices.iloc[3] = prices.iloc[2]
    prices.iloc[5] = np.nan
    result = run(prices).xs("A", level="Ticker")
    assert pd.isna(result.Hit.iloc[2])
    assert result.Hit.iloc[4:6].isna().all()
    assert result.Rolling_Hit_Rate.iloc[4:8].isna().all()


@pytest.mark.parametrize("defect", ["aware", "duplicate", "intraday", "gap", "negative", "infinite"])
def test_malformed_panel_is_refused(defect):
    prices = panel()
    if defect == "aware":
        prices.index = prices.index.tz_localize("UTC")
    elif defect == "duplicate":
        prices.index = pd.DatetimeIndex([prices.index[0], *prices.index[:-1]])
    elif defect == "intraday":
        prices.index += pd.Timedelta(hours=1)
    elif defect == "gap":
        prices = prices.drop(prices.index[5])
    else:
        prices.iloc[4] = -1 if defect == "negative" else np.inf
    with pytest.raises(ValueError):
        run(prices)


def test_short_history_and_default_63_session_window():
    prices = panel().iloc[:1]
    assert pd.isna(run(prices).iloc[0].Hit)
    default = paper_monitor.monitor(panel(), source="synthetic://Q22")
    assert default.Rolling_Hit_Rate.isna().all()
    for window in (0, -1, True, 1.5):
        with pytest.raises(ValueError, match="window"):
            run(window=window)


def state_oracle():
    assert run().loc[(panel().index[29], "A"), "Confidence"] == 1.0, "M1 state must read t"


def outcome_oracle():
    assert run().loc[(panel().index[29], "A"), "Next_Return"] == pytest.approx(1 / 102.9 - 1), "M2 outcome must read t+1"


def test_state_future_mutant_is_killed():
    killed(paper_monitor, "trend_confidence(closes, session)",
           "trend_confidence(closes, next_session)", state_oracle)


def test_outcome_shift_mutant_is_killed():
    killed(paper_monitor, "closes.shift(-1).div(closes)",
           "closes.div(closes.shift(1))", outcome_oracle)
