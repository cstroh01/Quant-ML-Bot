"""057 T011 Rule 12: each planted defect in scripts/fidelity_live_host.py must fail the real tests.

Usage: python tests/mutation/run_057_t011_mutants.py <evidence-dir>. Restores the source.
"""
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/'scripts/fidelity_live_host.py'
TESTS=['tests/test_057_live_host.py']
MUTANTS={
 'digest unchecked':('if hashlib.sha256(raw).hexdigest() != row["capital_gate_evidence_sha256"]:','if False:'),
 'checklist ignored':('if not checklist(json.loads(raw), Path(root))[0]:','if False:'),
 'expiry ignored':('not start <= now < end','not start <= now'),
 'anyone may arm':(' or row["activated_by"] != "Camden"',''),
 'preview fallback accepted':('record.get("mode") != "submit"','record.get("mode") not in ("submit", "preview")'),
 'denial accepted':('OUTCOMES = frozenset({"SUBMITTED", "BUDGET_REFUSED"})','OUTCOMES = frozenset({"SUBMITTED", "BUDGET_REFUSED", "DENIED"})'),
 'arming file left behind':('arming.unlink(missing_ok=True)','pass'),
 'other account accepted':('or record.get("account_fingerprint") != row["account_fingerprint"]','or False'),
 'unsettled day still fails':('return "UNSETTLED"','raise ValueError'),
 'unsettled skip with orders accepted':('or type(record.get("place_calls")) is not int or record["place_calls"] != 0','or False'),
 'unsettled skip ignores a latched halt':(' or (state / "HALTED").exists()):','):'),
 'unsettled skip from another account':('row["account_fingerprint"] != record.get("account_fingerprint")','False'),
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
