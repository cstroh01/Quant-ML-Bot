"""Rule 12 driver for spec 033 T037: every named DSR input and convention against a hand oracle.

Run: python tests/mutation/run_033_t037_mutants.py

Each mutant edits ONE site in an isolated copy (spec 043 D-4 helper). A kill counts only when the
JUnit report shows a FAILURE (never an error) in the T037 test whose assertion message carries the
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
ORACLE = "tests/test_033_dsr.py::test_t037_named_dsr_inputs_and_conventions"
SB = "scripts/selection_bias.py"
# (name, file, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("observation count off by one", SB, "observations=len(x),", "observations=len(x)-1,", "T037 OBSERVATIONS"),
    ("Sharpe annualized before DSR", SB, "sharpes = x.mean(axis=0)/scales",
     'sharpes = x.mean(axis=0)/scales*math.sqrt(matrix["family"]["risk_free"]["days_per_year"])', "T037 SHARPE"),
    ("population (ddof=0) Sharpe scale", SB, "scales = x.std(axis=0, ddof=1)", "scales = x.std(axis=0, ddof=0)", "T037 SHARPE"),
    ("selected column ignored", SB, "j = matrix[\"columns\"].index(selected_trial)", "j = 0", "T037 SHARPE"),
    ("Sharpe sign dropped", SB, "observed_sharpe=float(sharpes[j])", "observed_sharpe=abs(float(sharpes[j]))", "T037 SHARPE"),
    ("unsigned skew (sqrt b1)", SB, "skewness=float(np.mean(centered**3)/variance**1.5)",
     "skewness=abs(float(np.mean(centered**3)/variance**1.5))", "T037 SKEW"),
    ("unsigned skew in the PSR denominator", SB, "denominator = 1-skewness*observed_sharpe",
     "denominator = 1-abs(skewness)*observed_sharpe", "T037 Z"),
    ("skew standardized by sample variance", SB, "variance = np.mean(centered**2)",
     "variance = np.var(x[:, j], ddof=1)", "T037 SKEW"),
    ("excess kurtosis passed as Pearson", SB, "pearson_kurtosis=float(np.mean(centered**4)/variance**2)",
     "pearson_kurtosis=float(np.mean(centered**4)/variance**2)-3", "T037 KURTOSIS"),
    ("population (ddof=0) trial dispersion", SB, "trial_sharpe_std=float(sharpes.std(ddof=1))",
     "trial_sharpe_std=float(sharpes.std(ddof=0))", "T037 DISPERSION"),
    ("matrix columns used as N", SB, "ddof=1)), n_current=n_current)", 'ddof=1)), n_current=len(matrix["columns"]))',
     "T037 NCURRENT"),
    ("e dropped from second quantile", SB, "norm.ppf(1-1/(n_current*math.e))", "norm.ppf(1-1/n_current)", "T037 BENCHMARK"),
    ("sqrt(T) instead of sqrt(T-1)", SB, "math.sqrt(observations-1)/", "math.sqrt(observations)/", "T037 Z"),
    ("density instead of CDF", SB, "float(norm.cdf(z))", "float(norm.pdf(z))", "T037 CDF"),
    ("simple-rate risk-free", SB, '-math.log1p(rf["annual_rate"])/rf["days_per_year"]',
     '-rf["annual_rate"]/rf["days_per_year"]', "T037 RISKFREE"),
    ("repository days-per-year, not the family's", SB, '-math.log1p(rf["annual_rate"])/rf["days_per_year"]',
     "-math.log1p(rf[\"annual_rate\"])/TRADING_DAYS_PER_YEAR", "T037 RISKFREE"),
)
ASSERTION = ("AssertionError", "assert ")


def tree_digest(relatives) -> dict[str, str]:
    paths = [p for r in relatives for p in ([ROOT / r] if (ROOT / r).is_file() else sorted((ROOT / r).rglob("*")))]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def run_copy(mutant) -> list[tuple[str, str, str]]:
    """(kind, test name, message) for every failure/error; raises if nothing was collected."""
    with tempfile.TemporaryDirectory(prefix="t037-") as temporary:
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
