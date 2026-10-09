"""Spec 054 U2: ownership, staleness and capability gates (FR-003/004/005, D-3, D-4).

Synthetic snapshots only. EXAMPLE — NOT A RESULT.
"""
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import context  # noqa: F401
from fidelity_fixtures import POSITIONS
from holdings_import import (CapabilityError, HoldingsImportError, Position, external_exposure,
                             holdings_status, live_buy_refusals, parse_positions_csv, require_capability)
from mode_config import Holding, aggregate_exposure, bot_sell_quantities

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
SNAP = parse_positions_csv(POSITIONS)  # EXMP 2 @ 25.75, SPAXX** $49, as_of Wed 2026-10-07 22:45 ET
FRESH_NOW = datetime(2026, 10, 8, 9, 0, tzinfo=NY)
STALE_NOW = datetime(2026, 10, 9, 9, 0, tzinfo=NY)
PRICES = {"EXMP": 25.75, "OTHR": 50.0}
LIMITS = {"portfolio_value": 1000.0, "max_position_pct": 0.10}  # 100 USD per ticker


def test_imported_positions_are_external_and_sweep_is_cash():
    snap = replace(SNAP, positions=SNAP.positions + (Position("SPAXX**", 10.0, 1.0, 10.0),))
    exposure = external_exposure(snap, now=FRESH_NOW)
    assert exposure.holdings == (Holding("EXMP", 2.0, "external"),)
    assert exposure.cash_usd == 59.0 and exposure.status == "fresh"


def test_external_holdings_never_produce_sells():
    holdings = list(external_exposure(SNAP, now=FRESH_NOW).holdings)
    assert bot_sell_quantities({}, holdings) == {}
    assert bot_sell_quantities({"EXMP": 0.0}, holdings) == {}


def test_bot_lots_are_subtracted_not_double_counted():
    exposure = external_exposure(SNAP, now=FRESH_NOW, bot_lots={"EXMP": 0.5})
    assert exposure.holdings == (Holding("EXMP", 1.5, "external"),)
    combined = [Holding("EXMP", 0.5, "bot"), *exposure.holdings]
    assert aggregate_exposure(combined, PRICES) == {"EXMP": 51.5}


@pytest.mark.parametrize("lots", [{"EXMP": 2.5}, {"ZZZZ": 1.0}])
def test_bot_lots_the_import_cannot_cover_refuse(lots):
    with pytest.raises(HoldingsImportError, match="bot lot"):
        external_exposure(SNAP, now=FRESH_NOW, bot_lots=lots)


def test_non_usd_rows_excluded_with_reason():
    snap = replace(SNAP, positions=SNAP.positions + (Position("EXCAD", 3.0, 10.0, 30.0, currency="CAD"),))
    exposure = external_exposure(snap, now=FRESH_NOW)
    assert [h.ticker for h in exposure.holdings] == ["EXMP"]
    assert exposure.excluded == (("EXCAD", "non_usd:CAD"),)


@pytest.mark.parametrize("as_of", [None, datetime(2026, 10, 7, 22, 45)])
def test_missing_or_naive_as_of_refuses(as_of):
    with pytest.raises(HoldingsImportError, match="as_of"):
        external_exposure(replace(SNAP, as_of=as_of), now=FRESH_NOW)
    with pytest.raises(HoldingsImportError, match="as_of"):
        holdings_status(as_of, now=FRESH_NOW)


def test_future_as_of_refuses():
    with pytest.raises(HoldingsImportError, match="after now"):
        holdings_status(datetime(2026, 10, 8, 10, 0, tzinfo=NY), now=FRESH_NOW)


@pytest.mark.parametrize("as_of,now,expected", [
    (datetime(2026, 10, 7, 22, 45, tzinfo=NY), FRESH_NOW, "fresh"),
    (datetime(2026, 10, 7, 22, 45, tzinfo=NY), datetime(2026, 10, 8, 23, 0, tzinfo=NY), "fresh"),
    (datetime(2026, 10, 7, 22, 45, tzinfo=NY), STALE_NOW, "stale"),
    # weekend: Friday export is fresh on Monday, stale on Tuesday (sessions, not calendar days)
    (datetime(2026, 10, 9, 22, 0, tzinfo=NY), datetime(2026, 10, 12, 9, 0, tzinfo=NY), "fresh"),
    (datetime(2026, 10, 9, 22, 0, tzinfo=NY), datetime(2026, 10, 13, 9, 0, tzinfo=NY), "stale"),
    # Thanksgiving 2026-11-26 is not a session
    (datetime(2026, 11, 25, 18, 0, tzinfo=NY), datetime(2026, 11, 27, 9, 0, tzinfo=NY), "fresh"),
    # Monday 22:45 ET is Tuesday in UTC; the NY session date decides, so Wednesday is stale
    (datetime(2026, 10, 13, 2, 45, tzinfo=UTC), datetime(2026, 10, 14, 9, 0, tzinfo=NY), "stale"),
])
def test_staleness_counts_nyse_sessions_in_new_york(as_of, now, expected):
    assert holdings_status(as_of, now=now) == expected


def test_stale_exposure_keeps_its_holdings():
    exposure = external_exposure(SNAP, now=STALE_NOW)
    assert exposure.status == "stale" and exposure.holdings == (Holding("EXMP", 2.0, "external"),)


def test_fresh_guard_counts_external_exposure():
    exposure = external_exposure(SNAP, now=FRESH_NOW)
    refusals = live_buy_refusals(exposure, [], PRICES, {"EXMP": 2.0, "OTHR": 1.0}, now=FRESH_NOW, **LIMITS)
    assert refusals == [("EXMP", "concentration")]  # 51.50 external + 51.50 buy > 100; OTHR 50 fits


def test_fresh_guard_counts_bot_holdings():
    exposure = external_exposure(SNAP, now=FRESH_NOW)
    refusals = live_buy_refusals(exposure, [Holding("OTHR", 1.5, "bot")], PRICES, {"OTHR": 0.6},
                                 now=FRESH_NOW, **LIMITS)
    assert refusals == [("OTHR", "concentration")]  # 75 bot + 30 buy > 100


@pytest.mark.parametrize("exposure,now,reason", [
    (external_exposure(SNAP, now=FRESH_NOW), STALE_NOW, "holdings_stale"),
    (None, FRESH_NOW, "holdings_missing"),
])
def test_stale_or_missing_holdings_refuse_every_buy(exposure, now, reason):
    refusals = live_buy_refusals(exposure, [], PRICES, {"EXMP": 0.1, "OTHR": 0.1}, now=now, **LIMITS)
    assert refusals == [("EXMP", reason), ("OTHR", reason)]


def test_csv_sources_declare_read_capabilities_only():
    require_capability("fidelity_positions_csv", "read_holdings")
    require_capability("fidelity_history_csv", "read_activity")
    for source in ("fidelity_positions_csv", "fidelity_history_csv"):
        with pytest.raises(CapabilityError, match="submit_orders"):
            require_capability(source, "submit_orders")


def test_capability_gate_opens_only_for_a_declared_submitter():
    declared = {"reviewed_adapter": frozenset({"read_holdings", "submit_orders"})}
    require_capability("reviewed_adapter", "submit_orders", declared=declared)  # green control
    with pytest.raises(CapabilityError, match="unknown source"):
        require_capability("fidelity_api", "read_holdings")
    with pytest.raises(CapabilityError, match="unknown capability"):
        require_capability("fidelity_positions_csv", "submit_order")
