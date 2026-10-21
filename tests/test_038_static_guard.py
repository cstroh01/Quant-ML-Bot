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



# T064 / M1b: use the shared register already checked against actual SCOPE §6.
def readme_violations(documents):
    from disclosure import LIMITATIONS
    found = []
    for path, body in documents.items():
        normalized = re.sub(r"\s+", " ", body.replace("**", "")).strip()
        for item in LIMITATIONS:
            if item not in normalized:
                found.append(f"{path}: missing limitation: {item}")
    return found


def test_T064_root_and_web_readmes_carry_the_full_limitations_register():
    documents = {p: text(p) for p in ("README.md", "reports/web/README.md")}
    assert readme_violations(documents) == [], "T064 README REGISTER"


@pytest.mark.parametrize("path", ["README.md", "reports/web/README.md"])
def test_T064_dropped_limitation_is_caught_with_a_clean_control(path):
    from disclosure import LIMITATIONS
    documents = {p: text(p) for p in ("README.md", "reports/web/README.md")}
    assert readme_violations(documents) == [], "T064 clean control"
    missing = LIMITATIONS[2]
    documents[path] = documents[path].replace("- " + missing + "\n", "")
    assert f"{path}: missing limitation: {missing}" in readme_violations(documents), "T064 M1b dropped register item"


# T063 D4: each listed example keeps its label on its actual numeric line.
EXAMPLE_LABEL = "EXAMPLE — NOT A RESULT"
T063_ROWS = {
    "NIGHT_RUN_SUMMARY.md": (
        "Name A at 0.25 beside name B", "one name's confidence moving from 0 to 1e-9"),
    ".specify/specs/017-position-sizing-risk/tasks.md": ("**Matches:** 09-09 halted",),
    ".specify/specs/020-unadjusted-price-data/spec.md": ("**Historical Price Level Assertion**",),
    "docs/audit-2026-09-12/CODEX_LANE_HANDOFF.md": (
        "2026-08-24 through 2026-09-02", "$100 capital, $1 per fill", "fit: fold count 0;",
        "Policy net P&L **-$0.0220**;", "mean **-$0.0248**,"),
    "docs/implementation/spec-033/SPEC_CORRECTION_PROPOSAL.md": (
        "the paper specifies annualized Sharpe 2.5", "trial-Sharpe variance 0.5, 1,250 observations",
        "−3, and Pearson kurtosis 10", "Its N=46 control reports 0.9505.",
        "the moments to normal returns (skewness 0, kurtosis 3)",
        "using N=88 gives 0.910153014744707", "calculation agree. This still fails the unchanged 0.95 threshold",
        "unchanged N=46 control passes.", "change the asserted N=88 DSR target from 0.905"),
}
T063_AUDIT = "docs/audit-2026-09-12/AUDIT.md"


def T063_violations(documents):
    found = []
    for path, anchors in T063_ROWS.items():
        for anchor in anchors:
            rows = [line for line in documents[path].splitlines() if anchor in line]
            if len(rows) != 1:
                found.append(f"{path}: T063 expected one example row: {anchor}")
            elif EXAMPLE_LABEL not in rows[0]:
                found.append(f"{path}: T063 example label missing on numeric line: {anchor}")
    audit = documents[T063_AUDIT]
    if "(coverage.csv)" in audit or audit.count("(coverage.json)") != 2:
        found.append(f"{T063_AUDIT}: T063 coverage links must name committed coverage.json")
    return found


def T063_documents():
    return {p: text(p) for p in (*T063_ROWS, T063_AUDIT)}


@pytest.mark.parametrize("path", list(T063_ROWS))
def test_T063_numeric_example_lines_carry_their_own_label(path):
    documents = T063_documents()
    problems = [p for p in T063_violations(documents) if p.startswith(path + ":")]
    assert problems == [], "T063 SAME-LINE EXAMPLE LABEL: " + repr(problems)


