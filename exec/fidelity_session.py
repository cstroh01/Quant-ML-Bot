"""057 Q135/6c: daily lease, redacted evidence and dedicated-account bot ownership."""
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import uuid
from zoneinfo import ZoneInfo
from data import trading_days
from fidelity_live import FidelityLive, HaltProfile, LibraryBroker, account_hmac
from fidelity_reconcile import read_holdings
from holdings_import import _CASH_SYMBOLS, holdings_status, parse_positions_csv
from live_safety_gate import OrderIntent
from ops_runtime import acquire_lease, atomic_write, complete_lease, open_intents, queue_outbox

NY = ZoneInfo('America/New_York')
LIBRARY = {'version':'0.2.2','sha256':'f5a94056bd9a055ba88482ffcc7dc17013de9871b852b4d9b0dc55352506dd15'}
_STARTED = False

class PreviewUnaffordable(RuntimeError):
    """Normal refusal when no whole sleeve share fits settled cash."""

def validate_closes(closes, now):
    import numpy as np
    import pandas as pd
    from paper_loop import previous_session
    from signals import ALLOCATION_SLEEVES
    if now.utcoffset() is None or closes is None or closes.empty: raise HaltProfile('completed closes required')
    index=closes.index; today=now.astimezone(NY).date()
    if not isinstance(index,pd.DatetimeIndex) or index.tz is not None or not index.is_unique or not index.is_monotonic_increasing or not index.equals(index.normalize()):
        raise HaltProfile('session labels must be unique, ordered, naive midnight')
    if set(closes.columns)!=set(ALLOCATION_SLEEVES) or len(closes.columns)!=8 or index[-1].date()!=previous_session(today):
        raise HaltProfile('stale or missing sleeve closes')
    if not np.isfinite(closes.to_numpy()).all() or (closes<=0).any().any(): raise HaltProfile('finite positive closes required')

class UnsettledCash(RuntimeError):
    """Normal funding refusal; no login retry, order, incident or latched halt."""

def ownership(state, snapshot, fingerprint):
    """Dedicated account: never adopt broker holdings into an empty bot ledger."""
    state=Path(state); ledger=state/'bot-positions.json'
    held={p.symbol:p.quantity for p in snapshot.positions if not _CASH_SYMBOLS.match(p.symbol)}
    from signals import ALLOCATION_SLEEVES
    if not set(held)<=set(ALLOCATION_SLEEVES): raise HaltProfile('foreign symbol in dedicated account')
    if not ledger.exists() and not open_intents(state):
        atomic_write(ledger,json.dumps({'account_fingerprint':fingerprint,'positions':{},'orders':{}},sort_keys=True))
    book=json.loads(ledger.read_text(encoding='utf-8')); bot=book['positions']
    if book['account_fingerprint']!=fingerprint or not set(bot)<=set(ALLOCATION_SLEEVES):
        raise HaltProfile('bot ledger account or sleeve mismatch')
    if any(isinstance(v,bool) or not math.isfinite(float(v)) or float(v)<0 for v in bot.values()) or any(
        not math.isclose(held.get(s,0),bot.get(s,0),abs_tol=1e-8,rel_tol=0) for s in set(held)|set(bot)):
        raise HaltProfile('broker positions differ from bot ledger')
    return bot

