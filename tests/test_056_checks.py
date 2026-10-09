"""Spec 056 U2/U3: cross-source checks and EDGAR as-of selection. EXAMPLE — NOT A RESULT."""
from datetime import date, datetime, timezone

import pandas as pd
import pytest

import context  # noqa: F401
from data_sources import close_mismatches, facts_as_of

IDX = pd.to_datetime(["2026-10-05", "2026-10-06", "2026-10-07"])


def test_agreeing_sources_have_no_mismatch():
    a = pd.Series([100.0, 101.0, 102.0], index=IDX)
    assert close_mismatches(a, a * (1 + 1e-6), tolerance_bps=1.0).empty


def test_mismatch_is_reported_never_averaged():
    a = pd.Series([100.0, 101.0, 102.0], index=IDX)
    b = pd.Series([100.0, 103.0, 102.0], index=IDX)
    out = close_mismatches(a, b, tolerance_bps=5.0)
    assert list(out.index) == [pd.Timestamp("2026-10-06")]
    assert out.iloc[0]["primary"] == 101.0 and out.iloc[0]["check"] == 103.0


def test_session_missing_from_either_source_is_a_mismatch():
    a = pd.Series([100.0, 101.0, 102.0], index=IDX)
    b = pd.Series([100.0, 102.0], index=IDX[[0, 2]])
    out = close_mismatches(a, b, tolerance_bps=5.0)
    assert list(out.index) == [pd.Timestamp("2026-10-06")] and pd.isna(out.iloc[0]["check"])


def fact(value, end, filed):
    return {"val": value, "end": end, "filed": filed, "form": "10-Q", "accn": f"acc-{filed}"}


def test_fact_is_invisible_before_its_filed_date():
    facts = [fact(10, "2026-06-30", "2026-08-01")]
    assert facts_as_of(facts, date(2026, 7, 31)) == []
    assert [f["val"] for f in facts_as_of(facts, date(2026, 8, 1))] == [10]


def test_restatement_does_not_overwrite_the_originally_filed_value_before_its_own_filing():
    facts = [fact(10, "2026-06-30", "2026-08-01"), fact(12, "2026-06-30", "2026-11-01")]
    assert [f["val"] for f in facts_as_of(facts, date(2026, 9, 1))] == [10]
    assert [f["val"] for f in facts_as_of(facts, date(2026, 11, 2))] == [12]


def test_missing_filed_date_refuses():
    with pytest.raises(ValueError, match="filed"):
        facts_as_of([{"val": 1, "end": "2026-06-30"}], date(2026, 9, 1))


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), 0.0, -5.0, float("nan")])
@pytest.mark.parametrize("side", ["primary", "check"])
def test_non_finite_or_non_positive_close_is_a_mismatch(bad, side):
    a = pd.Series([100.0, 101.0, 102.0], index=IDX)
    b = a.copy()
    (a if side == "primary" else b).iloc[1] = bad
    assert list(close_mismatches(a, b, tolerance_bps=5.0).index) == [pd.Timestamp("2026-10-06")]


@pytest.mark.parametrize("tolerance", [float("nan"), float("inf"), -1.0])
def test_invalid_tolerance_refuses(tolerance):
    a = pd.Series([100.0], index=IDX[:1])
    with pytest.raises(ValueError, match="tolerance"):
        close_mismatches(a, a * 2, tolerance_bps=tolerance)


def test_facts_with_the_same_end_but_different_start_are_separate_periods():
    q3 = {"val": 5, "start": "2026-04-01", "end": "2026-06-30", "filed": "2026-08-01", "form": "10-Q"}
    ytd = {"val": 9, "start": "2026-01-01", "end": "2026-06-30", "filed": "2026-08-01", "form": "10-Q"}
    instant = {"val": 50, "end": "2026-06-30", "filed": "2026-08-01", "form": "10-Q"}
    assert sorted(f["val"] for f in facts_as_of([q3, ytd, instant], date(2026, 8, 2))) == [5, 9, 50]


def test_both_sources_infinite_is_a_mismatch_not_agreement():
    a = pd.Series([100.0, float("inf"), 102.0], index=IDX)
    assert list(close_mismatches(a, a.copy(), tolerance_bps=5.0).index) == [pd.Timestamp("2026-10-06")]
