"""061 T006 operator guards: serial, disposable copies; synthetic records/sends only."""
from pathlib import Path
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from driver_support import copy_into, guarded, run_pytest

TESTS=('tests/test_061_paper_scope.py','tests/test_061_preview_evidence.py','tests/test_055_ops_runner.py')
COPIED=('scripts','exec','docs/trials','tests/context.py','tests/mode_fixtures.py',
        'tests/test_110_paper_allocation.py',*TESTS)
MUTANTS=[
 ('workflow KILL ignored','scripts/ops_runner.py','if not (Path(state_dir) / "KILL").exists():','if True:'),
 ('cutoff absent','exec/paper_loop.py','    if now >= before:','    if False:'),
 ('slow persist crosses cutoff','exec/paper_loop.py','        _check_submit_deadline(before, clock)\n        return client.submit_market_on_open(intent)',
  '        return client.submit_market_on_open(intent)'),
 ('expired run reads broker','exec/paper_loop.py','    if submit:\n        _check_submit_deadline(submit_before, now_fn)',
  '    if False:\n        _check_submit_deadline(submit_before, now_fn)'),
 ('old policy counted','scripts/paper_evidence.py','run.get("allocation") == policy_evidence()','True'),
 ('drills counted','scripts/paper_evidence.py','run.get("evidence_scope") == "qualifying"','True'),
 ('denied preview accepted','scripts/fidelity_preview_evidence.py',"any(a.get('outcome')!='PREVIEW' for a in raw.get('actions',[]))",'False'),
 ('other preview policy accepted','scripts/fidelity_preview_evidence.py',"raw.get('allocation')!=policy_evidence()",'False'),
]


def main():
    out=Path(sys.argv[1]); out.mkdir(parents=True,exist_ok=True); results=[]
    def run(label,mutant=None):
        with tempfile.TemporaryDirectory(prefix='qmb-061-operator-') as temp:
            root=copy_into(Path(temp),COPIED)
            if mutant:
                _,relative,old,new=mutant; path=root/relative
                text=path.read_text(encoding='utf-8'); assert text.count(old)==1,label
                path.write_text(text.replace(old,new),encoding='utf-8')
            xml=root/'result.xml'
            proc=run_pytest(root,*TESTS,'-q','--junitxml='+str(xml))
            (out/(label+'.log')).write_text(proc.stdout+proc.stderr,encoding='utf-8')
            (out/(label+'.xml')).write_bytes(xml.read_bytes()); tree=ET.parse(xml)
            assert tree.findall('.//testcase') and not tree.findall('.//error')
            failed=[c.get('name') for c in tree.findall('.//testcase') if c.find('failure') is not None]
            return proc.returncode,failed
    with guarded():
        assert run('control')==(0,[])
        for number,mutant in enumerate(MUTANTS,1):
            code,failed=run(str(number),mutant); assert code==1 and failed,mutant[0]
            results.append(dict(mutant=mutant[0],killed=True,failed_tests=failed))
            print('KILLED '+mutant[0],flush=True)
    (out/'results.json').write_text(json.dumps(dict(control='PASS',killed=len(results),total=len(MUTANTS),results=results),indent=2),encoding='utf-8')


if __name__=='__main__': main()