def test_T063_coverage_links_resolve_to_the_committed_inventory():
    documents = T063_documents()
    problems = [p for p in T063_violations(documents) if p.startswith(T063_AUDIT + ":")]
    assert problems == [] and (ROOT / "docs/audit-2026-09-12/coverage.json").is_file(), "T063 COVERAGE LINK"


@pytest.mark.parametrize("path,anchor", [(p, a) for p, anchors in T063_ROWS.items() for a in anchors])
def test_T063_label_moved_off_numeric_line_is_caught(path, anchor):
    documents = T063_documents()
    assert T063_violations(documents) == [], "T063 clean control"
    lines = documents[path].splitlines()
    row = next(i for i, line in enumerate(lines) if anchor in line)
    lines[row] = lines[row].replace(EXAMPLE_LABEL, "illustration")
    lines.insert(row, "**" + EXAMPLE_LABEL + "**")
    documents[path] = "\n".join(lines)
    expected = f"{path}: T063 example label missing on numeric line: {anchor}"
    assert expected in T063_violations(documents), "T063 MOVED-LABEL MUTANT: " + expected


@pytest.mark.parametrize("which", [0, 1])
def test_T063_broken_coverage_link_is_caught(which):
    documents = T063_documents()
    assert T063_violations(documents) == [], "T063 clean control"
    before, after = documents[T063_AUDIT].split("(coverage.json)", 1)
    documents[T063_AUDIT] = (before + "(coverage.csv)" + after if which == 0 else
                             before + "(coverage.json)" + after.replace("(coverage.json)", "(coverage.csv)", 1))
    expected = f"{T063_AUDIT}: T063 coverage links must name committed coverage.json"
    assert expected in T063_violations(documents), "T063 COVERAGE-LINK MUTANT"


# T061 D2a only: historical-count metadata is not recovered returns or result provenance.
D2A_COUNT_POINTER = "docs/trials/backfill/manifest.json"
D2A_ARCHIVE_POINTER = "docs/audit-2026-09-12/AUDIT.md"
D2A_ROWS = {
    ".specify/specs/002-backtest-costs-baselines/spec.md":
        (r"8 trades|50% win rate|\$33", "8 trades, 50% win rate, ~$33 total P&L"),
    ".specify/specs/002-backtest-costs-baselines/plan.md":
        (r"8 trades|50% win rate|\$33", "8 trades, 50% win rate, ~$33 P&L"),
    ".specify/specs/006-embargo-window-semantics/spec.md":
        (r"0\.519|0\.542|47\.25|126\.71|74\.26|19\.00", "accuracy 0.519 against 0.542; P&L $47.25"),
    ".specify/specs/009-selectable-target/spec.md":
        (r"0\.519|0\.542", "AAPL accuracy 0.519 against 0.542"),
    ".specify/specs/012-cost-aware-entry-rule/spec.md":
        (r"0\.0122|0\.0313|0\.433|0\.263", "p = 0.0122 / 0.0313 / 0.433 / 0.263"),
}


def D2a_violations(documents):
    found = []
    for path, (pattern, _) in D2A_ROWS.items():
        body = documents[path]
        if re.search(pattern, body):
            found.append(f"{path}: D2a unsupported historical figure restored")
        if (STRUCK not in body or D2A_COUNT_POINTER not in body or D2A_ARCHIVE_POINTER not in body
                or "counts only, not returns" not in body or "not results provenance" not in body):
            found.append(f"{path}: D2a strike or count/archive context missing")
    return found


def D2a_documents():
    return {p: text(p) for p in D2A_ROWS}


@pytest.mark.parametrize("path", list(D2A_ROWS))
def test_D2a_actual_closed_spec_figures_are_struck_with_honest_pointers(path):
    problems = [v for v in D2a_violations(D2a_documents()) if v.startswith(path + ":")]
    assert problems == [], "D2a STATIC DISPOSITION: " + repr(problems)


