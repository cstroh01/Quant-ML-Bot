"""Armed LIVE cash basis: in-run fills and T+1 settlement are not P&L to the real gate.

EXAMPLE — NOT A RESULT. Fake filling broker, synthetic flat bars, real SQLite
LiveSafetyGate, sockets blocked. Settled cash moves only on the next session
(T+1), as a cash account's settled balance does; that Fidelity timing itself is
not verified here. Regression for the P1 in the independent reviews of #292/#293.
"""
from dataclasses import replace
from datetime import timedelta
import json

import pandas as pd
import pytest

import context  # noqa: F401
from test_057_q139 import blocked, NOW  # noqa: F401
from test_057_q135 import process  # noqa: F401
from test_057_q137 import Broker, bars, execute, profile
from live_safety_gate import DENY_LOSS_HALT, LiveSafetyGate
from mode_config import ArmingRecord
import fidelity_session as fs
import live_loop as loop

BUDGET = 200.0


class FillingBroker(Broker):
    """Every placed order fills at once at the last close; settled cash is set per day."""
    def __init__(self, closes, settled=BUDGET, held=None):
        super().__init__()
        self.close = {s: float(closes.iloc[-1][s]) for s in closes.columns}
        self.settled, self.held, self.spent = settled, dict(held or {}), 0.0

    def place(self, symbol, side, quantity, conf_num):
        self.calls.append(('place', symbol, side, quantity, conf_num))
        signed = quantity if side.upper().startswith('B') else -quantity
        self.held[symbol] = self.held.get(symbol, 0.0) + signed
        self.spent += signed * self.close[symbol]
        return conf_num

    def status(self, conf_num): return 'FILLED'
    def positions(self): return {'SPAXX': self.settled, **{s: q for s, q in self.held.items() if q}}
    def prices(self): return {s: self.close[s] for s, q in self.held.items() if q}
    def settled_cash(self, now):
        return {'amount': self.settled, 'settled_amt': self.settled, 'coreBalance': self.settled,
                'as_of': now.isoformat()}


def armed(now):
    return ArmingRecord('live_fidelity', profile().account_fingerprint, 'e' * 64, 'Camden',
                        now - timedelta(hours=1), now + timedelta(days=5))


def through(closes, run_at):
    """Append the flat completed session before ``run_at``; history is retained exactly."""
    c = closes.copy()
    c.loc[pd.Timestamp(loop.previous_session(run_at.astimezone(fs.NY).date()))] = c.iloc[-1]
    return c


def run(tmp_path, gate, broker, now, closes):
    return execute(tmp_path, profile=replace(profile(), bot_budget_usd=BUDGET), gate=gate, broker=broker,
                   now=now, closes=closes, arming=armed(now), persist=lambda: None)


@pytest.fixture
def gate(tmp_path):
    g = LiveSafetyGate(tmp_path / 'live-gate.sqlite', loop.ALLOCATION_SAFETY_CONFIG)
    yield g
    g.close()


def test_armed_rebalance_then_settlement_never_reads_as_a_loss(tmp_path, gate, monkeypatch):
    seen = []
    flow, evaluate = LiveSafetyGate.observe_equity_with_flows, LiveSafetyGate.evaluate_order
    monkeypatch.setattr(LiveSafetyGate, 'observe_equity_with_flows',
                        lambda self, snapshot, **kw: seen.append(snapshot.equity) or flow(self, snapshot, **kw))
    monkeypatch.setattr(LiveSafetyGate, 'evaluate_order',
                        lambda self, snapshot, intent, **kw: seen.append(snapshot.equity) or evaluate(self, snapshot, intent, **kw))
    day1 = bars()
    broker = FillingBroker(day1)
    first = run(tmp_path, gate, broker, NOW, day1)
    assert not first.get('aborted') and first['place_calls'] >= 2, first.get('abort_kind')
    assert all(a['outcome'] in ('SUBMITTED', 'BUDGET_REFUSED') for a in first['actions'])
    assert 0 < broker.spent <= BUDGET * 0.2 + 1e-6
    closes = day1
    # Deployment spans several sessions under the 20% daily cap. Each morning the previous
    # session's fills have settled (T+1): settled cash falls by their actual cost.
    for day in (1, 4, 5):  # Fri 10-16, Mon 10-19, Tue 10-20: NYSE sessions
        monkeypatch.setattr(fs, '_STARTED', False)
        broker.settled = BUDGET - broker.spent
        run_at = NOW + timedelta(days=day)
        closes = through(closes, run_at)
        record = run(tmp_path, gate, broker, run_at, closes)
        assert not record.get('aborted'), (day, record.get('abort_kind'))
        assert not any(a.get('reason') == DENY_LOSS_HALT for a in record['actions']), day
        assert any(a['outcome'] == 'SUBMITTED' for a in record['actions']), day  # deployment continues
    # Flat prices and fills at the close: neither a fill nor its settlement is P&L.
    assert len(seen) > 8 and max(seen) - min(seen) < 1e-6, seen


