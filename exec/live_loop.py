"""057 Q137: dormant 059 allocation; unarmed runs preview only. Camden reviews every line."""
import argparse
from dataclasses import replace
from decimal import Decimal, ROUND_FLOOR
from datetime import datetime, time, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
for directory in (ROOT/'scripts',ROOT/'exec'):
    if str(directory) not in sys.path: sys.path.insert(0,str(directory))
import numpy as np
import pandas as pd
from fidelity_live import HaltProfile, SecurityChallenge
from fidelity_reconcile import require_reconciled, TERMINAL, WORKING
from fidelity_session import Session, NY, ownership, UnsettledCash, PreviewUnaffordable
from live_safety_gate import BrokerSnapshot, LiveSafetyGate, OrderIntent
from mode_config import BuyRequest, ProfileError, bound_buys, load_profiles, require_armed, MAX_LIVE_BUDGET_USD
from allocation_policy import policy_evidence, DISCLOSURE as ALLOCATION_DISCLOSURE
from buffered_allocation import buffered_weights
from holdings_import import _CASH_SYMBOLS
from ops_runtime import atomic_write, client_order_id, queue_outbox
from order_gateway import OrderDeniedError, submit_order
from paper_loop import (ALLOCATION_SAFETY_CONFIG, AllocationPlanner, GAP_ALLOWANCE,
                        MAX_DAILY_LOG_MOVE, previous_session, persist_command)
from signals import ALLOCATION_SLEEVES
LIVE_CAP=MAX_LIVE_BUDGET_USD

def validate_live_budget(profile):
    if profile.bot_budget_usd > LIVE_CAP:
        raise HaltProfile('LIVE budget exceeds the reviewed $200 cap')

def live_order_precision(orders, fractional):
    step = Decimal('0.001') if fractional else Decimal('1')
    result = []
    for order in orders:
        magnitude = Decimal(str(abs(order.delta_quantity))).quantize(step, rounding=ROUND_FLOOR)
        if magnitude:
            result.append(replace(order, delta_quantity=float(magnitude) * (1 if order.delta_quantity > 0 else -1)))
    return result

def validate_allocation_bundle(bundle, closes):
    saved = bundle.get('allocation', {})
    if {key: saved.get(key) for key in policy_evidence()} != policy_evidence():
        raise HaltProfile('allocation input policy mismatch')
    book = buffered_weights(closes)
    if book.empty or saved.get('decision_session') != str(book.index[-1].date()):
        raise HaltProfile('allocation input decision mismatch')
    expected = book.iloc[-1].to_dict()
    targets = saved.get('targets', {})
    if set(targets) != set(expected) or any(not math.isclose(float(targets[key]), value, rel_tol=0, abs_tol=1e-12) for key, value in expected.items()):
        raise HaltProfile('allocation input target mismatch')

class DurableBroker:
    """Persist reservation + book + adapter intent immediately before a real send."""
    def __init__(self,broker,persist,secrets):
        self.inner,self.persist,self.secrets,self.place_calls=broker,persist,secrets,0
    def __getattr__(self,name): return getattr(self.inner,name)
    def preview(self,*args):
        conf=self.inner.preview(*args)
        if not isinstance(conf,str) or any(s and s in conf for s in self.secrets):
            raise SecurityChallenge('confirmation refused')
        return conf
    def place(self,*args):
        self.persist()
        self.place_calls+=1
        return self.inner.place(*args)

