"""Spec 057 U2 (T004): reconciliation by client id and positions for 054. Fakes only. EXAMPLE — NOT A RESULT."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

import pytest

import context  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exec"))
from fidelity_live import BrokerError, HaltProfile  # noqa: E402
from fidelity_reconcile import (SOURCE, ReconciliationBlocked, read_holdings, reconcile,  # noqa: E402
                                require_reconciled)
from holdings_import import CapabilityError, HoldingsImportError, external_exposure, require_capability  # noqa: E402

NOW = datetime(2026, 10, 8, 13, 0, tzinfo=timezone.utc)
FP = hashlib.sha256(b"synthetic-account").hexdigest()


class Gate:
    """The two reservation hooks of LiveSafetyGate that reconciliation uses."""

    def __init__(self, *ids, terminal=()):
        self.rows = [{"client_order_id": i, "terminal": i in terminal} for i in ids]
        self.released = []

    def pending_orders(self):
        return [dict(r) for r in self.rows]

    def record_order_outcome(self, client_order_id, *, terminal, reason, now):
        assert terminal and now.tzinfo is not None
        self.released.append((client_order_id, reason))
        for r in self.rows:
            if r["client_order_id"] == client_order_id:
                r["terminal"] = True


class Adapter:
    def __init__(self, statuses=None, error=None, held=None):
        self.statuses, self.error, self.held = statuses or {}, error, held or {}
        self.asked = []

    def order_status(self, client_order_id):
        self.asked.append(client_order_id)
        if self.error:
            raise self.error
        return self.statuses.get(client_order_id)

    def positions(self):
        return dict(self.held)


def test_terminal_status_releases_and_working_stays_open():
    gate = Gate("a", "b", "c", terminal=("c",))
    report = reconcile(gate, Adapter({"a": "Filled", "b": "OPEN"}), now=NOW)
    assert gate.released == [("a", "FILLED")]
    assert {r["client_order_id"]: r["state"] for r in report} == {"a": "released", "b": "working"}


def test_no_record_or_failed_lookup_stays_open_and_blocks_new_decisions():
    for adapter, state in [(Adapter({}), "unknown"), (Adapter(error=BrokerError("status failed: X")), "status_unavailable")]:
        gate = Gate("a")
        assert reconcile(gate, adapter, now=NOW)[0]["state"] == state and gate.released == []
        with pytest.raises(ReconciliationBlocked, match="1 reservation"):
            require_reconciled(gate, adapter, now=NOW)


def test_clean_reconciliation_allows_decisions():
    gate = Gate("a", "b")
    report = require_reconciled(gate, Adapter({"a": "CANCELED", "b": "ACCEPTED"}), now=NOW)
    assert [r["state"] for r in report] == ["released", "working"]


def test_security_challenge_during_reconciliation_propagates():
    with pytest.raises(HaltProfile):
        reconcile(Gate("a"), Adapter(error=HaltProfile("challenge")), now=NOW)


def test_naive_now_refuses():
    with pytest.raises(ValueError):
        reconcile(Gate("a"), Adapter(), now=datetime(2026, 10, 8, 13, 0))


def test_positions_feed_054_with_their_own_source_and_cash_sweep():
    snap = read_holdings(Adapter(held={"AAA": 3.0, "SPAXX**": 120.0}), now=NOW, prices={"AAA": 10.0},
                         account_fingerprint=FP)
    assert snap.source == SOURCE and snap.as_of == NOW and snap.account_pseudonyms == (FP,)
    exposure = external_exposure(snap, now=NOW)
    assert [(h.ticker, h.quantity, h.owner) for h in exposure.holdings] == [("AAA", 3.0, "external")]
    assert exposure.cash_usd == 120.0


@pytest.mark.parametrize("held,prices", [({"AAA": 3.0}, {}), ({"AAA": 3.0}, {"AAA": float("nan")}),
                                         ({"AAA": 3.0}, {"AAA": 0.0}), ({"AAA": float("inf")}, {"AAA": 1.0}),
                                         ({"AAA": -1.0}, {"AAA": 1.0})])
def test_unpriced_or_invalid_positions_refuse(held, prices):
    with pytest.raises(HoldingsImportError):
        read_holdings(Adapter(held=held), now=NOW, prices=prices, account_fingerprint=FP)


def test_live_positions_source_declares_read_holdings_only():
    require_capability(SOURCE, "read_holdings")
    with pytest.raises(CapabilityError):
        require_capability(SOURCE, "submit_orders")


@pytest.mark.parametrize("status", ["UNKNOWN", "unknown", "Verifying", "", "SUSPENDED?"])
def test_unrecognized_or_unknown_status_blocks_new_decisions(status):
    gate = Gate("a")
    with pytest.raises(ReconciliationBlocked):
        require_reconciled(gate, Adapter({"a": status}), now=NOW)
    assert gate.released == []


@pytest.mark.parametrize("status", ["OPEN", "ACCEPTED", "Partially Filled", "pending"])
def test_known_working_statuses_allow_decisions_and_stay_open(status):
    gate = Gate("a")
    report = require_reconciled(gate, Adapter({"a": status}), now=NOW)
    assert report[0]["state"] == "working" and gate.released == []
