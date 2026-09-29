"""EXAMPLE — NOT A RESULT. Offline Spec 041 policy and bundle contracts."""

from dataclasses import replace
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import socket
import tempfile

import pandas as pd
import pytest

import context  # noqa: F401 -- existing repository import bootstrap
import data
from backtest_harness import run_backtest
from unadjusted_fixtures import publish_bundle, session_prices


START, END = date(2024, 1, 2), date(2024, 1, 5)
MISSING_PAY = "dividend payment date missing"
BAD_BASIS = "dividend pay-date basis missing or invalid"
BAD_VALUE = "action values must be finite and positive"


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def deny_network(*args, **kwargs):
        pytest.fail("Spec 041 tests must not access the network")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(socket.socket, "connect", deny_network)


def dividend_actions(**changes):
    return pd.DataFrame([{
        "Date": pd.Timestamp("2024-01-04"), "Ticker": "AAPL",
        "Action_Type": "dividend", "Value": 0.5,
        "Dividend_Pay_Date": pd.Timestamp("2024-01-05"),
        "Dividend_Pay_Date_Basis": "sourced", **changes,
    }])


def contract_bundle(root, actions, *, version=2, policy="sourced"):
    """Plant action defects in a temporary bundle with matching integrity hashes.

    The writer first receives a valid sourced row. Replacing only the actions
    payload and its hash lets the loader reach the intended semantic check.
    Explicit version-1 fixtures retain the old CSV schema regardless of the
    current writer version; production bundles are never edited.
    """
    prices = session_prices("AAPL", START, END, [100.0] * 4)
    path = publish_bundle(root, "AAPL", prices, dividend_actions())
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["manifest_version"] = version
    manifest.pop("dividend_pay_date_bound_source", None)
    if policy is None:
        manifest.pop("dividend_pay_date_policy", None)
    else:
        manifest["dividend_pay_date_policy"] = policy
    if version == 1:
        actions = actions.drop(columns="Dividend_Pay_Date_Basis", errors="ignore")
    action_path = root / manifest["corporate_actions_file"]
    actions.to_csv(action_path, index=False)
    manifest["corporate_actions_sha256"] = hashlib.sha256(action_path.read_bytes()).hexdigest()
    manifest["corporate_actions_row_count"] = len(actions)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


RULE_CASES = [
    ("sourced-valid", {}, None),
    ("sourced-same-day", {"Dividend_Pay_Date": pd.Timestamp("2024-01-04")}, None),
    ("sourced-null", {"Dividend_Pay_Date": pd.NaT}, MISSING_PAY),
    ("bound-null", {"Dividend_Pay_Date": pd.NaT, "Dividend_Pay_Date_Basis": "bound"}, None),
    ("bound-with-vendor-date", {"Dividend_Pay_Date_Basis": "bound"},
     "bound dividend must not have a payment date"),
    ("missing-basis", {"Dividend_Pay_Date_Basis": None}, BAD_BASIS),
    ("invalid-basis", {"Dividend_Pay_Date_Basis": "invented"}, BAD_BASIS),
    ("missing-basis-column", {}, "missing columns ['Dividend_Pay_Date_Basis']"),
    ("zero-value", {"Value": 0.0}, BAD_VALUE),
    ("negative-value", {"Value": -0.5}, BAD_VALUE),
    ("nonfinite-value", {"Value": float("inf")}, BAD_VALUE),
    ("nan-value", {"Value": float("nan")}, BAD_VALUE),
    ("nonnumeric-value", {"Value": "invalid"}, "Value must be numeric"),
    ("ex-date-outside-sessions", {"Date": pd.Timestamp("2024-01-06")},
     "action has no price session"),
    ("ex-date-timezone", {"Date": pd.Timestamp("2024-01-04", tz="UTC")},
     "corporate-actions ex-date check failed: Date session labels must be timezone-naive"),
    ("pay-date-timezone", {"Dividend_Pay_Date": pd.Timestamp("2024-01-05", tz="UTC")},
     "payment-date check failed: sessions must be timezone-naive"),
    ("pay-date-before-ex", {"Dividend_Pay_Date": pd.Timestamp("2024-01-03")},
     "payment precedes ex-date"),
    ("pay-date-weekend", {"Dividend_Pay_Date": pd.Timestamp("2024-01-06")},
     "payment is not a market session"),
    ("duplicate", {}, "duplicate action row"),
    ("wrong-ticker", {"Ticker": "MSFT"}, "expected only AAPL"),
    ("unknown-type", {"Action_Type": "spinoff"}, "expected split or dividend"),
    ("split-payment", {"Action_Type": "split", "Dividend_Pay_Date_Basis": None},
     "split must not have a payment date"),
    ("split-basis", {"Action_Type": "split", "Dividend_Pay_Date": pd.NaT},
     "split must not have a pay-date basis"),
]


