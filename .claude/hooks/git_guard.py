"""PreToolUse hook: refuse any shell command that would run Git in a local session.

Guarantee: for a Bash or PowerShell tool call whose command, after unwrapping
common shells and launchers, invokes a ``git`` executable anywhere in a command
chain, this hook denies the call. Unparseable input is denied (fail closed).

Constitution Rule 10: local agents run no Git, including read-only commands.
No environment variable grants an exception here; lane identity cannot be
established from inside an agent-controlled session. Register this hook only
in machine-local settings (``.claude/settings.local.json``), never in the
tracked ``settings.json``, so the cloud lane's own authorized Git is untouched.

Limitation: this is a workflow check, not a sandbox. A program that invokes Git
indirectly (a Python ``subprocess`` call, a script file) is not detected.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from typing import Iterable

GUARDED_TOOLS = {"Bash", "PowerShell"}
MAX_DEPTH = 6

# Separators that start a new simple command in sh, cmd and PowerShell.
_SPLIT = re.compile(r"\|\||&&|[;|&\n\r]|\$\(|`|\(|\)|\{|\}")

# Launchers whose remaining arguments are themselves a command.
_PREFIX_LAUNCHERS = {
    "sudo", "env", "command", "exec", "nohup", "time", "nice", "xargs",
    "builtin", "doas", "stdbuf", "timeout", "start", "call", "&", ".",
    "start-process", "invoke-command", "watch",
    # Shell keywords that precede a command in a compound statement.
    "if", "then", "else", "elif", "do", "while", "until", "!",
}
# Shells whose -c / /c / -Command argument is a command string.
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "cmd", "powershell", "pwsh"}
_SHELL_CMD_FLAGS = {"-c", "/c", "/k", "/r", "-command", "-c:", "-encodedcommand", "-ec"}
_EVAL = {"eval", "iex", "invoke-expression"}

_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_GIT_WORD = re.compile(r"(?i)(?:^|[\s;&|(`'\"\\/=])git(?:\.exe|\.cmd)?(?=$|[\s;&|)`'\"])")


def _basename(token: str) -> str:
    """Lower-cased executable name with quotes, path and Windows suffix removed."""
    token = token.strip().strip("'\"").replace("\\", "/")
    name = token.rsplit("/", 1)[-1].lower()
    for suffix in (".exe", ".cmd", ".bat", ".com"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


def _is_git(name: str) -> bool:
    return name == "git" or name.startswith("git-")


def _tokenizations(segment: str) -> list[list[str]]:
    """Both POSIX and non-POSIX splits; Windows paths survive only the latter."""
    out = []
    for posix in (True, False):
        try:
            out.append(shlex.split(segment, posix=posix))
        except ValueError:
            continue
    return out


def _segments(command: str) -> Iterable[str]:
    for part in _SPLIT.split(command):
        part = part.strip()
        if part:
            yield part


def invokes_git(command: str, depth: int = 0) -> bool:
    """Return True if ``command`` would run Git, or cannot be parsed safely."""
    if depth > MAX_DEPTH:
        return True
    for segment in _segments(command):
        splits = _tokenizations(segment)
        if not splits:
            if _GIT_WORD.search(segment):
                return True
            continue
        if any(_tokens_invoke_git(toks, depth) for toks in splits):
            return True
    return False


def _tokens_invoke_git(toks: list[str], depth: int) -> bool:
    i = 0
    while i < len(toks):
        tok = toks[i]
        if _ASSIGN.match(tok) and i + 1 < len(toks):
            i += 1
            continue
        name = _basename(tok)
        if not name:
            i += 1
            continue
        if _is_git(name):
            return True
        if name in _EVAL:
            return invokes_git(" ".join(toks[i + 1:]), depth + 1)
        if name in _SHELLS:
            rest = toks[i + 1:]
            for j, arg in enumerate(rest):
                if arg.lower() in _SHELL_CMD_FLAGS:
                    return invokes_git(" ".join(rest[j + 1:]), depth + 1)
            # A shell with no command string runs a script or stdin: allow
            # the shell itself, but still inspect any following words.
            i += 1
            continue
        if name in _PREFIX_LAUNCHERS:
            # Launcher options may take operands (`sudo -u root`, `env -u VAR`,
            # `timeout -s KILL 5`), so the wrapped command can start at any later
            # word. Fail closed: deny if Git starts at ANY later position.
            if any(_tokens_invoke_git(toks[j:], depth + 1) for j in range(i + 1, len(toks))):
                return True
            return False
        return False
    return False


def decide(payload: object) -> tuple[str, str]:
    """Return ("allow" | "deny", reason) for one PreToolUse payload."""
    if not isinstance(payload, dict):
        return "deny", "git_guard: hook input is not a JSON object"
    tool = payload.get("tool_name")
    if tool not in GUARDED_TOOLS:
        return "allow", ""
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return "deny", "git_guard: shell tool call has no command string"
    if invokes_git(command):
        return "deny", (
            "Rule 10: local agents run no Git, including read-only commands. "
            "Camden runs version control in GitKraken. Read .git/HEAD or refs "
            "files directly if you need repository state."
        )
    return "allow", ""


def main(stdin: str) -> tuple[int, str, str]:
    """Return (exit code, stdout, stderr). Stdout carries only hook JSON."""
    try:
        payload = json.loads(stdin)
    except (json.JSONDecodeError, TypeError):
        return 2, "", "git_guard: invalid hook input; refusing (fail closed)"
    decision, reason = decide(payload)
    if decision == "allow":
        return 0, "", ""
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    return 0, json.dumps(out), ""


if __name__ == "__main__":
    code, out, err = main(sys.stdin.read())
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    sys.exit(code)
