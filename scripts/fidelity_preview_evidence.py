"""057 Q135/Q138 + 061 T006: offline, allowlisted item-6 evidence; never arms.

Reads the daily preview-sessions record, not the data-session runs.jsonl record.
No broker/network/vault access. Refusals and other policies never become evidence.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from allocation_policy import policy_evidence
from data import trading_days
from gate_checklist import fidelity_preview
from trial_registry import ROOT

DEST = Path('docs/implementation/spec-061/fidelity-preview')
API_RECONCILED = 'dedicated account reconciled exactly with bot ledger'  # exec/fidelity_session.py check


def body(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8')


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('xb') as stream: stream.write(content)
    temp.replace(path)


def record_session(source, *, root=ROOT, gate=None, record=False):
    root=Path(root).resolve()
    gate=Path(gate or root/'docs/implementation/spec-059/gate-manifest.json').resolve()
    if root not in gate.parents: raise ValueError('gate outside evidence root')
    raw=json.loads(Path(source).read_text(encoding='utf-8'))
    if (raw.get('mode')!='preview' or raw.get('allocation')!=policy_evidence()
            or any(a.get('outcome')!='PREVIEW' for a in raw.get('actions',[]))
            or not isinstance(raw.get('actions'),list)):
        raise ValueError('not a clean allocation preview')
    keys=('session','profile','clean','challenge','place_calls','account_fingerprint',
          'pin_sha','totp_step','library','settled_cash','holdings_match')
    row={k:raw[k] for k in keys}
    # Camden, 2026-10-22: "API holdings count." The session's own exact broker-API holdings
    # reconciliation is the item-6 holdings evidence; a CSV is optional and must match if present.
    row['api_holdings_reconciled']=API_RECONCILED in raw.get('checks',[])
    if not row['api_holdings_reconciled']: raise ValueError('API holdings reconciliation missing')
    row['settled_cash']={k:raw['settled_cash'][k] for k in ('amount','as_of')}
    row['previews']=[{'qty':float(p['qty']),'conf_num':p['conf_num']} for p in raw['previews']]
    if any(not isinstance(p['conf_num'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',p['conf_num'])
           for p in row['previews']): raise ValueError('invalid preview confirmation')
    if raw.get('csv_sha256') is not None: row['csv_sha256']=raw['csv_sha256']
    row['allocation']=policy_evidence()
    day=date.fromisoformat(row['session'])
    if trading_days(day,day)!=[day]: raise ValueError('not an NYSE session')
    stamp=datetime.fromisoformat(row['settled_cash']['as_of'])
    cash=row['settled_cash']['amount']
    if (row['profile']!='live_fidelity' or row['clean'] is not True or row['challenge'] is not False
            or row['place_calls']!=0 or type(row['totp_step']) is not bool
            or not re.fullmatch('[0-9a-f]{64}',row['account_fingerprint'])
            or not re.fullmatch('[0-9a-f]{40}',row['pin_sha'])
            or row['library']!={'version':'0.2.2','sha256':'f5a94056bd9a055ba88482ffcc7dc17013de9871b852b4d9b0dc55352506dd15'}
            or stamp.utcoffset() is None or stamp.astimezone(ZoneInfo('America/New_York')).date()!=day
            or isinstance(cash,bool) or not math.isfinite(cash) or cash<0
            or not any(p['qty']==1.0 and p['conf_num'] for p in row['previews'])
            or row['holdings_match'] not in (None,True)
            or (row['holdings_match'] is True and not re.fullmatch('[0-9a-f]{64}',row.get('csv_sha256','')))):
        raise ValueError('invalid fidelity_preview evidence')
    content=body(row); rel=DEST/(str(day)+'.json'); path=(root/rel).resolve()
    if root not in path.parents: raise ValueError('evidence path escapes root')
    item={'artifact':rel.as_posix(),'sha256':hashlib.sha256(content).hexdigest()}
    entry={'type':'fidelity_preview','artifact':(DEST/'manifest.json').as_posix(),
           'account_fingerprint':row['account_fingerprint'],'commit':row['pin_sha'],
           'date_utc':datetime.now(timezone.utc).isoformat()}
    manifest=json.loads(gate.read_text(encoding='utf-8'))
    existing=manifest.get('items',{}).get('6')
    if existing and (existing['commit']!=entry['commit'] or existing['account_fingerprint']!=entry['account_fingerprint']
                     or existing['artifact']!=entry['artifact']): raise ValueError('item 6 identity changed')
    index=root/DEST/'manifest.json'
    if existing and (hashlib.sha256(index.read_bytes()).hexdigest()!=existing['sha256']
                     or fidelity_preview(existing,root)[1]=='invalid fidelity_preview evidence'):
        raise ValueError('existing evidence changed')
    saved=json.loads(index.read_text(encoding='utf-8')) if index.exists() else {'sessions':[]}
    prior=next((i for i in saved['sessions'] if i['artifact']==item['artifact']),None)
    if prior:
        if prior!=item or path.read_bytes()!=content: raise ValueError('immutable day changed')
        return {'status':'ALREADY_RECORDED'}
    if path.exists() and path.read_bytes()!=content: raise ValueError('immutable day changed')
    if not record: return {'status':'PREFLIGHT_ONLY','no_writes':True}
    atomic(path,content)
    saved['sessions'].append(item); saved['sessions'].sort(key=lambda i:i['artifact'])
    index_body=body(saved); atomic(index,index_body)
    entry['sha256']=hashlib.sha256(index_body).hexdigest()
    manifest.setdefault('items',{})['6']=entry; atomic(gate,body(manifest))
    passed,detail=fidelity_preview(entry,root)
    return {'status':'RECORDED','item_6_evidenced':passed,'detail':detail}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session_record',type=Path)
    parser.add_argument('--record',action='store_true')
    args=parser.parse_args()
    try: print(json.dumps(record_session(args.session_record,record=args.record)))
    except (OSError,ValueError,KeyError,TypeError):
        parser.exit(1,'Preview evidence refused; inspect local daily record. No automatic retry.\n')


if __name__=='__main__': main()
