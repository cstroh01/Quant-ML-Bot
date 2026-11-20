"""Spec 069 Rule 12: each planted defect in fill observation must fail the real tests.

Usage: python tests/mutation/run_069_fill_observation_mutants.py. Restores every source byte for byte.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "exec/fidelity_live.py"
SESSION = ROOT / "exec/fidelity_session.py"
TESTS = ["tests/test_069_fill_observation.py"]
NUMBERS = '        numbers = [previous["conf_num"]]\n'
RECORD = '"conf_nums": sorted(set(numbers)), "status": status}'
MUTANTS = {
    "observation skipped": (LIVE, "        self._observe(intent.client_order_id, (conf_num, placed), quantity)\n", ""),
    "never waits": (LIVE, "                _sleep(wait)\n", ""),
    "waits longer than D-1": (LIVE, "_OBSERVE_WAITS = (2.0, 3.0, 5.0, 10.0)", "_OBSERVE_WAITS = (2.0, 3.0, 5.0, 10.0, 20.0)"),
    "non-terminal status recorded": (LIVE, "if found is None or found[0] not in TERMINAL_STATUSES:", "if found is None:"),
    "quantity mismatch recorded": (LIVE, 'if code == "FILLED" and not _same_quantity(executed, quantity):', "if False:"),
    "missing quantity refused": (LIVE, "    if executed is None:\n        return True\n", "    if executed is None:\n        return False\n"),
    "quantity tolerance loose": (LIVE, "abs(value - ordered) < 0.0005", "abs(value - ordered) < 0.01"),
    "only the preview number looked up": (LIVE, "        for number in numbers:\n            status, executed", "        for number in numbers[:1]:\n            status, executed"),
    "record outranks Fidelity": (LIVE, NUMBERS, '        if outcome is not None and outcome["outcome"] == _OBSERVED: return outcome["status"]\n' + NUMBERS),
    "record ignored next session": (LIVE, '            return outcome["status"]  # spec 069 FR-003', '            return None  # spec 069 FR-003'),
    "observation error changes the result": (LIVE, '            result = f"error {type(exc).__name__}"\n',
                                             '            raise BrokerError("observation failed") from None\n'),
    "challenge swallowed": (LIVE, "        except HaltProfile:\n            raise\n        except Exception as exc:  # noqa: BLE001 - the order is placed",
                            "        except Exception as exc:  # noqa: BLE001 - the order is placed"),
    "quantity recorded": (LIVE, RECORD, '"conf_nums": sorted(set(numbers)), "status": status, "qty": quantity}'),
    "any record superseded": (LIVE, 'current["outcome"] == "placed" and current["conf_nums"] == record["conf_nums"]', "True"),
    "malformed observation trusted": (LIVE, '                     and (not observed or record["status"] in TERMINAL_STATUSES)\n', ""),
    "executed quantity dropped": (LIVE, "executed = getattr(getattr(detail, 'amount_detail', None), 'qty_exec', None)", "executed = None"),
    "FR-004 not reported": (SESSION, "        if observed: self.record['observations']", "        if False: self.record['observations']"),
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
