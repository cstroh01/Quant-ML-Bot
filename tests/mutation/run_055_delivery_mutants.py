"""Rule 12 driver for 055 F02b: persist-before-broker and reliable delivery guards must each go red."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RN, RD, RT = (ROOT / "scripts" / n for n in ("ops_runner.py", "ops_deliver.py", "ops_runtime.py"))
WF = ROOT / "ops" / "workflows" / "paper-loop.yml"
MUTS = {
    "no summary queued": (RN, '    queue_outbox(state_dir, f"summary-', '    (lambda *a, **k: None)(state_dir, f"summary-'),
    "incident not queued": (RN, "        queue_outbox(ops.parent, f\"incident-", "        (lambda *a, **k: None)(ops.parent, f\"incident-"),
    "stale log record reused": (RN, "        stream.seek(offset)", "        stream.seek(0)"),
    "other profile's record used": (RN, '    if not isinstance(record, dict) or record.get("profile", profile) != profile:', "    if not isinstance(record, dict):"),
    "data session dropped": (RT, '        data_session = date.fromisoformat(str(record["session"])[:10]) if "session" in record else None', "        data_session = None"),
    "aborted not noted": (RT, '        notes.append(f"aborted: {record[\'aborted\']}")', "        pass"),
    "open reservations miscounted": (RT, "if str(row.get(\"broker_status\")).upper() not in _TERMINAL)", "if True)"),
}
killed = 0
for name, (path, a, b) in MUTS.items():
    orig = path.read_text()
    assert orig.count(a) == 1, name
    path.write_text(orig.replace(a, b))
    try:
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_055_delivery.py", "tests/test_055_runner.py",
                            "tests/test_055_alerts.py", "-q", "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
    finally:
        path.write_text(orig)
    ok = r.returncode != 0
    killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
print(f"{killed}/{len(MUTS)} killed")
sys.exit(0 if killed == len(MUTS) else 1)
