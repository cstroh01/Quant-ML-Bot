"""Q137: fake broker, blocked sockets, synthetic prices; no result or LIVE action."""
from dataclasses import replace
from datetime import timedelta
import json
from types import SimpleNamespace as NS
import pytest
import context  # noqa
from test_057_q139 import blocked, NOW
from test_057_q135 import Broker, process, ENV, live_profile
from test_110_paper_allocation import sleeve_closes
from live_safety_gate import ALLOW, GateDecision
from mode_config import ArmingRecord
import fidelity_session as fs
import live_loop as loop

def profile(): return replace(live_profile(),safety_config_version=loop.ALLOCATION_SAFETY_CONFIG.version)
def bars():
    c=sleeve_closes(end='2026-10-14'); c[c.columns[-1]]*=0.1; return c
class Gate:
    _config=loop.ALLOCATION_SAFETY_CONFIG
    def __init__(self, deny=False): self.calls=[]; self.deny=deny; self.outcomes=[]
    def pending_orders(self): return []
    def evaluate_order(self,snapshot,intent,*,now):
        self.calls.append((snapshot,intent))
        return GateDecision('DENY' if self.deny else ALLOW,'FIXTURE',self._config.version,'order',{})
    def record_order_outcome(self,cid,**kwargs): self.outcomes.append(cid)

def execute(tmp_path, **kw):
    args=dict(profile=profile(),state=tmp_path,now=NOW,closes=bars(),sources=[],
              broker=Broker(),environ=ENV,pin='a'*40,gate=Gate())
    args.update(kw); return loop.run_once(**args)

def test_unarmed_full_path_gateway_and_reconcile_first(tmp_path,monkeypatch):
    trace=[]; original=loop.require_reconciled
    def reconcile(*a,**k): trace.append('reconcile'); return original(*a,**k)
    monkeypatch.setattr(loop,'require_reconciled',reconcile)
    original_plan=loop.AllocationPlanner.plan
    def plan(*args,**kwargs):
        assert trace, 'decision made before reconciliation'
        return original_plan(*args,**kwargs)
    monkeypatch.setattr(loop.AllocationPlanner,'plan',plan)
    b=Broker(); g=Gate()
    r=execute(tmp_path,broker=b,gate=g)
    assert trace and set(trace)=={'reconcile'} and not r.get('aborted')
    assert r['mode']=='preview' and r['actions'] and all(a['outcome'] in ('PREVIEW','BUDGET_REFUSED') for a in r['actions'])
    assert len(g.calls)==sum(a['outcome']=='PREVIEW' for a in r['actions']) and len(g.outcomes)==len(g.calls)
    assert r['place_calls']==0 and all(c[0]=='preview' for c in b.calls)
    assert r['session']=='2026-10-14' and r['decision_session']=='2026-10-01'
    assert r['decision_executed'] is None and r['clean'] and r['budget']==10.0
    assert not (tmp_path/'ops/intents.jsonl').exists()

def test_gateway_deny_never_reaches_allocation_preview(tmp_path):
    b=Broker(); g=Gate(deny=True); r=execute(tmp_path,broker=b,gate=g)
    assert g.calls and all(a['outcome'] in ('DENIED','BUDGET_REFUSED') for a in r['actions'])
    assert len(b.calls)==2 and r['place_calls']==0

def test_armed_cap_daily_and_settled_not_buying_power(tmp_path):
    b=Broker(); b.settled_cash=lambda now:{'amount':1000.0,'settled_amt':1000.0,'coreBalance':1000.0,'as_of':now.isoformat(),'buying_power':1000000.0}
    b.status=lambda conf:'WORKING'
    arm=ArmingRecord('live_fidelity',profile().account_fingerprint,'e'*64,'Camden',NOW-timedelta(hours=1),NOW+timedelta(hours=1))
    persists=[]; g=Gate()
    r=execute(tmp_path,broker=b,gate=g,arming=arm,persist=lambda:persists.append(True))
    assert r['budget']==100.0 and not r.get('aborted') and r['place_calls']>0
    total=sum(abs(i.delta_quantity)*s.prices[i.instrument] for s,i in g.calls)
    assert total<=20.000001 and len(persists)>len(g.calls)
    book=json.loads((tmp_path/'bot-positions.json').read_text())
    assert len(book['orders'])==r['place_calls'] and book['positions']=={}

def test_lower_settled_cash_controls_spend(tmp_path):
    b=Broker(); b.settled_cash=lambda now:{'amount':2.0,'settled_amt':2.0,'coreBalance':100.0,'as_of':now.isoformat(),'buying_power':9000.0}
    r=execute(tmp_path,broker=b)
    assert r['budget']==2.0 and sum(a.get('notional',0) for a in r['actions'])<=0.400001

@pytest.mark.parametrize('change',['stale','jump','future','gap','naive'])
def test_bad_bars_refused_without_placing(tmp_path,change):
    c=bars()
    if change=='stale': c=c.iloc[:-1]
    if change=='jump': c.iloc[-1,0]*=2
    if change=='future': c.loc[c.index[-1]+timedelta(days=1)]=c.iloc[-1]
    if change=='gap': c.iloc[-1,0]=float('nan')
    if change=='naive':
        with pytest.raises(Exception): execute(tmp_path,now=NOW.replace(tzinfo=None))
        return
    b=Broker(); r=execute(tmp_path,broker=b,closes=c)
    assert r.get('aborted') and not b.calls and r['place_calls']==0

