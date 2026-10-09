"""Spec 056 U1: source manifests and publication permissions. EXAMPLE — NOT A RESULT."""
from datetime import datetime, timezone

import pytest

import context  # noqa: F401
from data_sources import ManifestError, SourceContract, SourceManifest, may_publish

NOW = datetime(2026, 10, 8, 3, 0, tzinfo=timezone.utc)


def manifest(**extra):
    values = dict(source="alpaca_sip_daily", endpoint="https://data.alpaca.markets/v2/stocks/bars?feed=sip&adjustment=raw",
                  fetched_at=NOW, completed_session="2026-10-07", adjustment="raw", row_count=21,
                  sha256="a" * 64, contract_version="2026-10-07")
    values.update(extra)
    return SourceManifest(**values)


def test_valid_manifest_constructs():
    assert manifest().row_count == 21


@pytest.mark.parametrize("url", ["https://x.example/v1?token=abc", "https://x.example/v1?apiKey=1&s=AAPL",
                                 "https://user:pass@x.example/v1", "https://x.example/v1?APCA-API-SECRET-KEY=z"])
def test_credentials_in_endpoint_refuse(url):
    with pytest.raises(ManifestError, match="credential"):
        manifest(endpoint=url)


@pytest.mark.parametrize("field,value", [("fetched_at", datetime(2026, 10, 8, 3, 0)), ("sha256", "short"),
                                         ("adjustment", "split_only"), ("row_count", -1), ("completed_session", "10/07/2026")])
def test_invalid_fields_refuse(field, value):
    with pytest.raises(ManifestError, match=field):
        manifest(**{field: value})


def contract(**extra):
    values = dict(source="tiingo_eod", verified_on="2026-10-07", private_research=True,
                  public_raw=False, public_derived=None)
    values.update(extra)
    return SourceContract(**values)


def test_unknown_or_denied_rights_never_publish():
    assert may_publish(contract(), "private_research") is True
    assert may_publish(contract(), "public_raw") is False
    assert may_publish(contract(), "public_derived") is False  # None = unverified → refuse


def test_private_permission_never_implies_public():
    assert may_publish(contract(private_research=True, public_raw=None, public_derived=None), "public_raw") is False


def test_unknown_output_class_refuses():
    with pytest.raises(ManifestError, match="output class"):
        may_publish(contract(), "tweet")


@pytest.mark.parametrize("session,fetched_at", [
    ("2026-10-03", NOW),                                            # past Saturday: not an NYSE session
    ("2026-10-08", NOW),                                            # session not yet closed at fetch
    ("2026-10-07", datetime(2026, 10, 7, 19, 59, tzinfo=timezone.utc)),  # 15:59 ET, before the close
])
def test_session_label_must_be_a_completed_nyse_session(session, fetched_at):
    with pytest.raises(ManifestError, match="completed_session"):
        manifest(completed_session=session, fetched_at=fetched_at)


def test_calendar_dated_sources_allow_non_sessions_but_never_the_future():
    assert manifest(completed_session="2026-10-04", label_calendar="calendar_date").completed_session == "2026-10-04"
    with pytest.raises(ManifestError, match="completed_session"):
        manifest(completed_session="2026-10-09", label_calendar="calendar_date")
    with pytest.raises(ManifestError, match="label_calendar"):
        manifest(label_calendar="lunar")