def run_once(*,profile,state,now,closes,sources,pin,broker=None,environ=None,
             arming=None,persist=None,gate=None,csv=None,now_fn=None):
    """One leased session; all decisions require reconciliation and every order uses the gateway."""
    if now.utcoffset() is None or not time(9,35)<=now.astimezone(NY).time()<time(12):
        raise HaltProfile('conservative NYSE morning window is 09:35-12:00 ET')
    now_fn=now_fn or (lambda:now)
    validate_live_budget(profile)
    session=Session(profile,state,now=now,broker=broker,environ=environ,pin=pin)
    own_gate=gate is None
    book_path=Path(state)/'bot-positions.json'
    def read_book():
        return json.loads(book_path.read_text(encoding='utf-8')) if book_path.exists() else {'account_fingerprint':profile.account_fingerprint,'positions':{},'orders':{}}
    try:
        if profile.safety_config_version!=ALLOCATION_SAFETY_CONFIG.version:
            raise HaltProfile('profile SafetyConfig version mismatch')
        gate=gate or LiveSafetyGate(Path(state)/'live-gate.sqlite',ALLOCATION_SAFETY_CONFIG)
        if gate._config!=ALLOCATION_SAFETY_CONFIG: raise HaltProfile('allocation SafetyConfig required')
        try:
            require_armed(profile,arming,now=now)
            armed=True
        except ProfileError: armed=False
        if armed and persist is None: raise HaltProfile('durable persistence required before LIVE')
        if persist: persist()  # durable daily lease before login, too
        def reconcile(live):
            session.record['reconciliation']=require_reconciled(gate,live,now=now_fn())
            book=read_book()
            for cid,order in book['orders'].items():
                if order.get('applied'): continue
                code=live.order_status(cid)
                code='_'.join(str(code).upper().split())
                if code in WORKING: continue
                if code not in TERMINAL: raise HaltProfile('bot order still unresolved')
                if code=='FILLED':
                    s=order['symbol']; book['positions'][s]=book['positions'].get(s,0)+order['delta']
                order['applied']=True
            if book_path.exists(): atomic_write(book_path,json.dumps(book,sort_keys=True))
            if persist: persist()
        live=session.connect(csv,reconcile=reconcile)
        secrets=[session.env.get(r,'') for r in profile.credential_refs]
        durable=DurableBroker(session.broker,persist,secrets)
        live._broker=durable
        cash=session.record['settled_cash']['settled_amt']
        grant=min(profile.bot_budget_usd,cash,LIVE_CAP)
        today=now.astimezone(NY).date()
        if closes.index.tz is not None or not closes.index.is_monotonic_increasing or not closes.index.is_unique:
            raise HaltProfile('session labels must be unique, ordered and naive')
        if set(closes.columns)!=set(ALLOCATION_SLEEVES) or (closes.index>=pd.Timestamp(today)).any():
            raise HaltProfile('sleeves or completed sessions refused')
        expected=previous_session(today)
        if closes.empty or closes.index[-1].date()!=expected:
            raise HaltProfile('stale allocation bars')
        last=closes.iloc[-1]
        if not np.isfinite(last).all() or (last<=0).any() or (np.log(closes/closes.shift(1)).abs()>MAX_DAILY_LOG_MOVE).any().any():
            raise HaltProfile('split/jump or incomplete allocation bars')
        # Cash bounds new buys; already-owned bot lots remain part of the capped allocation book.
        equity=min(profile.bot_budget_usd,LIVE_CAP,cash+sum(q*float(last[s]) for s,q in session.bot.items()))
        bounded=replace(profile,bot_budget_usd=equity)
        planner=AllocationPlanner(Path(state)/'allocation-state.json',{s:profile.fractional for s in ALLOCATION_SLEEVES})
        plan=planner.plan(closes,closes.index[-1],equity=equity,positions=session.bot)
        worst={s:float(last[s])*(1+GAP_ALLOWANCE) for s in ALLOCATION_SLEEVES}
        precise_orders=live_order_precision(plan.orders,profile.fractional)
        buys=[BuyRequest(o.ticker,o.delta_quantity,worst[o.ticker],profile.fractional)
              for o in precise_orders if o.delta_quantity>0]
        book=read_book()
        deployed=sum(o['notional'] for o in book['orders'].values() if o['session']==str(today) and o['delta']>0)
        sized,refused=bound_buys(bounded,buys,settled_cash=grant,deployed_today_usd=deployed,min_notional_usd=1.0)
        final_sized=[]
        step=Decimal('0.001') if profile.fractional else Decimal('1')
        for order in sized:
            quantity=float(Decimal(str(order.quantity)).quantize(step,rounding=ROUND_FLOOR))
            notional=quantity*worst[order.ticker]
            if quantity<=0 or notional<1.0:
                refused.append((order.ticker,'below_minimum'))
            else:
                final_sized.append(replace(order,quantity=quantity,notional=notional))
        sized=final_sized
        accepted={o.ticker:o.quantity for o in sized}
        shrunk=bool(refused) or any(accepted.get(o.ticker,0)<o.quantity for o in buys)
        orders=[o for o in precise_orders if o.delta_quantity<0]+[
            replace(o,delta_quantity=accepted[o.ticker]) for o in precise_orders if o.delta_quantity>0 and o.ticker in accepted]
        actions=[{'ticker':s,'outcome':'BUDGET_REFUSED','reason':reason} for s,reason in refused]
        for order in orders:
            reconcile(live)
            book=read_book()
            positions=live.positions()
            fresh=SimpleNamespace(positions=[SimpleNamespace(symbol=s,quantity=q) for s,q in positions.items()])
            session.bot=ownership(Path(state),fresh,profile.account_fingerprint)
            if order.ticker not in ALLOCATION_SLEEVES or order.delta_quantity < -session.bot.get(order.ticker,0):
                raise HaltProfile('bot ownership or sleeve boundary refused')
            side='buy' if order.delta_quantity>0 else 'sell'
            intent=OrderIntent(client_order_id(profile.name,today,order.ticker,side),order.ticker,order.delta_quantity)
            positions={s:q for s,q in positions.items() if not _CASH_SYMBOLS.match(s)}
            prices={**live.prices(),**worst}
            market_value=sum(q*prices[s] for s,q in positions.items())
            snapshot=BrokerSnapshot(now_fn(),'OK',market_value+cash,0.0,positions,prices)
            notional=abs(order.delta_quantity)*worst[order.ticker]
            def send(candidate):
                if not armed: return live.preview(candidate)
                book['orders'][candidate.client_order_id]={'symbol':candidate.instrument,'delta':candidate.delta_quantity,
                    'notional':notional,'session':str(today),'applied':False}
                atomic_write(book_path,json.dumps(book,sort_keys=True))
                return live.submit(candidate,arming=arming,now=now_fn())
            action={'ticker':order.ticker,'delta_quantity':order.delta_quantity,'notional':notional,
                    'target_weight':order.target_weight,'client_order_id':intent.client_order_id}
            try:
                result=submit_order(gate,snapshot=snapshot,intent=intent,now=now_fn(),submit=send)
                action['outcome']='SUBMITTED' if armed else 'PREVIEW'
                if not armed:
                    session.record['previews'].append(result)
                    gate.record_order_outcome(intent.client_order_id,terminal=True,reason='PREVIEW_ONLY',now=now_fn())
            except OrderDeniedError as exc:
                action.update(outcome='DENIED',reason=exc.decision.reason)
            actions.append(action)
        executed=None
        if armed and plan.pending and not plan.deferred and not shrunk and all(a['outcome']=='SUBMITTED' for a in actions):
            planner.complete(plan.decision_session); executed=plan.decision_session
        session.record.update(run_at_utc=now_fn().isoformat(),mode='submit' if armed else 'preview',
            equity_source='broker',data_session=str(expected),equity=equity,budget=grant,
            safety_config_version=ALLOCATION_SAFETY_CONFIG.version,allocation=policy_evidence(),quantity_decimal_places=3,decision=json.loads(plan.decision.to_json(orient='index')),
            decision_session=plan.decision_session,decision_executed=executed,actions=actions,sources=sources,
            disclosure=ALLOCATION_DISCLOSURE + f' LIVE budget ${profile.bot_budget_usd:g}; hard cap ${LIVE_CAP:g}. Last close + 5% is an estimate, not a fill-price guarantee.')
        if not armed: session.preview_pair(closes)
        else: session.record['clean']=True
        session.record['place_calls']=durable.place_calls
        if persist: persist()
        record=session.finish()
    except (UnsettledCash,PreviewUnaffordable) as exc:
        session.record['refused']='unsettled_cash' if isinstance(exc,UnsettledCash) else 'preview_unaffordable'
        record=session.finish()
    except Exception as exc:
        session.record.update(aborted='Fidelity loop halted; Camden review required',abort_kind=type(exc).__name__,place_calls=getattr(locals().get('durable'),'place_calls',0))
        record=session.finish(error=True)
    finally:
        if own_gate and gate is not None: gate.close()
    record=record|{'session':record.get('data_session',record['session'])}
    with (Path(state)/'runs.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(record,sort_keys=True)+'\n')
    return record

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('profile','profiles-file','state-dir','closes-file','sources-file'):
        p.add_argument('--'+arg,required=True)
    p.add_argument('--holdings-csv'); p.add_argument('--arming-file'); p.add_argument('--persist-command')
    a=p.parse_args(argv)
    try:
        from data_sources import SourceManifest
        raw=Path(a.closes_file).read_bytes(); bundle=json.loads(Path(a.sources_file).read_text(encoding='utf-8'))
        if hashlib.sha256(raw).hexdigest()!=bundle['csv_sha256'] or len(bundle['sources'])!=8: raise ValueError
        sources=bundle['sources']
        for source in sources:
            if SourceManifest(**(source|{'fetched_at':datetime.fromisoformat(source['fetched_at'])})).source!='alpaca_sip_daily': raise ValueError
        closes=pd.read_csv(a.closes_file,index_col=0,parse_dates=True)
        validate_allocation_bundle(bundle,closes)
        profile=load_profiles(json.loads(Path(a.profiles_file).read_text(encoding='utf-8')))[a.profile]
        arming=None
        if a.arming_file:
            from mode_config import ArmingRecord
            row=json.loads(Path(a.arming_file).read_text(encoding='utf-8'))
            for key in ('activated_at','expires_at'): row[key]=datetime.fromisoformat(row[key])
            arming=ArmingRecord(**row)
        record=run_once(profile=profile,state=a.state_dir,now=datetime.now(timezone.utc),closes=closes,sources=sources,
            pin=os.environ.get('QMB_PINNED_SHA',''),arming=arming,persist=persist_command(a.persist_command) if a.persist_command else None,
            csv=a.holdings_csv,now_fn=lambda:datetime.now(timezone.utc))
        return 1 if record.get('aborted') else 0
    except Exception:
        queue_outbox(a.state_dir,'fidelity-loop-refused',kind='incident',title='[live_fidelity] refused',body='Loop inputs or session refused; no automatic rerun.')
        print('Fidelity loop refused; review local evidence.'); return 1
if __name__=='__main__': raise SystemExit(main())
