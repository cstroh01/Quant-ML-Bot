"""057 T012 Rule 12: each planted defect in the FR-013 failure diagnostics must fail the real tests.

Usage: python tests/mutation/run_057_t012_mutants.py. Restores every source byte for byte.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "exec/fidelity_live.py"
SESSION = ROOT / "exec/fidelity_session.py"
LOOP = ROOT / "exec/live_loop.py"
TESTS = ["tests/test_057_t012_failure_diagnostics.py"]
MUTANTS = {
    "library message recorded": (LIVE, "'library ' + type(exc).__name__", "'library ' + str(exc)"),
    "last refusal wins": (LIVE, "if getattr(self, 'failure', None) is None:", "if True:"),
    "account digits kept in path": (LIVE, "'*' if any(c.isdigit() for c in s) or len(s) > 24 else s",
                                    "'*' if len(s) > 24 else s"),
    "trace unbounded": (LIVE, "            del trace[:-_TRACE_LIMIT]\n", ""),
    "earliest responses kept": (LIVE, "del trace[:-_TRACE_LIMIT]", "del trace[_TRACE_LIMIT:]"),
    "request-time refusal not noted": (LIVE, "            self._check_request(request)\n        except SecurityChallenge as exc:\n            self._note_refusal(str(exc))\n",
                                       "            self._check_request(request)\n        except SecurityChallenge as exc:\n"),
    "diagnostic can break a guard": (LIVE, "            del trace[:-_TRACE_LIMIT]\n        except Exception:\n            pass\n",
                                     "            del trace[:-_TRACE_LIMIT]\n        finally:\n            pass\n"),
    "non-integer auth code kept": (LIVE, "code if type(code) is int else None", "code"),
    "foreign message recorded": (SESSION, "if type(exc).__module__ in _OWN_MODULES else None", "if True else None"),
    "settled-cash stage not set": (SESSION, "self.stage='settled_cash'", "self.stage='login'"),
    "failure can raise": (SESSION, "            return {'stage':getattr(self,'stage',None),'kind':type(exc).__name__,'detail':None,'login':None}",
                          "            raise"),
    "failure omitted": (LOOP, "            failure=session.failure(exc))", "            )"),
    "allocation stage not set": (LOOP, "session.stage='allocation'", "pass"),
}
def run():
    return subprocess.run([sys.executable, "-B", "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True).returncode
def main():
    originals = {path: path.read_bytes() for path in (LIVE, SESSION, LOOP)}; results = {}
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
