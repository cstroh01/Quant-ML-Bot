"""Spec 058 T011: hypotheses H1-H8 as hold selections at close t (Rule 1, Rule 5).

EXAMPLE — NOT A RESULT. Seeded synthetic random walks; no figure here is a result.
"""
import numpy as np
import pandas as pd
import pytest
from signals import HYPOTHESES, SECTOR_ETFS, hypothesis_selection

TICKERS = ["SPY", "QQQ", "SHY", "TLT", "GLD", *SECTOR_ETFS]
SESSIONS = pd.bdate_range("2004-01-02", periods=420)
LISTED = 90  # the late ticker's first row
# Closes each configuration's lookback needs, ending at t.
ROWS = {"H1-3": 64, "H1-6": 127, "H1-12": 253, "H2-100": 100, "H2-200": 200, "H3-3": 253, "H3-5": 253,
        "H4": 61, "H5": 253, "H6-6": 127, "H6-12": 253, "H7": 61, "H8": 6}


def walk(seed, n=len(SESSIONS), start=100.0):
    return start * np.exp(np.cumsum(np.random.default_rng(seed).normal(0, 0.01, (n, len(TICKERS))), axis=0))


def panel(late, step):
    """Random walks, with `late` listing at row LISTED on a smooth path of `step` log return a day."""
    closes = pd.DataFrame(walk(7), index=SESSIONS, columns=TICKERS)
    closes[late] = np.where(np.arange(len(SESSIONS)) < LISTED, np.nan,
                            50 * np.exp(step * (np.arange(len(SESSIONS)) - LISTED)))
    return closes


def late_ticker(config):
    """A ticker each rule must pick once eligible: a smooth riser, or a sector faller for H8."""
    return ("XLB", -0.03) if config == "H8" else ("XLK", 0.01) if config == "H7" else ("GLD", 0.01)


def test_every_declared_configuration_h1_to_h8_is_covered():
    assert set(HYPOTHESES) == set(ROWS), "T011 COVERAGE"


@pytest.mark.parametrize("config", sorted(ROWS))
def test_future_rows_never_change_the_current_selection(config):
    base = panel(*late_ticker(config))
    full = hypothesis_selection(config, base)
    changed_after = False
    for cut in range(255, 400, 9):
        future = base.copy()
        tail = walk(cut, len(SESSIONS) - cut - 1, 1.0)
        future.iloc[cut + 1:] = base.iloc[cut].to_numpy() * tail ** 3  # replaced future, same row t
        future.iloc[cut + 1, TICKERS.index("GLD")] = np.nan  # and a future gap
        moved = hypothesis_selection(config, future)
        assert moved.iloc[:cut + 1].equals(full.iloc[:cut + 1]), f"T011 LOOKAHEAD {config} cut {cut}"
        changed_after |= not moved.iloc[cut + 1:].equals(full.iloc[cut + 1:])
    assert changed_after, f"T011 LOOKAHEAD vacuous: {config} never read the perturbed rows"


@pytest.mark.parametrize("config", sorted(ROWS))
def test_no_selection_before_the_full_lookback_is_observed(config):
    ticker, step = late_ticker(config)
    selected = hypothesis_selection(config, panel(ticker, step))[ticker]
    first = int(np.argmax(selected.to_numpy()))
    assert selected.any() and first == LISTED + ROWS[config] - 1, \
        f"T011 LISTING {config}: first selected row {first}, expected {LISTED + ROWS[config] - 1}"


def test_a_missing_row_inside_the_window_deselects_until_observed_again():
    closes = panel("GLD", 0.01)
    closes.iloc[300, TICKERS.index("GLD")] = np.nan
    held = hypothesis_selection("H4", closes)["GLD"]
    assert held.iloc[299] and not held.iloc[300:361].any() and held.iloc[361], "T011 GAP"


def test_time_series_momentum_skips_the_last_month():
    # Up 20% over the first 42 sessions, then down 30% in the last 21: H1-3 reads t-63 -> t-21 only.
    path = np.r_[np.linspace(100, 120, 43), np.linspace(118, 84, 21)]
    closes = pd.DataFrame(walk(3, 64), index=SESSIONS[:64], columns=TICKERS)
    closes["SPY"] = path
    assert path[-1] < path[0] and hypothesis_selection("H1-3", closes)["SPY"].iloc[-1], "T011 SKIP"


def test_dual_momentum_holds_shy_unless_the_winner_beats_it():
    closes = pd.DataFrame(100.0, index=SESSIONS[:127], columns=TICKERS)
    closes["SHY"] = np.linspace(100, 101, 127)
    closes["GLD"] = np.linspace(100, 100.5, 127)  # the best risky asset, positive but below SHY
    held = hypothesis_selection("H6-6", closes).iloc[-1]
    assert held["SHY"] and held.sum() == 1, f"T011 DUAL {held[held].index.tolist()}"
    closes["GLD"] = np.linspace(100, 102, 127)
    held = hypothesis_selection("H6-6", closes).iloc[-1]
    assert held["GLD"] and held.sum() == 1, f"T011 DUAL {held[held].index.tolist()}"


def test_ranked_picks_need_k_eligible_tickers():
    closes = panel("GLD", 0.01)
    closes.iloc[:150, 2:] = np.nan  # only SPY and QQQ observed before row 150
    held = hypothesis_selection("H3-3", closes)
    assert not held.iloc[:150 + 252].any().any() and held.iloc[-1].sum() == 3, "T011 FEW"


def test_sector_rules_select_only_sectors_and_reject_bad_panels():
    for config in ("H7", "H8"):
        held = hypothesis_selection(config, panel("XLB", -0.03))
        assert not held.drop(columns=list(SECTOR_ETFS)).any().any() and (held.sum(axis=1) <= 3).all()
    with pytest.raises(ValueError, match="sector"):
        hypothesis_selection("H7", panel("GLD", 0.01).drop(columns="XLE"))
    with pytest.raises(ValueError, match="naive"):
        hypothesis_selection("H4", panel("GLD", 0.01).tz_localize("UTC"))
    with pytest.raises(ValueError, match="unknown"):
        hypothesis_selection("H9", panel("GLD", 0.01))