def test_in_run_fills_leave_gate_equity_unchanged(tmp_path, gate, monkeypatch):
    seen = []
    original = LiveSafetyGate.evaluate_order

    def evaluate(self, snapshot, intent, **kw):
        seen.append(snapshot.equity)
        return original(self, snapshot, intent, **kw)
    monkeypatch.setattr(LiveSafetyGate, 'evaluate_order', evaluate)
    broker = FillingBroker(bars())
    record = run(tmp_path, gate, broker, NOW, bars())
    assert record['place_calls'] >= 2 and len(seen) >= 2
    assert max(seen) - min(seen) < 1e-9, seen  # fills move shares now, settled cash at T+1


def test_held_positions_count_at_last_close(tmp_path, gate):
    """Start-of-run holdings are valued at the last completed close, not the +5% bound."""
    closes = bars()
    held = {'SPY': 0.05}
    book = {'account_fingerprint': profile().account_fingerprint, 'positions': dict(held), 'orders': {}}
    (tmp_path / 'bot-positions.json').write_text(json.dumps(book))
    broker = FillingBroker(closes, settled=150.0, held=held)
    observed = []
    original = LiveSafetyGate.observe_equity_with_flows

    def flow(self, snapshot, **kw):
        observed.append(snapshot.equity)
        return original(self, snapshot, **kw)
    LiveSafetyGate.observe_equity_with_flows = flow
    try:
        record = run(tmp_path, gate, broker, NOW, closes)
    finally:
        LiveSafetyGate.observe_equity_with_flows = original
    assert not record.get('aborted'), record.get('abort_kind')
    assert observed == [pytest.approx(150.0 + 0.05 * float(closes.iloc[-1]['SPY']))]


def test_lagging_settlement_skips_the_day_instead_of_halting(tmp_path, gate, monkeypatch):
    """Settled cash one session late: the run is refused as unsettled, never read as a loss."""
    seen = []
    flow = LiveSafetyGate.observe_equity_with_flows
    monkeypatch.setattr(LiveSafetyGate, 'observe_equity_with_flows',
                        lambda self, snapshot, **kw: seen.append(snapshot.equity) or flow(self, snapshot, **kw))
    closes = bars()
    broker = FillingBroker(closes)
    first = run(tmp_path, gate, broker, NOW, closes)
    assert first['place_calls'] >= 2, first.get('abort_kind')
    monkeypatch.setattr(fs, '_STARTED', False)
    closes = through(closes, NOW + timedelta(days=1))
    lagged = run(tmp_path, gate, broker, NOW + timedelta(days=1), closes)  # Fri: settled cash not moved yet
    assert lagged.get('refused') == 'unsettled_cash' and not lagged.get('aborted')
    assert lagged['place_calls'] == 0 and not (tmp_path / 'HALTED').exists()
    monkeypatch.setattr(fs, '_STARTED', False)
    broker.settled = BUDGET - broker.spent  # Mon: the fills have settled
    closes = through(closes, NOW + timedelta(days=4))
    record = run(tmp_path, gate, broker, NOW + timedelta(days=4), closes)
    assert not record.get('aborted') and not record.get('refused'), record.get('abort_kind')
    assert any(a['outcome'] == 'SUBMITTED' for a in record['actions'])
    assert not any(a.get('reason') == DENY_LOSS_HALT for a in record['actions'])
    assert len(seen) == 2 and max(seen) - min(seen) < 1e-6, seen  # the lagged equity never reached the gate


def test_deposit_beside_settled_fills_skips_at_most_two_sessions(tmp_path, gate, monkeypatch):
    """A deposit can mask settlement; after two sessions the mismatch is a flow and the run proceeds."""
    closes = bars()
    broker = FillingBroker(closes)
    run(tmp_path, gate, broker, NOW, closes)
    broker.settled = BUDGET - broker.spent + 100.0
    outcomes = []
    for day in (1, 4, 5):  # Fri 10-16, Mon 10-19, Tue 10-20
        monkeypatch.setattr(fs, '_STARTED', False)
        closes = through(closes, NOW + timedelta(days=day))
        record = run(tmp_path, gate, broker, NOW + timedelta(days=day), closes)
        assert not record.get('aborted'), (day, record.get('abort_kind'))
        outcomes.append(record.get('refused'))
    assert outcomes == ['unsettled_cash', 'unsettled_cash', None], outcomes


def test_settled_cash_above_the_budget_counts_in_full(tmp_path, gate, monkeypatch):
    """Gate equity is the account's, not the budget-clipped planner equity: a clamp would hide losses."""
    observed = []
    flow = LiveSafetyGate.observe_equity_with_flows
    monkeypatch.setattr(LiveSafetyGate, 'observe_equity_with_flows',
                        lambda self, snapshot, **kw: observed.append(snapshot.equity) or flow(self, snapshot, **kw))
    record = run(tmp_path, gate, FillingBroker(bars(), settled=250.0), NOW, bars())
    assert not record.get('aborted'), record.get('abort_kind')
    assert observed == [pytest.approx(250.0)]
