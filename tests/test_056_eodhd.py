"""EXAMPLE — NOT A RESULT. Synthetic EODHD actions; no vendor network access."""
from datetime import date, datetime, timezone
import hashlib
import json
import socket

import pandas as pd
import pytest

import context  # noqa: F401
import eodhd_source as es
from corporate_actions import reconcile_dividends
from data_sources import SourceFetchError
from mutation_support_019 import killed

NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
START, END = date(2025, 10, 17), date(2026, 10, 16)
DIV = dict(date="2026-08-10", value=.25, unadjustedValue=1., currency="USD", paymentDate=None)
SPLIT = dict(date="2026-09-01", split="4.000000/1.000000")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        pytest.fail("EODHD tests must never access the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)


def client(monkeypatch, *, dividends=None, splits=None, transport=None, now=NOW, quota=None):
    monkeypatch.setenv("EODHD_API_KEY", "synthetic-do-not-log")
    calls = []
    bodies = {"div": [DIV] if dividends is None else dividends,
              "splits": [SPLIT] if splits is None else splits}
    def fake(method, url, headers, body):
        calls.append(url)
        return json.dumps(bodies["splits" if "/splits/" in url else "div"]).encode()
    return es.EodhdActions(transport=transport or fake, now=lambda: now,
                           quota=quota or es.RequestBudget(), rate=es.RateLimit(0)), calls, bodies


def test_nominal_cash_split_ratio_and_manifest_hashes(monkeypatch):
    api, calls, bodies = client(monkeypatch)
    result = api.fetch("AAA.US", START, END)
    assert len(calls) == 2 and all("fmt=json" in c and "api_token=" in c for c in calls)
    assert result.coverage == (pd.Timestamp(START), pd.Timestamp(END))
    dividend = result.actions.loc[result.actions.Action_Type.eq("dividend")].iloc[0]
    split = result.actions.loc[result.actions.Action_Type.eq("split")].iloc[0]
    assert dividend.Value == 1. and dividend.Amount_Basis == "per_share"
    assert pd.isna(dividend.Payment_Date)  # never synthesize a payment date
    assert split.Value == 4.
    assert result.actions.Date.dt.tz is None
    for manifest, kind in zip(result.manifests, ("div", "splits")):
        assert manifest.sha256 == hashlib.sha256(json.dumps(bodies[kind]).encode()).hexdigest()
        assert "api_token" not in manifest.endpoint and "synthetic-do-not-log" not in str(manifest)
        assert manifest.row_count == 1 and manifest.label_calendar == "calendar_date"


@pytest.mark.parametrize("change", [{"unadjustedValue": None}, {"currency": "EUR"}])
def test_unknown_nominal_basis_cannot_reconcile_as_dollars(monkeypatch, change):
    api, _, _ = client(monkeypatch, dividends=[DIV | change])
    result = api.fetch("AAA.US", START, END)
    primary = pd.DataFrame([dict(Date=pd.Timestamp(DIV["date"]), Action_Type="dividend",
                                 Value=1., Amount_Basis="per_share")])
    checked = reconcile_dividends(primary, result.actions, result.coverage,
                                 amount_tolerance=.0001, amount_basis="per_share")
    assert checked.Reconciliation_Status.tolist() == ["unreconciled"]


def test_real_reconciler_reports_mismatch_and_partial_coverage(monkeypatch):
    api, _, _ = client(monkeypatch)
    result = api.fetch("AAA.US", START, END)
    primary = pd.DataFrame([dict(Ticker="AAA", Date=pd.Timestamp(d), Action_Type="dividend", Value=v,
                                 Amount_Basis="per_share") for d, v in
                            [("2024-08-10", 1.), (DIV["date"], .25)]])
    checked = result.reconcile(primary)
    assert checked.Reconciliation_Status.tolist() == ["unreconciled", "mismatch"]
    primary.loc[1, "Value"] = 1.
    assert result.reconcile(primary).Reconciliation_Status.tolist() == ["unreconciled", "reconciled"]
    with pytest.raises(ValueError, match="single US instrument"):
        result.reconcile(primary.assign(Ticker="OTHER"))


@pytest.mark.parametrize("start,end", [(date(2025, 10, 16), END), (START, date(2026, 10, 18)),
                                        (END, START)])
def test_out_of_plan_or_future_requests_refuse_before_transport(monkeypatch, start, end):
    api, calls, _ = client(monkeypatch)
    with pytest.raises(SourceFetchError):
        api.fetch("AAA.US", start, end)
    assert not calls


@pytest.mark.parametrize("dividends,splits", [({"error": "forbidden"}, []),
    ([DIV | {"date": "2026-10-17"}], []), ([DIV, DIV], []),
    ([], [SPLIT | {"split": "-4/-1"}]), ([], [SPLIT | {"split": "1/0"}]),
    ([DIV | {"unadjustedValue": float("inf")}], [])])
def test_bad_or_truncated_payloads_refuse(monkeypatch, dividends, splits):
    api, _, _ = client(monkeypatch, dividends=dividends, splits=splits)
    with pytest.raises(SourceFetchError):
        api.fetch("AAA.US", START, END)


def test_credentials_transport_and_parse_errors_are_redacted(monkeypatch):
    def broken(*args):
        raise RuntimeError("synthetic-do-not-log")
    api, _, _ = client(monkeypatch, transport=broken)
    with pytest.raises(SourceFetchError) as caught:
        api.fetch("AAA.US", START, END)
    assert "synthetic-do-not-log" not in str(caught.value)
    monkeypatch.delenv("EODHD_API_KEY")
    with pytest.raises(SourceFetchError, match="not set"):
        api.fetch("AAA.US", START, END)


def test_redirects_cannot_forward_a_url_credential():
    assert es._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example") is None


def test_shared_quota_counts_failures_and_rolls_after_24_hours(monkeypatch):
    quota = es.RequestBudget()
    api, calls, _ = client(monkeypatch, dividends=[], splits=[], quota=quota)
    for _ in range(10):
        api.fetch("AAA.US", START, END)
    with pytest.raises(SourceFetchError, match="budget"):
        api.fetch("AAA.US", START, END)
    assert len(calls) == 20
    later, later_calls, _ = client(monkeypatch, quota=quota, now=NOW + pd.Timedelta(days=1),
                                   dividends=[], splits=[])
    later.fetch("AAA.US", START + pd.Timedelta(days=1), END)
    assert len(later_calls) == 2


def test_failed_transport_spends_its_reserved_allowance(monkeypatch):
    quota = es.RequestBudget()
    def broken(*args):
        raise OSError("synthetic transport failure")
    api, _, _ = client(monkeypatch, transport=broken, quota=quota)
    with pytest.raises(SourceFetchError):
        api.fetch("AAA.US", START, END)
    assert len(quota.calls) == 2


@pytest.mark.parametrize("old,new,case", [
    ('row.get("unadjustedValue")', 'row.get("value")', "nominal"),
    ('new / old', 'old / new', "ratio"),
    ('start < earliest', 'False', "history"),
    ('len(self.calls) + 2 > 20', 'len(self.calls) + 2 > 200', "quota"),
    ('currency == "USD" and value is not None', 'value is not None', "currency"),
], ids=["adjusted-cash", "inverted-split", "free-history", "quota", "currency"])
def test_planted_defects(monkeypatch, old, new, case):
    def oracle():
        if case == "history":
            api, _, _ = client(monkeypatch)
            try:
                api.fetch("AAA.US", date(2025, 10, 16), END)
            except SourceFetchError:
                return
            raise AssertionError("older than free history accepted")
        if case == "quota":
            quota = es.RequestBudget()
            for _ in range(10):
                quota.reserve(NOW)
            try:
                quota.reserve(NOW)
            except SourceFetchError:
                return
            raise AssertionError("free request budget exceeded")
        if case == "currency":
            test_unknown_nominal_basis_cannot_reconcile_as_dollars(monkeypatch, {"currency": "EUR"})
            return
        test_nominal_cash_split_ratio_and_manifest_hashes(monkeypatch)
    killed(es, old, new, oracle)
