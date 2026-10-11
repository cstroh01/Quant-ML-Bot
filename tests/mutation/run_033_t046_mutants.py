"""Rule 12 driver for spec 033 T046: reported DSR and HAC t-stat inputs verified independently.

Run: python tests/mutation/run_033_t046_mutants.py

Each mutant edits ONE site in an isolated copy (spec 043 D-4 helper). A kill counts only when the
JUnit report shows a FAILURE (never an error) in the T046 test whose assertion message carries the
named witness. An unchanged copy must pass with exactly one collected test, every mutated file must
compile, and the production sources and `docs/trials/` bytes must be identical before and after.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree

from driver_support import copy_into, guarded, run_pytest

ROOT = Path(__file__).resolve().parents[2]
COPIED = ("scripts", "tests/context.py", "tests/spec033_support.py", "tests/test_033_dsr.py")
ORACLE = "tests/test_033_dsr.py::test_t046_reported_dsr_and_t_stat_inputs_verified_independently"
SB = "scripts/selection_bias.py"
# (name, file, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("reported Sharpe rounded, value from the exact one", SB, "inputs = dict(observed_sharpe=observed_sharpe,",
     "inputs = dict(observed_sharpe=round(observed_sharpe, 4),", "T046 INPUTS"),
    ("simple-rate risk-free in the matrix", SB, '-math.log1p(rf["annual_rate"])/rf["days_per_year"]',
     '-rf["annual_rate"]/rf["days_per_year"]', "T046 INPUTS"),
    ("trial Sharpes reported sorted, not by column", SB, '"trial_sharpes": sharpes.tolist()',
     '"trial_sharpes": sorted(sharpes.tolist())', "T046 SHARPES"),
    ("best column reported, not the selected one", SB, 'j = matrix["columns"].index(selected_trial)',
     "j = int(np.argmax(sharpes))", "T046 INPUTS"),
    ("PSR denominator reported as its square root", SB, '"psr_denominator": denominator', '"psr_denominator": math.sqrt(denominator)',
     "T046 DSR"),
    ("matrix hash recomputed from values only", SB, '"matrix_hash": matrix["matrix_hash"]',
     '"matrix_hash": digest(matrix["values"])', "T046 PROVENANCE"),
    ("density instead of CDF", SB, "float(norm.cdf(z))", "float(norm.pdf(z))", "T046 DSR"),
    ("simple-rate risk-free in the t-stat", SB, "-math.log1p(annual_risk_free)/days_per_year",
     "-annual_risk_free/days_per_year", "T046 TSTAT"),
    ("t-stat reports the raw mean", SB, '"mean_excess_log_return": float(excess.mean())',
     '"mean_excess_log_return": float(np.mean(returns))', "T046 TSTAT"),
    ("t-stat uses the lag floor, not the requested lag", SB, "mean_log_return_se(excess, lags=lags,",
     "mean_log_return_se(excess, lags=horizon-1,", "T046 TSTAT"),
    ("t-stat records the lag floor", SB, '"reason": None, "hac_lags": lags,', '"reason": None, "hac_lags": horizon-1,',
     "T046 TSTAT"),
    ("t-stat uses the repository day count", SB, "-math.log1p(annual_risk_free)/days_per_year",
     "-math.log1p(annual_risk_free)/TRADING_DAYS_PER_YEAR", "T046 TSTAT"),
)
ASSERTION = ("AssertionError", "assert ")


def tree_digest(relatives) -> dict[str, str]:
    paths = [p for r in relatives for p in ([ROOT / r] if (ROOT / r).is_file() else sorted((ROOT / r).rglob("*")))]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def run_copy(mutant) -> list[tuple[str, str, str]]:
    """(kind, test name, message) for every failure/error; raises if nothing was collected."""
    with tempfile.TemporaryDirectory(prefix="t046-") as temporary:
        root = copy_into(Path(temporary), COPIED)
        if mutant is not None:
            path = root / mutant[1]
            text = path.read_text(encoding="utf-8")
            assert text.count(mutant[2]) == 1, f"{mutant[0]}: expected one site, found {text.count(mutant[2])}"
            path.write_text(text.replace(mutant[2], mutant[3]), encoding="utf-8")
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        xml = root / "r.xml"
        result = run_pytest(root, ORACLE, "-q", "-p", "no:cacheprovider", f"--junitxml={xml}")
        assert xml.exists(), f"no JUnit report: {result.stderr[-800:]}"
        suite = ElementTree.parse(xml).getroot().iter("testsuite")
        assert sum(int(s.get("tests", 0)) for s in suite) == 1, f"collection: {result.stdout[-800:]}"
        cases = ElementTree.parse(xml).getroot().iter("testcase")
        return [(kind, case.get("name", ""), el.get("message") or "")
                for case in cases for kind in ("failure", "error") for el in case.findall(kind)]


def main() -> int:
    sources = tree_digest(sorted({m[1] for m in MUTANTS}) + ["tests/test_033_dsr.py"])
    ledger = tree_digest(["docs/trials"])
    with guarded():
        control = run_copy(None)
        assert not control, f"unchanged copy is not green: {control}"
        print("CONTROL green (unchanged copied modules, 1 collected)")
        killed = 0
        for mutant in MUTANTS:
            results = run_copy(mutant)
            ok = not any(k == "error" for k, _, _ in results) and any(
                k == "failure" and name == ORACLE.rsplit("::", 1)[1] and msg.startswith(ASSERTION) and mutant[4] in msg
                for k, name, msg in results)
            killed += ok
            print("KILLED  " if ok else "SURVIVED", f"{mutant[0]} -> {mutant[4]}")
    assert tree_digest(sorted({m[1] for m in MUTANTS}) + ["tests/test_033_dsr.py"]) == sources, "source changed"
    assert tree_digest(["docs/trials"]) == ledger, "docs/trials changed"
    print(f"{killed}/{len(MUTANTS)} killed; sources and docs/trials ({len(ledger)} files) byte-identical")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
