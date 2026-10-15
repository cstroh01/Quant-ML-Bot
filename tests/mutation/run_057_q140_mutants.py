"""Q140 Rule 12: clean control, five real assertion failures, byte restoration."""
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'scripts/fidelity_launch.py'
MUTANTS = {
    'fingerprint mode prints account or key': ("    return hmac.new(bytes.fromhex(credentials['FIDELITY_LIVE_FP_KEY']),credentials['FIDELITY_LIVE_ACCOUNT'].encode(),hashlib.sha256).hexdigest()", "    return credentials['FIDELITY_LIVE_ACCOUNT']+credentials['FIDELITY_LIVE_FP_KEY']"),
    'credential on argv': ('spawn(list(command), env=child_env, check=False)',
                           'spawn(list(command)+[credentials[CREDENTIAL_NAMES[0]]], env=child_env, check=False)'),
    'credential printed': ('        child_env = dict(environ)',
                           '        print(credentials[CREDENTIAL_NAMES[0]])\n        child_env = dict(environ)'),
    'parent mutated': ('        child_env.update(credentials)',
                       '        os.environ.update(credentials)\n        child_env.update(credentials)'),
    'missing value runs': ('if missing is not None:',
                           'if False:'),
}


def main():
    directory = Path(sys.argv[1]); directory.mkdir(parents=True, exist_ok=True)
    original = PATH.read_bytes(); results = []
    def run(label):
        report = directory / (label+'.xml')
        proc = subprocess.run([sys.executable, '-B', '-m', 'pytest', 'tests/test_057_q140.py', '-q',
            '-p', 'no:cacheprovider', '--junitxml='+str(report)], cwd=ROOT, capture_output=True,
            text=True, encoding='utf-8')
        (directory/(label+'.log')).write_text(proc.stdout+proc.stderr, encoding='utf-8')
        tree = ET.parse(report); failures = tree.findall('.//failure')
        assert tree.findall('.//testcase') and not tree.findall('.//error')
        return proc.returncode, len(failures)
    try:
        assert run('control') == (0, 0)
        for i, (name, (old, new)) in enumerate(MUTANTS.items()):
            source = original.decode('utf-8'); assert source.count(old) == 1, name
            PATH.write_bytes(source.replace(old, new).encode('utf-8'))
            code, count = run(str(i)); assert code == 1 and count, name
            results.append({'mutant': name, 'killed': True, 'failing_tests': count})
            PATH.write_bytes(original)
    finally:
        PATH.write_bytes(original)
    (directory/'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps({'control': 'PASS', 'killed': len(results), 'total': len(MUTANTS),
                      'source_restored': PATH.read_bytes() == original}))


if __name__ == '__main__':
    main()
