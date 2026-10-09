"""Spec 057 U2 (T004): reconcile open reservations by client id; read positions for 054.

Rule 7: read every line before merge. Fakes only in tests; no Fidelity call happens here except
through an already-connected ``FidelityLive`` adapter.

What this module guarantees:

- **Unknown stays unknown (FR-006).** A reservation is released only when Fidelity reports a
  terminal status for its client id. No record, a non-terminal status, or a status call that fails
  keeps it open, and ``require_reconciled`` refuses any new decision while one is unresolved.
- **A security challenge stops everything.** ``HaltProfile`` from the adapter propagates.
- **Positions feed 054 as ``read_holdings`` (FR-008)** with an explicit source name, quantities
  from Fidelity and prices supplied by the caller; a position without a finite positive price is
  refused rather than valued at zero. Money-market sweep symbols are cash at $1.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from typing import Any

from fidelity_live import BrokerError, HaltProfile
from holdings_import import _CASH_SYMBOLS, HoldingsImportError, Position, PositionsSnapshot

TERMINAL = frozenset({"FILLED", "CANCELLED", "CANCELED", "EXPIRED", "REJECTED"})
SOURCE = "fidelity_live_positions"


class ReconciliationBlocked(RuntimeError):
    """At least one reservation has no known outcome; no new order decision may be made."""


def reconcile(gate: Any, adapter: Any, *, now: datetime) -> list[dict]:
    """Release reservations Fidelity reports terminal; report every open one with its state."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    report = []
    for row in gate.pending_orders():
        if row["terminal"]:
            continue
        client_id = row["client_order_id"]
        try:
            status = adapter.order_status(client_id)
        except HaltProfile:
            raise
        except BrokerError as exc:
            report.append({"client_order_id": client_id, "state": "status_unavailable", "detail": str(exc)})
            continue
        if status is None:
            report.append({"client_order_id": client_id, "state": "unknown"})
        elif str(status).upper() in TERMINAL:
            gate.record_order_outcome(client_id, terminal=True, reason=str(status).upper(), now=now)
            report.append({"client_order_id": client_id, "state": "released", "status": str(status).upper()})
        else:
            report.append({"client_order_id": client_id, "state": "working", "status": str(status)})
    return report


def require_reconciled(gate: Any, adapter: Any, *, now: datetime) -> list[dict]:
    """Reconcile, then refuse unless every open reservation has a known (working or terminal) state."""
    report = reconcile(gate, adapter, now=now)
    blocked = [r["client_order_id"] for r in report if r["state"] in ("unknown", "status_unavailable")]
    if blocked:
        raise ReconciliationBlocked(f"{len(blocked)} reservation(s) without a known outcome: {blocked}")
    return report


def read_holdings(adapter: Any, *, now: datetime, prices: dict[str, float],
                  account_fingerprint: str) -> PositionsSnapshot:
    """Fidelity positions as a 054 snapshot; quantities from Fidelity, prices from the caller."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    held = adapter.positions()
    positions = []
    for symbol in sorted(held):
        quantity = float(held[symbol])
        if not (math.isfinite(quantity) and quantity >= 0):
            raise HoldingsImportError(f"{symbol}: quantity {quantity!r} is not finite and non-negative")
        if _CASH_SYMBOLS.match(symbol):
            price = 1.0
        else:
            price = prices.get(symbol)
            if not (isinstance(price, (int, float)) and math.isfinite(price) and price > 0):
                raise HoldingsImportError(f"{symbol}: no finite positive price supplied; refusing to value it")
        positions.append(Position(symbol, quantity, float(price), quantity * float(price)))
    digest = hashlib.sha256(json.dumps({s: float(held[s]) for s in sorted(held)}, sort_keys=True).encode()).hexdigest()
    return PositionsSnapshot(tuple(positions), 0.0, now, digest, (account_fingerprint,), source=SOURCE)