@pytest.mark.parametrize("path", list(D2A_ROWS))
def test_D2a_restored_figure_is_caught_by_the_actual_guard(path):
    """EXAMPLE — NOT A RESULT. One old unsupported figure restored in a copy."""
    documents = D2a_documents()
    assert D2a_violations(documents) == [], "D2a clean control"
    documents[path] = documents[path].replace(STRUCK, D2A_ROWS[path][1], 1)
    expected = f"{path}: D2a unsupported historical figure restored"
    assert expected in D2a_violations(documents), "D2a RESTORED-FIGURE MUTANT"


@pytest.mark.parametrize("path", list(D2A_ROWS))
def test_D2a_dropped_historical_count_pointer_is_caught(path):
    """EXAMPLE — NOT A RESULT. A copied strike loses its count-record pointer."""
    documents = D2a_documents()
    assert D2a_violations(documents) == [], "D2a clean control"
    documents[path] = documents[path].replace(D2A_COUNT_POINTER, "history-unavailable")
    expected = f"{path}: D2a strike or count/archive context missing"
    assert expected in D2a_violations(documents), "D2a POINTER-DROPPED MUTANT"


# T061 D2b: only the three spec014 documents; normative bounds are untouched.
D2B_PATHS = tuple(".specify/specs/014-scale-free-features/" + p for p in ("spec.md", "plan.md", "tasks.md"))
D2B_FIGURES = (r"0\.998|36\.2\b|\b268\b|0\.865|0\.325|~0\.53|36\.17|2\.15|268\.31|1\.60|0\.527|"
               r"0\.5078|0\.5299|0\.00035600|0\.00035570|0\.00036282|0\.00036111|"
               r"0\.5155|0\.5180|0\.0122|0\.0313|0\.2633|0\.4329|improved 9x|Screening bar MET")


def D2b_documents():
    return {p: text(p) for p in D2B_PATHS}


def D2b_violations(documents):
    problems = []
    for path in D2B_PATHS:
        body = documents[path]
        old_counts = re.search(r"(?m)^  \| [1-6] \| .* \| \d+ \|\s*$|45 new tests|256\s*→\s*301|\b2 failures\b", body)
        if re.search(D2B_FIGURES, body) or old_counts:
            problems.append(f"{path}: D2b unsupported historical figure restored")
        if (STRUCK not in body or D2A_COUNT_POINTER not in body or D2A_ARCHIVE_POINTER not in body
                or "counts only, not returns" not in body or "not results provenance" not in body):
            problems.append(f"{path}: D2b strike or count/archive context missing")
    return problems


@pytest.mark.parametrize("path", D2B_PATHS)
def test_D2b_actual_closed_spec_figures_are_struck_with_honest_pointers(path):
    problems = [v for v in D2b_violations(D2b_documents()) if v.startswith(path + ":")]
    assert problems == [], "D2b STATIC DISPOSITION: " + repr(problems)


@pytest.mark.parametrize("path", D2B_PATHS)
def test_D2b_restored_figure_is_caught_by_actual_guard(path):
    """EXAMPLE — NOT A RESULT. Restore an old correlation to a copied document."""
    documents = D2b_documents()
    assert D2b_violations(documents) == [], "D2b clean control"
    documents[path] = documents[path].replace(STRUCK, "0.998", 1)
    expected = f"{path}: D2b unsupported historical figure restored"
    assert expected in D2b_violations(documents), "D2b RESTORED-FIGURE MUTANT"


@pytest.mark.parametrize("path", D2B_PATHS)
def test_D2b_dropped_count_pointer_is_caught(path):
    """EXAMPLE — NOT A RESULT. Remove a copied historical-count link."""
    documents = D2b_documents()
    assert D2b_violations(documents) == [], "D2b clean control"
    documents[path] = documents[path].replace(D2A_COUNT_POINTER, "history-unavailable")
    expected = f"{path}: D2b strike or count/archive context missing"
    assert expected in D2b_violations(documents), "D2b POINTER-DROPPED MUTANT"


D2B_VERIFICATION_MUTANTS = (
    (D2B_PATHS[0], "  | 1 | drop the `- 1` from `SMA_Spread` | 2 |"),
    (D2B_PATHS[1], "| 5 — Tests | 45 new tests; the suite goes 256 → 301, all passing. |"),
    (D2B_PATHS[2], "Historical mutation check: 2 failures."),
)


