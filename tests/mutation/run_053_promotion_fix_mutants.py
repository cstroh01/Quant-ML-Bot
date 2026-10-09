"""Rule 12 driver for the 053 promotion/evidence fix: each guard removed must turn a test red."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "scripts" / "model_registry.py"; orig = p.read_text()
muts = {
 "partial expected accepted": ('    if missing:\n        raise ManifestError(f"expected', '    if False:\n        raise ManifestError(f"expected'),
 "register champion allowed": ('if stage != "challenger":', 'if stage not in ("challenger", "champion"):'),
 "future gate3 accepted": ("if evidence.gate3_session > session:", "if False:"),
 "artifact unbound": ('if evidence.artifact_sha256 != record["artifact_sha256"]:', "if False:"),
 "config unbound": ('if evidence.config_sha256 != record["config_sha256"]:', "if False:"),
 "mode unbound": ("if evidence.mode != self.mode:", "if False:"),
 "foreign mode file read": ("if foreign:", "if False:"),
 "unregistered promote": ("if record is None:", "if False and record is None:"),
 "NaN counts accepted": ("            if isinstance(value, bool) or not isinstance(value, int) or value < 0:", "            if False:"),
 "truthy passes accepted": ("        if not (isinstance(evidence.gate3_pass, bool) and isinstance(evidence.oos_beats_baselines, bool)):", "        if False:"),
 "rollback single champion": ("if len(stack) < 2:", "if False:"),
}
killed = 0
for name, (a, b) in muts.items():
    assert orig.count(a) == 1, name
    p.write_text(orig.replace(a, b))
    r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_053_promotion.py", "tests/test_053_manifest.py", "-q", "-p", "no:cacheprovider", "-x"], capture_output=True, cwd=ROOT)
    ok = r.returncode != 0; killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
p.write_text(orig)
print(f"{killed}/{len(muts)} killed")
sys.exit(0 if killed == len(muts) else 1)
