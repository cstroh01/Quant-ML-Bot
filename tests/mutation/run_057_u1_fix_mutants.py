"""Rule 12 driver for 057 U1 fixes: each guard removed must turn a test red. Fakes only."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "exec" / "fidelity_live.py"
orig = p.read_text()
MUTS = {
    "non-timeout place error is known": ("        except Exception as exc:  # noqa: BLE001 - once place is called, the order may exist\n            raise SubmissionUnknown(",
                                         "        except TimeoutError as exc:  # noqa: BLE001 - once place is called, the order may exist\n            raise SubmissionUnknown("),
    "preview error unredacted": ("            raise BrokerError(f\"{stage} failed: {type(exc).__name__}\") from None",
                                 "            raise BrokerError(f\"{stage} failed: {exc}\") from None"),
    "retry previews again": ("        if previous is not None:\n            return self._resubmission(", "        if False:\n            return self._resubmission("),
    "unknown retry returns conf": ("        if status is None:\n            raise SubmissionUnknown(", "        if False:\n            raise SubmissionUnknown("),
    "reused id accepted": ('        if (previous["symbol"], previous["side"], previous["qty"]) != (symbol, side, quantity):', "        if False:"),
    "record after place": ("        record_intent(self._state_dir, intent.client_order_id,\n                      {\"symbol\": intent.instrument, \"side\": side, \"qty\": quantity, \"conf_num\": conf_num})\n        try:\n            return self._broker.place(intent.instrument, side, quantity, conf_num)",
                           "        try:\n            return self._broker.place(intent.instrument, side, quantity, conf_num)"),
    "challenge does not halt": ("        except SecurityChallenge:\n            self._halted = True\n            raise HaltProfile(f\"{self._profile.name}: security challenge at placement",
                                "        except SecurityChallenge:\n            raise HaltProfile(f\"{self._profile.name}: security challenge at placement"),
}
killed = 0
for name, (a, b) in MUTS.items():
    assert orig.count(a) == 1, name
    p.write_text(orig.replace(a, b))
    try:
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_057_fidelity_live.py", "-q",
                            "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
    finally:
        p.write_text(orig)
    ok = r.returncode != 0
    killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
print(f"{killed}/{len(MUTS)} killed")
sys.exit(0 if killed == len(MUTS) else 1)
