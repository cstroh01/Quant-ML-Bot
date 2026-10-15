"""Spec 059 T003 / FR-003 (queue Q109): the offline allocation report (Rules 3, 4, 11, 13, 15, 16).

EXAMPLE — NOT A RESULT. ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED. Seeded synthetic panels only.
"""
import math
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import norm

import allocation_report as ar
from cost_model import CostConfig, estimate_fill_cost
from data import trading_days
from data_sources import HoldoutSealError
from disclosure import LIMITATIONS
from portfolio_backtest import run_portfolio_backtest
from portfolio_risk import allocation_weights, equal_weight_book
from signals import ALLOCATION_SLEEVES, allocation_selection, decision_sessions, matched_activity, random_selections

S = pd.DatetimeIndex(trading_days(date(2019, 1, 2), date(2021, 6, 30)))
COMMISSION = 1.0
PRIMARY = CostConfig()
SEEDS = [11, 12, 13]


def bars(seed=1, index=S, extra=("QQQ",)):
    """Synthetic OHLCV per ticker on NYSE sessions; DBC lists late."""
    rng = np.random.default_rng(seed)
    tickers = [*ALLOCATION_SLEEVES, *extra]
    steps = (0.4 * rng.normal(0, 1, (len(index), 1)) + 0.9 * rng.normal(0, 1, (len(index), len(tickers)))) * 0.01
    closes = 100 * np.exp(np.cumsum(steps + 0.0002, axis=0))
    out = {}
    for k, ticker in enumerate(tickers):
        c = closes[:, k]
        o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 0.002, len(c)))
        frame = pd.DataFrame({"Open": o, "High": np.maximum(o, c) * 1.004, "Low": np.minimum(o, c) * 0.996,
                              "Close": c, "Volume": rng.uniform(2e6, 4e6, len(c))}, index=index)
        frame = frame.iloc[200:] if ticker == "DBC" else frame
        frame.attrs["volume_basis"] = "provider_nominal"
        out[ticker] = frame
    return out


def panel_of(data):
    sleeves = [t for t in ALLOCATION_SLEEVES if t in data]
    return (pd.DataFrame({t: data[t]["Open"] for t in sleeves}), pd.DataFrame({t: data[t]["Close"] for t in sleeves}))


def fill(data, config=PRIMARY):
    return lambda ticker, as_of, quantity: estimate_fill_cost(data[ticker], as_of=as_of, quantity=quantity,
                                                             config=config, split_sessions=()).total


def equity(data, weights, fill_cost=None):
    o, c = panel_of(data)
    return run_portfolio_backtest(o, c, weights, starting_capital=1e5, commission_per_fill=COMMISSION,
                                  fill_cost=fill_cost or fill(data)).equity


def report(data, **changes):
    args = dict(commission_per_fill=COMMISSION, cost_config=PRIMARY, split_sessions={}, seeds=SEEDS) | changes
    return ar.allocation_report(data, **args)


def test_every_series_is_the_spec_046_costed_backtest_of_its_own_weights():
    data = bars()
    result = report(data)
    _, c = panel_of(data)
    rows = decision_sessions(c.index, cadence="monthly")
    selection = allocation_selection(c)
    alloc = ar.series_stats(equity(data, allocation_weights(selection, c, rows)))
    assert result["allocation"] == alloc and alloc["sharpe"] is not None, "Q109 ALLOCATION"
    assert result["buy_and_hold"] == ar.series_stats(equity(data, equal_weight_book(c.notna(), max_gross=1.0).loc[rows])), \
        "Q109 BH"
    degenerate = matched_activity(selection, c, decision_mask=rows)
    assert degenerate["exit_probability"] == 0 and degenerate["initial_probability"] > 0.85, \
        "precondition: a matched chain would reproduce the always-invested allocation"
    draws = random_selections(c, decision_mask=rows, seeds=SEEDS, enter_probability=0.5, exit_probability=0.5,
                              initial_probability=0.5)
    for seed in SEEDS:
        expected = ar.series_stats(equity(data, allocation_weights(draws[seed], c, rows)))
        assert result["random"][seed] == expected, f"Q109 RANDOM {seed}"
    sharpes = [result["random"][s]["sharpe"] for s in SEEDS]
    assert len(set(sharpes)) == len(SEEDS) and alloc["sharpe"] not in sharpes, "Q109 RANDOM distinct"
    assert result["random_dispersion"]["std_sharpe"] == np.std(sharpes, ddof=1), "Q109 DISPERSION"
    assert result["costs"] == {"commission": COMMISSION, "slippage": PRIMARY.as_mapping()}, "Q109 COSTS recorded"
    free = ar.series_stats(equity(data, allocation_weights(selection, c, rows), fill_cost=lambda *_: 0.0))
    assert free != alloc, "precondition: costs move the allocation's statistics"


def test_the_cost_config_passed_is_the_one_applied():
    data = bars(2)
    heavy = CostConfig(role="robustness", impact_coef=2.0)
    primary, robust = report(data), report(data, cost_config=heavy)
    assert robust["allocation"] != primary["allocation"] and robust["costs"]["slippage"] == heavy.as_mapping(), \
        "Q109 COSTS applied"


