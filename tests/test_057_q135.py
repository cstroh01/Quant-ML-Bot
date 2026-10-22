"""Q135: synthetic offline sessions, never a real broker or credential."""
from datetime import timedelta
import hashlib
import hmac
import pandas as pd
import json
from pathlib import Path
import pytest
import context  # noqa
from test_057_q139 import blocked, NOW
from test_057_fidelity_live import ENV as BASE_ENV, live_profile as base_profile, FakeBroker
from dataclasses import replace
ENV={'FIDELITY_LIVE_'+k:BASE_ENV['LIVE_FIDELITY_'+k] for k in ('USERNAME','PASSWORD','TOTP')}|{'FIDELITY_LIVE_ACCOUNT':'DEDICATED-FIXTURE-ACCOUNT','FIDELITY_LIVE_FP_KEY':'ab'*32}
def live_profile():
    return replace(base_profile(),credential_refs=tuple(ENV),account_fingerprint=hmac.new(bytes.fromhex(ENV['FIDELITY_LIVE_FP_KEY']),ENV['FIDELITY_LIVE_ACCOUNT'].encode(),hashlib.sha256).hexdigest())
from fidelity_live import FidelityLive, HaltProfile, SecurityChallenge
from live_safety_gate import OrderIntent
import fidelity_session as fs
from fidelity_preview_session import run_session as actual_run
from paper_loop import previous_session
from signals import ALLOCATION_SLEEVES
def closes(now=NOW):
    return pd.DataFrame([{s:(600.0 if s=='SPY' else 5.0) for s in ALLOCATION_SLEEVES}],index=pd.DatetimeIndex([previous_session(now.date())]))
def run_session(*args,**kw):
    return actual_run(*args,closes=kw.pop('closes',closes(kw.get('now',NOW))),**kw)
from gate_checklist import fidelity_preview

class Broker(FakeBroker):
    totp_step = True
    account_fingerprint = live_profile().account_fingerprint
    def positions(self): return {'SPAXX': 100.0}
    def prices(self): return {}
    def settled_cash(self, now): return {'amount':10.0,'settled_amt':10.0,'coreBalance':100.0,'as_of':now.isoformat()}

@pytest.fixture(autouse=True)
def process(monkeypatch): monkeypatch.setattr(fs, '_STARTED', False)

def test_preview_connected_without_arming_and_without_writes(tmp_path):
    b = Broker(); live = FidelityLive(live_profile(), broker=b, state_dir=tmp_path, environ=ENV)
    with pytest.raises(Exception): live.preview(OrderIntent('x', 'SPY', 1.0))
    live.connect()
    assert live.preview(OrderIntent('x', 'SPY', 1.0))['conf_num'] == 'CONF-1'
    assert [x[0] for x in b.calls] == ['preview']
    assert not (tmp_path / 'ops/intents.jsonl').exists()
    with pytest.raises(Exception): live.preview(OrderIntent('y', 'QQQ', 1.0))

def test_clean_record_and_daily_lease(tmp_path, monkeypatch):
    b = Broker()
    r = run_session(live_profile(), tmp_path, now=NOW, broker=b, environ=ENV, pin='a'*40)
    assert r['clean'] and r['place_calls'] == 0 and r['totp_step'] is True
    assert r['settled_cash']['amount'] == 10.0 and len(r['previews']) == 2
    assert [c[0] for c in b.calls] == ['preview', 'preview'] and b.logins == 1
    assert json.loads((tmp_path / 'bot-positions.json').read_text()) == {'account_fingerprint':live_profile().account_fingerprint,'positions':{},'orders':{}}
    assert r['account_fingerprint']==live_profile().account_fingerprint and not (tmp_path/'manual-baseline.json').exists()
    with pytest.raises(Exception): run_session(live_profile(), tmp_path, now=NOW, broker=b, environ=ENV, pin='a'*40)
    assert list((tmp_path/'ops/outbox').glob('*.json'))
    monkeypatch.setattr(fs, '_STARTED', False)  # fresh process still refuses same durable day
    with pytest.raises(Exception): run_session(live_profile(), tmp_path, now=NOW, broker=b, environ=ENV, pin='a'*40)
    assert b.logins == 1

