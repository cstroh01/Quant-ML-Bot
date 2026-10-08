"""Spec 056 U4b1: SEC EDGAR adapters and the shared rate limit on fakes. EXAMPLE — NOT A RESULT."""
import json
from datetime import date, datetime, timezone

import pandas as pd
import pytest

import context  # noqa: F401
from data_sources import EdgarCompanyFacts, EdgarSubmissions, RateLimit, SourceFetchError

NOW = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)
UA = "Example Research example@example.com"


class Fake:
    def __init__(self, *payloads):
        self.payloads = [p if isinstance(p, bytes) else json.dumps(p).encode() for p in payloads]
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers), body))
        return self.payloads.pop(0)


class Clock:
    def __init__(self):
        self.t, self.slept = 0.0, []

    def sleep(self, seconds):
        self.slept.append(round(seconds, 6))
        self.t += seconds


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", UA)


RECENT = {"accessionNumber": ["0000000001-26-000010", "0000000001-26-000009"], "form": ["10-Q", "8-K"],
          "filingDate": ["2026-08-01", "2026-05-01"],
          "acceptanceDateTime": ["2026-07-31T18:05:00.000Z", "2026-05-01T16:30:00.000Z"]}
USD = [{"start": "2026-04-01", "end": "2026-06-30", "val": 10, "accn": "a1", "form": "10-Q", "filed": "2026-08-01"},
       {"start": "2026-01-01", "end": "2026-06-30", "val": 25, "accn": "a1", "form": "10-Q", "filed": "2026-08-01"},
       {"start": "2026-04-01", "end": "2026-06-30", "val": 12, "accn": "a2", "form": "10-Q/A", "filed": "2026-11-01"}]
SHARES = [{"end": "2026-07-15", "val": 1000, "accn": "a1", "form": "10-Q", "filed": "2026-08-01"}]
FACTS = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": USD}}},
                   "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": SHARES}}}}}


def test_submissions_keep_accession_form_and_acceptance_as_new_york_instant():
    fake = Fake({"filings": {"recent": RECENT, "files": []}})
    frame, manifest = EdgarSubmissions(transport=fake, now=lambda: NOW).fetch(1)
    assert fake.calls[0][1].endswith("/submissions/CIK0000000001.json") and fake.calls[0][2] == {"User-Agent": UA}
    assert list(frame["accession"]) == RECENT["accessionNumber"] and list(frame["form"]) == ["10-Q", "8-K"]
    assert frame["accepted_at"].iloc[0] == pd.Timestamp("2026-07-31 18:05", tz="America/New_York")
    assert frame["filing_date"].iloc[0] == pd.Timestamp("2026-08-01") and frame["filing_date"].dt.tz is None
    assert manifest.completed_session == "2026-08-01" and manifest.row_count == 2


def test_sec_requests_need_a_declared_user_agent(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT")
    fake = Fake({"filings": {"recent": RECENT}})
    with pytest.raises(SourceFetchError, match="User-Agent"):
        EdgarSubmissions(transport=fake, now=lambda: NOW).fetch(1)
    assert fake.calls == []


def test_sec_adapters_share_one_ten_per_second_limit():
    assert EdgarSubmissions().limit is EdgarCompanyFacts().limit and EdgarSubmissions().limit.interval == 0.1
    clock = Clock()
    shared = RateLimit(0.1, clock=lambda: clock.t, sleep=clock.sleep)
    fake = Fake({"filings": {"recent": RECENT}}, FACTS, FACTS)
    EdgarSubmissions(transport=fake, now=lambda: NOW, limit=shared).fetch(1)
    facts = EdgarCompanyFacts(transport=fake, now=lambda: NOW, limit=shared)
    facts.fetch(1), facts.fetch(2)
    assert clock.slept == [0.1, 0.1]


def test_companyfacts_keep_units_periods_accession_and_filed():
    rows, manifest = EdgarCompanyFacts(transport=Fake(FACTS), now=lambda: NOW).fetch(1)
    assert len(rows) == 4 and manifest.row_count == 4 and manifest.completed_session == "2026-11-01"
    assert {"taxonomy": "us-gaap", "concept": "Revenues", "unit": "USD", **USD[0]} in rows


def test_companyfact_is_invisible_before_filed_and_restatement_waits_for_its_own_filing():
    rows, _ = EdgarCompanyFacts(transport=Fake(FACTS), now=lambda: NOW).fetch(1)
    view = lambda day: [(f["start"], f["val"]) for f in EdgarCompanyFacts.as_of(rows, "Revenues", "USD", day)]  # noqa: E731
    assert view(date(2026, 7, 31)) == []
    assert view(date(2026, 8, 1)) == [("2026-01-01", 25), ("2026-04-01", 10)]
    assert view(date(2026, 11, 2)) == [("2026-01-01", 25), ("2026-04-01", 12)]
    shares = EdgarCompanyFacts.as_of(rows, "EntityCommonStockSharesOutstanding", "shares", date(2026, 8, 1), "dei")
    assert [f["val"] for f in shares] == [1000] and EdgarCompanyFacts.as_of(rows, "Revenues", "EUR", NOW.date()) == []
