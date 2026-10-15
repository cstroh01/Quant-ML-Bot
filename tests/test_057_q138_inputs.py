"""Q138 input bundle: synthetic fetcher only; the bundle must pass the session's own pre-login checks."""
from dataclasses import replace
from datetime import date, datetime, timezone
import hashlib
import json

import pandas as pd
import pytest

import context  # noqa: F401
import fidelity_inputs as fi
from data import trading_days
from data_sources import SourceManifest
from fidelity_session import validate_closes
from signals import ALLOCATION_SLEEVES

NOW = datetime(2026, 10, 15, 22, 0, tzinfo=timezone.utc)  # 18:00 New York, after the 10-15 close
RUN = date(2026, 10, 16)


class Fetcher:
    def __init__(self, last=date(2026, 10, 15), bad=None):
        self.last, self.bad, self.calls = last, bad, []

    def fetch(self, symbol, start, end):
        self.calls.append(symbol)
        days = trading_days(date(2026, 6, 1), self.last)
        frame = pd.DataFrame({"close": [100.0 + i * 0.01 for i in range(len(days))]}, index=pd.DatetimeIndex(days))
        if self.bad == symbol:
            frame.iloc[-1, 0] = float("nan")
        manifest = SourceManifest("alpaca_sip_daily", "https://data.alpaca.markets/v2/stocks/X/bars", NOW,
                                  str(self.last), "raw", len(frame), "c" * 64, "fixture")
        return frame, manifest


def test_bundle_round_trips_through_the_session_checks(tmp_path):
    summary = fi.build_bundle(tmp_path, now=NOW, session=RUN, fetcher=Fetcher())
    raw = (tmp_path / "closes.csv").read_bytes()
    bundle = json.loads((tmp_path / "sources.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(raw).hexdigest() == bundle["csv_sha256"] == summary["csv_sha256"], "Q138 HASH"
    assert len(bundle["sources"]) == 8 and summary["last_session"] == "2026-10-15"
    for source in bundle["sources"]:  # exactly the CLI's reconstruction
        assert SourceManifest(**(source | {"fetched_at": datetime.fromisoformat(source["fetched_at"])})).source \
            == "alpaca_sip_daily"
    closes = pd.read_csv(tmp_path / "closes.csv", index_col=0, parse_dates=True)
    assert list(closes.columns) == list(ALLOCATION_SLEEVES)
    validate_closes(closes, datetime(2026, 10, 16, 14, 0, tzinfo=timezone.utc))  # raises on any defect


@pytest.mark.parametrize("case", ["stale", "nan", "naive"])
def test_refusals_write_nothing(tmp_path, case):
    fetcher = Fetcher(last=date(2026, 10, 14)) if case == "stale" else Fetcher(bad="GLD" if case == "nan" else None)
    now = NOW.replace(tzinfo=None) if case == "naive" else NOW
    with pytest.raises(fi.InputsRefused):
        fi.build_bundle(tmp_path / "out", now=now, session=RUN, fetcher=fetcher)
    assert not (tmp_path / "out").exists(), "Q138 NOTHING WRITTEN"


def test_fetch_failure_is_named_without_its_payload(tmp_path):
    class Broken(Fetcher):
        def fetch(self, symbol, start, end):
            from data_sources import SourceFetchError
            raise SourceFetchError("SECRET-PAYLOAD")
    with pytest.raises(fi.InputsRefused) as info:
        fi.build_bundle(tmp_path, now=NOW, session=RUN, fetcher=Broken())
    assert "SECRET-PAYLOAD" not in str(info.value)
