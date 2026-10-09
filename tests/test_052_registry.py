"""Spec 052 U1: dated instrument identity and as-of snapshots. EXAMPLE — NOT A RESULT."""
from datetime import date, datetime, timezone

import pytest

import context  # noqa: F401
from asset_registry import Fact, Registry, RegistryError

UTC = timezone.utc


def obs(y, m, d):
    return datetime(y, m, d, 22, 0, tzinfo=UTC)


def registry():
    return Registry([
        Fact("I1", "symbol", "OLDC", date(2015, 1, 2), obs(2015, 1, 2), "sec:cik-1"),
        Fact("I1", "listed", "NASDAQ", date(2015, 1, 2), obs(2015, 1, 2), "nasdaqtrader"),
        Fact("I1", "symbol", "NEWC", date(2021, 6, 1), obs(2021, 5, 20), "sec:8-K"),
        Fact("I2", "symbol", "GONE", date(2016, 3, 1), obs(2016, 3, 1), "sec:cik-2"),
        Fact("I2", "listed", "NYSE", date(2016, 3, 1), obs(2016, 3, 1), "nasdaqtrader"),
        Fact("I2", "delisted", "acquired", date(2020, 2, 3), obs(2020, 2, 3), "sec:25-NSE"),
        Fact("I3", "symbol", "LATE", date(2024, 1, 2), obs(2024, 1, 2), "sec:cik-3"),
        Fact("I3", "listed", "NYSE", date(2024, 1, 2), obs(2024, 1, 2), "nasdaqtrader"),
    ])


def test_future_listing_never_appears_in_a_past_snapshot():
    assert "I3" not in registry().snapshot(date(2019, 6, 3))


def test_rename_keeps_identity_and_uses_the_symbol_in_force_then():
    reg = registry()
    assert reg.snapshot(date(2019, 6, 3))["I1"]["symbol"] == "OLDC"
    assert reg.snapshot(date(2022, 6, 1))["I1"]["symbol"] == "NEWC"


def test_delisted_instrument_stays_in_history_and_is_flagged_after_delisting():
    reg = registry()
    assert reg.snapshot(date(2019, 6, 3))["I2"]["active"] is True
    after = reg.snapshot(date(2021, 1, 4))
    assert after["I2"]["active"] is False and after["I2"]["delisted"] == "acquired"


def test_fact_observed_after_the_session_is_invisible_that_session():
    reg = Registry([Fact("I9", "symbol", "LEAK", date(2020, 1, 2), obs(2020, 1, 10), "late-filing")])
    assert "I9" not in reg.snapshot(date(2020, 1, 6))
    assert "I9" in reg.snapshot(date(2020, 1, 10))


def test_snapshot_is_reproducible_by_hash():
    assert registry().snapshot_hash(date(2022, 6, 1)) == registry().snapshot_hash(date(2022, 6, 1))
    assert registry().snapshot_hash(date(2022, 6, 1)) != registry().snapshot_hash(date(2019, 6, 3))


@pytest.mark.parametrize("bad", [
    dict(observed_at=datetime(2020, 1, 2, 12, 0)), dict(source=""), dict(field="colour")])
def test_invalid_facts_refuse(bad):
    values = dict(instrument_id="I1", field="symbol", value="X", effective_date=date(2020, 1, 2),
                  observed_at=obs(2020, 1, 2), source="s") | bad
    with pytest.raises(RegistryError):
        Fact(**values)


def test_announced_but_not_yet_effective_listing_is_excluded():
    reg = Registry([Fact("I8", "listed", "NYSE", date(2019, 7, 1), obs(2019, 5, 1), "exchange-notice")])
    assert "I8" not in reg.snapshot(date(2019, 6, 3))
    assert "I8" in reg.snapshot(date(2019, 7, 1))


def test_a_symbol_without_a_listing_is_known_but_not_active():
    reg = Registry([Fact("I8", "symbol", "PRE", date(2020, 1, 2), obs(2020, 1, 2), "sec:cik-8"),
                    Fact("I8", "listed", "NYSE", date(2020, 3, 2), obs(2020, 3, 2), "nasdaqtrader")])
    assert reg.snapshot(date(2020, 2, 3))["I8"]["active"] is False
    assert reg.snapshot(date(2020, 3, 2))["I8"]["active"] is True
