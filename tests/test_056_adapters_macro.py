"""Spec 056 U4b2: OpenFIGI, ALFRED and French factor adapters on fakes. EXAMPLE — NOT A RESULT."""
import hashlib
import io
import json
import zipfile
from datetime import date, datetime, timezone

import pandas as pd
import pytest

import context  # noqa: F401
from data_sources import AlfredSeries, FrenchFactors, OpenFigiMap, RateLimit, SourceFetchError

NOW = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)
FIGI_KEY, FRED_KEY = "example-figi-key", "examplefredkey0123"


class Fake:
    def __init__(self, *payloads):
        self.payloads = [p if isinstance(p, bytes) else json.dumps(p).encode() for p in payloads]
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers), body))
        return self.payloads.pop(0)


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv("OPENFIGI_API_KEY", FIGI_KEY)
    monkeypatch.setenv("FRED_API_KEY", FRED_KEY)


def figi(n):
    return [{"data": [{"figi": f"BBG00000000{i}", "compositeFIGI": f"BBG10000000{i}"}]} for i in range(n)]


def test_openfigi_sends_at_most_five_jobs_per_request():
    jobs = [{"idType": "TICKER", "idValue": f"T{i}", "exchCode": "US"} for i in range(7)]
    answers = figi(5), figi(1) + [{"warning": "No identifier found."}]
    fake = Fake(*answers)
    frame, manifest = OpenFigiMap(transport=fake, now=lambda: NOW, limit=RateLimit(0)).fetch(jobs)
    assert [json.loads(c[3]) for c in fake.calls] == [jobs[:5], jobs[5:]] and {c[0] for c in fake.calls} == {"POST"}
    assert list(frame["idValue"]) == [f"T{i}" for i in range(7)] and frame["status"].iloc[-1] == "No identifier found."
    assert "X-OPENFIGI-APIKEY" not in fake.calls[0][2] and manifest.row_count == 7


def test_openfigi_key_rides_in_a_header_and_answers_must_align():
    fake = Fake(figi(1))
    adapter = OpenFigiMap(transport=fake, now=lambda: NOW, key_env="OPENFIGI_API_KEY")
    _, manifest = adapter.fetch([{"idType": "TICKER", "idValue": "T0"}])
    assert fake.calls[0][2]["X-OPENFIGI-APIKEY"] == FIGI_KEY and adapter.limit.interval == 6 / 25
    assert FIGI_KEY not in manifest.endpoint + repr(manifest) + repr(adapter) and OpenFigiMap().limit.interval == 60 / 25
    with pytest.raises(SourceFetchError, match="align"):
        OpenFigiMap(transport=Fake(figi(1)), now=lambda: NOW, limit=RateLimit(0)).fetch([{"idValue": "A"}, {"idValue": "B"}])


OBS = {"count": 3, "observations": [
    {"realtime_start": "2020-01-30", "realtime_end": "2020-02-26", "date": "2019-10-01", "value": "21542.0"},
    {"realtime_start": "2020-02-27", "realtime_end": "9999-12-31", "date": "2019-10-01", "value": "21600.0"},
    {"realtime_start": "2020-02-27", "realtime_end": "9999-12-31", "date": "2020-01-01", "value": "."}]}


def test_alfred_key_reaches_the_request_but_never_the_manifest():
    fake = Fake(OBS)
    adapter = AlfredSeries(transport=fake, now=lambda: NOW, limit=RateLimit(0))
    frame, manifest = adapter.fetch("GDP", date(1776, 7, 4), date(9999, 12, 31))
    assert f"api_key={FRED_KEY}" in fake.calls[0][1] and "realtime_start=1776-07-04" in manifest.endpoint
    assert FRED_KEY not in manifest.endpoint + repr(manifest) + repr(adapter) and manifest.completed_session == "2020-02-27"
    with pytest.raises(SourceFetchError) as caught:
        AlfredSeries(transport=lambda *a: (_ for _ in ()).throw(OSError(a[1])), limit=RateLimit(0)).fetch(
            "GDP", date(2020, 1, 1), date(2020, 2, 1))
    assert FRED_KEY not in str(caught.value)


def test_alfred_value_is_the_vintage_published_on_the_as_of_date():
    frame, _ = AlfredSeries(transport=Fake(OBS), now=lambda: NOW, limit=RateLimit(0)).fetch(
        "GDP", date(1776, 7, 4), date(9999, 12, 31))
    assert AlfredSeries.vintage(frame, date(2020, 1, 29)).empty
    assert AlfredSeries.vintage(frame, date(2020, 2, 26)).to_dict() == {pd.Timestamp("2019-10-01"): 21542.0}
    later = AlfredSeries.vintage(frame, date(2020, 2, 27))
    assert later[pd.Timestamp("2019-10-01")] == 21600.0 and pd.isna(later[pd.Timestamp("2020-01-01")])
    with pytest.raises(SourceFetchError, match="truncated"):
        AlfredSeries(transport=Fake({**OBS, "count": 4}), now=lambda: NOW, limit=RateLimit(0)).fetch(
            "GDP", date(1776, 7, 4), date(9999, 12, 31))


def zipped(text):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("F-F_Example.CSV", text)
    return buffer.getvalue()


DAILY = ("Example header line\n\n,Mkt-RF,SMB,HML,RF\n20260803,    0.50,   -0.10,    0.20,    0.020\n"
         "20260804,  -99.99,    0.30,   -0.40,    0.020\n\nCopyright 2026 Example\n")
MONTHLY = ("Example\n,Mkt-RF,RF\n202607,    1.00,    0.40\n\n Annual Factors: January-December \n"
           ",Mkt-RF,RF\n  2025,   10.00,    4.00\n")


def test_french_daily_zip_parses_to_decimal_returns_with_version_label():
    payload = zipped(DAILY)
    frame, manifest = FrenchFactors(transport=Fake(payload), now=lambda: NOW, version="CIZ").fetch("F-F_Example_daily")
    assert list(frame.index) == [pd.Timestamp("2026-08-03"), pd.Timestamp("2026-08-04")] and frame.index.tz is None
    assert frame.loc["2026-08-03", "Mkt-RF"] == pytest.approx(0.005) and pd.isna(frame.loc["2026-08-04", "Mkt-RF"])
    assert manifest.source == "kenneth_french_CIZ" and manifest.sha256 == hashlib.sha256(payload).hexdigest()
    assert manifest.completed_session == "2026-08-04"


def test_french_monthly_stops_before_the_annual_table_and_version_is_required():
    frame, _ = FrenchFactors(transport=Fake(zipped(MONTHLY)), now=lambda: NOW, version="FIZ").fetch("F-F_Example")
    assert list(frame.index) == [pd.Timestamp("2026-07-31")] and list(frame.columns) == ["Mkt-RF", "RF"]
    with pytest.raises(SourceFetchError, match="CIZ or FIZ"):
        FrenchFactors(transport=Fake(zipped(MONTHLY)), now=lambda: NOW).fetch("F-F_Example")