@pytest.mark.parametrize("path,restored", D2B_VERIFICATION_MUTANTS)
def test_D2b_restored_historical_verification_counts_are_caught(path, restored):
    """EXAMPLE — NOT A RESULT. Restore one historical verification-result row."""
    documents = D2b_documents()
    assert D2b_violations(documents) == [], "D2b clean control"
    documents[path] += "\n" + restored + "\n"
    expected = f"{path}: D2b unsupported historical figure restored"
    assert expected in D2b_violations(documents), "D2b OLD-COUNT MUTANT"


# T061 D2c: historical figures only; risk limits and synthetic halt output stay intact.
D2C_ROWS = {
    ".specify/specs/017-position-sizing-risk/spec.md":
        (r"52\.99%|181 bps|0\.0598|0\.0181|3\.3×|1\.65×|21-day vol 10%–58%", "52.99%"),
    ".specify/specs/017-position-sizing-risk/research.md":
        (r"0\.5299|0\.0181|3\.30×|1\.65×|0\.83×|165%", "0.5299"),
    ".specify/specs/017-position-sizing-risk/tasks.md":
        (r"2,514|2,451|2\.20|3\.24|4\.02|1\.22|0\.27|0\.38|0\.57|69%|75%|4\.48|4\.44|3\.71|0 sessions|0\.15|0\.218|0\.177|0\.117|0\.115|0\.099|0\.73|~1\.5", "mean overlap 3.24"),
}


def D2c_documents():
    return {p: text(p) for p in D2C_ROWS}


def D2c_violations(documents):
    found = []
    for path, (pattern, _) in D2C_ROWS.items():
        body = documents[path]
        checked = body
        if path.endswith("/tasks.md"):
            checked = body.split("- [X] T031 ", 1)[1].split("- [X] T032 ", 1)[0]
        if re.search(pattern, checked):
            found.append(f"{path}: D2c unsupported historical figure restored")
        if (STRUCK not in body or D2A_COUNT_POINTER not in body or D2A_ARCHIVE_POINTER not in body
                or "counts only, not returns" not in body or "not results provenance" not in body):
            found.append(f"{path}: D2c strike or count/archive context missing")
    return found


@pytest.mark.parametrize("path", list(D2C_ROWS))
def test_D2c_actual_registered_figures_are_struck(path):
    problems = [v for v in D2c_violations(D2c_documents()) if v.startswith(path + ":")]
    assert problems == [], "D2c STATIC DISPOSITION: " + repr(problems)


@pytest.mark.parametrize("path", list(D2C_ROWS))
def test_D2c_restored_figure_is_caught(path):
    """EXAMPLE — NOT A RESULT. Restore an unsupported sizing figure in a copy."""
    documents = D2c_documents()
    assert D2c_violations(documents) == [], "D2c clean control"
    old = documents[path]
    if path.endswith("/tasks.md"):
        before, selected = old.split("- [X] T031 ", 1)
        documents[path] = before + "- [X] T031 " + selected.replace(STRUCK, D2C_ROWS[path][1], 1)
    else:
        documents[path] = old.replace(STRUCK, D2C_ROWS[path][1], 1)
    expected = f"{path}: D2c unsupported historical figure restored"
    assert expected in D2c_violations(documents), "D2c RESTORED-FIGURE MUTANT"


@pytest.mark.parametrize("path", list(D2C_ROWS))
def test_D2c_dropped_count_pointer_is_caught(path):
    """EXAMPLE — NOT A RESULT. Remove the history-only context from a copy."""
    documents = D2c_documents()
    assert D2c_violations(documents) == [], "D2c clean control"
    documents[path] = documents[path].replace(D2A_COUNT_POINTER, "history-unavailable")
    expected = f"{path}: D2c strike or count/archive context missing"
    assert expected in D2c_violations(documents), "D2c POINTER-DROPPED MUTANT"
