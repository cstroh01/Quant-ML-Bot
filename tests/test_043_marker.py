"""T030 / AC-7: one ASCII-escaped synthetic label, compared exactly."""
from pathlib import Path

import pytest

import context  # noqa: F401
from trial_runner import SYNTHETIC_LABEL, current_ledger

REPO = Path(__file__).resolve().parents[1]


def test_defining_line_is_ascii_escaped():
    lines = [line for line in (REPO / "scripts/trial_runner.py").read_bytes().splitlines()
             if line.startswith(b"SYNTHETIC_LABEL =")]
    assert len(lines) == 1
    assert lines[0].isascii() and b"\\u2014" in lines[0], lines[0]
    assert SYNTHETIC_LABEL == "EXAMPLE — NOT A RESULT"


@pytest.mark.parametrize("relative", ["tests/conftest.py", "tests/spec033_support.py"])
def test_consumers_import_the_one_constant(relative):
    source = (REPO / relative).read_text(encoding="utf-8")
    assert "from trial_runner import SYNTHETIC_LABEL" in source
    assert "NOT A RESULT\"" not in source and "NOT A RESULT'" not in source


def context_root(tmp_path, monkeypatch, payload: bytes):
    (tmp_path / "synthetic-context.json").write_bytes(payload)
    monkeypatch.setenv("SPEC033_SYNTHETIC_ROOT", str(tmp_path))


def test_exact_label_selects_synthetic_ledger(tmp_path, monkeypatch):
    context_root(tmp_path, monkeypatch, SYNTHETIC_LABEL.encode("utf-8"))
    ledger = current_ledger()
    assert ledger.synthetic and ledger.root.is_relative_to(tmp_path)


@pytest.mark.parametrize("payload", [
    "EXAMPLE � NOT A RESULT".encode("utf-8"),
    b"EXAMPLE \x97 NOT A RESULT",
], ids=["U+FFFD", "cp1252-0x97"])
def test_corrupted_label_is_refused(tmp_path, monkeypatch, payload):
    context_root(tmp_path, monkeypatch, payload)
    with pytest.raises(ValueError):
        current_ledger()
