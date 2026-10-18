"""Q138: pin validation treats Git LF/CRLF as equivalent and rejects changed code."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
GUARD = (ROOT / "scripts/fidelity_preview_day.ps1").read_text().split("$PinGuard=@'\n", 1)[1].split("\n'@", 1)[0]


def blob_sha(body):
    return hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()


def run_guard(tmp_path, monkeypatch, local_newline, git_newline, *, changed=False, extra=False):
    sources = {
        "scripts/allocation_policy.py": b"POLICY_ID='061-b7-ew-v1'\n",
        "scripts/mode_config.py": b"MAX_LIVE_BUDGET_USD = 200.0\n",
        "scripts/ops_runner.py": b"# --preview\n",
        "exec/fidelity_live.py": b"# reviewed source\n# second line\n",
    }
    entries = []
    for name, body in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body.replace(b"\n", local_newline))
        entries.append({"path": name, "type": "blob", "sha": blob_sha(body.replace(b"\n", git_newline))})
    if changed:
        (tmp_path / "exec/fidelity_live.py").write_bytes(b"# unreviewed source\n")
    if extra:
        (tmp_path / "scripts/unreviewed.py").write_bytes(b"# extra\n")

    def api(command, **kwargs):
        assert command[:2] == ["gh", "api"]
        result = {"tree": entries, "truncated": False} if "/git/trees/" in command[2] else {"status": "identical"}
        return SimpleNamespace(stdout=json.dumps(result))

    monkeypatch.setattr(subprocess, "run", api)
    monkeypatch.setattr(sys, "argv", ["guard", str(tmp_path), "a" * 40])
    monkeypatch.setattr(sys, "version_info", (3, 12))
    monkeypatch.setattr(sys, "path", sys.path.copy())
    for name, attribute, value in [("allocation_policy", "POLICY_ID", "061-b7-ew-v1"),
                                   ("mode_config", "MAX_LIVE_BUDGET_USD", 200.0)]:
        module = ModuleType(name)
        setattr(module, attribute, value)
        monkeypatch.setitem(sys.modules, name, module)
    exec(compile(GUARD, "<Q138 PinGuard>", "exec"), {})


@pytest.mark.parametrize("local_newline", [b"\n", b"\r\n"])
@pytest.mark.parametrize("git_newline", [b"\n", b"\r\n"])
def test_reviewed_pin_accepts_equivalent_line_endings(tmp_path, monkeypatch, local_newline, git_newline):
    run_guard(tmp_path, monkeypatch, local_newline, git_newline)


@pytest.mark.parametrize("mutation", ["changed", "extra"])
def test_reviewed_pin_refuses_unreviewed_source(tmp_path, monkeypatch, mutation):
    with pytest.raises(SystemExit) as error:
        run_guard(tmp_path, monkeypatch, b"\r\n", b"\r\n", **{mutation: True})
    assert error.value.code == 2
