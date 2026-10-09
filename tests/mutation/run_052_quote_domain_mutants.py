"""052 T008 causal mutants: only the expected contract failure counts; source restored."""
import ast
import pathlib
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
TARGET = ROOT / "scripts" / "asset_registry.py"
ORIGINAL = TARGET.read_bytes()
TEXT = ORIGINAL.decode("utf-8")
MUTANTS = [
    ("age", "    if isinstance(max_quote_age_seconds, bool) or not (_finite(max_quote_age_seconds) and float(max_quote_age_seconds) >= 0):", "    if False:", "test_invalid_age_configuration_refused[infinite]", "DID NOT RAISE"),
    ("spread", "    elif quote.spread_bps < 0:", "    elif False:", "test_negative_quote_domain_refused_with_valid_sibling", "spread_invalid: negative domain admitted"),
    ("minimum", "    elif quote.min_notional_usd < 0:", "    elif False:", "test_negative_quote_domain_refused_with_valid_sibling", "broker_minimum_invalid: negative domain admitted"),
]
def run(xml):
    command = [sys.executable, "-B", "-m", "pytest", "tests/test_052_quote_domain.py", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}"]
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True)

with tempfile.TemporaryDirectory(prefix="qmb-052-f02-") as tmp:
    xml = pathlib.Path(tmp) / "contracts.xml"
    assert run(xml).returncode == 0, "unmutated control must pass"
    try:
        for name, old, new, node, message in MUTANTS:
            assert TEXT.count(old) == 1, name
            changed = TEXT.replace(old, new)
            ast.parse(changed)
            TARGET.write_bytes(changed.encode("utf-8"))
            proc = run(xml)
            cases = list(ET.parse(xml).getroot().iter("testcase"))
            assert proc.returncode == 1 and not any(c.find("error") is not None for c in cases), name
            assert any(node in c.attrib["name"] and message in c.find("failure").attrib.get("message", "")
                       for c in cases if c.find("failure") is not None), f"{name}: intended assertion did not fail"
            print(f"KILLED {name}: {node}: {message}", flush=True)
            TARGET.write_bytes(ORIGINAL)
    finally:
        TARGET.write_bytes(ORIGINAL)
assert TARGET.read_bytes() == ORIGINAL
print("3/3 intended contract kills; source restored")
