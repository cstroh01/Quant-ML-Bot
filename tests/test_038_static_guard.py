"""Spec 038 static guard (T065, queue Q57): absent-source (X) figures stay struck (D-5 = (b)).

D-5 (b): X figures are struck even in audit and history documents; Q covers only
figures with a committed source; a struck line keeps its historical context and a
source pointer. This guard reads the committed documents and fails if a struck
figure returns, if a strike loses its pointer, or if a committed-source (Q) figure
beside it was struck by mistake.
"""

from pathlib import Path

import pytest

from context import SCRIPTS_DIR

ROOT = SCRIPTS_DIR.parent
COMPARISON = "data/cache/feature_set_comparison.json"
STRUCK = "[struck]"

# path -> (X figures that must be absent, pointer that must be present, Q figures that must stay)
X_FIGURES = {
    "docs/audit-2026-09-12/AUDIT.md": (
        ("113 outer folds", "2,359 paired", "50.784%", "52.989%", "51.547%", "51.802%",
         "0.01219", "0.43293", "0.03135", "0.26327", "0.0003560020", "0.0003557017",
         "0.0003628177", "0.0003611051", "0.0844%"),
        f"their only source, `{COMPARISON}`, is absent", ("53.540%",)),
    "docs/audit-2026-09-12/REMEDIATION_PLAN.md": (
        ("52.99%", "0.0844%", "113 folds", "2,359 pairs"),
        f"only source, `{COMPARISON}`, is absent", ("53.54%",)),
    "docs/audit-2026-09-12/remediation-map.html": (
        ("52.99%", "0.0844%", "0.0003560", "0.0003557", "113 folds", "2,359"),
        f"only source, {COMPARISON}, is absent", ("53.54%",)),
    "NIGHT_RUN_SUMMARY.md": (
        ("**3.24**", "**0.38**", "**69%**", "Peak overlap 4.48", "4.44 around", "3.71 around",
         "2,451 sized sessions", "3.5 ms", "52.99%", "1.65×"),
        "scratchpad outside the repository", ()),
}


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def violations(documents: dict[str, str]) -> list[str]:
    """Every rule broken, as ``path: reason`` strings; empty when the documents comply."""
    found = []
    for path, (struck, pointer, kept) in X_FIGURES.items():
        body = documents[path]
        found += [f"{path}: X figure {figure!r} restored" for figure in struck if figure in body]
        if STRUCK not in body or pointer not in body:
            found.append(f"{path}: strike without its source pointer")
        found += [f"{path}: committed-source figure {figure!r} struck" for figure in kept
                  if figure not in body]
    return found


def test_no_absent_source_figure_survives_and_every_strike_points_to_its_source():
    assert violations({path: text(path) for path in X_FIGURES}) == []


@pytest.mark.parametrize("path, edit, message", [
    # A tired reviewer reverting one table cell: the figure comes back.
    ("docs/audit-2026-09-12/AUDIT.md", lambda t: t.replace(STRUCK, "52.989%", 1), "X figure '52.989%'"),
    ("NIGHT_RUN_SUMMARY.md", lambda t: t.replace("Half Kelly on a [struck] accuracy", "Half Kelly on 52.99% accuracy"),
     "X figure '52.99%'"),
    # The pointer line deleted, leaving bare [struck] cells.
    ("docs/audit-2026-09-12/REMEDIATION_PLAN.md",
     lambda t: t.replace(f"only source, `{COMPARISON}`, is absent", "source unknown"),
     "strike without its source pointer"),
    # Over-striking: the committed always-up figure removed with its neighbour.
    ("docs/audit-2026-09-12/remediation-map.html", lambda t: t.replace("53.54%", STRUCK),
     "committed-source figure '53.54%' struck"),
], ids=["restored-audit-cell", "restored-kelly-line", "pointer-dropped", "q-figure-struck"])
def test_planted_defects_turn_the_guard_red(path, edit, message):
    """Rule 12: each defect is planted in an in-memory copy, never in the committed file."""
    documents = {p: text(p) for p in X_FIGURES}
    assert violations(documents) == [], "control: the committed documents comply"
    documents[path] = edit(documents[path])
    assert documents[path] != text(path), "the planted edit must change the copy"
    assert any(v.startswith(f"{path}: {message}") for v in violations(documents)), violations(documents)
