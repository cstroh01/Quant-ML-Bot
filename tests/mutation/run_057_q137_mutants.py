"""Q137 Rule 12: blocked sockets, synthetic brokers, require real failing tests."""
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/'exec/live_loop.py'
MUTANTS={
 'places unarmed':('if not armed: return live.preview(candidate)',"if not armed:\n                    session.broker.place(candidate.instrument,'B',candidate.delta_quantity,'FIXTURE')\n                    return live.preview(candidate)"),
 'bypasses gateway':('result=submit_order(gate,snapshot=snapshot,intent=intent,now=now_fn(),submit=send)','result=send(intent)'),
 'skips reconcile':("session.record['reconciliation']=require_reconciled(gate,live,now=now_fn())","session.record['reconciliation']=[]"),
 'exceeds 200 cap':('LIVE_CAP=MAX_LIVE_BUDGET_USD','LIVE_CAP=1000.0'),
 'uses unsettled cash':("cash=session.record['settled_cash']['settled_amt']","cash=session.record['settled_cash'].get('coreBalance',9000.0)"),
}
def main():
    directory=Path(sys.argv[1]); directory.mkdir(parents=True,exist_ok=True)
    original=PATH.read_bytes(); results=[]
    def run(label):
        report=directory/(label+'.xml')
        proc=subprocess.run([sys.executable,'-B','-m','pytest','tests/test_057_q137.py','tests/test_v12_protected_budget.py','-q',
            '-p','no:cacheprovider','--junitxml='+str(report)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
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
