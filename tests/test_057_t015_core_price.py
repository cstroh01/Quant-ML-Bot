"""057 T015 / D-8: a core money-market row without a broker price must not halt the preview.

Fake broker, blocked sockets, synthetic prices; the real LiveSafetyGate where it matters.
"""
import pytest
import context  # noqa: F401
from test_057_q139 import blocked  # noqa: F401  (autouse: no sockets)
from test_057_q135 import Broker, process  # noqa: F401  (autouse: fresh process)
from test_057_q137 import Gate, execute, bars
import live_loop as loop

CASH = ('SPAXX**', 'FDRXX**', 'FCASH', 'Cash', 'CORE**')


class CorePrice(Broker):
    def __init__(self, core='SPAXX**', price=None, extra=None):
        super().__init__()
        self.core, self.price, self.extra = core, price, extra or {}
    def settled_cash(self, now): return {'amount': 200.0, 'settled_amt': 200.0, 'coreBalance': 200.0, 'as_of': now.isoformat()}
    def positions(self): return {self.core: 200.0, **{s: q for s, (q, _) in self.extra.items()}}
    def prices(self): return {self.core: self.price, **{s: p for s, (_, p) in self.extra.items()}}


@pytest.mark.parametrize('core', CASH)
@pytest.mark.parametrize('price', [None, 1.0])
def test_real_gate_previews_clean_whatever_the_core_price(tmp_path, core, price):
    r = execute(tmp_path, broker=CorePrice(core, price), gate=None)
    assert not r.get('aborted') and r['clean'] and r['place_calls'] == 0
    assert any(a['outcome'] == 'PREVIEW' for a in r['actions']) and len(r['previews']) >= 2
    assert not (tmp_path / 'HALTED').exists()


@pytest.mark.parametrize('price', [None, 1.0])
def test_flow_observation_marks_hold_no_cash_symbol(tmp_path, price):
    g = Gate()
    r = execute(tmp_path, broker=CorePrice('SPAXX**', price), gate=g)
    assert not r.get('aborted')
    (snapshot, _), = g.flow_calls
    assert not any(loop._CASH_SYMBOLS.match(s) for s in snapshot.prices)
    assert set(snapshot.prices) == set(loop.ALLOCATION_SLEEVES)


def worst(symbol):
    return pytest.approx(float(bars().iloc[-1][symbol]) * (1 + loop.GAP_ALLOWANCE))


# Every sleeve carries a held-at-zero row with an absurd broker price: the worst-case mark must win.
ABSURD = {s: (0.0, 9999.0) for s in loop.ALLOCATION_SLEEVES}


@pytest.mark.parametrize('price', [None, 1.0])
def test_order_snapshots_hold_no_cash_symbol_and_keep_worst_sleeve_marks(tmp_path, price):
    g = Gate()
    r = execute(tmp_path, broker=CorePrice('SPAXX**', price, ABSURD), gate=g)
    assert g.calls and not r.get('aborted')
    for snapshot, intent in g.calls:
        assert not any(loop._CASH_SYMBOLS.match(s) for s in snapshot.prices)
        assert all(snapshot.prices[s] == worst(s) for s in loop.ALLOCATION_SLEEVES)


def test_sleeve_broker_price_is_still_overridden_by_worst_case_mark(tmp_path):
    g = Gate()
    execute(tmp_path, broker=CorePrice('SPAXX**', None, ABSURD), gate=g)
    (snapshot, _), = g.flow_calls
    assert all(snapshot.prices[s] == worst(s) for s in loop.ALLOCATION_SLEEVES)


def test_noncash_prices_keeps_every_non_cash_symbol_and_drops_only_cash():
    live = CorePrice('SPAXX**', None, {'SPY': (0.0, 600.0), 'AAPL': (0.0, None)})
    assert loop.noncash_prices(live) == {'SPY': 600.0, 'AAPL': None}


def test_foreign_symbol_still_halts_before_any_preview(tmp_path):
    b = CorePrice('SPAXX**', None, {'AAPL': (1.0, 200.0)})
    r = execute(tmp_path, broker=b)
    assert r.get('aborted') and r['place_calls'] == 0
    assert r['failure']['detail'] == 'foreign symbol in dedicated account'
    assert (tmp_path / 'HALTED').exists() and not [c for c in b.calls if c[0] == 'preview']
