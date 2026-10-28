"""057 T013 Rule 12: each planted defect in the D-6a login-page-move allowance must fail the real tests.

Usage: python tests/mutation/run_057_t013_mutants.py. Restores every source byte for byte.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "exec/fidelity_live.py"
TESTS = ["tests/test_057_t013_login_page_move.py"]
MUTANTS = {
    "allowance removed": (LIVE, "if not self._page_moved(response, target) and (", "if True and ("),
    "any method": (LIVE, "response.request.method == 'GET' and ", ""),
    "any status": (LIVE, " and response.status_code == 308", ""),
    "allowed after auth": (LIVE, "                and not getattr(self, '_auth_started', True)\n", ""),
    "missing marker allows": (LIVE, "getattr(self, '_auth_started', True)", "getattr(self, '_auth_started', False)"),
    "any scheme": (LIVE, "                and src.scheme == dst.scheme == 'https'\n", ""),
    "any fidelity host": (LIVE, "src.hostname == dst.hostname == 'digital.fidelity.com'", "src.hostname == dst.hostname"),
    "target path only": (LIVE, "(src.path, dst.path) == _LOGIN_PAGE_MOVE", "dst.path == _LOGIN_PAGE_MOVE[1]"),
    "query ignored": (LIVE, " and src.query == dst.query)", ")"),
    "auth marker never set": (LIVE, "            self._auth_started = True\n", "            pass\n"),
    "marker set on any host": (LIVE, "if request.url.host == 'ecaap.fidelity.com':", "if True:"),
    "broker starts after auth": (LIVE, "        self._auth_started = False\n", "        self._auth_started = True\n"),
}
def run():
    return subprocess.run([sys.executable, "-B", "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True).returncode
def main():
    originals = {path: path.read_bytes() for path in (LIVE,)}; results = {}
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
