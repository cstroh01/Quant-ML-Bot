"""Spec 060 FR-002/FR-004 (queue Q114): the Massive Stocks Basic adapter, offline (Rules 12, 14).

EXAMPLE — NOT A RESULT. Every response is a fake; no network, no key on disk.
"""
import json
from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import pytest

import massive_source as ms
from corporate_actions import DIVIDEND_AMOUNT_BASIS, DIVIDEND_AMOUNT_TOLERANCE, reconcile_dividends
from data_sources import RateLimit, SourceFetchError

NOW = datetime(2026, 10, 12, 22, 0, tzinfo=timezone.utc)
KEY = "fake-massive-key-123"


class Fake:
    """Serves queued pages by path; records every (url, headers)."""

    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((url, dict(headers)))
        path = urlsplit(url).path
        queue = self.pages[path]
        return json.dumps(queue.pop(0)).encode()


class Clock:
    def __init__(self):
        self.t, self.slept = 0.0, []

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


def adapter(pages, monkeypatch, clock=None):
    monkeypatch.setenv("MASSIVE_API_KEY", KEY)
    clock = clock or Clock()
    fake = Fake(pages)
    return ms.MassiveReference(transport=fake, now=lambda: NOW,
                               limit=RateLimit(12.0, clock=clock, sleep=clock.sleep)), fake


DIV = {"ticker": "SPY", "ex_dividend_date": "2026-03-20", "cash_amount": 1.7, "currency": "USD"}
SPLIT = {"ticker": "SPY", "execution_date": "2025-06-09", "split_from": 1, "split_to": 4}


def pages(divs=(DIV,), splits=(SPLIT,)):
    return {"/v3/reference/dividends": [{"results": list(divs)}], "/v3/reference/splits": [{"results": list(splits)}]}


def test_actions_use_spec_035_shape_and_feed_reconciliation(monkeypatch):
    source, _ = adapter(pages(), monkeypatch)
    frame, coverage, manifests = source.actions("SPY", date(2025, 1, 2), date(2026, 10, 9))
    assert list(frame["Action_Type"]) == ["split", "dividend"] and frame["Value"].tolist() == [4.0, 1.7], "T060 ACTIONS"
    assert frame.loc[1, "Amount_Basis"] == "per_share" and coverage == (pd.Timestamp("2025-01-02"), pd.Timestamp("2026-10-09"))
    assert [m.label_calendar for m in manifests] == ["calendar_date"] * 2 and all(m.adjustment == "raw" for m in manifests)
    primary = pd.DataFrame([{"Date": pd.Timestamp("2026-03-20"), "Action_Type": "dividend", "Value": 1.7,
                             "Amount_Basis": "per_share"}])
    agree = reconcile_dividends(primary, frame, coverage, amount_tolerance=DIVIDEND_AMOUNT_TOLERANCE,
                                amount_basis=DIVIDEND_AMOUNT_BASIS)
    disagree = reconcile_dividends(primary.assign(Value=1.75), frame, coverage, amount_tolerance=DIVIDEND_AMOUNT_TOLERANCE,
                                   amount_basis=DIVIDEND_AMOUNT_BASIS)
    assert agree["Reconciliation_Status"].tolist() == ["reconciled"], "T060 RECONCILE agree"
    assert disagree["Reconciliation_Status"].tolist() == ["mismatch"], "T060 RECONCILE disagree"


def test_non_usd_cash_is_not_claimed_per_share(monkeypatch):
    source, _ = adapter(pages(divs=[{**DIV, "currency": "CAD"}], splits=[]), monkeypatch)
    frame, _, _ = source.actions("SPY", date(2025, 1, 2), date(2026, 10, 9))
    assert frame.loc[0, "Amount_Basis"] is None, "T060 BASIS"


