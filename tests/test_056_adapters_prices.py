"""Spec 056 U4a: price adapters on injected transports. Synthetic fixtures: EXAMPLE — NOT A RESULT."""
import hashlib
import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

import context  # noqa: F401
from data_sources import AlpacaDailyBars, SourceFetchError, TiingoDailyRaw

NOW = datetime(2026, 10, 8, 3, 0, tzinfo=timezone.utc)  # 23:00 New York, 2026-10-07
START = datetime(2026, 10, 1, tzinfo=timezone.utc)
KEY, SECRET, TOKEN = "AKEXAMPLEKEYID", "example-secret-value", "example-tiingo-token"


class Fake:
    """Serves canned pages in order and records each request. No network."""
    def __init__(self, *pages):
        self.pages = [p if isinstance(p, bytes) else json.dumps(p).encode() for p in pages]
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        return self.pages.pop(0)


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv("APCA_API_KEY_ID", KEY)
    monkeypatch.setenv("APCA_API_SECRET_KEY", SECRET)
    monkeypatch.setenv("TIINGO_API_TOKEN", TOKEN)


def bar(t, close):
    return {"t": t, "o": close - 1, "h": close + 1, "l": close - 2, "c": close, "v": 1000, "n": 9, "vw": close}


def alpaca(*pages):
    fake = Fake(*pages)
    return AlpacaDailyBars(transport=fake, now=lambda: NOW), fake


def test_alpaca_requests_sip_raw_with_keys_only_in_headers():
    adapter, fake = alpaca({"bars": [bar("2026-10-06T04:00:00Z", 100.0)], "next_page_token": None})
    frame, manifest = adapter.fetch("AAPL", START, NOW - timedelta(hours=1))
    method, url, headers = fake.calls[0]
    assert "feed=sip" in url and "adjustment=raw" in url and "start=" in url and "end=" in url
    assert headers == {"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET}
    assert manifest.adjustment == "raw" and manifest.fetched_at == NOW and manifest.row_count == 1
    for text in (url, manifest.endpoint, repr(manifest), repr(adapter)):
        assert KEY not in text and SECRET not in text
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]


def test_alpaca_follows_every_page_and_hashes_the_raw_bytes():
    page1 = {"bars": [bar("2026-10-05T04:00:00Z", 100.0)], "next_page_token": "tok1"}
    page2 = {"bars": [bar("2026-10-06T04:00:00Z", 101.0)], "next_page_token": None}
    adapter, fake = alpaca(page1, page2)
    frame, manifest = adapter.fetch("AAPL", START, NOW - timedelta(hours=1))
    assert "page_token=tok1" in fake.calls[1][1] and "page_token" not in fake.calls[0][1]
    assert list(frame["close"]) == [100.0, 101.0] and manifest.row_count == 2
    raw = json.dumps(page1).encode() + json.dumps(page2).encode()
    assert manifest.sha256 == hashlib.sha256(raw).hexdigest()


def test_alpaca_labels_are_new_york_session_dates_across_dst():
    bars = [bar("2026-03-06T05:00:00Z", 1.0), bar("2026-03-09T04:00:00Z", 2.0)]  # EST, then EDT
    frame, _ = alpaca({"bars": bars})[0].fetch("AAPL", START, NOW - timedelta(hours=1))
    assert list(frame.index) == [pd.Timestamp("2026-03-06"), pd.Timestamp("2026-03-09")]
    assert frame.index.tz is None and (frame.index == frame.index.normalize()).all()


@pytest.mark.parametrize("end", [NOW - timedelta(minutes=14, seconds=59), datetime(2026, 10, 7, 20)])
def test_alpaca_refuses_an_end_that_is_too_recent_or_naive(end):
    adapter, fake = alpaca({"bars": [bar("2026-10-06T04:00:00Z", 1.0)]})
    with pytest.raises(SourceFetchError, match="end"):
        adapter.fetch("AAPL", START, end)
    assert fake.calls == [] and adapter.fetch("AAPL", START, NOW - timedelta(minutes=15))[1].row_count == 1