def test_reconcile_blocks_before_planner_and_protects_manual(tmp_path):
    g=Gate(); g.pending_orders=lambda:[{'terminal':False,'client_order_id':'UNKNOWN'}]
    b=Broker(); r=execute(tmp_path,gate=g,broker=b)
    assert r.get('aborted') and not b.calls and not g.calls

def test_wrong_or_expired_arm_previews_only(tmp_path):
    arm=ArmingRecord('WRONG',profile().account_fingerprint,'e'*64,'Camden',NOW-timedelta(hours=1),NOW+timedelta(hours=1))
    r=execute(tmp_path,arming=arm)
    assert r['mode']=='preview' and r['place_calls']==0

def test_dedicated_account_has_no_untracked_sells(tmp_path):
    b=Broker(); c=bars()
    r=execute(tmp_path,broker=b)
    assert all(a['ticker'] in loop.ALLOCATION_SLEEVES for a in r['actions'])
    assert all(a.get('delta_quantity',1)>0 for a in r['actions'])

def test_market_window_boundaries(tmp_path):
    b=Broker()
    with pytest.raises(Exception): execute(tmp_path,broker=b,now=NOW.replace(hour=13,minute=34))
    assert b.logins==0

def test_real_safety_gate_gets_valid_snapshot_and_releases_previews(tmp_path):
    from live_safety_gate import LiveSafetyGate
    b=Broker()
    gate=LiveSafetyGate(tmp_path/'gate.sqlite',loop.ALLOCATION_SAFETY_CONFIG)
    try:
        r=execute(tmp_path,broker=b,gate=gate)
        assert any(a['outcome']=='PREVIEW' for a in r['actions']) and r['place_calls']==0
        assert all(row['terminal'] for row in gate.pending_orders())
        evidence=json.loads((tmp_path/'preview-sessions/2026-10-15.json').read_text())
        assert evidence['session']=='2026-10-15' and evidence['data_session']=='2026-10-14'
    finally: gate.close()

def test_filled_bot_order_applies_once_to_dedicated_ledger(tmp_path,monkeypatch):
    b=Broker(); arm=ArmingRecord('live_fidelity',profile().account_fingerprint,'e'*64,'Camden',NOW-timedelta(hours=1),NOW+timedelta(hours=1))
    b.status=lambda conf:'WORKING'
    r=execute(tmp_path,broker=b,arming=arm,persist=lambda:None)
    assert r['place_calls']>0
    book=json.loads((tmp_path/'bot-positions.json').read_text())
    filled={s:q for s,q in Broker().positions().items()}
    for row in book['orders'].values(): filled[row['symbol']]=filled.get(row['symbol'],0)+row['delta']
    b.positions=lambda:filled
    b.status=lambda conf:'FILLED'
    b.prices=lambda:{**Broker().prices(),**{s:float(bars().iloc[-1][s]) for s in loop.ALLOCATION_SLEEVES}}
    monkeypatch.setattr(fs,'_STARTED',False)
    c=sleeve_closes(end='2026-10-15')
    # Keep the retained history exactly; only the newly completed bar is added.
    c=bars().copy(); c.loc[c.index[-1]+timedelta(days=1)]=c.iloc[-1]
    r=execute(tmp_path,now=NOW+timedelta(days=1),broker=b,closes=c)
    assert not r.get('aborted')
    updated=json.loads((tmp_path/'bot-positions.json').read_text())
    assert all(row['applied'] for row in updated['orders'].values())
    assert updated['positions']=={s:filled[s] for s in filled if s in loop.ALLOCATION_SLEEVES}

def test_foreign_change_between_orders_halts_before_next_preview(tmp_path):
    b=Broker(); original=b.preview
    def preview(*args):
        result=original(*args)
        b.positions=lambda:{'QQQ':0.1,'SPAXX':100.0}
        return result
    b.preview=preview
    r=execute(tmp_path,broker=b)
    assert r.get('aborted') and len(b.calls)==1 and r['place_calls']==0

def test_unsettled_ach_is_normal_refusal_without_decision(tmp_path):
    b=Broker(); b.settled_cash=lambda now:{'amount':0,'settled_amt':0,'coreBalance':100,'as_of':now.isoformat()}
    g=Gate(); r=execute(tmp_path,broker=b,gate=g)
    assert r['refused']=='unsettled_cash' and not r.get('aborted') and not r['challenge']
    assert not b.calls and not g.calls and not (tmp_path/'HALTED').exists()

def test_cash_budget_and_existing_bot_equity_are_separate(tmp_path):
    c=bars(); qty=0.01
    (tmp_path/'bot-positions.json').write_text(json.dumps({'account_fingerprint':profile().account_fingerprint,
        'positions':{'SPY':qty},'orders':{}}))
    b=Broker(); b.positions=lambda:{'SPY':qty,'SPAXX':95.0}; b.prices=lambda:{'SPY':float(c.iloc[-1]['SPY'])}
    b.settled_cash=lambda now:{'amount':95,'settled_amt':95,'coreBalance':95,'as_of':now.isoformat()}
    r=execute(tmp_path,broker=b,closes=c)
    assert not r.get('aborted') and r['budget']==95
    assert r['equity']==min(100,95+qty*float(c.iloc[-1]['SPY']))