@pytest.mark.parametrize("policy", ["sourced", "unbounded"])
@pytest.mark.parametrize("case, changes, error", RULE_CASES, ids=[case[0] for case in RULE_CASES])
def test_v2_action_rule_table(tmp_path, policy, case, changes, error):
    actions = dividend_actions(**changes)
    if case == "missing-basis-column":
        actions = actions.drop(columns="Dividend_Pay_Date_Basis")
    elif case == "duplicate":
        actions = pd.concat([actions, actions], ignore_index=True)
    elif case == "bound-null" and policy == "sourced":
        error = MISSING_PAY
    path = contract_bundle(tmp_path, actions, policy=policy)
    if error is not None:
        with pytest.raises(ValueError, match=re.escape(error)):
            data.load_unadjusted_market_data(path)
    else:
        frame = data.load_unadjusted_market_data(path)
        row = frame.loc[frame["Dividend"].gt(0)].iloc[0]
        assert row["Dividend_Pay_Date_Basis"] == actions.iloc[0]["Dividend_Pay_Date_Basis"]
        if case == "bound-null":
            assert row["Dividend_Pay_Date"] > frame["Date"].max()
        else:
            assert row["Dividend_Pay_Date"] == actions.iloc[0]["Dividend_Pay_Date"]


@pytest.mark.parametrize("missing, policy", [(False, None), (True, None), (True, "unbounded")])
def test_v1_stays_strict_with_or_without_a_policy_field(tmp_path, missing, policy):
    actions = dividend_actions()
    if missing:
        actions["Dividend_Pay_Date"] = pd.NaT
    path = contract_bundle(tmp_path, actions, version=1, policy=policy)
    if missing:
        with pytest.raises(ValueError, match=MISSING_PAY):
            data.load_unadjusted_market_data(path)
    else:
        frame = data.load_unadjusted_market_data(path)
        assert frame.attrs["price_basis"] == "unadjusted_dollars"
        assert frame.loc[2, "Dividend_Pay_Date"] == pd.Timestamp("2024-01-05")


def synthetic_history():
    """EXAMPLE — NOT A RESULT: same-day split/dividend and final-session dividend."""
    history = session_prices("AAPL", START, END, [100.0, 100.0, 50.0, 50.0])
    history = history.drop(columns="Ticker").set_index("Date")
    history["Dividends"] = [0.0, 0.0, 0.5, 0.25]
    history["Stock Splits"] = [0.0, 0.0, 2.0, 0.0]
    return history


def fake_adapter(history, calls):
    class FakeTicker:
        def history(self, **kwargs):
            calls.append(kwargs)
            return history.copy()

    def ticker_factory(ticker):
        assert ticker == "AAPL"
        return FakeTicker()

    return data.YFinanceUnadjustedAdapter(ticker_factory=ticker_factory)


def download(root, adapter):
    return data.download_unadjusted_market_data(
        "AAPL", START, END, created_by_revision="spec-041-synthetic",
        cache_dir=root, adapter=adapter,
    )