def test_key_comes_from_the_environment_into_a_header_only(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # a key file sits beside the run from the start; it must never be read
    (tmp_path / ".env").write_text(f"MASSIVE_API_KEY={KEY}\n")
    (tmp_path / "MASSIVE_API_KEY").write_text(KEY)
    source, fake = adapter(pages(), monkeypatch)
    _, _, manifests = source.actions("SPY", date(2025, 1, 2), date(2026, 10, 9))
    assert all(headers == {"Authorization": f"Bearer {KEY}"} and KEY not in url for url, headers in fake.calls), "T060 KEY"
    assert all(KEY not in m.endpoint for m in manifests), "T060 KEY manifest"
    monkeypatch.delenv("MASSIVE_API_KEY")
    refused = ""
    try:
        ms.MassiveReference(transport=Fake(pages()), now=lambda: NOW).actions("SPY", date(2025, 1, 2), date(2026, 10, 9))
    except SourceFetchError as error:
        refused = str(error)
    assert "MASSIVE_API_KEY" in refused and KEY not in refused, "T060 KEY environment only"


def test_a_failed_request_never_echoes_the_key(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", KEY)
    def leaky(method, url, headers, body=None):
        raise OSError(f"boom {headers}")
    message = ""
    try:
        ms.MassiveReference(transport=leaky, now=lambda: NOW, limit=RateLimit(0.0)).actions("SPY", date(2025, 1, 2),
                                                                                           date(2026, 10, 9))
    except SourceFetchError as error:
        message = str(error)
    assert message and KEY not in message, "T060 SECRET"


def test_five_calls_per_minute(monkeypatch):
    clock = Clock()
    source, fake = adapter({**pages(), "/v3/reference/tickers": [{"results": []}]}, monkeypatch, clock)
    source.actions("SPY", date(2025, 1, 2), date(2026, 10, 9))
    source.tickers(active=True, as_of=date(2026, 10, 9))
    assert len(fake.calls) == 3 and clock.slept == [12.0, 12.0], f"T060 RATE {clock.slept}"
    assert ms.MASSIVE_RATE.interval == 12.0, "T060 RATE plan"


@pytest.mark.parametrize("next_url, ok", [
    (ms.BASE_URL + "/v3/reference/dividends?cursor=abc", True),
    (ms.BASE_URL + "/v3/reference/dividends?cursor=abc&apiKey=" + KEY, False),
    ("https://elsewhere.example/v3/reference/dividends?cursor=abc", False),
])
def test_pagination_is_followed_on_host_and_without_credentials(monkeypatch, next_url, ok):
    page_two = {**DIV, "ex_dividend_date": "2026-06-20"}
    divs = [{"results": [DIV], "next_url": next_url}, {"results": [page_two]}]
    source, fake = adapter({"/v3/reference/dividends": divs, "/v3/reference/splits": [{"results": []}]}, monkeypatch)
    try:
        frame, _, _ = source.actions("SPY", date(2025, 1, 2), date(2026, 10, 9))
        followed = len(frame) == 2 and fake.calls[1][0] == next_url
    except SourceFetchError:
        followed = None
    assert followed is (True if ok else None), f"T060 PAGES {next_url}"


@pytest.mark.parametrize("start, end", [(date(2024, 10, 1), date(2026, 10, 9)), (date(2026, 1, 2), date(2026, 10, 20))])
def test_out_of_plan_windows_are_refused_not_truncated(monkeypatch, start, end):
    source, fake = adapter(pages(), monkeypatch)
    refused = False
    try:
        source.actions("SPY", start, end)
    except SourceFetchError:
        refused = True
    assert refused and fake.calls == [], f"T060 WINDOW {start}..{end}"


def test_inactive_tickers_are_listed_and_a_wrong_flag_refused(monkeypatch):
    gone = {"ticker": "XYZ", "name": "Closed ETF", "type": "ETF", "active": False, "delisted_utc": "2025-04-01T00:00:00Z"}
    source, fake = adapter({"/v3/reference/tickers": [{"results": [gone]}, {"results": [{**gone, "active": True}]}]},
                           monkeypatch)
    frame, manifest = source.tickers(active=False, as_of=date(2026, 10, 9))
    assert frame.loc[0, "Delisted_UTC"] == gone["delisted_utc"] and manifest.row_count == 1, "T060 TICKERS"
    assert parse_qs(urlsplit(fake.calls[0][0]).query)["active"] == ["false"], "T060 TICKERS query"
    refused = False
    try:
        source.tickers(active=False, as_of=date(2026, 10, 9))
    except SourceFetchError:
        refused = True
    assert refused, "T060 TICKERS flag"
