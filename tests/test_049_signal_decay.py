"""049 T012 signal decay on synthetic closes: EXAMPLE — NOT A RESULT."""
import random
from datetime import date

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401
import data
import paper_targets
from scripts import signal_decay


def panel():
    """A: uptrend whose next-session moves alternate (t odd -> up); tie at t=40. B: downtrend (flat state)."""
    sessions = pd.DatetimeIndex(data.trading_days(date(2024, 1, 2), date(2024, 6, 28))[:60])
    i = np.arange(60)
    a = 100.0 + i + 0.8 * (-1.0) ** i
    a[41] = a[40]
    return pd.DataFrame({"A": a, "B": 200.0 - i}, index=sessions)


def table(prices=None, at=50, **kw):
    prices = panel() if prices is None else prices
    kw = {"seed": 7, "window": 60, "min_obs": 20, **kw}
    return signal_decay.decay_table(prices, as_of=prices.index[at], source="synthetic://049-T012", **kw)


def expected(prices, at, window):
    """Independent count: long state at t, t+1 <= as_of, nonzero next return."""
    longs = hits = 0
    for t in range(max(0, at - window), at):
        move = prices.A.iloc[t + 1] / prices.A.iloc[t] - 1
        if paper_targets.trend_confidence(prices, prices.index[t])["A"] == 1.0 and move != 0:
            longs, hits = longs + 1, hits + (move > 0)
    return longs, hits


def test_binomial_two_sided_is_exact():
    assert signal_decay.binomial_two_sided(2, 10) == signal_decay.binomial_two_sided(8, 10) == 112 / 1024
    assert signal_decay.binomial_two_sided(0, 5) == 2 / 32
    assert signal_decay.binomial_two_sided(5, 10) == 1.0
    assert signal_decay.binomial_two_sided(11, 20) == pytest.approx(1 - 184756 / 2 ** 20)
    assert np.isnan(signal_decay.binomial_two_sided(0, 0))
    with pytest.raises(ValueError):
        signal_decay.binomial_two_sided(3, 2)


@pytest.mark.parametrize("window", [60, 5])
def test_flat_state_and_zero_moves_are_excluded_not_misses(window):
    row = table(window=window).loc["A"]
    assert (row.Long_Obs, row.Hits) == expected(panel(), 50, window)
    assert (row.Long_Obs, row.Hits) == ((20, 11) if window == 60 else (5, 3))
    assert row.Hit_Rate == row.Hits / row.Long_Obs
    assert row.P_Value_Two_Sided == signal_decay.binomial_two_sided(row.Hits, row.Long_Obs)
    flat = table().loc["B"]
    assert flat.Long_Obs == 0 and np.isnan(flat.Hit_Rate) and not flat.Decay


@pytest.mark.parametrize("factor", [2.0, 0.5])
def test_close_at_s_plus_1_cannot_change_the_value_as_of_s(factor):
    # Field perturbed: Close at s+1, the one close that decides r(s -> s+1), the hit
    # of decision session s, which is unknown at s's close. State at s is long.
    prices = panel()
    assert paper_targets.trend_confidence(prices, prices.index[50])["A"] == 1.0
    moved = prices.copy()
    moved.iloc[51] *= factor
    pd.testing.assert_frame_equal(table(prices), table(moved))
    # Provenance covers exactly the data read: the panel is cut at s before the hash.
    assert table(prices).attrs["input_sha256"] == table(moved).attrs["input_sha256"]


def test_a_hit_enters_only_after_its_outcome_session():
    before, after = table(at=50).loc["A"], table(at=51).loc["A"]
    assert after.Long_Obs == before.Long_Obs + 1 and after.Hits == before.Hits  # r(50->51) is down


def test_random_baseline_is_seeded_and_leaves_global_state_alone():
    np.random.seed(0)
    random.seed(0)
    np_state, py_state = np.random.get_state()[1].copy(), random.getstate()
    first, again, other = table(), table(), table(seed=8)
    assert np.array_equal(np.random.get_state()[1], np_state) and random.getstate() == py_state
    pd.testing.assert_frame_equal(first, again)
    assert first.loc["A", "Random_Mean"] != other.loc["A", "Random_Mean"]
    assert 0 < first.loc["A", "Random_Std"] and 0 < first.loc["A", "Random_Mean"] < 1


def test_decay_flag_needs_min_obs_and_a_rate_below_threshold():
    assert table(threshold=0.6).loc["A", "Decay"]
    assert not table(threshold=0.6, min_obs=21).loc["A", "Decay"]
    assert not table(threshold=0.55).loc["A", "Decay"]  # 11/20 is not below 0.55


def test_render_carries_disclosure_top_and_bottom_and_provenance():
    text = signal_decay.render(table())
    head, tail = text.split("| Ticker |")
    for part in (head, tail):
        assert signal_decay.LIMITATIONS in part and signal_decay.DECAY_NOTE in part
    for item in ("synthetic://049-T012", "2024-03-14", "seed 7", "input sha256"):
        assert item in head
    assert "sharpe" not in text.lower() and "DECAY" not in text


@pytest.mark.parametrize("bad", [{"window": 0}, {"min_obs": 0}, {"n_draws": 1}, {"threshold": 1.5},
                                 {"seed": -1}, {"seed": True}])
def test_invalid_parameters_are_refused(bad):
    with pytest.raises(ValueError):
        table(**bad)
    with pytest.raises(ValueError, match="as_of"):
        signal_decay.decay_table(panel(), as_of="2024-12-31", source="x", seed=1)