def test_offline_download_load_and_funded_backtest(tmp_path):
    calls = []
    adapter = fake_adapter(synthetic_history(), calls)
    path = download(tmp_path, adapter)
    assert calls == [{"start": "2024-01-02", "end": "2024-01-06",
                      "interval": "1d", "auto_adjust": False, "actions": True}]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 2
    assert manifest["dividend_pay_date_policy"] == "unbounded"
    actions = pd.read_csv(tmp_path / manifest["corporate_actions_file"])
    dividends = actions.loc[actions["Action_Type"].eq("dividend")]
    assert len(dividends) == 2
    assert dividends["Dividend_Pay_Date"].isna().all()
    assert dividends["Dividend_Pay_Date_Basis"].tolist() == ["bound", "bound"]
    splits = actions.loc[actions["Action_Type"].eq("split")]
    assert len(splits) == 1
    assert splits["Dividend_Pay_Date_Basis"].isna().all()

    frame = data.load_unadjusted_market_data(path)
    assert frame.attrs["price_basis"] == "unadjusted_dollars"
    assert frame.attrs["dividend_pay_date_policy"] == "unbounded"
    assert frame.attrs["dividend_pay_date_bound_source"] is None
    assert (frame.attrs["dividends_bound"], frame.attrs["dividends_sourced"]) == (2, 0)
    assert frame.attrs["capital_gate_eligible"] is False
    assert tuple(manifest["source_limitations"]) == frame.attrs["source_limitations"]
    bound = frame.loc[frame["Dividend"].gt(0)]
    assert bound["Dividend_Pay_Date_Basis"].tolist() == ["bound", "bound"]
    assert (bound["Dividend_Pay_Date"] > frame["Date"].max()).all()
    frame["Buy_Next_Open"] = [True, False, False, False]
    frame["Sell_Next_Open"] = False
    trades = run_backtest(frame, starting_capital=101.0, commission_per_trade=1.0,
                          slippage_bps=0.0, liquidate=False)
    events = trades.attrs["ledger"]
    paid = events.loc[events["Event"].eq("dividend")]
    assert paid["Pay_Date_Basis"].tolist() == ["bound", "bound"]
    assert "payment" not in events["Event"].tolist()
    final = events.iloc[-1]
    assert final["Receivable"] == 1.5
    assert final["Cash"] == final["Buying_Power"] == 0.0
    assert final["Equity"] == final["Cash"] + 2 * 50.0 + final["Receivable"]


@pytest.mark.parametrize("defect, exception, message", [
    ("empty", RuntimeError, "yfinance provisional source returned no rows for AAPL"),
    ("missing-session", ValueError, "session-contiguity check failed"),
    ("ex-date-outside-sessions", ValueError, "action has no price session"),
])
def test_failed_download_writes_nothing(tmp_path, defect, exception, message):
    history = synthetic_history()
    if defect == "empty":
        history = history.iloc[:0]
    elif defect == "missing-session":
        history = history.drop(history.index[1])
    adapter = fake_adapter(history, [])
    if defect == "ex-date-outside-sessions":
        original = adapter

        class BadExDate:
            def fetch(self, ticker, start, end):
                snapshot = original.fetch(ticker, start, end)
                actions = snapshot.corporate_actions.copy()
                dividend_index = actions.index[actions["Action_Type"].eq("dividend")][0]
                actions.loc[dividend_index, "Date"] = pd.Timestamp("2024-01-06")
                return replace(snapshot, corporate_actions=actions)

        adapter = BadExDate()
    cache = tmp_path / "bundle"
    cache.mkdir()
    with pytest.raises(exception, match=re.escape(message)):
        download(cache, adapter)
    assert list(cache.iterdir()) == []


# ---------------------------------------------------------------------------
# Unit 2 (T005-T006): SC-005 oracles, SC-006 direction, FR-002 (SC-005 M4).
# Tests only. Every value below is EXAMPLE — NOT A RESULT.
#
# The oracles are no-argument callables that raise AssertionError on failure,
# because tests/mutation_support_019.killed() catches only AssertionError. The
# killed() wiring for M1-M3 needs the production source lines they mutate, so
# it lands with the implementation (tasks.md T015). These oracles are tested
# directly here, and M1's oracle is proven sensitive by a control that passes
# on today's code.
# ---------------------------------------------------------------------------

CITATION = "EXAMPLE — NOT A RESULT: synthetic test citation, not a filing"
LAG_CONSTANT = "DIVIDEND_PAY_DATE_DECLARED_LAG_SESSIONS"
SOURCE_CONSTANT = "DIVIDEND_PAY_DATE_BOUND_SOURCE"
POLICY_FIELD = "manifest dividend_pay_date_policy check failed"
SOURCE_FIELD = "manifest dividend_pay_date_bound_source check failed"
UNCITED_LAG = "requires a cited upper-bound source"
BAD_LAG = "must be a positive number of sessions"


def raises_containing(call, fragment):
    """Oracle-safe raise check: a miss is an AssertionError, which killed() catches."""
    try:
        call()
    except ValueError as error:
        assert fragment in str(error), str(error)
        return
    raise AssertionError(f"expected ValueError containing {fragment!r}")


def unpaid_dividend():
    """Five dollars per share, ex-dated 2024-01-03, with no vendor pay date."""
    return dividend_actions(
        Date=pd.Timestamp("2024-01-03"), Value=5.0,
        Dividend_Pay_Date=pd.NaT, Dividend_Pay_Date_Basis="bound",
    )


def paid_dividend():
    """The same dividend with a vendor pay date of 2024-01-04."""
    return dividend_actions(
        Date=pd.Timestamp("2024-01-03"), Value=5.0,
        Dividend_Pay_Date=pd.Timestamp("2024-01-04"),
    )