def test_psr_is_the_probabilistic_sharpe_against_zero_at_n_one():
    data = bars(2)
    _, c = panel_of(data)
    eq = equity(data, allocation_weights(allocation_selection(c), c, decision_sessions(c.index, cadence="monthly")))
    excess = np.log(eq / eq.shift(1)).iloc[1:].to_numpy() - math.log1p(0.0378) / 252
    sr = excess.mean() / excess.std(ddof=1)
    z = excess - excess.mean()
    skew, kurt = (z ** 3).mean() / (z ** 2).mean() ** 1.5, (z ** 4).mean() / (z ** 2).mean() ** 2
    psr = norm.cdf(sr * math.sqrt(len(excess) - 1) / math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
    stats = ar.series_stats(eq)
    assert math.isclose(stats["psr"], psr, rel_tol=1e-9), "Q109 PSR"
    assert math.isclose(stats["sharpe"], sr * math.sqrt(252), rel_tol=1e-12), "Q109 SHARPE"


def test_non_sleeve_tickers_change_nothing():
    data = bars(3)
    assert "QQQ" in data and report(data) == report({t: f for t, f in data.items() if t != "QQQ"}), "Q109 SLEEVES"


def test_refusals():
    late = pd.DatetimeIndex(trading_days(date(2021, 1, 4), date(2023, 10, 2)))
    refused = {}
    for name, call in (("holdout", lambda: report(bars(4, late))),
                       ("label only", lambda: report(bars(4), cost_config={"model": "spread_plus_sqrt_impact"})),
                       ("negative commission", lambda: report(bars(4), commission_per_fill=-1.0)),
                       ("one seed", lambda: report(bars(4), seeds=[1]))):
        try:
            call()
            refused[name] = None
        except (HoldoutSealError, ValueError) as error:
            refused[name] = type(error).__name__
    assert refused == {"holdout": "HoldoutSealError", "label only": "ValueError", "negative commission": "ValueError",
                       "one seed": "ValueError"}, f"Q109 REFUSE {refused}"


def test_render_stamps_first_labels_every_sharpe_and_carries_the_register():
    stamp = ["source: data/cache/EXAMPLE.csv sha256=" + "0" * 64, "commit: unknown"]
    lines = ar.render(report(bars(5)), stamp)
    assert lines[:2] == stamp and lines[2] == ar.LABEL, "Q109 RENDER stamp"
    sharpe = [line for line in lines if "Sharpe" in line]
    assert len(sharpe) == 3 and all(ar.LABEL in line for line in sharpe), "Q109 RENDER label"
    text = "\n".join(lines)
    assert all(f"- {item}" in lines for item in LIMITATIONS) and "spread_plus_sqrt_impact" in text, "Q109 RENDER register"
    assert "folds, purge and embargo do not apply" in text and "rebalanced monthly" in text, "Q109 RENDER disclosure"


def gapped(seed=1):
    """`bars` with 13 SPY bars missing just after DBC lists (rows 205-217): SPY keeps its volatility,
    but the SPY-DBC pair lacks 60 coinciding returns when DBC first becomes eligible, so the
    covariance is undefined there and spec 059 D-6 makes the whole book cash for that month."""
    data = bars(seed)
    spy = data["SPY"].drop(data["SPY"].index[205:218])
    spy.attrs["volume_basis"] = "provider_nominal"
    return data | {"SPY": spy}


def test_a_planted_covariance_gap_is_exactly_one_cash_month_at_its_date():
    result = report(gapped())
    cash = result["cash_months"]
    assert cash["allocation"] == {"count": 1, "dates": ["2020-02-03"]}, f"Q127 CASH allocation {cash['allocation']}"
    _, c = panel_of(gapped())
    rows = decision_sessions(c.index, cadence="monthly")
    weights = allocation_weights(allocation_selection(c), c, rows)
    assert (weights.loc["2020-02-03"] == 0).all() and allocation_selection(c).loc["2020-02-03"].any(), \
        "precondition: the gap month holds an eligible sleeve yet the book is flat"
    assert cash["buy_and_hold"] == {"count": 0, "dates": []}, f"Q127 CASH buy-and-hold {cash['buy_and_hold']}"
    assert set(cash["random"]) == set(SEEDS), "Q127 CASH random seeds"


def test_no_gap_gives_zero_cash_months_for_every_series():
    cash = report(bars())["cash_months"]
    assert cash["allocation"] == {"count": 0, "dates": []}, f"Q127 CASH control allocation {cash['allocation']}"
    assert cash["buy_and_hold"] == {"count": 0, "dates": []}, f"Q127 CASH control buy-and-hold {cash['buy_and_hold']}"
    assert all(v == {"count": 0, "dates": []} for v in cash["random"].values()), f"Q127 CASH control random {cash['random']}"
    assert cash["warmup_rows"] == 2, "precondition: the two warm-up rows (no sleeve eligible) are not D-6 cash months"


def test_cash_months_count_only_flat_rows_that_hold_an_eligible_sleeve():
    index = pd.DatetimeIndex(["2020-01-02", "2020-02-03", "2020-03-02"])
    weights = pd.DataFrame({"SPY": [0.0, 0.0, 0.5], "IEF": [0.0, float("nan"), 0.0]}, index=index)
    required = pd.DataFrame({"SPY": [False, True, True], "IEF": [False, True, False]}, index=index)
    assert ar.cash_months(weights, required) == {"count": 1, "dates": ["2020-02-03"]}, "Q127 CASH unit"


def test_render_prints_the_cash_months():
    stamp = ["source: data/cache/EXAMPLE.csv sha256=" + "0" * 64, "commit: unknown"]
    text = "\n".join(ar.render(report(gapped()), stamp))
    assert "cash months (D-6" in text and "allocation 1 [2020-02-03]" in text and "buy-and-hold 0 []" in text, \
        f"Q127 RENDER cash months: {text}"
