"""Spec 052 U2/U3: research and executable eligibility with reasons. EXAMPLE — NOT A RESULT."""
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

import context  # noqa: F401
from asset_registry import ExecutableQuote, EligibilityLimits, executable_eligibility, research_eligibility

LIM = EligibilityLimits(min_sessions=5, min_price=5.0, min_median_dollar_volume=1_000_000.0,
                        max_spread_bps=50.0, max_participation=0.01)


def bars(close=20.0, volume=100_000, n=8, end="2026-10-07"):
    idx = pd.bdate_range(end=end, periods=n)
    return pd.DataFrame({"Close": [close] * n, "Volume": [volume] * n}, index=idx)


def test_eligible_name_has_no_reasons():
    assert research_eligibility(bars(), as_of=date(2026, 10, 7), limits=LIM, actions_reconciled=True,
                                basis_known=True) == []


@pytest.mark.parametrize("frame,kw,reason", [
    (bars(n=3), {}, "insufficient_history"),
    (bars(close=4.0, volume=1_000_000), {}, "price_below_floor"),
    (bars(volume=1_000), {}, "illiquid"),
    (bars(), {"actions_reconciled": False}, "corporate_actions_unreconciled"),
    (bars(), {"basis_known": False}, "price_basis_unknown"),
])
def test_each_failure_names_its_reason(frame, kw, reason):
    args = dict(actions_reconciled=True, basis_known=True) | kw
    assert reason in research_eligibility(frame, as_of=date(2026, 10, 7), limits=LIM, **args)


def test_rows_after_as_of_are_ignored():
    future_spike = bars(volume=1_000, n=8, end="2026-10-07")
    future_spike.loc[pd.Timestamp("2026-10-08")] = [20.0, 10_000_000]
    assert "illiquid" in research_eligibility(future_spike, as_of=date(2026, 10, 7), limits=LIM,
                                              actions_reconciled=True, basis_known=True)


NOW = datetime(2026, 10, 8, 13, 25, tzinfo=timezone.utc)


def quote(**extra):
    values = dict(tradable=True, halted=False, last_bar_session=date(2026, 10, 7), instrument_class="us_equity",
                  spread_bps=10.0, adv_shares=100_000.0, min_notional_usd=1.0, quoted_at=NOW - timedelta(seconds=5))
    values.update(extra)
    return ExecutableQuote(**values)


def test_executable_ok_and_each_refusal():
    kw = dict(previous_session=date(2026, 10, 7), allowed_classes=("us_equity", "etf"), order_qty=500, order_notional=10_000.0, limits=LIM,
              now=NOW, max_quote_age_seconds=60)
    assert executable_eligibility(quote(), **kw) == []
    assert executable_eligibility(quote(tradable=False), **kw) == ["not_tradable"]
    assert executable_eligibility(quote(halted=True), **kw) == ["halted"]
    assert executable_eligibility(quote(last_bar_session=date(2026, 10, 6)), **kw) == ["stale_bar"]
    assert executable_eligibility(quote(instrument_class="option"), **kw) == ["class_not_permitted"]
    assert executable_eligibility(quote(spread_bps=80.0), **kw) == ["spread_too_wide"]
    assert executable_eligibility(quote(adv_shares=10_000.0), **kw) == ["participation_too_high"]
    assert executable_eligibility(quote(min_notional_usd=50_000.0), **kw) == ["below_broker_minimum"]


def test_a_future_price_cannot_lift_a_name_over_the_floor():
    frame = bars(close=4.0, volume=1_000_000)
    frame.loc[pd.Timestamp("2026-10-08")] = [50.0, 1_000_000]
    assert "price_below_floor" in research_eligibility(frame, as_of=date(2026, 10, 7), limits=LIM,
                                                       actions_reconciled=True, basis_known=True)


KW = dict(previous_session=date(2026, 10, 7), allowed_classes=("us_equity", "etf"), order_qty=500,
          order_notional=10_000.0, limits=LIM, now=NOW, max_quote_age_seconds=60)
NAN = float("nan")


@pytest.mark.parametrize("change,reason", [
    (dict(spread_bps=NAN), "spread_unknown"), (dict(adv_shares=NAN), "adv_unknown"),
    (dict(min_notional_usd=NAN), "broker_minimum_unknown"),
    (dict(quoted_at=NOW - timedelta(seconds=61)), "stale_quote"),
    (dict(quoted_at=NOW + timedelta(seconds=1)), "stale_quote"),
    (dict(quoted_at=datetime(2026, 10, 8, 13, 25)), "stale_quote"),
])
def test_unknown_or_stale_quote_fields_fail_closed(change, reason):
    assert reason in executable_eligibility(quote(**change), **KW)


@pytest.mark.parametrize("change", [dict(order_qty=NAN), dict(order_notional=NAN), dict(order_qty=-1.0)])
def test_invalid_order_fails_closed(change):
    assert "order_invalid" in executable_eligibility(quote(), **(KW | change))


@pytest.mark.parametrize("column,reason", [("Close", "price_below_floor"), ("Volume", "illiquid")])
def test_nan_bars_fail_closed(column, reason):
    frame = bars()
    frame.loc[frame.index[-1], column] = NAN
    assert reason in research_eligibility(frame, as_of=date(2026, 10, 7), limits=LIM, actions_reconciled=True,
                                          basis_known=True)


@pytest.mark.parametrize("change", [dict(max_participation=NAN), dict(max_participation=0.0),
                                    dict(max_participation=1.5), dict(max_spread_bps=NAN),
                                    dict(min_price=float("inf")), dict(min_median_dollar_volume=-1.0),
                                    dict(min_sessions=0), dict(min_sessions=5.5)])
def test_invalid_limits_refuse_at_construction(change):
    values = dict(min_sessions=5, min_price=5.0, min_median_dollar_volume=1_000_000.0,
                  max_spread_bps=50.0, max_participation=0.01) | change
    with pytest.raises(ValueError):
        EligibilityLimits(**values)


def test_valid_cap_still_refuses_high_participation():
    assert executable_eligibility(quote(adv_shares=10_000.0), **KW) == ["participation_too_high"]


@pytest.mark.parametrize("bad", [float("inf"), -1.0])
def test_one_infinite_or_negative_volume_in_the_window_fails_closed(bad):
    frame = bars(volume=1_000_000.0, n=20)
    frame.loc[frame.index[5], "Volume"] = bad
    assert "illiquid" in research_eligibility(frame, as_of=date(2026, 10, 7), limits=LIM,
                                              actions_reconciled=True, basis_known=True)
    clean = bars(volume=1_000_000, n=20)
    assert research_eligibility(clean, as_of=date(2026, 10, 7), limits=LIM, actions_reconciled=True,
                                basis_known=True) == []
