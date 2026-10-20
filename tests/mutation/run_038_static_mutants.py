"""EXAMPLE — NOT A RESULT. 038 T063: mutate document copies against the actual guard."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
import test_038_static_guard as guard  # noqa: E402


def main():
    documents = guard.T063_documents()
    original = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in documents}
    problems = guard.T063_violations(documents)
    if problems:
        raise RuntimeError("T063 clean control failed: " + repr(problems))
    results = []
    for path, anchors in guard.T063_ROWS.items():
        for anchor in anchors:
            copy = dict(documents)
            lines = copy[path].splitlines()
            row = next(i for i, line in enumerate(lines) if anchor in line)
            lines[row] = lines[row].replace(guard.EXAMPLE_LABEL, "illustration")
            lines.insert(row, "**" + guard.EXAMPLE_LABEL + "**")
            copy[path] = "\n".join(lines)
            expected = f"{path}: T063 example label missing on numeric line: {anchor}"
            results.append(dict(path=path, anchor=anchor, mutant="label-moved-off-line",
                                killed=expected in guard.T063_violations(copy)))
    for which in (0, 1):
        copy = dict(documents)
        before, after = copy[guard.T063_AUDIT].split("(coverage.json)", 1)
        copy[guard.T063_AUDIT] = (before + "(coverage.csv)" + after if which == 0 else
            before + "(coverage.json)" + after.replace("(coverage.json)", "(coverage.csv)", 1))
        expected = f"{guard.T063_AUDIT}: T063 coverage links must name committed coverage.json"
        results.append(dict(path=guard.T063_AUDIT, mutant="broken-coverage-link-" + str(which),
                            killed=expected in guard.T063_violations(copy)))
    unchanged = all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == sha for p, sha in original.items())
    print(json.dumps(dict(control="PASS", results=results, mutants=len(results),
                         killed=sum(r["killed"] for r in results), documents_unchanged=unchanged), indent=2))
    return 0 if unchanged and all(r["killed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
