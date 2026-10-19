"""Q138: pin validation treats Git LF/CRLF as equivalent and rejects changed code."""
import base64
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


def run_guard(tmp_path, monkeypatch, local_newline, git_newline, *, changed=False, extra=False, mixed=False, substitute_blob=False):
    sources = {
        "scripts/allocation_policy.py": b"POLICY_ID='061-b7-ew-v1'\n",
        "scripts/mode_config.py": b"MAX_LIVE_BUDGET_USD = 200.0\n",
        "scripts/ops_runner.py": b"# --preview\n",
        "exec/fidelity_live.py": b"# reviewed source\n# second line\n",
    }
    entries = []
    remote_bodies = {}
    for name, body in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        git_body = body.replace(b"\n", git_newline)
        if mixed and name == "exec/fidelity_live.py":
            git_body = b"# reviewed source\r\n# second line\n"
        local_body = git_body if local_newline == b"mixed" else body.replace(b"\n", local_newline)
        path.write_bytes(local_body)
        digest = blob_sha(git_body)
        remote_bodies[digest] = (git_body, name)
        entries.append({"path": name, "type": "blob", "sha": digest})
    if changed:
        (tmp_path / "exec/fidelity_live.py").write_bytes(b"# unreviewed source\n")
    if extra:
        (tmp_path / "scripts/unreviewed.py").write_bytes(b"# extra\n")

    def api(command, **kwargs):
        assert command[:2] == ["gh", "api"]
        if "/git/blobs/" in command[2]:
            raw, name = remote_bodies[command[2].rsplit("/", 1)[1]]
            if substitute_blob:
                raw = (tmp_path / name).read_bytes()
            result = {"encoding": "base64", "content": base64.b64encode(raw).decode()}
        else:
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


@pytest.mark.parametrize("local_newline", [b"mixed", b"\n", b"\r\n"])
def test_reviewed_mixed_git_blob_accepts_only_newline_equivalence(tmp_path, monkeypatch, local_newline):
    run_guard(tmp_path, monkeypatch, local_newline, b"\n", mixed=True)


def test_wrong_blob_cannot_replace_reviewed_content(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as error:
        run_guard(tmp_path, monkeypatch, b"\n", b"\n", changed=True, substitute_blob=True)
    assert error.value.code == 2


@pytest.mark.parametrize("marker,substitute", [("BLOB_IDENTITY", True), ("NEWLINE_ONLY", False)])
def test_mixed_blob_safety_checks_have_semantic_red_proofs(tmp_path, monkeypatch, marker, substitute):
    def oracle():
        path = tmp_path / str(len(list(tmp_path.iterdir())))
        path.mkdir()
        try:
            run_guard(path, monkeypatch, b"\n", b"\n", changed=True,
                      substitute_blob=substitute)
        except SystemExit as error:
            assert error.code == 2
            return
        raise AssertionError("unreviewed code accepted")
    oracle()
    target = next(line for line in GUARD.splitlines() if "# " + marker in line)
    replacement = target[:len(target) - len(target.lstrip())] + "assert True"
    mutant = GUARD.replace(target, replacement)
    module = sys.modules[__name__]
    with monkeypatch.context() as edit:
        edit.setattr(module, "GUARD", mutant)
        with pytest.raises(AssertionError, match="unreviewed code accepted"):
            oracle()
