"""EXAMPLE — NOT A RESULT. Spec 035 U1 contracts: pure dividend reconciler (T005/T006)."""

import socket

import pandas as pd
import pytest

import context  # noqa: F401 -- existing repository import bootstrap
import corporate_actions as ca
from mutation_support_019 import killed

# Spec 035 §8 D-2 (recorded 2026-10-09): absolute $0.0001 per share, per-share basis.
TOL, BASIS = 0.0001, "per_share"
# Fri 2024-01-05 to Mon 2024-01-08 is one session across a weekend (Rule 5 gap edge).
BEFORE, START, MID, END, AFTER = (
    pd.Timestamp(d) for d in ("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08")
)
COVERAGE = (START, END)
FAILED = "dividend reconciliation failed"


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    """FR-009: any socket use fails the test."""
    def deny_network(*args, **kwargs):
        pytest.fail("Spec 035 tests must not access the network")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(socket.socket, "connect", deny_network)


def divs(*rows, basis=BASIS, extra=()):
    """Actions table: (date, amount) dividends plus any ``extra`` full rows."""
    frame = [{"Date": d, "Ticker": "AAPL", "Action_Type": "dividend", "Value": v,
              "Amount_Basis": basis} for d, v in rows]
    return pd.DataFrame([*frame, *extra])


def run(primary, second, coverage=COVERAGE):
    return ca.reconcile_dividends(primary, second, coverage, amount_tolerance=TOL,
                                  amount_basis=BASIS)


def status(result, date):
    row = result.loc[result["Date"].eq(date)]
    assert len(row) == 1, f"expected exactly one row for {date.date()}"
    return row["Reconciliation_Status"].item(), row["Reconciliation_Reason"].item()


def test_fr009_guard_fails_a_socket_open():
    with pytest.raises(pytest.fail.Exception, match="must not access the network"):
        socket.create_connection(("127.0.0.1", 9))


def test_union_sweep_gives_one_row_per_ex_date_in_either_source():
    split = {"Date": MID, "Ticker": "AAPL", "Action_Type": "split", "Value": 4.0}
    result = run(divs((START, 0.24), (MID, 0.25), extra=[split]), divs((START, 0.24), (END, 0.26)))
    assert list(result["Date"]) == [START, MID, END]
    assert status(result, START) == (ca.RECONCILED, None)
    assert status(result, MID) == (ca.MISMATCH, "primary only")
    assert status(result, END) == (ca.MISMATCH, "second source only")


def test_coverage_edges_are_inclusive_and_neighbours_are_unreconciled():
    both = [(BEFORE, 0.2), (START, 0.2), (END, 0.2), (AFTER, 0.2)]
    result = run(divs(*both), divs(*both))
    assert status(result, START) == (ca.RECONCILED, None)
    assert status(result, END) == (ca.RECONCILED, None)
    assert status(result, BEFORE) == (ca.UNRECONCILED, "outside second-source coverage")
    assert status(result, AFTER) == (ca.UNRECONCILED, "outside second-source coverage")


def test_empty_coverage_makes_every_dividend_unreconciled():
    result = run(divs((START, 0.2)), divs((START, 0.2), (MID, 0.3)), coverage=None)
    assert set(result["Reconciliation_Status"]) == {ca.UNRECONCILED}
    assert len(result) == 2
    ca.assert_no_mismatch(result)


def test_ex_dates_one_session_apart_are_mismatches():
    result = run(divs((END, 0.2)), divs((MID, 0.2)))
    assert status(result, MID)[0] == ca.MISMATCH
    assert status(result, END)[0] == ca.MISMATCH


@pytest.mark.parametrize("mine, theirs, expected", [
    # Exactly one $0.0001 tick is inside for every amount (0.24 is the float-noise case).
    (0.24, 0.2401, ca.RECONCILED), (0.24, 0.2399, ca.RECONCILED), (0.3, 0.3001, ca.RECONCILED),
    (0.24, 0.24015, ca.MISMATCH), (0.24, 0.2402, ca.MISMATCH), (0.24, 0.2398, ca.MISMATCH),
    (0.24, float("nan"), ca.MISMATCH), (0.24, None, ca.MISMATCH),
])
def test_amount_tolerance_is_d2(mine, theirs, expected):
    assert ca.DIVIDEND_AMOUNT_TOLERANCE == TOL and ca.DIVIDEND_AMOUNT_BASIS == BASIS
    assert status(run(divs((MID, mine)), divs((MID, theirs))), MID)[0] == expected


