"""057 T014 Rule 12: each planted defect in the D-4a pyotp lock line must fail the real tests.

Usage: python tests/mutation/run_057_t014_mutants.py. Restores every source byte for byte.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "requirements-fidelity-host.txt"
PREVIEW = ROOT / "ops/workflows/fidelity-preview.yml"
LIVE = ROOT / "ops/workflows/fidelity-live.yml"
SDK = ROOT / "exec/fidelity_sdk.py"
TESTS = ["tests/test_057_t014_totp_dependency.py"]
PIN = "pyotp==2.10.0 --hash=sha256:1df2f6a1bcc3bb0716172a5215ddc2f8c7c7fd26a13df9927d52e1746934836c\n"
MUTANTS = {
    "pyotp line removed (main)": (LOCK, PIN, ""),
    "pyotp commented out": (LOCK, PIN, "# " + PIN),
    "pyotp hash changed": (LOCK, "1df2f6a1bcc3bb07", "1df2f6a1bcc3bb08"),
    "pyotp hash dropped": (LOCK, " --hash=sha256:1df2f6a1bcc3bb0716172a5215ddc2f8c7c7fd26a13df9927d52e1746934836c", ""),
    "pyotp other version": (LOCK, "pyotp==2.10.0", "pyotp==2.9.0"),
    "pyotp unpinned range": (LOCK, "pyotp==2.10.0", "pyotp>=2.10.0"),
    "pyotp Windows-only marker": (LOCK, "pyotp==2.10.0 --hash", "pyotp==2.10.0 ; sys_platform == \"win32\" --hash"),
    "pyotp listed twice": (LOCK, PIN, PIN + PIN),
    "second pyotp spelling": (LOCK, PIN, PIN + "PyOTP==2.9.0 --hash=sha256:" + "0" * 64 + "\n"),
    "another line unhashed": (LOCK, "idna==3.20 --hash=sha256:ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c", "idna==3.20"),
    "preview drops require-hashes": (PREVIEW, "pip install --require-hashes --only-binary=:all: -r qmb/requirements-fidelity-host.txt",
                                     "pip install --only-binary=:all: -r qmb/requirements-fidelity-host.txt"),
    "live drops require-hashes": (LIVE, "pip install --require-hashes --only-binary=:all: -r qmb/requirements-fidelity-host.txt",
                                  "pip install --only-binary=:all: -r qmb/requirements-fidelity-host.txt"),
    "preview allows sdists": (PREVIEW, "--require-hashes --only-binary=:all: -r qmb/requirements-fidelity-host.txt",
                              "--require-hashes -r qmb/requirements-fidelity-host.txt"),
    "audited session changed": (SDK, "'auth/session': '57f707dd", "'auth/session': '57f707de"),
}
def run():
    return subprocess.run([sys.executable, "-B", "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True).returncode
def main():
    originals = {path: path.read_bytes() for path in (LOCK, PREVIEW, LIVE, SDK)}; results = {}
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
