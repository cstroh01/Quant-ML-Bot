"""Q135: preview-only operator entry point; never arms or submits."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'exec'))
from fidelity_session import Session, UnsettledCash, PreviewUnaffordable, validate_closes
from mode_config import load_profiles
from ops_runtime import queue_outbox

def run_session(profile,state,*,now,broker=None,environ=None,pin,csv=None,closes=None):
    validate_closes(closes,now)
    try:
        session=Session(profile,state,now=now,broker=broker,environ=environ,pin=pin)
    except Exception:
        queue_outbox(state,'fidelity-session-refused',kind='incident',title='[live_fidelity] refused',
                     body='Session claim refused; nothing logged in or rerun.')
        raise
    try:
        session.connect(csv)
        session.preview_pair(closes)
    except (UnsettledCash,PreviewUnaffordable) as exc:
        session.record['refused']='unsettled_cash' if isinstance(exc,UnsettledCash) else 'preview_unaffordable'
        return session.finish()
    except Exception:
        return session.finish(error=True)
    return session.finish()

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',required=True,choices=['live_fidelity'])
    p.add_argument('--profiles-file',type=Path,required=True)
    p.add_argument('--state-dir',type=Path,required=True)
    p.add_argument('--holdings-csv',type=Path)
    p.add_argument('--closes-file',type=Path,required=True)
    p.add_argument('--sources-file',type=Path,required=True)
    a=p.parse_args(argv)
    try:
        import hashlib, pandas as pd
        from data_sources import SourceManifest
        raw=a.closes_file.read_bytes(); bundle=json.loads(a.sources_file.read_text(encoding='utf-8'))
        if hashlib.sha256(raw).hexdigest()!=bundle['csv_sha256'] or len(bundle['sources'])!=8: raise ValueError
        for source in bundle['sources']:
            if SourceManifest(**(source|{'fetched_at':datetime.fromisoformat(source['fetched_at'])})).source!='alpaca_sip_daily': raise ValueError
        closes=pd.read_csv(a.closes_file,index_col=0,parse_dates=True)
        profile=load_profiles(json.loads(a.profiles_file.read_text(encoding='utf-8')))[a.profile]
        r=run_session(profile,a.state_dir,now=datetime.now(timezone.utc),pin=os.environ.get('QMB_PINNED_SHA',''),csv=a.holdings_csv,closes=closes)
    except Exception:
        print('Fidelity preview refused; no session rerun.'); return 1
    print(json.dumps({'clean':r['clean'],'place_calls':r['place_calls'],'challenge':r['challenge']}))
    return 0 if r['clean'] or r.get('refused') in ('unsettled_cash','preview_unaffordable') else 1

if __name__=='__main__': raise SystemExit(main())