@pytest.mark.parametrize("end_utc_hour,kept", [(19, ["2026-10-06"]), (20, ["2026-10-06", "2026-10-07"])])
def test_alpaca_keeps_only_sessions_closed_by_end(end_utc_hour, kept):
    bars = [bar("2026-10-06T04:00:00Z", 1.0), bar("2026-10-07T04:00:00Z", 2.0)]
    end = datetime(2026, 10, 7, end_utc_hour, tzinfo=timezone.utc)  # 15:00 / 16:00 New York
    frame, manifest = alpaca({"bars": bars})[0].fetch("AAPL", START, end)
    assert [d.strftime("%Y-%m-%d") for d in frame.index] == kept
    assert manifest.completed_session == kept[-1] and manifest.row_count == len(kept)


def test_alpaca_refuses_when_no_completed_session_remains():
    with pytest.raises(SourceFetchError, match="no completed session"):
        alpaca({"bars": []})[0].fetch("AAPL", START, NOW - timedelta(hours=1))


def test_failures_never_echo_url_or_credentials(monkeypatch):
    def leaky(method, url, headers, body=None):
        raise RuntimeError(f"boom {url} {headers}")
    with pytest.raises(SourceFetchError) as caught:
        AlpacaDailyBars(transport=leaky, now=lambda: NOW).fetch("AAPL", START, NOW - timedelta(hours=1))
    assert KEY not in str(caught.value) and SECRET not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    monkeypatch.delenv("APCA_API_SECRET_KEY")
    with pytest.raises(SourceFetchError, match="APCA_API_SECRET_KEY is not set"):
        alpaca({"bars": []})[0].fetch("AAPL", START, NOW - timedelta(hours=1))


def tiingo_row(day, close, adj, split=1.0, div=0.0):
    return {"date": f"{day}T00:00:00.000Z", "open": close, "high": close + 1, "low": close - 1, "close": close,
            "volume": 500, "adjOpen": adj, "adjHigh": adj, "adjLow": adj, "adjClose": adj, "adjVolume": 250,
            "divCash": div, "splitFactor": split}


def tiingo(rows, now=NOW):
    fake = Fake(rows)
    return TiingoDailyRaw(transport=fake, now=lambda: now), fake


def test_tiingo_keeps_raw_fields_and_sends_token_in_header():
    rows = [tiingo_row("2026-10-05", 200.0, 100.0), tiingo_row("2026-10-06", 100.0, 100.0, split=2.0)]
    adapter, fake = tiingo(rows)
    frame, manifest = adapter.fetch("AAPL", date(2026, 10, 1), date(2026, 10, 7))
    method, url, headers = fake.calls[0]
    assert list(frame["close"]) == [200.0, 100.0] and list(frame["volume"]) == [500, 500]
    assert list(frame.index) == [pd.Timestamp("2026-10-05"), pd.Timestamp("2026-10-06")]  # never shifted
    assert headers == {"Authorization": f"Token {TOKEN}"} and TOKEN not in url
    assert TOKEN not in manifest.endpoint and TOKEN not in repr(manifest) and TOKEN not in repr(adapter)
    assert manifest.adjustment == "raw" and manifest.sha256 == hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def test_tiingo_refuses_adjusted_values_stamped_raw():
    rows = [tiingo_row("2026-10-05", 100.0, 100.0), tiingo_row("2026-10-06", 100.0, 100.0, split=2.0)]
    with pytest.raises(SourceFetchError, match="adjusted"):
        tiingo(rows)[0].fetch("AAPL", date(2026, 10, 1), date(2026, 10, 7))


def test_tiingo_refuses_a_payload_without_raw_fields():
    row = {k: v for k, v in tiingo_row("2026-10-05", 1.0, 1.0).items() if k != "close"}
    with pytest.raises(SourceFetchError, match="close"):
        tiingo([row])[0].fetch("AAPL", date(2026, 10, 1), date(2026, 10, 7))


def test_tiingo_drops_a_session_not_closed_15_minutes_ago():
    rows = [tiingo_row("2026-10-06", 1.0, 1.0), tiingo_row("2026-10-07", 2.0, 2.0)]
    now = datetime(2026, 10, 7, 20, 14, tzinfo=timezone.utc)  # 16:14 New York
    frame, manifest = tiingo(rows, now=now)[0].fetch("AAPL", date(2026, 10, 1), date(2026, 10, 7))
    assert list(frame.index) == [pd.Timestamp("2026-10-06")] and manifest.completed_session == "2026-10-06"
