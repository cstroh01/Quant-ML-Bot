"""EXAMPLE — NOT A RESULT. 056 T011 synthetic failure diagnostics; no network."""
import hashlib
import io
import json
import socket
import traceback
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError

import pytest
import context  # noqa: F401
from data_sources import SourceFetchError
from source_diagnostics import DiagnosticAlpacaDailyBars as AlpacaDailyBars

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
SENTINEL = "SYNTHETIC-NEVER-LOG-056"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv("APCA_API_KEY_ID", SENTINEL + "-key")
    monkeypatch.setenv("APCA_API_SECRET_KEY", SENTINEL + "-secret")
    def forbidden(*args, **kwargs):
        pytest.fail("T011 attempted a real socket")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def request(error):
    calls = []
    def transport(*args, **kwargs):
        calls.append(1)
        raise error
    adapter = AlpacaDailyBars(transport=transport, now=lambda: NOW)
    with pytest.raises(SourceFetchError) as caught:
        adapter.fetch("SPY", NOW - timedelta(days=5), NOW - timedelta(hours=1))
    assert calls == [1], "T011 failure must not retry"
    return caught.value


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_http_status_is_retained_without_payload(status, capsys):
    error = HTTPError("https://example.invalid/" + SENTINEL, status, SENTINEL,
                      {"Authorization": SENTINEL}, io.BytesIO(SENTINEL.encode()))
    result = request(error)
    assert getattr(result, "http_status", None) == status, "T011 STATUS DROPPED"
    assert getattr(result, "category", None) == "HTTPError", "T011 CATEGORY"
    assert f"http_status={status}" in str(result), "T011 printable status missing"
    rendered = str(result) + repr(result) + "".join(traceback.format_exception(result))
    assert SENTINEL not in rendered, "T011 RAW EXCEPTION LEAK"
    assert "example.invalid" not in rendered, "T011 URL LEAK"
    assert result.__cause__ is None and result.__suppress_context__
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("status", [None, True, False, "403", 99, 600, -1, float("inf")])
def test_malformed_http_status_remains_unknown(status):
    result = request(HTTPError("https://example.invalid/", status, SENTINEL, {}, None))
    assert getattr(result, "http_status", "absent") is None, "T011 INVALID STATUS"
    assert "http_status=unknown" in str(result), "T011 UNKNOWN STATUS"
    assert SENTINEL not in str(result)


@pytest.mark.parametrize("error,category", [
    (TimeoutError(SENTINEL), "TimeoutError"),
    (URLError(SENTINEL), "URLError"),
    (OSError(SENTINEL), "OSError"),
    (RuntimeError(SENTINEL), "TransportError"),
])
def test_non_http_failure_is_categorical_and_unknown(error, category):
    result = request(error)
    assert getattr(result, "category", None) == category, "T011 CATEGORY"
    assert getattr(result, "http_status", "absent") is None, "T011 NON HTTP STATUS"
    assert "http_status=unknown" in str(result)
    assert SENTINEL not in "".join(traceback.format_exception(result)), "T011 RAW EXCEPTION LEAK"


def test_arbitrary_exception_type_name_is_not_rendered():
    error_type = type(SENTINEL, (Exception,), {})
    result = request(error_type(SENTINEL))
    assert SENTINEL not in str(result), "T011 EXCEPTION CLASS LEAK"
    assert getattr(result, "category", None) == "TransportError"


def test_success_preserves_response_digest_and_manifest():
    body = json.dumps({"bars": [{"t": "2026-10-19T04:00:00Z", "o": 99,
        "h": 102, "l": 98, "c": 100, "v": 1000}]}).encode()
    calls = []
    def transport(*args, **kwargs):
        calls.append(1)
        return body
    frame, manifest = AlpacaDailyBars(transport=transport, now=lambda: NOW).fetch(
        "SPY", NOW - timedelta(days=5), NOW - timedelta(hours=1))
    assert calls == [1] and manifest.sha256 == hashlib.sha256(body).hexdigest()
    assert manifest.row_count == 1 and frame.close.tolist() == [100]
    assert SENTINEL not in repr(manifest)


def test_paper_default_fetch_path_retains_sanitized_http_status(monkeypatch):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'exec'))
    import paper_loop
    import urllib.request
    def fail(*args, **kwargs):
        raise HTTPError('https://example.invalid/' + SENTINEL, 403, SENTINEL, {}, None)
    monkeypatch.setattr(urllib.request, 'urlopen', fail)
    monkeypatch.setattr(urllib.request.OpenerDirector, 'open', fail)
    with pytest.raises(paper_loop.RunAborted) as result:
        paper_loop.fetch_sleeve_closes(NOW, symbols=('SPY',))
    assert 'http_status=403' in str(result.value), 'T011 PAPER DEFAULT DIAGNOSTIC'
    assert SENTINEL not in str(result.value)



def test_configured_transport_refuses_redirect_before_forwarding_headers(monkeypatch):
    from email.message import Message
    from urllib.response import addinfourl
    import urllib.request
    calls = []
    def fake_https(handler, req):
        calls.append((req.full_url, dict(req.headers)))
        headers = Message()
        headers['Location'] = 'https://other.invalid/target'
        response = addinfourl(io.BytesIO(b'{}'), headers, req.full_url,
                             302 if len(calls) == 1 else 200)
        response.msg = 'Found' if len(calls) == 1 else 'OK'
        return response
    monkeypatch.setattr(urllib.request.HTTPSHandler, 'https_open', fake_https)
    adapter = AlpacaDailyBars(now=lambda: NOW)
    refused = False
    try:
        adapter._request(hashlib.sha256(), 'https://source.invalid/bars',
                         {'APCA-API-KEY-ID': SENTINEL})
    except SourceFetchError as error:
        refused = getattr(error, 'http_status', None) == 302
        assert SENTINEL not in str(error)
    assert refused and len(calls) == 1, 'T011 REDIRECT CREDENTIAL BOUNDARY'
