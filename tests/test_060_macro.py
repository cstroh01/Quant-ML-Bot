"""EXAMPLE — NOT A RESULT. Spec 060 FR-003 (queue Q115): point-in-time macro and rates joins.

Every value below is a synthetic fixture, not an observation. Rule 1: a value
joined to session ``d`` must have been public at ``d``'s decision time.
"""

import socket
from datetime import date

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401 -- existing repository import bootstrap
import macro_sources as ms
from mutation_support_019 import killed

D = pd.Timestamp


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def deny_network(*args, **kwargs):
        pytest.fail("Spec 060 tests must not access the network")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(socket.socket, "connect", deny_network)


def alfred(*rows):
    """ALFRED rows in the adapter's shape: (obs date, realtime_start, realtime_end, value)."""
    return pd.DataFrame({
        "date": pd.to_datetime([r[0] for r in rows]),
        "realtime_start": [date.fromisoformat(r[1]) for r in rows],
        "realtime_end": [date.fromisoformat(r[2]) for r in rows],
        "value": [r[3] for r in rows],
    })


OPEN = "9999-12-31"
# January CPI-like print: first released 2024-02-13, revised 2024-03-12.
SERIES = alfred(
    ("2023-12-01", "2024-01-11", OPEN, 3.4),
    ("2024-01-01", "2024-02-13", "2024-03-11", 3.1),
    ("2024-01-01", "2024-03-12", OPEN, 3.2),
)


def test_alfred_value_is_visible_from_the_session_after_its_vintage_start():
    """ALFRED dates availability, not the moment: a vintage starting on d may have been
    released after d's 16:00 decision (WALCL posts Thursdays 16:30 ET), so it is used from
    the next session on (Rule 1 over spec 060 FR-003's "vintage start <= d")."""
    out = ms.alfred_asof(SERIES, [D("2024-02-12"), D("2024-02-13"), D("2024-02-14")])
    assert out[D("2024-02-12")] == 3.4  # January not yet released: December's print carries
    assert out[D("2024-02-13")] == 3.4  # released that day, possibly after the close
    assert out[D("2024-02-14")] == 3.1


def test_alfred_uses_the_vintage_current_on_each_session():
    sessions = [D("2024-03-11"), D("2024-03-12"), D("2024-03-13"), D("2024-06-03")]
    assert list(ms.alfred_asof(SERIES, sessions)) == [3.1, 3.1, 3.2, 3.2]  # revision from 03-13


def test_alfred_first_sessions_before_any_release_are_nan():
    out = ms.alfred_asof(SERIES, [D("2024-01-11"), D("2024-01-12")])
    assert np.isnan(out[D("2024-01-11")]) and out[D("2024-01-12")] == 3.4


def test_alfred_weekly_release_after_the_close_waits_one_session():
    walcl = alfred(("2024-03-06", "2024-03-07", OPEN, 7.5e6))  # posted Thu 2024-03-07 16:30 ET
    out = ms.alfred_asof(walcl, [D("2024-03-07"), D("2024-03-08")])
    assert np.isnan(out[D("2024-03-07")]) and out[D("2024-03-08")] == 7.5e6


def test_alfred_missing_value_does_not_mask_the_last_known_print():
    series = pd.concat([SERIES, alfred(("2024-02-01", "2024-03-13", OPEN, np.nan))])
    assert ms.alfred_asof(series, [D("2024-03-14")])[D("2024-03-14")] == 3.2


def test_alfred_gap_carries_the_last_known_value_across_holidays():
    sessions = [D("2024-02-16"), D("2024-02-20")]  # Presidents Day 2024-02-19 has no session
    assert list(ms.alfred_asof(SERIES, sessions)) == [3.1, 3.1]


def test_alfred_index_is_the_sessions_and_inputs_are_not_mutated():
    before = SERIES.copy(deep=True)
    out = ms.alfred_asof(SERIES, [D("2024-03-12"), D("2024-02-13")])
    assert list(out.index) == [D("2024-03-12"), D("2024-02-13")]
    pd.testing.assert_frame_equal(SERIES, before)


def test_alfred_refuses_aware_sessions():
    with pytest.raises(ValueError, match="naive session labels"):
        ms.alfred_asof(SERIES, [D("2024-02-13", tz="America/New_York")])