def test_challenge_latches_across_process_and_redacts(tmp_path, monkeypatch):
    b = Broker(login_error=SecurityChallenge('PRIVATE'))
    r = run_session(live_profile(), tmp_path, now=NOW, broker=b, environ=ENV, pin='a'*40)
    assert not r['clean'] and r['challenge'] and (tmp_path / 'HALTED').exists()
    assert list((tmp_path / 'ops/outbox').glob('*.json'))
    monkeypatch.setattr(fs, '_STARTED', False)
    with pytest.raises(HaltProfile): run_session(live_profile(), tmp_path, now=NOW+timedelta(days=1), broker=b, environ=ENV, pin='a'*40)
    assert 'PRIVATE' not in ''.join(p.read_text() for p in tmp_path.rglob('*.json'))

def test_credential_never_written_even_in_success_payload(tmp_path):
    b = Broker(); b.preview = lambda *a: ENV['FIDELITY_LIVE_PASSWORD']
    r = run_session(live_profile(), tmp_path, now=NOW, broker=b, environ=ENV, pin='a'*40)
    assert ENV['FIDELITY_LIVE_PASSWORD'] not in ''.join(p.read_text() for p in tmp_path.rglob('*') if p.is_file())
    assert not r['clean']

def test_foreign_positions_never_adopted(tmp_path, monkeypatch):
    run_session(live_profile(), tmp_path, now=NOW, broker=Broker(), environ=ENV, pin='a'*40)
    monkeypatch.setattr(fs, '_STARTED', False)
    b = Broker(); b.positions = lambda: {'QQQ':0.1,'SPAXX':100.0}
    r = run_session(live_profile(), tmp_path, now=NOW+timedelta(days=1), broker=b, environ=ENV, pin='a'*40)
    assert not r['clean'] and not b.calls

@pytest.mark.parametrize('when', [NOW.replace(tzinfo=None), NOW+timedelta(days=2)])
def test_calendar_refuses_before_login(tmp_path, when):
    b=Broker()
    with pytest.raises(Exception): run_session(live_profile(), tmp_path, now=when, broker=b, environ=ENV, pin='a'*40)
    assert b.logins == 0

