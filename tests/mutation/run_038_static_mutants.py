"""EXAMPLE — NOT A RESULT. 038 T063 and T061 D2a/D2b/D2c only: mutate document copies against their actual guards."""
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
    d2a = guard.D2a_documents()
    original.update({p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in d2a})
    if guard.D2a_violations(d2a):
        raise RuntimeError("D2a clean control failed")
    for path, (_, figure) in guard.D2A_ROWS.items():
        for defect in ("restored-figure", "missing-count-pointer"):
            copy = dict(d2a)
            if defect == "restored-figure":
                copy[path] = copy[path].replace(guard.STRUCK, figure, 1)
                expected = f"{path}: D2a unsupported historical figure restored"
            else:
                copy[path] = copy[path].replace(guard.D2A_COUNT_POINTER, "history-unavailable")
                expected = f"{path}: D2a strike or count/archive context missing"
            results.append(dict(path=path, mutant=defect,
                                killed=expected in guard.D2a_violations(copy)))
    d2b = guard.D2b_documents()
    original.update({p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in d2b})
    if guard.D2b_violations(d2b):
        raise RuntimeError("D2b clean control failed")
    for path in guard.D2B_PATHS:
        for defect in ("restored-figure", "missing-count-pointer"):
            copy = dict(d2b)
            if defect == "restored-figure":
                copy[path] = copy[path].replace(guard.STRUCK, "0.998", 1)
                expected = f"{path}: D2b unsupported historical figure restored"
            else:
                copy[path] = copy[path].replace(guard.D2A_COUNT_POINTER, "history-unavailable")
                expected = f"{path}: D2b strike or count/archive context missing"
            results.append(dict(path=path, mutant="D2b-" + defect,
                                killed=expected in guard.D2b_violations(copy)))
    for path, restored in guard.D2B_VERIFICATION_MUTANTS:
        copy = dict(d2b)
        copy[path] += "\n" + restored + "\n"
        expected = f"{path}: D2b unsupported historical figure restored"
        results.append(dict(path=path, mutant="D2b-old-verification-count",
                            killed=expected in guard.D2b_violations(copy)))
    d2c = guard.D2c_documents()
    original.update({p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in d2c})
    if guard.D2c_violations(d2c):
        raise RuntimeError("D2c clean control failed")
    for path, (_, figure) in guard.D2C_ROWS.items():
        for defect in ("restored-figure", "missing-count-pointer"):
            copy = dict(d2c)
            if defect == "restored-figure":
                if path.endswith("/tasks.md"):
                    before, selected = copy[path].split("- [X] T031 ", 1)
                    copy[path] = before + "- [X] T031 " + selected.replace(guard.STRUCK, figure, 1)
                else:
                    copy[path] = copy[path].replace(guard.STRUCK, figure, 1)
                expected = f"{path}: D2c unsupported historical figure restored"
            else:
                copy[path] = copy[path].replace(guard.D2A_COUNT_POINTER, "history-unavailable")
                expected = f"{path}: D2c strike or count/archive context missing"
            results.append(dict(path=path, mutant="D2c-" + defect,
                                killed=expected in guard.D2c_violations(copy)))
    unchanged = all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == sha for p, sha in original.items())
    print(json.dumps(dict(control="PASS", results=results, mutants=len(results),
                         killed=sum(r["killed"] for r in results), documents_unchanged=unchanged), indent=2))
    return 0 if unchanged and all(r["killed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
