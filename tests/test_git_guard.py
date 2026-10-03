"""Tests for the local PreToolUse hook .claude/hooks/git_guard.py (Rule 10).

No test launches Git or a real pytest child: the guard is a pure string
classifier, and the Stop hook's runner is injected.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_hook_{name}", HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


guard = _load("git_guard")


def _payload(command: str, tool: str = "Bash") -> str:
    return json.dumps({"tool_name": tool, "tool_input": {"command": command}})


def _decision(command: str, tool: str = "Bash") -> str:
    code, out, _ = guard.main(_payload(command, tool))
    assert code == 0
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "allow"


# ---------------------------------------------------------------- git guard

ALLOWED = [
    "python -m pytest tests",
    "ls -la .git/refs/heads",
    "cat .git/HEAD",
    'grep -n "git" CLAUDE.md',
    'echo "use git in GitKraken"',
    "python scripts/digit_check.py",
    "gitkraken_notes.txt",
    "Get-Content .gitignore",
]

REFUSED = [
    "git status",
    "git log --oneline -5",
    "GIT_DIR=.git git rev-parse HEAD",
    "/usr/bin/git diff",
    '"C:\\Program Files\\Git\\cmd\\git.exe" status',
    r"C:\Git\bin\git.exe status",
    "& 'C:\\Program Files\\Git\\bin\\git.exe' log",
    "echo hi && git push",
    "echo hi; git commit -m x",
    "true || git fetch",
    "ls | git hash-object --stdin",
    "echo $(git rev-parse HEAD)",
    "echo `git branch`",
    "bash -c 'git status'",
    'sh -c "cd x && git add ."',
    "cmd /c git status",
    "cmd.exe /C git status",
    'powershell -Command "git status"',
    "pwsh -c 'git log'",
    "sudo -u root git status",
    "env -u FOO git status",
    "timeout -s KILL 5 git push",
    "sudo -u root bash -c 'git status'",
    "nice -n 5 env -u X git log",
    "bash -lc 'git status'",
    "bash -xc 'git status'",
    "pwsh -NoProfile -Command 'git log'",
    ">/tmp/out git status",
    "2>/dev/null git status",
    "2> /dev/null git status",
    "< in.txt git hash-object --stdin",
    "env -i git status",
    "sudo git clean -fdx",
    "timeout 5 git fetch",
    "xargs git add",
    "eval git status",
    "iex 'git status'",
    "if true; then git status; fi",
    "git-upload-pack .",
    "GIT.EXE status",
]


@pytest.mark.parametrize("command", ALLOWED)
def test_safe_commands_are_allowed(command):
    assert _decision(command) == "allow"


@pytest.mark.parametrize("command", REFUSED)
def test_git_invocations_are_refused(command):
    assert _decision(command) == "deny"


@pytest.mark.parametrize("command", ["git status", "cmd /c git log"])
def test_powershell_tool_is_guarded(command):
    assert _decision(command, tool="PowerShell") == "deny"


def test_non_shell_tools_pass_through():
    code, out, _ = guard.main(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "git"}}))
    assert (code, out) == (0, "")


@pytest.mark.parametrize("env", ["GITHUB_ACTIONS", "CLAUDE_CODE_REMOTE", "CLAUDE_LANE"])
def test_lane_environment_spoofing_grants_nothing(monkeypatch, env):
    monkeypatch.setenv(env, "true")
    assert _decision("git push -u origin claude/x") == "deny"


@pytest.mark.parametrize("raw", ["", "not json", "[1, 2]", "null"])
def test_invalid_input_fails_closed(raw):
    code, out, err = guard.main(raw)
    if code == 0:
        assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"
    else:
        assert code == 2 and out == "" and err


def test_missing_command_fails_closed():
    code, out, _ = guard.main(json.dumps({"tool_name": "Bash", "tool_input": {}}))
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_stdout_is_pure_json_on_deny():
    _, out, err = guard.main(_payload("git status"))
    assert err == "" and json.loads(out)["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


def test_rule12_planted_defect_goes_red(monkeypatch):
    """Planted defect: shell unwrapping removed. The wrapper case must flip."""
    assert guard.invokes_git("bash -c 'git status'")
    monkeypatch.setattr(guard, "_SHELLS", set())
    assert not guard.invokes_git("bash -c 'git status'"), "mutant not caught by wrapper case"


def test_rule12_planted_path_defect_goes_red(monkeypatch):
    """Planted defect: executable compared without stripping its path."""
    monkeypatch.setattr(guard, "_basename", lambda t: t.strip("'\"").lower())
    assert not guard.invokes_git("/usr/bin/git diff")
