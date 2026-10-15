"""Q139 Rule 12: require clean control and real assertion failures; restore bytes."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'exec/fidelity_live.py'
ORIGINAL = PATH.read_bytes()
MUTANTS = {
 'account filter omitted': ('get_positions([self.__account])', 'get_positions([])'),
 'account filter swapped': ('get_balances([self.__account])', "get_balances(['OTHER'])"),
 'top-level status': ("getattr(getattr(order, 'id_detail', None), 'conf_num', None)", "getattr(order, 'conf_num', None)"),
 'auth not halting': ("raise SecurityChallenge('Fidelity authentication or entitlement refused') from None", "raise BrokerError('Fidelity authentication refused') from None"),
 'foreign redirect': ("if not self._allowed(target) or any(", "if False and any("),
 'buying power as cash': ('amount = snapshot.cash_detail.settled_amt', 'amount = snapshot.buying_power_detail.cash'),
 'stale accepted': ("when.astimezone(ZoneInfo('America/New_York')).date() != as_of.astimezone(ZoneInfo('America/New_York')).date()", 'False'),
 'inner text disclosed': ("except Exception:\n            raise SecurityChallenge('Fidelity authentication or entitlement refused') from None", "except Exception as exc:\n            raise SecurityChallenge(str(exc)) from None"),
}


def run(directory, label):
    report = directory / (label + '.xml')
    proc = subprocess.run([sys.executable, '-B', '-m', 'pytest', 'tests/test_057_q139.py', '-q',
                           '-p', 'no:cacheprovider', '--junitxml=' + str(report)], cwd=ROOT, capture_output=True, text=True)
    (directory / (label + '.log')).write_text(proc.stdout + proc.stderr)
    if not report.exists(): raise RuntimeError('No test report')
    tree = ET.parse(report)
    cases = tree.findall('.//testcase')
    failures = [c for c in cases if c.find('failure') is not None]
    assert cases and not tree.findall('.//error'), 'Collection/import errors are not killed mutants'
    return proc.returncode, failures


def main():
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix='q139-mutants-'))
    directory.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        code, failures = run(directory, 'control')
        assert code == 0 and not failures, 'Clean control failed'
        source = ORIGINAL.decode()
        for i, (name, (old, new)) in enumerate(MUTANTS.items()):
            assert source.count(old) == 1, name
            PATH.write_bytes(source.replace(old, new).encode())
            code, failures = run(directory, str(i))
            assert code == 1 and failures, 'Mutant survived: ' + name
            results.append({'mutant': name, 'killed': True, 'witnesses': [c.attrib['name'] for c in failures]})
            PATH.write_bytes(ORIGINAL)
    finally:
        PATH.write_bytes(ORIGINAL)
    (directory / 'results.json').write_text(json.dumps(results, indent=2))
    print(json.dumps({'control': 'PASS', 'killed': len(results), 'total': len(MUTANTS), 'source_restored': PATH.read_bytes() == ORIGINAL}))


if __name__ == '__main__':
    main()
