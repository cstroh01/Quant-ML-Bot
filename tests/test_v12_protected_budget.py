"""Protected v1.2 draft: fake brokers, blocked sockets, no credentials or real orders."""
from dataclasses import replace
from decimal import Decimal

import pytest
import context
from test_057_q137 import Broker, Gate, NOW, bars, blocked, execute, profile, process
from fidelity_live import HaltProfile
from paper_targets import OrderDelta
import live_loop as loop


def funded():
    broker = Broker()
    broker.settled_cash = lambda now: {'amount':1000.0,'settled_amt':1000.0,
        'coreBalance':1000.0,'as_of':now.isoformat(),'buying_power':1000000.0}
    return broker


def test_200_allowed_200_01_refused_before_login(tmp_path):
    allowed = replace(profile(), bot_budget_usd=200.0)
    loop.validate_live_budget(allowed)
    broker = funded()
    with pytest.raises(HaltProfile, match=r'reviewed \$200 cap'):
        execute(tmp_path, profile=replace(allowed, bot_budget_usd=200.01), broker=broker)
    assert broker.logins == 0, 'PROTECTED BUDGET failure must precede broker access'


def test_all_eight_orders_fit_200_and_use_broker_precision(tmp_path):
    gate = Gate()
    result = execute(tmp_path, profile=replace(profile(), bot_budget_usd=200.0, daily_deploy_fraction=1.0),
                     broker=funded(), gate=gate)
    assert not result.get('aborted') and result['budget'] == 200.0
    assert len(gate.calls) == 8, 'PROTECTED FULL DEPLOY all eight allocation buys'
    for snapshot, intent in gate.calls:
        qty = Decimal(str(abs(intent.delta_quantity)))
        assert qty == qty.quantize(Decimal('.001')), 'PROTECTED PRECISION .001 shares'
        assert qty * Decimal(str(snapshot.prices[intent.instrument])) >= 2, 'PROTECTED MINIMUM twice $1'
    assert result['place_calls'] == 0 and result['mode'] == 'preview'


def test_cap_shrinking_is_rounded_again_before_preview(tmp_path):
    gate = Gate()
    result = execute(tmp_path, profile=replace(profile(), bot_budget_usd=200.0, daily_deploy_fraction=0.2),
                     broker=funded(), gate=gate)
    assert not result.get('aborted') and gate.calls
    total = 0
    for snapshot, intent in gate.calls:
        qty = Decimal(str(abs(intent.delta_quantity)))
        assert qty == qty.quantize(Decimal('.001')), 'PROTECTED PRECISION after cap shrink'
        total += float(qty) * snapshot.prices[intent.instrument]
    assert total <= 40.0


def test_sells_round_toward_zero_without_overselling():
    order = OrderDelta('SPY', -0.123456, 0.11625, 600.0)
    precise = loop.live_order_precision([order], True)
    assert precise[0].delta_quantity == -0.123


def test_bundle_identity_and_targets_cannot_be_substituted(tmp_path):
    from allocation_policy import policy_evidence
    from buffered_allocation import buffered_weights
    closes = bars()
    book = buffered_weights(closes)
    allocation = {**policy_evidence(), 'decision_session':str(book.index[-1].date()),
                  'targets':book.iloc[-1].to_dict()}
    loop.validate_allocation_bundle({'allocation':allocation}, closes)
    allocation['targets']['SPY'] = 0.12
    with pytest.raises(HaltProfile, match='target mismatch'):
        loop.validate_allocation_bundle({'allocation':allocation}, closes)
    with pytest.raises(HaltProfile, match='policy mismatch'):
        loop.validate_allocation_bundle({}, closes)
