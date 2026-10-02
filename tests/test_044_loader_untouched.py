"""Spec 044 FR-010: the loader gains exactly one line, the `volume_basis` attr; nothing else changes.

The fingerprint is the SHA-256 of `ast.unparse` of `load_unadjusted_market_data`
with its docstring removed and, if present, FR-010's single permitted
`"volume_basis": manifest.get("volume_basis")` entry removed. Formatting, comments
and line endings (data.py mixes CRLF and LF) do not move it; any other change does.
"""
import ast
import hashlib
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "scripts" / "data.py"
LOADER = "load_unadjusted_market_data"
# Pre-044 loader, main 3e52db9, computed 2026-10-02 (identical on CPython 3.11, 3.12, 3.13).
PINNED = "899e067325df0693b4577668d7bd29ac176164982525b7039ef5823b52ae2fb0"
ALLOWED = ast.unparse(ast.parse('manifest.get("volume_basis")', mode="eval").body)
ANCHOR = '"dividends_bound": 0 if basis is None else int(basis.eq("bound").sum()),'
ONE_LINE = ANCHOR + '\n            "volume_basis": manifest.get("volume_basis"),'


def loader_fingerprint(source: str) -> str:
    """Fingerprint the loader minus FR-010's one permitted entry; refuse any other volume_basis use."""
    found = [node for node in ast.parse(source).body
             if isinstance(node, ast.FunctionDef) and node.name == LOADER]
    assert len(found) == 1, f"expected exactly one {LOADER}, found {len(found)}"
    function = found[0]
    first = function.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        function.body = function.body[1:]
    entries = 0
    for node in ast.walk(function):
        if not isinstance(node, ast.Dict):
            continue
        pairs = list(zip(node.keys, node.values))
        hits = [value for key, value in pairs if isinstance(key, ast.Constant) and key.value == "volume_basis"]
        for value in hits:
            assert ast.unparse(value) == ALLOWED, (
                f"FR-010: volume_basis must be {ALLOWED} (None for a pre-044 manifest); got {ast.unparse(value)}")
        entries += len(hits)
        kept = [(key, value) for key, value in pairs
                if not (isinstance(key, ast.Constant) and key.value == "volume_basis")]
        node.keys, node.values = [key for key, _ in kept], [value for _, value in kept]
    assert entries <= 1, f"FR-010 permits one volume_basis entry; found {entries}"
    text = ast.unparse(function)
    assert "volume_basis" not in text, f"FR-010: volume_basis used outside the one permitted entry:\n{text}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source() -> str:
    text = DATA.read_text(encoding="utf-8")
    assert text.count(ANCHOR) == 1, "anchor line for the planted cases moved; update ANCHOR"
    return text


def test_loader_matches_pre_044_fingerprint():
    assert loader_fingerprint(source()) == PINNED, (
        f"{LOADER} changed beyond FR-010's single volume_basis entry; "
        "a loader change needs its own spec amendment and a new pin")


def test_the_one_permitted_line_keeps_the_fingerprint():
    """Green control: exactly FR-010's line, added where T051 adds it."""
    assert loader_fingerprint(source().replace(ANCHOR, ONE_LINE)) == PINNED


@pytest.mark.parametrize("old, new, message", [
    # Strict read: a pre-044 manifest has no key, so loading it raises KeyError.
    (ANCHOR, ANCHOR + '\n"volume_basis": manifest["volume_basis"],', "must be"),
    # The attr is added twice (copy-paste); a dict literal keeps only the last.
    (ANCHOR, ONE_LINE + '\n"volume_basis": manifest.get("volume_basis"),', "permits one"),
    # A validation branch on the new field: FR-010 says no validation change.
    ("    return result\n\n\nclass UnadjustedDataUnavailable",
     '    if result.attrs["volume_basis"] not in (None, "provider_unverified"):\n'
     '        raise ValueError("volume_basis")\n'
     "    return result\n\n\nclass UnadjustedDataUnavailable", "outside the one permitted"),
    # The permitted line lands, and a neighbouring argument is dropped in the same edit.
    ("bundle.prices, bundle.corporate_actions, pay_date_policy=bundle.pay_date_policy,",
     "bundle.prices, bundle.corporate_actions,", None),
], ids=["strict-read", "added-twice", "validation-branch", "neighbour-dropped"])
def test_planted_loader_changes_are_refused(old, new, message):
    text = source().replace(ANCHOR, ONE_LINE) if message is None else source()
    text = text.replace("\r\n", "\n")
    assert text.count(old) == 1, f"planted-defect anchor not found once: {old!r}"
    planted = text.replace(old, new)
    if message is None:
        assert loader_fingerprint(planted) != PINNED
    else:
        with pytest.raises(AssertionError, match=message):
            loader_fingerprint(planted)
