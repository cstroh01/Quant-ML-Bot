"""Spec 068 Rule 12: each planted defect in placement acceptance must fail the real tests.

Usage: python tests/mutation/run_068_place_acceptance_mutants.py. Restores every source byte for byte.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "exec/fidelity_live.py"
RECONCILE = ROOT / "exec/fidelity_reconcile.py"
TESTS = ["tests/test_068_place_acceptance.py"]
NUMBER = ("        if not response.conf_num:  # accepted without a number: the order may exist\n"
          "            raise SubmissionUnknown(\"placement accepted without a confirmation number\")\n"
          "        return response.conf_num\n")
REJECTED = '            self._settle(intent.client_order_id, "rejected", (conf_num, exc.conf_num))\n'
NUMBERS = '        numbers = [previous["conf_num"]]\n'
NOT_SENT = '            return "REJECTED" if outcome is not None and outcome["outcome"] == "not_sent" else None\n'
MUTANTS = {
    "A check dropped": (LIVE, '        if not response.is_accepted:  # spec 068 FR-002', '        if False:  # spec 068 FR-002'),
    "falls back to the preview number": (LIVE, NUMBER, "        return response.conf_num or conf_num\n"),
    "V check dropped": (LIVE, "        if not response.is_validated or not conf:", "        if not conf:"),
    "REJECTED without asking the broker": (LIVE, NUMBERS, '        if outcome is not None and outcome["outcome"] == "rejected": return "REJECTED"\n' + NUMBERS),
    "message text recorded": (LIVE, "k.lower().endswith(('code', 'type', 'severity'))", "k.lower().endswith(('code', 'type', 'severity', 'text', 'detail'))"),
    "raw reply kept": (LIVE, "self._replies()[endpoint] = _order_reply_facts(endpoint, response.json())", "self._replies()[endpoint] = response.json()"),
    "earlier reply reported": (LIVE, "        self._replies().pop('place', None)  # FR-005: never report an earlier request's reply\n", ""),
    "rejection not marked": (LIVE, REJECTED, "            pass\n"),
    "rejection reported as unknown": (LIVE, REJECTED + "            raise\n", REJECTED + "            raise SubmissionUnknown('placement outcome unknown') from None\n"),
    "refused preview not marked": (LIVE, '            self._mark(intent.client_order_id, "not_sent", ())  # FR-001: placement never ran\n', "            pass\n"),
    "any marker without intent counts": (LIVE, NOT_SENT, '            return "REJECTED" if outcome is not None else None\n'),
    "placement number not recorded": (LIVE, '        if placed != conf_num:  # FR-002.3', '        if False:  # FR-002.3'),
    "different record overwritten": (LIVE, "        if self._outcome(client_order_id) not in (None, record):", "        if False:"),
    "malformed record trusted": (LIVE, "        if not valid:\n", "        if False:\n"),
    "FR-004 states dropped": (RECONCILE, "{', '.join(why)}", "{blocked}"),
    "FR-004 raw status": (RECONCILE, "f' {_label(r[\"status\"])}'", "f' {r[\"status\"]}'"),
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
