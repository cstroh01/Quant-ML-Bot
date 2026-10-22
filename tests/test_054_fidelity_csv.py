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


CASH_ONLY_2026_10 = (  # Fidelity's October 2026 layout: sentence-case headers, trailing comma
    "Account number,Account name,Symbol,Description,Quantity,Last price,Last price change,Current value,"
    "Today's gain/loss dollar,Today's gain/loss percent,Total gain/loss dollar,Total gain/loss percent,"
    "Percent of account,Cost basis total,Average cost basis,Type\n"
    "Z00000000,Individual,SPAXX**,HELD IN MONEY MARKET,,,,$49.00,,,,,100.00%,,,Cash,\n"
    "\n"
    '"Date downloaded Oct-07-2026 10:45 p.m ET"\n'
)


def test_sentence_case_headers_parse_like_title_case():
    snap = parse_positions_csv(CASH_ONLY_2026_10)
    assert snap.positions == () and snap.cash_usd == 49.0
    assert snap.as_of == datetime(2026, 10, 7, 22, 45, tzinfo=NY)
    assert len(snap.account_pseudonyms) == 1 and "Z00000000" not in repr(snap)
    other = POSITIONS.replace("Account Number", "account number").replace("Current Value", "CURRENT VALUE")
    assert other != POSITIONS
    assert parse_positions_csv(other).positions == parse_positions_csv(POSITIONS).positions
    assert parse_positions_csv(other).cash_usd == parse_positions_csv(POSITIONS).cash_usd


def test_headers_differing_only_in_case_refuse():
    body = CASH_ONLY_2026_10.replace("Account name", "Current VALUE", 1)
    with pytest.raises(HoldingsImportError, match="duplicate column headers"):
        parse_positions_csv(body)


@pytest.mark.parametrize("renamed", [("Symbol", "Ticker"), ("Current value", "Current value ($)")])
def test_a_renamed_required_positions_column_refuses_instead_of_reading_empty(renamed):
    # A renamed column used to parse as "no positions, $0 cash": a plausible, wrong snapshot.
    # (A renamed "Account number" already refuses: the header line is located by that column.)
    body = CASH_ONLY_2026_10.replace(renamed[0], renamed[1], 1)
    with pytest.raises(HoldingsImportError, match="missing required column"):
        parse_positions_csv(body)


@pytest.mark.parametrize("renamed", [("Action", "Activity"), ("Symbol", "Ticker"), ("Quantity", "Shares"),
                                     ("Amount ($)", "Amount")])
def test_a_renamed_required_history_column_refuses(renamed):
    with pytest.raises(HoldingsImportError, match="missing required column"):
        parse_history_csv(HISTORY.replace(renamed[0], renamed[1], 1))


def test_row_membership_ignores_case_like_lookup():
    from holdings_import import _rows
    row = _rows(CASH_ONLY_2026_10, "Account Number")[0]
    assert "Symbol" in row and "symbol" in row and row["SYMBOL"] == row.get("Symbol") == "SPAXX**"


def test_history_headers_match_without_regard_to_case():
    lowered = HISTORY.replace("Run Date", "Run date").replace("Amount ($)", "amount ($)")
    assert lowered != HISTORY
    assert parse_history_csv(lowered).activity == parse_history_csv(HISTORY).activity


@pytest.mark.parametrize("token", ["NaN", "nan", "Infinity", "-inf", "1e999"])
@pytest.mark.parametrize("parser,name,old", [
    (parse_positions_csv, "positions_example.csv", "$25.75"),
    (parse_history_csv, "history_example.csv", ",-51,"),
])
def test_non_finite_numbers_refuse(parser, name, old, token):
    source = text(name)
    assert old in source
    with pytest.raises(HoldingsImportError, match="finite"):
        parser(source.replace(old, f",{token}," if old.startswith(",") else token, 1))
