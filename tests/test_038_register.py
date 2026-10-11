"""Spec 038 T020 (FR-001, FR-003): the limitations register matches SCOPE-V1 §6.

The parity test parses the real `docs/SCOPE-V1.md` by its section boundaries, so
neither side can drift alone. Witness strings let the T022 driver count a kill.
"""
from pathlib import Path

from context import SCRIPTS_DIR
import disclosure

SCOPE = SCRIPTS_DIR.parent / "docs" / "SCOPE-V1.md"


def scope_register(text: str) -> list[str]:
    """Bullets of the `## 6.` section only, emphasis and wrapping removed."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("## 6. ")]
    if len(starts) != 1:
        raise RuntimeError(f"expected one '## 6.' heading, found {len(starts)}")
    items: list[str] = []
    for line in lines[starts[0] + 1:]:
        if line.startswith("## "):
            break
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif line.startswith("  ") and line.strip() and items:
            items[-1] += " " + line.strip()
    if not items:
        raise RuntimeError("SCOPE §6 has no bullets")
    return [item.replace("**", "") for item in items]


def test_register_matches_scope_section_6_both_directions():
    scope = scope_register(SCOPE.read_text(encoding="utf-8"))
    ours = list(disclosure.LIMITATIONS)
    missing = [item for item in scope if item not in ours]
    extra = [item for item in ours if item not in scope]
    assert ours == scope, (
        f"038 REGISTER drift: missing from LIMITATIONS {missing}; not in SCOPE §6 {extra}; order must match")


def test_parser_reads_only_section_6():
    text = "## 5. Gate\n\n- not a limitation\n\n## 6. Register\n\n- **A.** one\n  two\n- B.\n\n## 7. Cut\n\n- also not\n"
    assert scope_register(text) == ["A. one two", "B."], "038 REGISTER parser read outside §6"


def test_sharpe_status_wording_is_fr003():
    assert disclosure.SHARPE_STATUS == "provisional, undeflated (Rule 15)", "038 REGISTER sharpe_status"
