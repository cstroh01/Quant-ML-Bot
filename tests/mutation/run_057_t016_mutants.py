"""057 T016 Rule 12: each planted defect in the D-9 entitlement facts must fail the real tests.

Usage: python tests/mutation/run_057_t016_mutants.py. Restores every source byte for byte.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "exec/fidelity_live.py"
TESTS = ["tests/test_057_t016_entitlement_diagnostic.py"]
GUARD = "if getattr(context, 'has_atp_access', None) is not True or getattr(context, 'errors', None) != []:"
LABEL = "return value if isinstance(value, str) and _LABEL.fullmatch(value) and not re.search(r'[0-9]{3}', value) else '*'"
VALUE = "row['value'].lower() if isinstance(row.get('value'), str) and row['value'].lower() in ('true', 'false') else 'other'"
FACT = "fact[name] = value if type(value) is int and abs(value) < 100000 else _label(value)"
MUTANTS = {
    "guard: errors ignored": (LIVE, GUARD, "if getattr(context, 'has_atp_access', None) is not True:"),
    "guard: entitlement ignored": (LIVE, GUARD, "if getattr(context, 'errors', None) != []:"),
    "label: digit run allowed": (LIVE, LABEL, "return value if isinstance(value, str) and _LABEL.fullmatch(value) else '*'"),
    "label: match not full": (LIVE, LABEL, "return value if isinstance(value, str) and _LABEL.match(value) and not re.search(r'[0-9]{3}', value) else '*'"),
    "label: raw text kept": (LIVE, LABEL, "return value if isinstance(value, str) else '*'"),
    "label: length unbounded": (LIVE, "_LABEL = re.compile(r'[A-Za-z][A-Za-z0-9_ -]{0,31}')", "_LABEL = re.compile(r'[A-Za-z][A-Za-z0-9_ -]*')"),
    "value: raw value kept": (LIVE, VALUE, "row.get('value')"),
    "value: not lowered": (LIVE, VALUE, "row['value'] if isinstance(row.get('value'), str) and row['value'] in ('true', 'false') else 'other'"),
    "error: message recorded": (LIVE, "for name in ('code', 'type', 'status'):", "for name in ('code', 'type', 'status', 'message'):"),
    "error: identifier-size int kept": (LIVE, FACT, "fact[name] = value if type(value) is int else _label(value)"),
    "error: bool kept as int": (LIVE, FACT, "fact[name] = value if isinstance(value, int) and abs(value) < 100000 else _label(value)"),
    "error: non-dict text recorded": (LIVE, "        return {'kind': type(error).__name__}\n", "        return {'kind': str(error)}\n"),
    "keys: names unmasked": (LIVE, "return sorted(_label(k) for k in value)[:_KEY_LIMIT]", "return sorted(value)[:_KEY_LIMIT]"),
    "keys: uncapped": (LIVE, "return sorted(_label(k) for k in value)[:_KEY_LIMIT]", "return sorted(_label(k) for k in value)"),
    "rows: uncapped": (LIVE, "for row in rows[:_ENTITLEMENT_LIMIT]]", "for row in rows]"),
    "errors: uncapped": (LIVE, "for error in errors[:_ERROR_LIMIT]]", "for error in errors]"),
    "payload: raw non-dict recorded": (LIVE, "        return {'kind': type(payload).__name__}\n", "        return {'kind': str(payload)}\n"),
    "row: raw non-dict recorded": (LIVE, "if isinstance(row, dict) else {'kind': type(row).__name__} for row", "if isinstance(row, dict) else {'kind': str(row)} for row"),
    "any path read": (LIVE, "if url.path.endswith('/context/security'):", "if True:"),
    "facts never stored": (LIVE, "self.entitlement = _entitlement_facts(response.json())", "_entitlement_facts(response.json())"),
    "facts built before the trace": (LIVE, "            trace.append(entry)\n", "            if url.path.endswith('/context/security'): _entitlement_facts(response.json())\n            trace.append(entry)\n"),
    "diagnostic omits facts": (LIVE, "            facts['entitlement'] = self.entitlement  # D-9\n", "            pass\n"),
    "diagnostic key always present": (LIVE, "if getattr(self, 'entitlement', None) is not None:", "if True:"),
}
def run():
    return subprocess.run([sys.executable, "-B", "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True).returncode
def main():
    paths = {path for path, _, _ in MUTANTS.values()}
    originals = {path: path.read_bytes() for path in paths}; results = {}
    try:
        assert run() == 0, "control"
        for name, (path, old, new) in MUTANTS.items():
            raw = originals[path].decode("utf-8"); crlf = "\r\n" in raw
            source = raw.replace("\r\n", "\n"); assert source.count(old) == 1, name
            mutated = source.replace(old, new)
            path.write_bytes((mutated.replace("\n", "\r\n") if crlf else mutated).encode("utf-8"))
            results[name] = "killed" if run() else "SURVIVED"
            path.write_bytes(originals[path])
    finally:
        for path, data in originals.items():
            path.write_bytes(data)
    print(json.dumps({"control": "PASS", "killed": sum(v == "killed" for v in results.values()),
                      "total": len(MUTANTS), "survivors": [k for k, v in results.items() if v != "killed"]}))
    return 0 if all(v == "killed" for v in results.values()) else 1
if __name__ == "__main__":
    sys.exit(main())
