"""061 T006e/f: EXAMPLE — NOT A RESULT. Fake sends and recorded synthetic sessions."""
from datetime import date, datetime, timedelta, timezone

import pytest
import context
from test_110_paper_allocation import Client
from paper_loop import Durable, RunAborted, _durable_send
from paper_loop import run_once
from live_safety_gate import OrderIntent
from allocation_policy import policy_evidence
from paper_evidence import completed_sessions, evidence_rows

CUTOFF = datetime(2026, 10, 19, 13, 15, tzinfo=timezone.utc)  # 08:15 Chicago


@pytest.mark.parametrize("instant", [CUTOFF, CUTOFF + timedelta(microseconds=1)])
def test_no_send_at_or_after_deadline(instant):
    client = Client()
    send = _durable_send(client, None, date(2026, 10, 19), "buy", 10,
                         before=CUTOFF, now_fn=lambda: instant)
    with pytest.raises(RunAborted, match="supervised submission cutoff"):
        send(OrderIntent("synthetic", "SPY", 1.0))
    assert client.submitted == [], "061 CUTOFF no broker call at or after cutoff"


def test_deadline_crossed_while_persisting_never_sends(tmp_path):
    client = Client()
    time = [CUTOFF - timedelta(seconds=1)]
    durable = Durable(tmp_path, lambda: time.__setitem__(0, CUTOFF))
    send = _durable_send(client, durable, date(2026, 10, 19), "buy", 10,
                         before=CUTOFF, now_fn=lambda: time[0])
    with pytest.raises(RunAborted, match="supervised submission cutoff"):
        send(OrderIntent("synthetic", "SPY", 1.0))
    assert client.submitted == [], "061 CUTOFF slow state push cannot cross the deadline"


def test_before_deadline_sends_once_and_requires_aware_instants():
    client = Client()
    send = _durable_send(client, None, date(2026, 10, 19), "buy", 10,
                         before=CUTOFF, now_fn=lambda: CUTOFF - timedelta(microseconds=1))
    send(OrderIntent("synthetic", "SPY", 1.0))
    assert len(client.submitted) == 1
    with pytest.raises(RunAborted, match="timezone-aware"):
        _durable_send(client, None, date(2026, 10, 19), "buy", 10, before=CUTOFF.replace(tzinfo=None))
    send = _durable_send(client, None, date(2026, 10, 19), "buy", 10,
                         before=CUTOFF, now_fn=lambda: CUTOFF.replace(tzinfo=None))
    with pytest.raises(RunAborted, match="timezone-aware"): send(OrderIntent("synthetic", "SPY", 1.0))


def test_expired_run_refuses_before_any_broker_read():
    class UnavailableClient:
        def clock(self): raise AssertionError('broker read after expired deadline')
    with pytest.raises(RunAborted,match='cutoff reached'):
        run_once(client=UnavailableClient(),gate=None,closes=None,submit=True,submit_before=CUTOFF,now_fn=lambda:CUTOFF)


def test_old_policy_and_drill_runs_never_count_or_supply_fills():
    base = {"profile":"paper_small", "mode":"submit", "session":"2026-10-16", "actions":[],
            "allocation":policy_evidence(), "evidence_scope":"qualifying"}
    assert completed_sessions([base]) == {"paper_small":[date(2026, 10, 16)]}
    for update in ({"allocation":None}, {"allocation":{"policy_id":"059-a1"}}, {"evidence_scope":"drill"}):
        record = base | update
        assert completed_sessions([record]) == {}, "061 SCOPE excluded allocation/drill cannot start the clock"
        assert evidence_rows([record], {}, {}, {}) == [], "061 SCOPE excluded fill cannot satisfy another policy"
