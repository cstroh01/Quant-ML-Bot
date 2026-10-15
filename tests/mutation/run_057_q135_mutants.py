"""Q135 Rule 12; synthetic witnesses, require assertion failures, restore bytes."""
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
MUTANTS={
 'whole-share symbol ignores affordability':('exec/fidelity_session.py',"bound,symbol=affordable[0]","bound,symbol=affordable[0]; symbol='SPY'"),
 'unkeyed fingerprint':('exec/fidelity_live.py','return hmac.new(bytes.fromhex(key),account.encode(),hashlib.sha256).hexdigest()','return hashlib.sha256(account.encode()).hexdigest()'),
 'preview calls place':('exec/fidelity_live.py',"conf = self._call('preview', self._broker.preview, intent.instrument, side, qty)","self._broker.place(intent.instrument, side, qty, 'FIXTURE')\n        conf = self._call('preview', self._broker.preview, intent.instrument, side, qty)"),
 'preview writes intent':('exec/fidelity_live.py',"return {'symbol': intent.instrument, 'side': side, 'qty': qty, 'conf_num': conf}","record_intent(self._state_dir, intent.client_order_id, {'conf_num':conf})\n        return {'symbol': intent.instrument, 'side': side, 'qty': qty, 'conf_num': conf}"),
 'preview requires arming':('exec/fidelity_live.py',"side = 'B' if intent.delta_quantity > 0 else 'S'","require_armed(self._profile, None, now=datetime.now(timezone.utc))\n        side = 'B' if intent.delta_quantity > 0 else 'S'"),
 'second daily session':('exec/fidelity_session.py','acquire_lease(self.state,profile.name,self.day,run_id=self.run_id)','pass # lease bypass'),
 'challenge ignored':('exec/fidelity_session.py',"atomic_write(self.state/'HALTED','Camden review required\\n')","pass # persistent halt bypass"),
 'credential JSON leak':('exec/fidelity_session.py','if any(secret and any(secret in s for s in strings(self.record)) for secret in secrets):','if False:'),
}
def main():
    directory=Path(sys.argv[1]); directory.mkdir(parents=True,exist_ok=True)
    originals={p:(ROOT/p).read_bytes() for p,_,_ in MUTANTS.values()}
    results=[]
    def run(label):
        report=directory/(label+'.xml')
        proc=subprocess.run([sys.executable,'-B','-m','pytest','tests/test_057_q135.py','-q',
            '-p','no:cacheprovider','--junitxml='+str(report)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        (directory/(label+'.log')).write_text(proc.stdout+proc.stderr,encoding='utf-8')
        tree=ET.parse(report); failures=tree.findall('.//failure')
        assert tree.findall('.//testcase') and not tree.findall('.//error')
        return proc.returncode,len(failures)
    try:
        assert run('control')==(0,0)
        for i,(name,(p,old,new)) in enumerate(MUTANTS.items()):
            source=originals[p].decode('utf-8'); assert source.count(old)==1,name
            (ROOT/p).write_bytes(source.replace(old,new).encode('utf-8'))
            code,count=run(str(i)); assert code==1 and count,name
            results.append({'mutant':name,'killed':True,'assertion_failures':count})
            (ROOT/p).write_bytes(originals[p])
    finally:
        for p,data in originals.items(): (ROOT/p).write_bytes(data)
    (directory/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps({'control':'PASS','killed':len(results),'total':len(MUTANTS)}))
if __name__=='__main__': main()
