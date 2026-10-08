"""Spec 054: read-only normalization of Fidelity CSV exports.

Guarantees: account numbers never leave this module except as SHA-256
pseudonyms; every snapshot carries the export's own "Date downloaded"
instant (America/New_York) and the raw file's SHA-256; Fidelity's preamble,
"Pending Activity" and disclaimer/footer lines never become positions; a
value that should be numeric but is not refuses the whole import. No network,
no credentials, no order intents.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import csv
import hashlib
import io
import re
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
_CASH_SYMBOLS = re.compile(r"^(SPAXX|FDRXX|FZFXX|SPRXX|FCASH|CORE)\**$|^Cash$", re.I)


class HoldingsImportError(ValueError):
    """An export that must not be used."""


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: float
    price: float
    market_value: float


@dataclass(frozen=True)
class PositionsSnapshot:
    positions: tuple[Position, ...]
    cash_usd: float
    as_of: datetime
    raw_sha256: str
    account_pseudonyms: tuple[str, ...]
    source: str = "fidelity_positions_csv"


@dataclass(frozen=True)
class Activity:
    run_date: date
    action: str
    symbol: str
    quantity: float
    amount: float
    cash_balance: float | None


@dataclass(frozen=True)
class HistorySnapshot:
    activity: tuple[Activity, ...]
    as_of: datetime
    raw_sha256: str
    source: str = "fidelity_history_csv"


def _number(value: str, field: str, symbol: str, *, blank_ok: bool = True) -> float | None:
    cleaned = (value or "").strip().replace("$", "").replace(",", "").replace("%", "")
    if cleaned in ("", "--", "n/a"):
        if blank_ok:
            return None
        raise HoldingsImportError(f"{symbol}: {field} is blank")
    try:
        return float(cleaned)
    except ValueError as error:
        raise HoldingsImportError(f"{symbol}: {field} {value!r} is not numeric") from error


def _downloaded(text: str) -> datetime:
    for line in text.splitlines():
        stripped = line.strip().strip('"')
        if not stripped.startswith("Date downloaded"):
            continue
        stamp = stripped[len("Date downloaded"):].strip()
        stamp = re.sub(r"\s*ET$", "", stamp)
        stamp = re.sub(r"\b([ap])\.?m\.?$", lambda m: m.group(1).upper() + "M", stamp, flags=re.I)
        for fmt in ("%m/%d/%Y %I:%M %p", "%b-%d-%Y %I:%M %p"):
            try:
                return datetime.strptime(stamp, fmt).replace(tzinfo=NY)
            except ValueError:
                continue
        raise HoldingsImportError(f"Date downloaded {stamp!r} not understood")
    raise HoldingsImportError("Date downloaded line missing: export time unknown")


def _rows(text: str, first_header: str) -> list[dict]:
    lines = text.replace("\r\n", "\n").split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith(first_header)), None)
    if start is None:
        raise HoldingsImportError(f"header starting {first_header!r} not found")
    block = []
    for line in lines[start:]:
        if not line.strip():
            break
        block.append(line)
    return list(csv.DictReader(io.StringIO("\n".join(block))))


def parse_positions_csv(text: str) -> PositionsSnapshot:
    """Normalize a Fidelity Positions export into a dated, pseudonymized snapshot."""
    as_of = _downloaded(text)
    positions, cash, accounts = [], 0.0, set()
    for row in _rows(text, "Account Number"):
        symbol = (row.get("Symbol") or "").strip()
        if row.get("Account Number"):
            accounts.add(hashlib.sha256(row["Account Number"].strip().encode()).hexdigest())
        if not symbol or symbol == "Pending Activity":
            continue
        value = _number(row.get("Current Value", ""), "Current Value", symbol)
        if _CASH_SYMBOLS.match(symbol):
            cash += value or 0.0
            continue
        quantity = _number(row.get("Quantity", ""), "Quantity", symbol, blank_ok=False)
        price = _number(row.get("Last Price", ""), "Last Price", symbol, blank_ok=False)
        positions.append(Position(symbol, quantity, price, value if value is not None else quantity * price))
    return PositionsSnapshot(tuple(positions), cash, as_of, hashlib.sha256(text.encode()).hexdigest(),
                             tuple(sorted(accounts)))


def parse_history_csv(text: str) -> HistorySnapshot:
    """Normalize a Fidelity activity/History export; run dates are session labels."""
    as_of = _downloaded(text)
    activity = []
    for row in _rows(text, "Run Date"):
        symbol = (row.get("Symbol") or "").strip()
        run_date = datetime.strptime(row["Run Date"].strip(), "%m/%d/%Y").date()
        activity.append(Activity(
            run_date, (row.get("Action") or "").strip(), symbol,
            _number(row.get("Quantity", ""), "Quantity", symbol or "cash") or 0.0,
            _number(row.get("Amount ($)", ""), "Amount", symbol or "cash", blank_ok=False),
            _number(row.get("Cash Balance ($)", ""), "Cash Balance", symbol or "cash"),
        ))
    return HistorySnapshot(tuple(activity), as_of, hashlib.sha256(text.encode()).hexdigest())
