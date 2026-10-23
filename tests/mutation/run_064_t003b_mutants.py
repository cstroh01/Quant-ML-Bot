"""064 T003b Rule 12: each planted defect in exec/live_loop.py must fail the real tests.

Usage: python tests/mutation/run_064_t003b_mutants.py <evidence-dir>. Restores the source.
"""
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/'exec/live_loop.py'
TESTS=['tests/test_064_live_cash_flows.py','tests/test_057_live_cash_basis.py','tests/test_057_q137.py','tests/test_v12_protected_budget.py']
MUTANTS={
 'stale halt ignored':("if observed.reconciliation_halt: raise HaltProfile","if False: raise HaltProfile"),
 'events dropped':("events=list(flows.events(live,now_fn()))","events=[]"),
 'injected source ignored':("flows=flow_source or UNSUPPORTED_FLOWS","flows=UNSUPPORTED_FLOWS"),
 'flow also sent per order':("snapshot=BrokerSnapshot(now_fn(),'OK',gate_equity,0.0,positions,prices)",
                             "snapshot=BrokerSnapshot(now_fn(),'OK',gate_equity,float(observed.net_flow),positions,prices)"),
 'order equity counts in-run fills':("snapshot=BrokerSnapshot(now_fn(),'OK',gate_equity,0.0,positions,prices)",
                                     "snapshot=BrokerSnapshot(now_fn(),'OK',cash+sum(q*prices[s] for s,q in positions.items()),0.0,positions,prices)"),
 'held valued at the +5% bound':("gate_equity=cash+sum(q*float(last[s]) for s,q in held.items())",
                                 "gate_equity=cash+sum(q*marks[s] for s,q in held.items())"),
 'held valued at zero':("gate_equity=cash+sum(q*float(last[s]) for s,q in held.items())","gate_equity=cash"),
 'quarantine unreported':("'quarantined':observed.quarantined","'quarantined':False"),
 'observation id not per run':("observation_id=f'{profile.name}:{today}:{session.run_id}'","observation_id=profile.name"),
}
def main():
    directory=Path(sys.argv[1]); directory.mkdir(parents=True,exist_ok=True)
    original=PATH.read_bytes(); results=[]
    def run(label):
        report=directory/(label+'.xml')
        proc=subprocess.run([sys.executable,'-B','-m','pytest',*TESTS,'-q','-p','no:cacheprovider','--junitxml='+str(report)],
                            cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        (directory/(label+'.log')).write_text(proc.stdout+proc.stderr,encoding='utf-8')
        tree=ET.parse(report); failures=tree.findall('.//failure')
        assert tree.findall('.//testcase') and not tree.findall('.//error')
        return proc.returncode,len(failures)
    try:
        assert run('control')==(0,0)
        for i,(name,(old,new)) in enumerate(MUTANTS.items()):
            source=original.decode('utf-8'); assert source.count(old)==1,name
            PATH.write_bytes(source.replace(old,new).encode('utf-8'))
            code,count=run(str(i)); assert code==1 and count,name
            results.append({'mutant':name,'killed':True,'failing_tests':count})
            PATH.write_bytes(original)
    finally: PATH.write_bytes(original)
    (directory/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps({'control':'PASS','killed':len(results),'total':len(MUTANTS)}))
if __name__=='__main__': main()