class Session:
    def __init__(self, profile, state, *, now, environ=None, broker=None, pin):
        global _STARTED
        self.state, self.now, self.profile = Path(state), now, profile
        self.env = os.environ if environ is None else environ
        if profile.name != 'live_fidelity' or profile.mode != 'LIVE' or profile.broker != 'fidelity':
            raise HaltProfile('live_fidelity profile required')
        if set(profile.credential_refs)!={'FIDELITY_LIVE_USERNAME','FIDELITY_LIVE_PASSWORD','FIDELITY_LIVE_TOTP','FIDELITY_LIVE_ACCOUNT','FIDELITY_LIVE_FP_KEY'} or len(profile.credential_refs)!=5: raise HaltProfile('fixed credential references required')
        if account_hmac(self.env.get('FIDELITY_LIVE_ACCOUNT'),self.env.get('FIDELITY_LIVE_FP_KEY'))!=profile.account_fingerprint: raise HaltProfile('account fingerprint mismatch')
        if (self.state/'HALTED').exists(): raise HaltProfile('latched halt; Camden review required')
        self.day = now.astimezone(NY).date() if now.utcoffset() is not None else None
        if self.day is None or trading_days(self.day,self.day) != [self.day] or not re.fullmatch('[0-9a-f]{40}',pin):
            raise HaltProfile('trading session and exact pin required')
        if _STARTED: raise HaltProfile('one session per process')
        self.run_id = uuid.uuid4().hex
        acquire_lease(self.state,profile.name,self.day,run_id=self.run_id)
        _STARTED = True
        self.record = {'session':str(self.day),'profile':profile.name,'clean':False,'checks':[],
                       'previews':[],'place_calls':0,'challenge':False,'holdings_match':None,
                       'library':LIBRARY,'pin_sha':pin,'totp_step':False,'settled_cash':None,
                       'account_fingerprint':profile.account_fingerprint}
        self.broker = broker
        self.live = None

    def connect(self, csv=None):
        if self.broker is None:
            self.broker=LibraryBroker('FIDELITY_LIVE_ACCOUNT',self.env)
        if self.broker.account_fingerprint != self.profile.account_fingerprint:
            raise HaltProfile('account fingerprint mismatch')
        self.live=FidelityLive(self.profile,broker=self.broker,state_dir=self.state,environ=self.env)
        self.live.connect()
        self.record['totp_step']=bool(self.broker.totp_step)
        self.record['settled_cash']=self.live.settled_cash(self.now)
        if self.record['settled_cash']['settled_amt']<=0: raise UnsettledCash('deposit not settled')
        self.snapshot=read_holdings(self.live,now=self.now,prices=self.live.prices(),
                                    account_fingerprint=self.profile.account_fingerprint)
        self.bot=ownership(self.state,self.snapshot,self.profile.account_fingerprint)
        if csv:
            imported=parse_positions_csv(Path(csv).read_text(encoding='utf-8-sig'),account_fingerprint_fn=lambda account:account_hmac(account,self.env['FIDELITY_LIVE_FP_KEY']))
            actual={p.symbol:p.quantity for p in self.snapshot.positions if not _CASH_SYMBOLS.match(p.symbol)}
            wanted={p.symbol:p.quantity for p in imported.positions}
            match=(holdings_status(imported.as_of,now=self.now)=='fresh' and
                   imported.account_pseudonyms==(self.profile.account_fingerprint,) and actual==wanted and
                   math.isclose(imported.cash_usd,sum(p.market_value for p in self.snapshot.positions
                                if _CASH_SYMBOLS.match(p.symbol)),abs_tol=0.01,rel_tol=0))
            self.record.update(holdings_match=match,csv_sha256=imported.raw_sha256)
            if not match: raise HaltProfile('CSV holdings mismatch')
        self.record['checks'].append('dedicated account reconciled exactly with bot ledger')
        return self.live

    def preview_pair(self, closes):
        from paper_loop import GAP_ALLOWANCE
        validate_closes(closes,self.now)
        last=closes.iloc[-1]
        affordable=sorted((float(last[s])*(1+GAP_ALLOWANCE),s) for s in last.index if float(last[s])*(1+GAP_ALLOWANCE)<=self.record['settled_cash']['settled_amt'])
        if not affordable: raise PreviewUnaffordable('no affordable sleeve')
        bound,symbol=affordable[0]
        for qty in (1.0,0.01):
            try:
                row=self.live.preview(OrderIntent('preview-only',symbol if qty==1.0 else 'SPY',qty))
                if qty==1.0: row.update(last_close=float(last[symbol]),bound=bound)
                self.record['previews'].append(row)
            except HaltProfile: raise
            except Exception:
                if qty==1.0: raise
                self.record['checks'].append('fractional preview refused; broker support UNVERIFIED')
        self.record['clean']=True

    def finish(self, error=False):
        if error:
            self.record.update(clean=False,challenge=True)
            self.record['previews']=[]
        text=json.dumps(self.record,sort_keys=True,allow_nan=False)
        secrets=[self.env.get(r,'') for r in self.profile.credential_refs]
        # Compare decoded strings too: JSON escaping must not bypass the output guard.
        def strings(value):
            if isinstance(value,str): return [value]
            if isinstance(value,dict): return [s for v in value.values() for s in strings(v)]
            if isinstance(value,list): return [s for v in value for s in strings(v)]
            return []
        if any(secret and any(secret in s for s in strings(self.record)) for secret in secrets):
            self.record={'session':str(self.day),'profile':self.profile.name,'clean':False,'challenge':True,
                         'place_calls':self.record['place_calls'],'previews':[],
                         'checks':['sensitive output refused'],'aborted':'Sensitive output refused; Camden review required'}
            text=json.dumps(self.record,sort_keys=True,allow_nan=False)
        if not self.record['clean'] and self.record.get('refused') not in ('unsettled_cash','preview_unaffordable'):
            atomic_write(self.state/'HALTED','Camden review required\n')
            queue_outbox(self.state,'fidelity-halt-'+str(self.day),kind='incident',
                         title='[live_fidelity] halted',body='Fidelity session refused; review local evidence.')
        atomic_write(self.state/'preview-sessions'/f'{self.day}.json',text)
        complete_lease(self.state,self.profile.name,self.day,run_id=self.run_id)
        return self.record
