"""Spec 038 static guard (T065, queue Q57): absent-source (X) figures stay struck (D-5 = (b)).

D-5 (b): X figures are struck even in audit and history documents; Q covers only
figures with a committed source; a struck line keeps its historical context and a
source pointer. This guard reads the committed documents and fails if a struck
figure returns, if a strike loses its pointer, or if a committed-source (Q) figure
beside it was struck by mistake.
"""

from pathlib import Path
import re

import pytest

from context import SCRIPTS_DIR

ROOT = SCRIPTS_DIR.parent
COMPARISON = "data/cache/feature_set_comparison.json"
STRUCK = "[struck]"

# path -> (X figure patterns that must not match, pointer that must be present, Q figures that must stay).
# Patterns, not literals: a figure must stay struck in every form it is written (bold, rounded,
# inside prose, in a JS string). OVERLAP covers the scratchpad overlap diagnostic everywhere it is quoted.
P_VALUES = r"0\.0122|0\.4329|0\.0313|0\.2633|0\.01219|0\.43293|0\.03135|0\.26327"
OVERLAP = r"(?<![\d.])0\.38(?!\d)|(?<![\d.])69%|(?<![\d.])1\.22(?!\d)"
X_FIGURES = {
    "docs/audit-2026-09-12/AUDIT.md": (
        (r"113 outer folds", r"2,359", r"50\.784", r"52\.989", r"51\.547", r"51\.802", P_VALUES,
         r"0\.000356", r"0\.000362", r"0\.000361", r"0\.0844", OVERLAP),
        f"their only source, `{COMPARISON}`, is absent", ("53.540%",)),
    "docs/audit-2026-09-12/REMEDIATION_PLAN.md": (
        (r"52\.99", r"0\.0844", r"113 folds", r"2,359", P_VALUES, OVERLAP),
        f"only source, `{COMPARISON}`, is absent", ("53.54%",)),
    "docs/audit-2026-09-12/remediation-map.html": (
        (r"52\.99", r"0\.0844", r"0\.000356", r"113 folds", r"2,359", P_VALUES, OVERLAP),
        f"only source, {COMPARISON}, is absent", ("53.54%",)),
    "NIGHT_RUN_SUMMARY.md": (
        (r"3\.24", r"(?<![\d.])4\.48", r"4\.44 around", r"3\.71 around", r"2,451", r"3\.5 ms",
         r"52\.99", r"1\.65×", OVERLAP),
        "scratchpad outside the repository", ()),
}


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def violations(documents: dict[str, str]) -> list[str]:
    """Every rule broken, as ``path: reason`` strings; empty when the documents comply."""
    found = []
    for path, (struck, pointer, kept) in X_FIGURES.items():
        body = documents[path]
        found += [f"{path}: X figure {m.group(0)!r} restored" for pattern in struck
                  for m in [re.search(pattern, body)] if m]
        if STRUCK not in body or pointer not in body:
            found.append(f"{path}: strike without its source pointer")
        found += [f"{path}: committed-source figure {figure!r} struck" for figure in kept
                  if figure not in body]
    return found


def test_no_absent_source_figure_survives_and_every_strike_points_to_its_source():
    assert violations({path: text(path) for path in X_FIGURES}) == []


@pytest.mark.parametrize("path, edit, message", [
    # A tired reviewer reverting one table cell: the figure comes back.
    ("docs/audit-2026-09-12/AUDIT.md", lambda t: t.replace(STRUCK, "52.989%", 1), "X figure '52.989'"),
    ("NIGHT_RUN_SUMMARY.md", lambda t: t.replace("Half Kelly on a [struck] accuracy", "Half Kelly on 52.99% accuracy"),
     "X figure '52.99'"),
    # The pointer line deleted, leaving bare [struck] cells.
    ("docs/audit-2026-09-12/REMEDIATION_PLAN.md",
     lambda t: t.replace(f"only source, `{COMPARISON}`, is absent", "source unknown"),
     "strike without its source pointer"),
    # Over-striking: the committed always-up figure removed with its neighbour.
    ("docs/audit-2026-09-12/remediation-map.html", lambda t: t.replace("53.54%", STRUCK),
     "committed-source figure '53.54%' struck"),
    # The same figure in another form: rounded p-values and unbolded overlap stats in prose.
    ("docs/audit-2026-09-12/remediation-map.html",
     lambda t: t.replace("The saved run says [struck]", "The saved run says 0.0122"), "X figure '0.0122'"),
    ("NIGHT_RUN_SUMMARY.md", lambda t: t.replace("removes a median [struck]", "removes a median 69%"),
     "X figure '69%'"),
], ids=["restored-audit-cell", "restored-kelly-line", "pointer-dropped", "q-figure-struck",
        "rounded-p-value", "unbolded-overlap"])
def test_planted_defects_turn_the_guard_red(path, edit, message):
    """Rule 12: each defect is planted in an in-memory copy, never in the committed file."""
    documents = {p: text(p) for p in X_FIGURES}
    assert violations(documents) == [], "control: the committed documents comply"
    documents[path] = edit(documents[path])
    assert documents[path] != text(path), "the planted edit must change the copy"
    assert any(v.startswith(f"{path}: {message}") for v in violations(documents)), violations(documents)
