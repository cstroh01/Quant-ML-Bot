"""064 T002: EXAMPLE — NOT A RESULT. Synthetic transfer evidence only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import json
import socket

import pytest
import context  # noqa: F401
from cash_flow_journal import empty_journal, reconcile

ACCOUNT, OTHER = "a" * 64, "b" * 64
NOW = datetime(2026, 10, 21, 14, tzinfo=timezone.utc)
SOURCES = {"fixture_transfer_feed"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("external network forbidden")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def event(**changes):
    return dict(transfer_id="transfer-1", account_fingerprint=ACCOUNT,
                source_id="fixture_transfer_feed", evidence_ref="c" * 64,
                direction="deposit", amount="10.01", currency="USD",
                observed_at=NOW.isoformat(), effective_at=NOW.isoformat(),
                status="settled") | changes


def run(events, journal=None, **changes):
    return reconcile(empty_journal(ACCOUNT, SOURCES) if journal is None else journal,
                     events, account_fingerprint=ACCOUNT, approved_sources=SOURCES,
                     as_of=NOW, **changes)


def test_exact_signed_flow_purity_and_serialized_restart():
    initial = empty_journal(ACCOUNT, SOURCES)
    events = [event(), event(transfer_id="withdraw-1", direction="withdrawal", amount="-2.02")]
    before = deepcopy((initial, events))
    with localcontext() as ctx:
        ctx.prec = 2
        result = run(events, initial)
    assert result.net_flow == Decimal("7.99"), "FLOW exact signed arithmetic"
    assert not result.quarantined and not result.journal["blocked"]
    assert (initial, events) == before, "FLOW inputs mutated"
    restarted = json.loads(json.dumps(result.journal))
    assert run(list(reversed(events)) * 2, restarted).net_flow == 0, "FLOW restart dedupe"


def test_pending_settles_once_and_observation_changes_are_not_conflicts():
    pending = event(status="pending", observed_at=(NOW - timedelta(hours=1)).isoformat())
    first = run([pending])
    assert first.net_flow == 0 and not first.quarantined, "FLOW unsettled counted"
    second = run([event()], json.loads(json.dumps(first.journal)))
    assert second.net_flow == Decimal("10.01"), "FLOW settlement lost"
    assert run([pending, event()], second.journal).net_flow == 0, "FLOW transition duplicated"


@pytest.mark.parametrize("reverse", [False, True])
def test_batch_conflict_validated_before_any_flow(reverse):
    events = [event(), event(amount="11.01"), event(transfer_id="other")]
    result = run(list(reversed(events)) if reverse else events)
    assert result.net_flow == 0 and result.journal["entries"] == {}, "FLOW batch conflict applied"
    assert {q["reason"] for q in result.quarantined} == {"identity_conflict"}
    later = run([event()], json.loads(json.dumps(result.journal)))
    assert later.net_flow == 0 and later.journal["blocked"], "FLOW quarantine lost on restart"


@pytest.mark.parametrize("field,value", [
    ("amount", "9.00"), ("evidence_ref", "d" * 64),
    ("effective_at", (NOW - timedelta(seconds=1)).isoformat()),
    ("direction", "withdrawal"),
])
def test_seen_identity_payload_is_checked_before_dedupe(field, value):
    original = run([event()]).journal
    result = run([event(**{field: value})], original)
    assert result.net_flow == 0 and result.quarantined, "FLOW seen payload ignored"
    assert result.journal["blocked"] and not original["blocked"]


@pytest.mark.parametrize("change", [
    {"account_fingerprint": OTHER}, {"source_id": "unapproved"},
    {"transfer_id": ""}, {"evidence_ref": ""}, {"status": "unknown"},
    {"direction": "dividend"}, {"currency": "EUR"}, {"amount": True},
    {"amount": 1.5}, {"amount": "NaN"}, {"amount": "Infinity"},
    {"amount": Decimal("-Infinity")}, {"amount": "0"},
    {"amount": "-1"}, {"equity_change": "100"},
    {"effective_at": NOW + timedelta(microseconds=1)},
    {"observed_at": NOW + timedelta(microseconds=1)},
    {"effective_at": NOW.replace(tzinfo=None)},
])
def test_ambiguous_unsupported_and_future_events_quarantine(change):
    candidate = event(**change)
    result = run([candidate])
    assert result.net_flow == 0 and result.quarantined, "FLOW invalid attribution applied"
    assert result.journal["blocked"] and result.journal["entries"] == {}
    assert all(set(q) == {"index", "reason"} for q in result.quarantined)
    assert "amount" not in repr(result.quarantined), "FLOW raw payload disclosed"


def test_effective_boundary_and_timezone_equivalence():
    candidate = event(amount=Decimal("0.000000000000000001"),
                      effective_at=NOW.astimezone(timezone(timedelta(hours=-4))))
    result = run([candidate])
    assert result.net_flow == Decimal("0.000000000000000001"), "FLOW boundary shifted"


def test_pending_transition_after_calendar_gap_and_foreign_batch_atomicity():
    earlier = NOW - timedelta(days=4)
    first = event(status="pending", observed_at=earlier, effective_at=earlier)
    journal = run([first]).journal
    settled = first | {"status": "settled", "observed_at": NOW}
    assert run([settled], journal).net_flow == Decimal("10.01"), "FLOW calendar gap lost"
    refused = run([event(), event(transfer_id="foreign", account_fingerprint=OTHER)])
    assert refused.net_flow == 0 and not refused.journal["entries"], "FLOW partial batch applied"


def test_numeric_amount_representations_are_identical_not_new_flows():
    original = run([event()]).journal
    again = run([event(amount="10.010")], original)
    assert not again.quarantined and again.net_flow == 0, "FLOW numeric identity mismatch"
    assert not run([event(amount=Decimal("10.0100")), event()]).quarantined


def test_future_pending_waits_then_settles_after_effective_boundary():
    effective = NOW + timedelta(days=2)
    pending = event(status="pending", effective_at=effective)
    waiting = run([pending])
    assert waiting.net_flow == 0 and not waiting.quarantined, "FLOW normal pending latched"
    assert not waiting.journal["blocked"] and waiting.journal["entries"]
    kwargs = dict(account_fingerprint=ACCOUNT, approved_sources=SOURCES)
    restart = json.loads(json.dumps(waiting.journal))
    before = reconcile(restart, [], as_of=effective - timedelta(microseconds=1), **kwargs)
    assert before.net_flow == 0 and not before.quarantined, "FLOW pending spent early"
    settled = pending | {"status": "settled", "observed_at": effective}
    boundary = reconcile(before.journal, [settled], as_of=effective, **kwargs)
    assert boundary.net_flow == Decimal("10.01") and not boundary.quarantined
    assert reconcile(boundary.journal, [settled], as_of=effective, **kwargs).net_flow == 0
    assert run([pending | {"observed_at": NOW + timedelta(seconds=1)}]).quarantined


def test_input_order_and_source_provenance():
    sources = SOURCES | {"second_fixture_feed"}
    events = [event(status="pending"), event(), event(transfer_id="transfer-2", source_id="second_fixture_feed")]
    journal = empty_journal(ACCOUNT, sources)
    kwargs = dict(account_fingerprint=ACCOUNT, approved_sources=sources, as_of=NOW)
    left = reconcile(journal, events, **kwargs)
    right = reconcile(journal, list(reversed(events)), **kwargs)
    assert left.net_flow == Decimal("20.02") and left.journal == right.journal
    assert reconcile(left.journal, events, **kwargs).net_flow == 0
    conflict = reconcile(journal, [event(), event(source_id="second_fixture_feed")], **kwargs)
    assert conflict.net_flow == 0 and conflict.quarantined, "FLOW source swap evaded identity"


@pytest.mark.parametrize("corruption", [
    {"schema": 2}, {"account_fingerprint": OTHER}, {"blocked": False, "quarantine_reasons": ["invalid_event"]},
    {"entries": {"forged": {}}}, {"approved_sources": ["unapproved"]},
    {"as_of": (NOW + timedelta(seconds=1)).isoformat()},
])
def test_corrupt_snapshot_refuses_without_silent_reset(corruption):
    journal = run([event()]).journal | corruption
    with pytest.raises(ValueError, match="journal"):
        run([event()], journal)


def test_applied_marker_is_validated_and_missing_identity_is_not_inferred():
    journal = run([event(status="pending")]).journal
    next(iter(journal["entries"].values()))["applied"] = True
    with pytest.raises(ValueError, match="journal"):
        run([], journal)
    with pytest.raises(ValueError, match="as_of"):
        reconcile(empty_journal(ACCOUNT, SOURCES), [], account_fingerprint=ACCOUNT,
                  approved_sources=SOURCES, as_of=NOW.replace(tzinfo=None))
    for invalid in (None, {"cash_change": "100"}, {"equity": "100"}):
        assert run([invalid]).quarantined, "FLOW inferred unidentified transfer"
