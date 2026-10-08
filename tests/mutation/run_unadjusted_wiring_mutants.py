"""Kill spec 036 wiring mutants in isolated copies of the source tree.

Run: python tests/mutation/run_unadjusted_wiring_mutants.py
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
COPIED = (
    "scripts", "reports/__init__.py", "reports/api", "tests/conftest.py", "tests/ledger_copy_support.py",
    "tests/context.py", "tests/api_fixtures.py", "tests/unadjusted_fixtures.py",
    "tests/test_unadjusted_caller_wiring.py", "tests/test_reports_api.py",
)
WIRING = "tests/test_unadjusted_caller_wiring.py::"
API = "tests/test_reports_api.py::TestReportsApi::"

# (name, source path, exact old fragment, mutant fragment, focused oracle)
MUTANTS = (
    ("adjusted fallback", "scripts/ma_crossover_backtest.py",
     "    nominal = load_unadjusted_for_ticker(ticker, cache_dir, manifest_path=args.manifest)\n",
     "    try:\n        nominal = load_unadjusted_for_ticker(ticker, cache_dir, manifest_path=args.manifest)\n"
     "    except UnadjustedDataUnavailable:\n        from data import download_market_data\n"
     "        nominal = download_market_data([ticker])\n",
     WIRING + "test_cli_unavailable_has_no_download_output_or_trial"),
    ("ambiguous selection", "scripts/data.py",
     "    if len(matches) > 1:\n        raise UnadjustedDataUnavailable(canonical, \"ambiguous\", \", \".join(map(str, matches)))",
     "    if len(matches) > 1:\n        return matches[-1]",
     WIRING + "test_resolver_ambiguous_lists_both_paths_sorted"),
    ("broad ticker prefix", "scripts/data.py",
     "pattern.fullmatch(path.name)", "path.name.startswith(canonical)",
     WIRING + "test_resolver_exact_stem_and_lowercase"),
    ("nominal split signal", "scripts/ma_crossover_backtest.py",
     '    signal_input["Close"] = research["Research_Close"]',
     '    signal_input["Close"] = nominal["Close"]',
     WIRING + "test_signal_uses_causal_research_close_across_split"),
    ("trial before load", "scripts/ma_crossover_backtest.py",
     "    nominal = load_unadjusted_for_ticker(ticker, cache_dir, manifest_path=args.manifest)\n",
     "    with research_attempt(research_config(\"scripts/ma_crossover_backtest.py:run_backtest\", locals()), role=\"candidate\"):\n"
     "        nominal = load_unadjusted_for_ticker(ticker, cache_dir, manifest_path=args.manifest)\n",
     WIRING + "test_cli_unavailable_has_no_download_output_or_trial"),
    ("missing 503 mapping", "reports/api/routes/backtest.py",
     "    except UnadjustedDataUnavailable as error:",
     "    except TypeError as error:",
     API + "test_tearsheet_503_missing"),
    ("baseline funding omitted", "scripts/ma_crossover_backtest.py",
     "            **costs,\n            **account,\n        )",
     "            **costs,\n            starting_capital=1.0, liquidate=LIQUIDATE_AT_END,\n        )",
     API + "test_backtest_tearsheet"),
)


def source_digest() -> str:
    digest = hashlib.sha256()
    for relative in sorted({row[1] for row in MUTANTS}):
        digest.update((ROOT / relative).read_bytes())
    return digest.hexdigest()


def run_copy(mutant: tuple | None, oracle: str) -> tuple[int, set[str]]:
    with tempfile.TemporaryDirectory(prefix="spec036-mutant-") as temporary:
        root = Path(temporary)
        for relative in COPIED:
            source, target = ROOT / relative, root / relative
            if source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        if mutant is not None:
            path = root / mutant[1]
            content = path.read_text(encoding="utf-8")
            if content.count(mutant[2]) != 1:
                raise RuntimeError(f"{mutant[0]}: expected one mutation site, found {content.count(mutant[2])}")
            path.write_text(content.replace(mutant[2], mutant[3]), encoding="utf-8")
        xml = root / "result.xml"
        result = subprocess.run(
            [sys.executable, "-B", "-m", "pytest", oracle, "-q", f"--junitxml={xml}"],
            cwd=root, capture_output=True, text=True, errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=False,
        )
        if not xml.exists():
            raise RuntimeError(f"{oracle}: pytest produced no JUnit file: {result.stderr[-1000:]}")
        failed = {
            f"{case.get('classname')}.{case.get('name')}"
            for case in ElementTree.parse(xml).findall(".//testcase")
            if case.find("failure") is not None or case.find("error") is not None
        }
        return result.returncode, failed


def main() -> int:
    before = source_digest()
    controls = {row[4] for row in MUTANTS}
    for oracle in sorted(controls):
        code, failures = run_copy(None, oracle)
        if code or failures:
            print(f"CONTROL RED: {oracle}: exit={code}, failures={sorted(failures)}")
            return 1
    print(f"Control: {len(controls)} focused tests passed")
    survivors = []
    for mutant in MUTANTS:
        code, failures = run_copy(mutant, mutant[4])
        killed = code != 0 and bool(failures)
        print(f"{mutant[0]}: {'KILLED' if killed else 'SURVIVED'}; failures={sorted(failures)}")
        if not killed:
            survivors.append(mutant[0])
    after = source_digest()
    print(f"Source SHA-256: {'identical' if before == after else 'CHANGED'} ({before[:16]} -> {after[:16]})")
    return 1 if survivors or before != after else 0


if __name__ == "__main__":
    raise SystemExit(main())