def test_gate_five_distinct_clean_days_and_csv_required(tmp_path):
    rows=[]
    for day in (8,9,12,13,14):
        p=tmp_path/f'{day}.json'
        row={'session':f'2026-10-{day:02}', 'profile':'live_fidelity','clean':True,'challenge':False,'place_calls':0,
             'previews':[{'qty':1.0,'conf_num':'FIXTURE'}],
             'pin_sha':'a'*40,'library':fs.LIBRARY,'holdings_match':True,'csv_sha256':'b'*64,'account_fingerprint':live_profile().account_fingerprint,
             'api_holdings_reconciled':True,'totp_step':True,'settled_cash':{'amount':10,'as_of':f'2026-10-{day:02}T15:00:00+00:00'}}
        p.write_text(json.dumps(row)); rows.append({'artifact':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    p=tmp_path/'sessions.json'; p.write_text(json.dumps({'sessions':rows}))
    entry={'type':'fidelity_preview','artifact':p.name,'account_fingerprint':live_profile().account_fingerprint}
    assert fidelity_preview(entry,tmp_path)[0]
    rows[-1]=rows[0]; p.write_text(json.dumps({'sessions':rows}))
    assert not fidelity_preview(entry,tmp_path)[0]
    rows.pop(); p.write_text(json.dumps({'sessions':rows}))
    assert not fidelity_preview(entry,tmp_path)[0]  # four days never suffice

def test_csv_match_and_stale_or_wrong_account_refused(tmp_path, monkeypatch):
    from types import SimpleNamespace as NS
    snapshot=NS(as_of=NOW,positions=[],cash_usd=100.0,account_pseudonyms=(live_profile().account_fingerprint,),raw_sha256='d'*64)
    monkeypatch.setattr(fs,'parse_positions_csv',lambda text,**kwargs:snapshot)
    csv=tmp_path/'fixture.csv'; csv.write_text('SYNTHETIC')
    r=run_session(live_profile(),tmp_path/'one',now=NOW,broker=Broker(),environ=ENV,pin='a'*40,csv=csv)
    assert r['clean'] and r['holdings_match'] and r['csv_sha256']=='d'*64
    monkeypatch.setattr(fs,'_STARTED',False); snapshot.account_pseudonyms=('WRONG',)
    b=Broker(); r=run_session(live_profile(),tmp_path/'two',now=NOW,broker=b,environ=ENV,pin='a'*40,csv=csv)
    assert not r['clean'] and not b.calls

def test_fractional_refusal_optional_but_challenge_halts(tmp_path, monkeypatch):
    b=Broker(); original=b.preview
    def preview(s,side,q):
        if q<1: raise ValueError('fraction refused')
        return original(s,side,q)
    b.preview=preview
    assert run_session(live_profile(),tmp_path/'one',now=NOW,broker=b,environ=ENV,pin='a'*40)['clean']
    monkeypatch.setattr(fs,'_STARTED',False)
    def challenge(s,side,q):
        if q<1: raise SecurityChallenge('FIXTURE')
        return original(s,side,q)
    b.preview=challenge
    assert not run_session(live_profile(),tmp_path/'two',now=NOW,broker=b,environ=ENV,pin='a'*40)['clean']

def test_gate_records_totp_observation_without_inventing_a_new_clean_condition(tmp_path):
    from test_059_gate_checklist import evidenced
    entry=evidenced(tmp_path)['items']['6']
    manifest=tmp_path/entry['artifact']; bundle=json.loads(manifest.read_text())
    item=bundle['sessions'][-1]; p=tmp_path/item['artifact']; row=json.loads(p.read_text())
    row['totp_step']=False  # status 1200 success can require no 1201 step
    p.write_text(json.dumps(row)); item['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(bundle))
    assert fidelity_preview(entry,tmp_path)[0]
    row['holdings_match']=None; row.pop('csv_sha256'); p.write_text(json.dumps(row))
    item['sha256']=hashlib.sha256(p.read_bytes()).hexdigest(); manifest.write_text(json.dumps(bundle))
    assert fidelity_preview(entry,tmp_path)[0]  # Camden 2026-10-22: "API holdings count."
    row['api_holdings_reconciled']=False; p.write_text(json.dumps(row))
    item['sha256']=hashlib.sha256(p.read_bytes()).hexdigest(); manifest.write_text(json.dumps(bundle))
    assert not fidelity_preview(entry,tmp_path)[0]  # every session needs its own API reconciliation

def test_session_records_the_exact_api_check_the_evidence_requires(tmp_path):
    from fidelity_preview_evidence import API_RECONCILED
    r=run_session(live_profile(),tmp_path,now=NOW,broker=Broker(),environ=ENV,pin='a'*40)
    assert r['clean'] and r['holdings_match'] is None and API_RECONCILED in r['checks']

def test_output_guard_drops_untrusted_nested_fields(tmp_path):
    session=fs.Session(live_profile(),tmp_path,now=NOW,broker=Broker(),environ=ENV,pin='a'*40)
    session.record['sources']=[{'unexpected':ENV['FIDELITY_LIVE_PASSWORD']}]
    session.record['clean']=True
    record=session.finish()
    assert not record['clean'] and record['aborted']
    assert ENV['FIDELITY_LIVE_PASSWORD'] not in (tmp_path/'preview-sessions/2026-10-15.json').read_text()

def test_unsettled_deposit_is_normal_refusal(tmp_path):
    b=Broker(); b.settled_cash=lambda now:{'amount':0,'settled_amt':0,'coreBalance':100,'as_of':now.isoformat()}
    r=run_session(live_profile(),tmp_path,now=NOW,broker=b,environ=ENV,pin='a'*40)
    assert not r['clean'] and r['refused']=='unsettled_cash' and not r['challenge']
    assert r['settled_cash']['coreBalance']==100 and r['settled_cash']['settled_amt']==0
    assert not b.calls and not (tmp_path/'HALTED').exists() and not (tmp_path/'ops/outbox').exists()

def test_untracked_sleeve_quantity_is_not_adopted(tmp_path):
    b=Broker(); b.positions=lambda:{'SPY':0.1,'SPAXX':100.0}; b.prices=lambda:{'SPY':600.0}
    r=run_session(live_profile(),tmp_path,now=NOW,broker=b,environ=ENV,pin='a'*40)
    assert not r['clean'] and r['challenge'] and (tmp_path/'HALTED').exists() and not b.calls

def test_fixed_credential_names_refuse_legacy_or_extra_before_login(tmp_path):
    for refs in (tuple(BASE_ENV),tuple(ENV)+('EXTRA',)):
        b=Broker()
        with pytest.raises(HaltProfile): fs.Session(replace(live_profile(),credential_refs=refs),tmp_path,now=NOW,broker=b,environ=ENV,pin='a'*40)
        assert b.logins==0 and not (tmp_path/'ops').exists()

def test_funds_model_old_spy_fails_new_choice_passes(tmp_path):
    b=Broker(); prices=closes().iloc[-1]; original=b.preview
    def funded(s,side,q):
        if q*prices[s]>10: raise ValueError('insufficient settled cash')
        return original(s,side,q)
    b.preview=funded
    with pytest.raises(ValueError): b.preview('SPY','B',1.0)
    r=run_session(live_profile(),tmp_path,now=NOW,broker=b,environ=ENV,pin='a'*40)
    assert r['clean'] and r['previews'], 'affordable whole-share preview must succeed'
    row=r['previews'][0]; expected=min(s for s in ALLOCATION_SLEEVES if s!='SPY')
    assert r['clean'] and row['symbol']==expected and row['qty']==1.0 and row['conf_num']
    assert row['last_close']==5.0 and row['bound']==5.25

def test_no_affordable_sleeve_refuses_normally(tmp_path):
    b=Broker(); r=run_session(live_profile(),tmp_path,now=NOW,broker=b,environ=ENV,pin='a'*40,closes=closes()*1000)
    assert r['refused']=='preview_unaffordable' and not r['clean'] and not r['challenge']
    assert not b.calls and not (tmp_path/'HALTED').exists() and not (tmp_path/'ops/outbox').exists()

@pytest.mark.parametrize('bad',['missing','stale','future','aware','duplicate','unordered','nan','negative','sleeves','intraday'])
def test_bad_closes_before_login(tmp_path,bad):
    c=closes()
    if bad=='missing': c=None
    elif bad in ('stale','future','intraday'): c.index+=pd.Timedelta(days=-1 if bad=='stale' else 1) if bad!='intraday' else pd.Timedelta(hours=1)
    elif bad=='aware': c.index=c.index.tz_localize('UTC')
    elif bad=='duplicate': c=pd.concat([c,c])
    elif bad=='unordered': c=pd.concat([c,c.set_axis(c.index-pd.Timedelta(days=1))])
    elif bad=='sleeves': c=c.drop(columns=['SPY'])
    else: c.iloc[0,0]=float('nan') if bad=='nan' else -1
    b=Broker()
    with pytest.raises(Exception): run_session(live_profile(),tmp_path,now=NOW,broker=b,environ=ENV,pin='a'*40,closes=c)
    assert b.logins==0 and not b.calls

@pytest.mark.parametrize('key',[None,'ab','AB'*32,'z'*64,'cd'*32])
def test_invalid_key_refuses_before_login(tmp_path,key):
    b=Broker()
    with pytest.raises(HaltProfile): fs.Session(live_profile(),tmp_path,now=NOW,broker=b,environ=ENV|{'FIDELITY_LIVE_FP_KEY':key},pin='a'*40)
    assert b.logins==0 and not (tmp_path/'ops').exists()

def test_unkeyed_profile_rejected_and_key_redacted(tmp_path,monkeypatch):
    actual=fs.LibraryBroker.__new__(fs.LibraryBroker); actual._LibraryBroker__account=ENV['FIDELITY_LIVE_ACCOUNT']; actual._LibraryBroker__fp_key=ENV['FIDELITY_LIVE_FP_KEY']
    assert actual.account_fingerprint==live_profile().account_fingerprint
    b=Broker(); p=replace(live_profile(),account_fingerprint=hashlib.sha256(ENV['FIDELITY_LIVE_ACCOUNT'].encode()).hexdigest())
    with pytest.raises(HaltProfile): run_session(p,tmp_path/'bad',now=NOW,broker=b,environ=ENV,pin='a'*40)
    assert b.logins==0
    session=fs.Session(live_profile(),tmp_path/'good',now=NOW,broker=b,environ=ENV,pin='a'*40)
    session.record['checks'].append(ENV['FIDELITY_LIVE_FP_KEY']); session.finish()
    assert ENV['FIDELITY_LIVE_FP_KEY'] not in ''.join(p.read_text() for p in tmp_path.rglob('*') if p.is_file())

@pytest.mark.parametrize('bad',['control','hash','count','source','missing','stale','holiday'])
def test_cli_bundle_prelogin(tmp_path,monkeypatch,bad):
    import fidelity_preview_session as cli
    from types import SimpleNamespace as NS
    b=Broker(); c=closes(); original=fs.Session
    if bad=='stale': c.index-=pd.Timedelta(days=1)
    if bad=='holiday': c=closes(NOW.replace(month=9,day=8))  # Labor Day: previous session is Friday
    monkeypatch.setattr(cli,'datetime',NS(now=lambda zone:NOW if bad!='holiday' else NOW.replace(month=9,day=8),fromisoformat=NOW.fromisoformat))
    monkeypatch.setattr(cli,'load_profiles',lambda value:{'live_fidelity':live_profile()})
    monkeypatch.setattr(cli,'Session',lambda *a,**k:original(*a,**(k|{'broker':b,'environ':ENV,'pin':'a'*40})))
    csv=tmp_path/'closes.csv'; c.to_csv(csv); profiles=tmp_path/'profiles.json'; profiles.write_text('{}')
    source=dict(source='alpaca_sip_daily',endpoint='https://data.alpaca.markets/v2/stocks/bars',fetched_at=NOW.isoformat(),completed_session='2026-10-14',adjustment='raw',row_count=1,sha256='b'*64,contract_version='fixture')
    if bad=='source': source['source']='tiingo_eod'
    bundle={'csv_sha256':hashlib.sha256(csv.read_bytes()).hexdigest(),'sources':[source]*(7 if bad=='count' else 8)}
    if bad=='hash': bundle['csv_sha256']='0'*64
    sources=tmp_path/'sources.json'; sources.write_text(json.dumps(bundle))
    if bad=='missing': csv.unlink()
    result=cli.main(['--profile','live_fidelity','--profiles-file',str(profiles),'--state-dir',str(tmp_path/'state'),'--closes-file',str(csv),'--sources-file',str(sources)])
    assert result==(0 if bad in ('control','holiday') else 1) and b.logins==(1 if bad in ('control','holiday') else 0)

@pytest.mark.parametrize('account',[ENV['FIDELITY_LIVE_ACCOUNT'],'FOREIGN-FIXTURE'])
def test_real_csv_keyed_identity(tmp_path,account):
    csv=tmp_path/'holdings.csv'
    csv.write_text('Account Number,Symbol,Current Value\n'+account+',SPAXX,100\n\nDate downloaded 10/15/2026 10:00 AM ET\n')
    r=run_session(live_profile(),tmp_path/'state',now=NOW,broker=Broker(),environ=ENV,pin='a'*40,csv=csv)
    assert r['clean']==(account==ENV['FIDELITY_LIVE_ACCOUNT']) and r['holdings_match']==r['clean']
    assert ENV['FIDELITY_LIVE_FP_KEY'] not in ''.join(p.read_text() for p in (tmp_path/'state').rglob('*') if p.is_file())