def reentry_ledger(actions, *, version, policy):
    """Fully allocated account: buy 01-02, hold through the ex-date, sell 01-04, re-buy 01-05.

    Capital 101 buys one 100-dollar share plus a 1-dollar commission, so cash is
    zero. After the sale cash is 99 and the re-buy needs 101. Only a 5-dollar
    dividend that has already become cash makes the re-buy affordable.
    """
    with tempfile.TemporaryDirectory() as directory:
        path = contract_bundle(Path(directory), actions, version=version, policy=policy)
        frame = data.load_unadjusted_market_data(path)
    frame["Buy_Next_Open"] = [True, False, False, True]
    frame["Sell_Next_Open"] = [False, False, True, False]
    trades = run_backtest(frame, starting_capital=101.0, commission_per_trade=1.0,
                          slippage_bps=0.0, liquidate=False)
    return trades.attrs["ledger"]


def oracle_m1_unpaid_dividend_cannot_fund_a_reentry():
    """M1 (option B via the loader): an unbounded dividend must stay Receivable."""
    ledger = reentry_ledger(unpaid_dividend(), version=2, policy="unbounded")
    events = ledger["Event"].tolist()
    assert events.count("rejected") == 1, events
    assert "payment" not in events, events
    final = ledger.iloc[-1]
    assert (final["Cash"], final["Receivable"], final["Quantity"]) == (99.0, 5.0, 0.0), dict(final)


def oracle_m2_a_null_pay_date_needs_a_declared_policy():
    """M2 (pass-through validator): version 1 and a sourced or mislabelled row stay strict."""
    null_date = dividend_actions(Dividend_Pay_Date=pd.NaT)
    with tempfile.TemporaryDirectory() as directory:
        for number, (version, policy) in enumerate([(1, None), (2, "sourced"), (2, "unbounded")]):
            root = Path(directory) / str(number)
            root.mkdir()
            path = contract_bundle(root, null_date, version=version, policy=policy)
            raises_containing(lambda: data.load_unadjusted_market_data(path), MISSING_PAY)


def oracle_m3_bound_rows_are_never_relabelled_sourced():
    """M3 (provenance laundering): a row whose on-disk date is null keeps basis bound."""
    actions = pd.concat([
        dividend_actions(Date=pd.Timestamp("2024-01-03"),
                         Dividend_Pay_Date=pd.Timestamp("2024-01-05")),
        dividend_actions(Date=pd.Timestamp("2024-01-04"), Dividend_Pay_Date=pd.NaT,
                         Dividend_Pay_Date_Basis="bound"),
    ], ignore_index=True)
    with tempfile.TemporaryDirectory() as directory:
        path = contract_bundle(Path(directory), actions, policy="unbounded")
        frame = data.load_unadjusted_market_data(path)
    rows = frame.loc[frame["Dividend"].gt(0)].set_index("Date")
    assert rows.loc[pd.Timestamp("2024-01-04"), "Dividend_Pay_Date_Basis"] == "bound"
    assert rows.loc[pd.Timestamp("2024-01-04"), "Dividend_Pay_Date"] > frame["Date"].max()
    assert rows.loc[pd.Timestamp("2024-01-03"), "Dividend_Pay_Date_Basis"] == "sourced"
    assert rows.loc[pd.Timestamp("2024-01-03"), "Dividend_Pay_Date"] == pd.Timestamp("2024-01-05")
    assert (frame.attrs["dividends_bound"], frame.attrs["dividends_sourced"]) == (1, 1)


def test_m1_oracle():
    oracle_m1_unpaid_dividend_cannot_fund_a_reentry()


def test_m1_oracle_control_a_paid_dividend_admits_the_reentry():
    """Green today: the M1 scenario really does hinge on when the dividend becomes cash."""
    events = reentry_ledger(paid_dividend(), version=1, policy=None)["Event"].tolist()
    assert events.count("rejected") == 0, events
    assert events.count("payment") == 1, events
    assert events.count("buy") == 2, events


def test_m2_oracle():
    oracle_m2_a_null_pay_date_needs_a_declared_policy()


def test_m3_oracle():
    oracle_m3_bound_rows_are_never_relabelled_sourced()