def rates(*rows):
    """Normalized daily rates: (record date, published_at instant, 3-month yield)."""
    return pd.DataFrame({
        "date": pd.to_datetime([r[0] for r in rows]),
        "published_at": [D(r[1]) for r in rows],
        "y3m": [r[2] for r in rows],
    })


RATES = rates(
    ("2024-03-07", "2024-03-07 17:45-05:00", 5.37),
    ("2024-03-08", "2024-03-08 17:45-05:00", 5.38),
    ("2024-03-11", "2024-03-11 15:59-04:00", 5.40),  # first session after the DST change
)


def test_rates_published_after_the_close_are_used_from_the_next_session():
    out = ms.published_asof(RATES, [D("2024-03-07"), D("2024-03-08")], ["y3m"])
    assert np.isnan(out.loc[D("2024-03-07"), "y3m"])
    assert out.loc[D("2024-03-08"), "y3m"] == 5.37


def test_rates_published_before_the_close_are_usable_that_session():
    out = ms.published_asof(RATES, [D("2024-03-11")], ["y3m"])
    assert out.loc[D("2024-03-11"), "y3m"] == 5.40


@pytest.mark.parametrize("published, usable", [
    ("2024-03-11 16:00-04:00", True),    # exactly the 16:00 New York decision time
    ("2024-03-11 16:01-04:00", False),
    ("2024-03-11 20:00+00:00", True),    # 16:00 EDT written in UTC
    ("2024-03-11 20:01+00:00", False),
])
def test_rates_decision_time_is_16_00_new_york_inclusive(published, usable):
    frame = rates(("2024-03-11", published, 5.40))
    value = ms.published_asof(frame, [D("2024-03-11")], ["y3m"]).loc[D("2024-03-11"), "y3m"]
    assert (value == 5.40) if usable else np.isnan(value)


def test_rates_a_revision_replaces_the_value_only_once_published():
    frame = pd.concat([RATES, rates(("2024-03-08", "2024-03-12 09:00-04:00", 5.39))])
    out = ms.published_asof(frame, [D("2024-03-11"), D("2024-03-12")], ["y3m"])
    assert out.loc[D("2024-03-11"), "y3m"] == 5.40
    assert out.loc[D("2024-03-12"), "y3m"] == 5.40  # newest record date wins, revised or not
    only_friday = frame.loc[frame["date"] <= D("2024-03-08")]
    out = ms.published_asof(only_friday, [D("2024-03-11"), D("2024-03-12")], ["y3m"])
    assert list(out["y3m"]) == [5.38, 5.39]


def test_rates_refuse_naive_publication_instants_and_aware_sessions():
    naive = RATES.assign(published_at=RATES["published_at"].map(lambda t: t.tz_localize(None)))
    with pytest.raises(ValueError, match="timezone-aware"):
        ms.published_asof(naive, [D("2024-03-11")], ["y3m"])
    with pytest.raises(ValueError, match="naive session labels"):
        ms.published_asof(RATES, [D("2024-03-11", tz="UTC")], ["y3m"])


def test_rates_record_dated_after_the_session_is_never_used():
    frame = rates(("2024-03-12", "2024-03-11 09:00-04:00", 9.99))  # a forward-dated record
    assert np.isnan(ms.published_asof(frame, [D("2024-03-11")], ["y3m"]).loc[D("2024-03-11"), "y3m"])


# --- Rule 12 planted defects (spec 060 §6: an ALFRED value used before its vintage) ---

def oracle_vintage_start():
    test_alfred_value_is_visible_from_the_session_after_its_vintage_start()


def oracle_close():
    test_rates_published_after_the_close_are_used_from_the_next_session()
    test_rates_decision_time_is_16_00_new_york_inclusive("2024-03-11 16:01-04:00", False)


@pytest.mark.parametrize("old, new, oracle", [
    # A vintage is used on its own start date, possibly before it was released (the
    # spec's literal "vintage start <= d" at a 16:00 decision).
    ("known_by = day - pd.Timedelta(days=1)", "known_by = day", oracle_vintage_start),
    # Rates are joined at end of day instead of the 16:00 decision time.
    ("DECISION_TIME = time(16, 0)", "DECISION_TIME = time(23, 59)", oracle_close),
], ids=["vintage-start", "close-time"])
def test_planted_defects_are_killed(old, new, oracle):
    killed(ms, old, new, oracle)
