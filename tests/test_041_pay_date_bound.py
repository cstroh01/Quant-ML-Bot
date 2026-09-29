"""EXAMPLE — NOT A RESULT. Offline Spec 041 policy and bundle contracts."""

from dataclasses import replace
from datetime import date
import hashlib
import json
import re
import socket

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