@pytest.mark.parametrize("lag, source, fragment", [
    (5, None, UNCITED_LAG),
    (5, "", UNCITED_LAG),
    (5, "   ", UNCITED_LAG),
    (0, CITATION, BAD_LAG),
    (-1, CITATION, BAD_LAG),
])
def test_m4_an_uncited_or_nonpositive_lag_cannot_write_a_bundle(
        tmp_path, monkeypatch, lag, source, fragment):
    monkeypatch.setattr(data, LAG_CONSTANT, lag)
    monkeypatch.setattr(data, SOURCE_CONSTANT, source)
    cache = tmp_path / "bundle"
    cache.mkdir()
    with pytest.raises(ValueError, match=re.escape(fragment)):
        download(cache, fake_adapter(synthetic_history(), []))
    assert list(cache.iterdir()) == []


# Ex-dates 2024-01-04 (with a same-day split) and 2024-01-05 (the final session).
# Hand-counted NYSE sessions after each ex-date; 2024-01-15 is a market holiday,
# so N=8 crosses it and lands past the bundle's end.
FINITE_BOUND_CASES = [
    (1, ["2024-01-05", "2024-01-08"], ["2024-01-05"]),
    (3, ["2024-01-09", "2024-01-10"], []),
    (8, ["2024-01-17", "2024-01-18"], []),
]


@pytest.mark.parametrize("lag, resolved, payments", FINITE_BOUND_CASES)
def test_finite_bound_resolves_n_sessions_after_the_ex_date(tmp_path, monkeypatch, lag, resolved, payments):
    monkeypatch.setattr(data, LAG_CONSTANT, lag)
    monkeypatch.setattr(data, SOURCE_CONSTANT, CITATION)
    path = download(tmp_path, fake_adapter(synthetic_history(), []))
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["dividend_pay_date_policy"] == f"bound_sessions:{lag}"
    assert manifest["dividend_pay_date_bound_source"] == CITATION
    # The loader must read the policy from the manifest, never from the constants.
    monkeypatch.setattr(data, LAG_CONSTANT, None)
    monkeypatch.setattr(data, SOURCE_CONSTANT, None)
    frame = data.load_unadjusted_market_data(path)
    assert frame.attrs["dividend_pay_date_policy"] == f"bound_sessions:{lag}"
    assert frame.attrs["dividend_pay_date_bound_source"] == CITATION
    rows = frame.loc[frame["Dividend"].gt(0)]
    assert rows["Dividend_Pay_Date_Basis"].tolist() == ["bound", "bound"]
    assert rows["Dividend_Pay_Date"].tolist() == [pd.Timestamp(day) for day in resolved]
    assert (rows["Dividend_Pay_Date"] > rows["Date"]).all()
    frame["Buy_Next_Open"] = [True, False, False, False]
    frame["Sell_Next_Open"] = False
    trades = run_backtest(frame, starting_capital=101.0, commission_per_trade=1.0,
                          slippage_bps=0.0, liquidate=False)
    ledger = trades.attrs["ledger"]
    paid = ledger.loc[ledger["Event"].eq("payment"), "Date"]
    assert paid.tolist() == [pd.Timestamp(day) for day in payments]


def test_unbounded_bound_dividends_never_become_cash_in_the_run(tmp_path, monkeypatch):
    path = download(tmp_path, fake_adapter(synthetic_history(), []))
    # A later, finite constant must not reinterpret a bundle written as unbounded.
    monkeypatch.setattr(data, LAG_CONSTANT, 2)
    monkeypatch.setattr(data, SOURCE_CONSTANT, CITATION)
    frame = data.load_unadjusted_market_data(path)
    assert frame.attrs["dividend_pay_date_policy"] == "unbounded"
    rows = frame.loc[frame["Dividend"].gt(0)]
    assert (rows["Dividend_Pay_Date"] > frame["Date"].max()).all()
    frame["Buy_Next_Open"] = [True, False, False, False]
    frame["Sell_Next_Open"] = False
    trades = run_backtest(frame, starting_capital=101.0, commission_per_trade=1.0,
                          slippage_bps=0.0, liquidate=True)
    assert "payment" not in trades.attrs["ledger"]["Event"].tolist()


@pytest.mark.parametrize("policy, fragment", [
    (None, POLICY_FIELD),
    ("typical_lag", POLICY_FIELD),
    ("bound_sessions:0", POLICY_FIELD),
    ("bound_sessions:-1", POLICY_FIELD),
    ("bound_sessions:3", SOURCE_FIELD),
])
def test_v2_manifest_policy_fields_are_validated(tmp_path, policy, fragment):
    path = contract_bundle(tmp_path, dividend_actions(), policy=policy)
    with pytest.raises(ValueError, match=re.escape(fragment)):
        data.load_unadjusted_market_data(path)
