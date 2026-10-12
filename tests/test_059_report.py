"""Spec 059 T003 / FR-003 (queue Q109): the offline allocation report (Rules 3, 4, 11, 13, 15, 16).

EXAMPLE — NOT A RESULT. ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED. Seeded synthetic panels only.
"""
import math

import numpy as np
import pandas as pd
from scipy.stats import norm

import allocation_report as ar
from data_sources import HoldoutSealError
from disclosure import LIMITATIONS
from portfolio_backtest import run_portfolio_backtest
from portfolio_risk import allocation_weights, equal_weight_book
from signals import ALLOCATION_SLEEVES, allocation_selection, decision_sessions, matched_activity, random_selections

S = pd.bdate_range("2019-01-02", "2021-06-30")
COSTS = {"commission": 1.0, "slippage": {"model": "spread_plus_sqrt_impact", "source": "synthetic fixture"}}
FILL = lambda ticker, as_of, quantity: 4e-4  # noqa: E731
SEEDS = [11, 12, 13]


def panel(seed=1, index=S, extra=("QQQ",)):
    tickers = [*ALLOCATION_SLEEVES, *extra]
    rng = np.random.default_rng(seed)
    steps = (0.4 * rng.normal(0, 1, (len(index), 1)) + 0.9 * rng.normal(0, 1, (len(index), len(tickers)))) * 0.01
    closes = pd.DataFrame(100 * np.exp(np.cumsum(steps + 0.0002, axis=0)), index=index, columns=tickers)
    closes.iloc[:200, tickers.index("DBC")] = np.nan  # a late listing
    opens = (closes.shift(1) * np.exp(rng.normal(0, 0.002, closes.shape))).fillna(closes)
    return opens.where(closes.notna()), closes


def equity(opens, closes, weights, fill=FILL):
    return run_portfolio_backtest(opens, closes, weights, starting_capital=1e5, commission_per_fill=1.0,
                                  fill_cost=fill).equity


def report(opens, closes, **changes):
    return ar.allocation_report(opens, closes, fill_cost=FILL, costs=changes.get("costs", COSTS),
                                seeds=changes.get("seeds", SEEDS))


def test_every_series_is_the_costed_backtest_of_its_own_weights():
    opens, closes = panel()
    result = report(opens, closes)
    o, c = opens[list(ALLOCATION_SLEEVES)], closes[list(ALLOCATION_SLEEVES)]
    rows = decision_sessions(c.index, cadence="monthly")
    selection = allocation_selection(c)
    alloc = ar.series_stats(equity(o, c, allocation_weights(selection, c, rows)))
    assert result["allocation"] == alloc and alloc["sharpe"] is not None, "Q109 ALLOCATION"
    assert result["buy_and_hold"] == ar.series_stats(equity(o, c, equal_weight_book(c.notna(), max_gross=1.0).loc[rows])), \
        "Q109 BH"
    degenerate = matched_activity(selection, c, decision_mask=rows)
    assert degenerate["exit_probability"] == 0 and degenerate["initial_probability"] > 0.85, \
        "precondition: a matched chain would reproduce the always-invested allocation"
    draws = random_selections(c, decision_mask=rows, seeds=SEEDS, enter_probability=0.5, exit_probability=0.5,
                              initial_probability=0.5)
    for seed in SEEDS:
        expected = ar.series_stats(equity(o, c, allocation_weights(draws[seed], c, rows)))
        assert result["random"][seed] == expected, f"Q109 RANDOM {seed}"
    sharpes = [result["random"][s]["sharpe"] for s in SEEDS]
    assert len(set(sharpes)) == len(SEEDS) and alloc["sharpe"] not in sharpes, "Q109 RANDOM distinct"
    assert result["random_dispersion"]["std_sharpe"] == np.std(sharpes, ddof=1), "Q109 DISPERSION"
    free = ar.series_stats(equity(o, c, allocation_weights(selection, c, rows), fill=lambda *_: 0.0))
    assert free != alloc, "precondition: costs move the allocation's statistics"


def test_psr_is_the_probabilistic_sharpe_against_zero_at_n_one():
    opens, closes = panel(2)
    eq = equity(opens[list(ALLOCATION_SLEEVES)], closes[list(ALLOCATION_SLEEVES)],
                allocation_weights(allocation_selection(closes[list(ALLOCATION_SLEEVES)]), closes[list(ALLOCATION_SLEEVES)],
                                   decision_sessions(closes.index, cadence="monthly")))
    excess = np.log(eq / eq.shift(1)).iloc[1:].to_numpy() - math.log1p(0.0378) / 252
    sr = excess.mean() / excess.std(ddof=1)
    z = excess - excess.mean()
    skew, kurt = (z ** 3).mean() / (z ** 2).mean() ** 1.5, (z ** 4).mean() / (z ** 2).mean() ** 2
    psr = norm.cdf(sr * math.sqrt(len(excess) - 1) / math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
    stats = ar.series_stats(eq)
    assert math.isclose(stats["psr"], psr, rel_tol=1e-9), "Q109 PSR"
    assert math.isclose(stats["sharpe"], sr * math.sqrt(252), rel_tol=1e-12), "Q109 SHARPE"


def test_non_sleeve_columns_change_nothing():
    opens, closes = panel(3)
    with_extra, without = report(opens, closes), report(opens[list(ALLOCATION_SLEEVES)], closes[list(ALLOCATION_SLEEVES)])
    assert with_extra == without, "Q109 SLEEVES"


def test_refusals():
    opens, closes = panel(4, pd.bdate_range("2021-01-04", "2023-10-02"))
    refused = {}
    for name, call in (("holdout", lambda: report(opens, closes)),
                       ("flat bps", lambda: report(*panel(4), costs={"commission": 1.0,
                                                                     "slippage": {"model": "flat_bps", "bps": 5}})),
                       ("one seed", lambda: report(*panel(4), seeds=[1]))):
        try:
            call()
            refused[name] = None
        except (HoldoutSealError, ValueError) as error:
            refused[name] = type(error).__name__
    assert refused == {"holdout": "HoldoutSealError", "flat bps": "ValueError", "one seed": "ValueError"}, \
        f"Q109 REFUSE {refused}"


def test_render_stamps_first_labels_every_sharpe_and_carries_the_register():
    stamp = ["source: data/cache/EXAMPLE.csv sha256=" + "0" * 64, "commit: unknown"]
    lines = ar.render(report(*panel(5)), stamp)
    assert lines[:2] == stamp and lines[2] == ar.LABEL, "Q109 RENDER stamp"
    sharpe = [line for line in lines if "Sharpe" in line]
    assert len(sharpe) == 3 and all(ar.LABEL in line for line in sharpe), "Q109 RENDER label"
    assert all(f"- {item}" in lines for item in LIMITATIONS) and "spread_plus_sqrt_impact" in "\n".join(lines), \
        "Q109 RENDER register"
