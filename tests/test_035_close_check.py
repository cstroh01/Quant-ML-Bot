"""EXAMPLE — NOT A RESULT. Spec 035 U2 contracts: nominal `Close` cross-check (T007/T008).

Rule 12 field statement: every refusal fixture below perturbs `Close` and only
`Close`, because that is the column a dividend-adjusted basis moves (spec 035
FR-005, M1) and the only column `cross_check_close` is specified to read.
`Open`, `High`, `Low` and `Volume` stay identical across sources, so a check
that read any other column would pass every refusal fixture and go red.
"""

import socket

import pandas as pd
import pytest

import context  # noqa: F401 -- existing repository import bootstrap
import corporate_actions as ca
from mutation_support_019 import killed

# Spec 035 §8 D-2 (recorded 2026-10-09): `Close` tolerance relative 1e-3.
TOL = 1e-3
FAILED = "close cross-check failed"
# Sessions around MLK Day 2024-01-15 (an NYSE holiday): Fri 12th, Tue 16th.
S = [pd.Timestamp(d) for d in (
    "2024-01-10", "2024-01-11", "2024-01-12", "2024-01-16", "2024-01-17", "2024-01-18",
)]
COVERAGE = (S[1], S[4])
BASE = 100.0
COLUMNS = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    """FR-009: any socket use fails the test."""
    def deny_network(*args, **kwargs):
        pytest.fail("Spec 035 tests must not access the network")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(socket.socket, "connect", deny_network)


def bars(dates=S, close=None):
    """Tidy bars; ``close`` maps a session to its `Close`, every other column fixed."""
    close = close or {}
    return pd.DataFrame(columns=COLUMNS, data=[{
        "Date": d, "Ticker": "AAPL", "Open": BASE, "High": BASE + 2, "Low": BASE - 2,
        "Close": close.get(d, BASE), "Volume": 1_000_000,
    } for d in dates])


def run(primary, second, coverage=COVERAGE):
    return ca.cross_check_close(primary, second, coverage, close_tolerance=TOL)


def refuses(primary, second, named, coverage=COVERAGE):
    """Assert the cross-check refuses with its own message naming ``named``."""
    try:
        run(primary, second, coverage)
    except ValueError as error:
        assert FAILED in str(error) and named in str(error), str(error)
    else:
        raise AssertionError("close cross-check did not refuse")


def test_fr009_guard_fails_a_socket_open():
    with pytest.raises(pytest.fail.Exception, match="must not access the network"):
        socket.create_connection(("127.0.0.1", 9))


def test_d2_tolerance_is_recorded_value():
    assert ca.CLOSE_RELATIVE_TOLERANCE == TOL


def test_identical_bars_pass_and_count_covered_sessions():
    assert run(bars(), bars()) == 4  # S[1]..S[4]; the holiday is in neither source


def test_session_only_in_primary_refuses():
    refuses(bars(), bars([d for d in S if d != S[2]]), "2024-01-12")


def test_session_only_in_second_source_refuses():
    refuses(bars([d for d in S if d != S[3]]), bars(), "2024-01-16")


@pytest.mark.parametrize("second_close, ok", [
    (BASE * (1 + 0.9e-3), True), (BASE * (1 - 0.9e-3), True),
    (BASE * (1 + 1.1e-3), False), (BASE * (1 - 1.1e-3), False),
    (BASE + 0.1, True),  # exactly 1e-3 relative is inside (inclusive)
    (float("nan"), False),
])
def test_relative_close_tolerance_is_d2(second_close, ok):
    second = bars(close={S[2]: second_close})
    if ok:
        assert run(bars(), second) == 4
    else:
        refuses(bars(), second, "2024-01-12")


def test_refusal_names_the_first_offending_session():
    primary = bars([d for d in S if d != S[4]], close={S[3]: BASE * 1.01})
    with pytest.raises(ValueError, match=f"^{FAILED}: 2024-01-16 "):
        run(primary, bars(close={S[2]: BASE}))
    # A one-sided session earlier than a tolerance breach is named first.
    with pytest.raises(ValueError, match=f"^{FAILED}: 2024-01-11 "):
        run(bars([d for d in S if d != S[1]], close={S[3]: BASE * 1.01}), bars())


def test_sessions_outside_coverage_are_ignored():
    off = {S[0]: BASE * 2, S[5]: BASE * 2}
    assert run(bars(close=off), bars()) == 4
    assert run(bars(S[1:5]), bars()) == 4  # primary lacks both out-of-coverage sessions


def test_first_and_last_covered_sessions_are_checked():
    refuses(bars(close={S[1]: BASE * 1.01}), bars(), "2024-01-11")
    refuses(bars(close={S[4]: BASE * 1.01}), bars(), "2024-01-17")


def test_holiday_absent_from_both_sources_is_not_a_gap():
    coverage = (pd.Timestamp("2024-01-12"), pd.Timestamp("2024-01-16"))
    assert run(bars(), bars(), coverage) == 2


def test_no_coverage_checks_nothing():
    assert run(bars(close={S[2]: BASE * 2}), bars([]), None) == 0


def test_intraday_labels_normalize_to_their_session():
    second = bars().assign(Date=lambda f: f["Date"] + pd.Timedelta(hours=16))
    assert run(bars(), second, (S[1] + pd.Timedelta(hours=9), S[4])) == 4


@pytest.mark.parametrize("which", ["primary", "second"])
def test_aware_dates_are_refused(which):
    aware = bars().assign(Date=lambda f: f["Date"].dt.tz_localize("America/New_York"))
    args = (aware, bars()) if which == "primary" else (bars(), aware)
    with pytest.raises(ValueError, match="naive session labels"):
        run(*args)


def test_aware_coverage_is_refused():
    with pytest.raises(ValueError, match="naive session labels"):
        run(bars(), bars(), (S[1].tz_localize("UTC"), S[4]))


def test_duplicate_sessions_are_refused():
    with pytest.raises(ValueError, match="duplicate"):
        run(bars([*S, S[2]]), bars())


def test_inputs_are_not_mutated():
    primary, second = bars(close={S[0]: 1.0}), bars()
    before = primary.copy(deep=True), second.copy(deep=True)
    run(primary, second)
    pd.testing.assert_frame_equal(primary, before[0])
    pd.testing.assert_frame_equal(second, before[1])


def oracle_close_only():
    """Perturb only `Close` (a 1% dividend-basis gap); the check must refuse."""
    run(bars(), bars())  # control: identical bars pass
    refuses(bars(close={S[2]: BASE * 0.99}), bars(), "2024-01-12")


def oracle_union():
    run(bars(), bars())
    refuses(bars([d for d in S if d != S[3]]), bars(), "2024-01-16")


@pytest.mark.parametrize("old, new, oracle", [
    # T007 Rule 12: the comparison reads `Open` instead of `Close`.
    ('frame["Close"]', 'frame["Open"]', oracle_close_only),
    # The sweep compares the primary's sessions only (second-source-only bars pass).
    ("sorted(mine.keys() | theirs.keys())", "sorted(mine.keys())", oracle_union),
], ids=["open-for-close", "primary-only-sweep"])
def test_planted_defects_are_killed(old, new, oracle):
    killed(ca, old, new, oracle)
