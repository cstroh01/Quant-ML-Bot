"""Spec 054: read-only normalization of Fidelity CSV exports.

Guarantees: account numbers never leave this module except as SHA-256
pseudonyms; every snapshot carries the export's own "Date downloaded"
instant (America/New_York) and the raw file's SHA-256; Fidelity's preamble,
"Pending Activity" and disclaimer/footer lines never become positions; a
value that should be numeric but is not refuses the whole import. U2: every
imported position is external, staleness is judged in NYSE sessions, and only a
declared capability is ever granted. No network, no credentials, no order intents.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import csv
import hashlib
import io
import re
from zoneinfo import ZoneInfo

from data import trading_days
from mode_config import Holding, concentration_refusals

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
    currency: str = "USD"  # Fidelity's US Positions export is USD-denominated ($-prefixed values)


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


# --- U2: ownership, staleness and capability gates (FR-003/004/005, D-3, D-4) ---

CAPABILITIES = frozenset({"read_holdings", "read_activity", "submit_orders"})
SOURCE_CAPABILITIES: dict[str, frozenset[str]] = {
    "fidelity_positions_csv": frozenset({"read_holdings"}),
    "fidelity_history_csv": frozenset({"read_activity"}),
    "fidelity_live_positions": frozenset({"read_holdings"}),  # 057 U2 positions read (FR-008)
}
MAX_AGE_SESSIONS = 1  # D-3: stale after one NYSE business day
_EPS = 1e-9


class CapabilityError(PermissionError):
    """A source asked to do something it never declared it can do."""


def require_capability(source: str, capability: str, *,
                       declared: dict[str, frozenset[str]] = SOURCE_CAPABILITIES) -> None:
    """Return only if ``source`` itself declared ``capability``; no label stands in for another."""
    if capability not in CAPABILITIES:
        raise CapabilityError(f"unknown capability {capability!r}")
    if source not in declared:
        raise CapabilityError(f"unknown source {source!r}")
    if capability not in declared[source]:
        raise CapabilityError(f"{source} declares {sorted(declared[source])}, not {capability}")


def holdings_status(as_of: datetime | None, *, now: datetime) -> str:
    """``fresh`` or ``stale`` by NYSE sessions elapsed on the New York calendar.

    Guarantees: a missing, naive or future ``as_of`` refuses; a snapshot is stale
    once more than MAX_AGE_SESSIONS sessions have opened after its New York date,
    so weekends and exchange holidays never age it and a late-evening ET export
    is never moved to the next UTC day.
    """
    if now.tzinfo is None:
        raise HoldingsImportError("now must be timezone-aware")
    if as_of is None or as_of.tzinfo is None:
        raise HoldingsImportError("snapshot as_of missing or naive: exposure time unknown")
    if as_of > now:
        raise HoldingsImportError(f"snapshot as_of {as_of.isoformat()} is after now")
    elapsed = trading_days(as_of.astimezone(NY).date() + timedelta(days=1), now.astimezone(NY).date())
    return "stale" if len(elapsed) > MAX_AGE_SESSIONS else "fresh"


@dataclass(frozen=True)
class ExternalExposure:
    holdings: tuple[Holding, ...]
    cash_usd: float
    as_of: datetime
    status: str
    source: str
    excluded: tuple[tuple[str, str], ...] = field(default=())


def external_exposure(snapshot: PositionsSnapshot, *, now: datetime,
                      bot_lots: dict[str, float] | None = None) -> ExternalExposure:
    """Imported positions as ``owner="external"`` holdings, net of lots the bot itself opened.

    Guarantees: no imported quantity is ever bot-owned; a money-market sweep is
    cash, not a position; a non-USD row is excluded with a reason; a stale
    snapshot keeps its holdings (status says stale, quantities are never zeroed);
    a bot lot the import cannot cover refuses rather than being clipped.
    """
    status = holdings_status(snapshot.as_of, now=now)
    imported: dict[str, float] = {}
    excluded, cash = [], snapshot.cash_usd
    for position in snapshot.positions:
        if position.currency != "USD":
            excluded.append((position.symbol, f"non_usd:{position.currency}"))
        elif _CASH_SYMBOLS.match(position.symbol):
            cash += position.market_value
        else:
            imported[position.symbol] = imported.get(position.symbol, 0.0) + position.quantity
    lots = dict(bot_lots or {})
    short = sorted(s for s, q in lots.items() if q > imported.get(s, 0.0) + _EPS)
    if short:
        raise HoldingsImportError(f"bot lot exceeds imported quantity: {short}")
    holdings = tuple(Holding(s, q - lots.get(s, 0.0), "external") for s, q in imported.items()
                     if q - lots.get(s, 0.0) > _EPS)
    return ExternalExposure(holdings, cash, snapshot.as_of, status, snapshot.source, tuple(excluded))


def live_buy_refusals(exposure: ExternalExposure | None, bot_holdings: list[Holding], prices: dict[str, float],
                      proposed_buy_qty: dict[str, float], *, now: datetime, portfolio_value: float,
                      max_position_pct: float) -> list[tuple[str, str]]:
    """(ticker, reason) for each proposed LIVE buy that must not proceed.

    Guarantees: missing or stale external holdings refuse every buy
    (``holdings_missing`` / ``holdings_stale``), because unknown exposure is never
    read as zero; with fresh holdings a buy is refused (``concentration``) when
    bot plus external exposure after it exceeds the 051 limit.
    """
    if exposure is None:
        return [(t, "holdings_missing") for t in sorted(proposed_buy_qty)]
    if holdings_status(exposure.as_of, now=now) != "fresh":
        return [(t, "holdings_stale") for t in sorted(proposed_buy_qty)]
    held = list(bot_holdings) + list(exposure.holdings)
    return [(t, "concentration") for t in concentration_refusals(
        held, prices, proposed_buy_qty, portfolio_value=portfolio_value, max_position_pct=max_position_pct)]
