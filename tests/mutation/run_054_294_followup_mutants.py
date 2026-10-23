"""054/#294 review follow-ups, Rule 12: each planted defect must fail the real tests.

Usage: python tests/mutation/run_054_294_followup_mutants.py <evidence-dir>. Restores every source.
"""
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
TESTS=['tests/test_054_fidelity_csv.py','tests/test_057_q135.py','tests/test_059_gate_checklist.py']
MUTANTS={
 'missing API field read as reconciled':('scripts/gate_checklist.py',"row['api_holdings_reconciled'] is not True","row.get('api_holdings_reconciled') is False"),
 'header names not stripped':('scripts/holdings_import.py','headers = [name.strip().casefold()','headers = [name.casefold()'),
 'row keys not stripped':('scripts/holdings_import.py','{key.strip().casefold(): value','{key.casefold(): value'),
 'history cash balance optional':('scripts/holdings_import.py',', "Amount ($)", "Cash Balance ($)")',', "Amount ($)")'),
}
def main():
    directory=Path(sys.argv[1]); directory.mkdir(parents=True,exist_ok=True)
    originals={rel:(ROOT/rel).read_bytes() for rel,_,_ in MUTANTS.values()}; results=[]
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
        for i,(name,(rel,old,new)) in enumerate(MUTANTS.items()):
            source=originals[rel].decode('utf-8'); assert source.count(old)==1,name
            (ROOT/rel).write_bytes(source.replace(old,new).encode('utf-8'))
            code,count=run(str(i)); assert code==1 and count,name
            results.append({'mutant':name,'killed':True,'failing_tests':count})
            (ROOT/rel).write_bytes(originals[rel])
    finally:
        for rel,data in originals.items(): (ROOT/rel).write_bytes(data)
    (directory/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps({'control':'PASS','killed':len(results),'total':len(MUTANTS)}))
if __name__=='__main__': main()
