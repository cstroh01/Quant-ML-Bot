"""Rule 12 driver for 055 F03 (exec/paper_loop durable integration). Fakes only."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PL, RT, RN = ROOT / "exec" / "paper_loop.py", ROOT / "scripts" / "ops_runtime.py", ROOT / "scripts" / "ops_runner.py"
MUTS = {
    "random client ids": ("intent = OrderIntent(client_order_id(owner, today, order.ticker, side), order.ticker, order.delta_quantity)",
                          "import uuid; intent = OrderIntent(uuid.uuid4().hex, order.ticker, order.delta_quantity)"),
    "unknown reservations ignored": ("    if unresolved:\n        raise RunAborted(", "    if False:\n        raise RunAborted("),
    "account not verified": ("        if not number or hashlib.sha256(number.encode()).hexdigest() != profile.account_fingerprint:", "        if False:"),
}
killed = 0
for name, spec in MUTS.items():
    path, a, b = spec if len(spec) == 3 else (PL, *spec)
    orig = path.read_text()
    assert orig.count(a) == 1, name
    path.write_text(orig.replace(a, b))
    try:
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_055_paper_loop_durable.py", "tests/test_049_paper_loop.py",
                            "tests/test_051_paper_loop_profile.py", "-q",
                            "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
    finally:
        path.write_text(orig)
    ok = r.returncode != 0
    killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
print(f"{killed}/{len(MUTS)} killed")
sys.exit(0 if killed == len(MUTS) else 1)