def test_intraday_labels_normalize_to_their_session():
    result = run(divs((MID, 0.24)), divs((MID + pd.Timedelta(hours=16), 0.24)),
                 coverage=(START + pd.Timedelta(hours=9), END))
    assert status(result, MID) == (ca.RECONCILED, None)


@pytest.mark.parametrize("basis", [None, float("nan"), "per_adr"])
def test_unstated_amount_basis_is_unreconciled_with_reason(basis):
    result = run(divs((MID, 0.24)), divs((MID, 0.24), basis=basis))
    assert status(result, MID) == (ca.UNRECONCILED, "amount basis not stated as per_share")
    no_column = divs((MID, 0.24)).drop(columns="Amount_Basis")
    assert status(run(no_column, divs((MID, 0.24))), MID)[0] == ca.UNRECONCILED


def test_aware_dates_are_refused():
    aware = divs((MID.tz_localize("America/New_York"), 0.24))
    with pytest.raises(ValueError, match="naive session labels"):
        run(aware, divs((MID, 0.24)))


def test_inputs_are_not_mutated():
    primary, second = divs((START, 0.2), (MID, 0.3)), divs((MID, 0.3001), (END, 0.4))
    before = primary.copy(deep=True), second.copy(deep=True)
    run(primary, second)
    pd.testing.assert_frame_equal(primary, before[0])
    pd.testing.assert_frame_equal(second, before[1])


def test_assert_no_mismatch_names_each_mismatched_ex_date():
    result = run(divs((START, 0.2), (MID, 0.2)), divs((START, 0.2), (END, 0.2)))
    with pytest.raises(ValueError, match=f"{FAILED}: mismatch on 2024-01-04, 2024-01-05$"):
        ca.assert_no_mismatch(result)
    ca.assert_no_mismatch(run(divs((START, 0.2)), divs((START, 0.2))))


def expect_refusal(primary, second, named):
    try:
        ca.assert_no_mismatch(run(primary, second))
    except ValueError as error:
        assert FAILED in str(error) and named in str(error), str(error)
    else:
        raise AssertionError("dividend reconciliation did not refuse")


def oracle_m3():
    assert status(run(divs((BEFORE, 0.2)), divs((BEFORE, 0.2))), BEFORE)[0] == ca.UNRECONCILED
    assert status(run(divs((START, 0.2)), divs((START, 0.2))), START)[0] == ca.RECONCILED


def oracle_m4():
    expect_refusal(divs((END, 0.2)), divs((MID, 0.2)), "2024-01-04")
    ca.assert_no_mismatch(run(divs((MID, 0.2)), divs((MID, 0.2))))


def oracle_m5():
    expect_refusal(divs((START, 0.2)), divs((START, 0.2), (MID, 0.3)), "2024-01-04")
    ca.assert_no_mismatch(run(divs((START, 0.2), (MID, 0.3)), divs((START, 0.2), (MID, 0.3))))


@pytest.mark.parametrize("old, new, oracle", [
    # M3: coverage start comparison shifted by one session.
    ("coverage[0] <= date", "coverage[0] - pd.offsets.BDay(1) <= date", oracle_m3),
    # M4: the matcher accepts an ex-date one session either side.
    ("return table.get(date)", "return table.get(date) or table.get(date - pd.offsets.BDay(1))"
     " or table.get(date + pd.offsets.BDay(1))", oracle_m4),
    # M5: the sweep iterates the primary's dividends only.
    ("sorted(first.keys() | other.keys())", "sorted(first.keys())", oracle_m5),
], ids=["M3", "M4", "M5"])
def test_planted_defects_are_killed(old, new, oracle):
    killed(ca, old, new, oracle)
