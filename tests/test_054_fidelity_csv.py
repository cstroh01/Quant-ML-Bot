"""Spec 054 U1: Fidelity CSV exports parse into normalized snapshots.

Fixtures mirror Fidelity's real export layout with synthetic values. EXAMPLE — NOT A RESULT.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import context  # noqa: F401
from fidelity_fixtures import HISTORY, POSITIONS
from holdings_import import HoldingsImportError, parse_history_csv, parse_positions_csv

NY = ZoneInfo("America/New_York")


def text(name):
    return {"positions_example.csv": POSITIONS, "history_example.csv": HISTORY}[name]


def test_positions_parse_symbols_quantities_cash_and_as_of():
    snap = parse_positions_csv(text("positions_example.csv"))
    assert [(p.symbol, p.quantity, p.price, p.market_value) for p in snap.positions] == [("EXMP", 2.0, 25.75, 51.5)]
    assert snap.cash_usd == 49.0
    assert snap.as_of == datetime(2026, 10, 7, 22, 45, tzinfo=NY)
    assert len(snap.raw_sha256) == 64 and snap.source == "fidelity_positions_csv"


def test_account_numbers_are_pseudonymized_never_kept():
    snap = parse_positions_csv(text("positions_example.csv"))
    assert "Z00000000" not in repr(snap)
    assert all(len(a) == 64 for a in snap.account_pseudonyms)


def test_footer_disclaimer_and_pending_activity_are_not_positions():
    snap = parse_positions_csv(text("positions_example.csv"))
    symbols = {p.symbol for p in snap.positions}
    assert "Pending Activity" not in symbols and not any("data and information" in s for s in symbols)


def test_history_parses_activity_and_cash_balance():
    hist = parse_history_csv(text("history_example.csv"))
    assert [(a.run_date.isoformat(), a.symbol, a.quantity, a.amount, a.cash_balance) for a in hist.activity] == [
        ("2026-09-25", "", 0.0, 100.0, 100.0), ("2026-10-01", "EXMP", 2.0, -51.0, 49.0)]
    assert hist.as_of == datetime(2026, 10, 7, 22, 41, tzinfo=NY)


@pytest.mark.parametrize("parser,name", [(parse_positions_csv, "positions_example.csv"),
                                         (parse_history_csv, "history_example.csv")])
def test_missing_download_timestamp_refuses(parser, name):
    body = "\n".join(line for line in text(name).splitlines() if "Date downloaded" not in line)
    with pytest.raises(HoldingsImportError, match="Date downloaded"):
        parser(body)


def test_line_endings_do_not_change_the_parse():
    crlf = text("positions_example.csv").replace("\r\n", "\n").replace("\n", "\r\n")
    lf = crlf.replace("\r\n", "\n")
    assert parse_positions_csv(crlf).positions == parse_positions_csv(lf).positions


def test_non_numeric_quantity_refuses():
    body = text("positions_example.csv").replace(",EXMP,EXAMPLE ETF,2,", ",EXMP,EXAMPLE ETF,two,")
    with pytest.raises(HoldingsImportError, match="EXMP"):
        parse_positions_csv(body)
