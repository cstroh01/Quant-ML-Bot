"""Kill the spec 020 mutant that stamps prices without bundle validation."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
TEST_RELATIVE = Path("tests/test_020_unadjusted_price_data.py")

ORIGINAL = """    bundle = _validate_manifest_bundle(Path(manifest_path))
    result = _merge_actions_for_execution(bundle.prices, bundle.corporate_actions)
"""

MUTANT = """    # MUTANT: trust filenames in JSON and stamp without validating the bundle.
    unsafe_manifest, unsafe_manifest_payload = _read_manifest_document(Path(manifest_path))
    unsafe_root = Path(manifest_path).parent
    unsafe_prices = pd.read_csv(unsafe_root / str(unsafe_manifest[\"data_file\"]), parse_dates=[\"Date\"])
    unsafe_actions = pd.read_csv(
        unsafe_root / str(unsafe_manifest[\"corporate_actions_file\"]),
        parse_dates=[\"Date\", \"Dividend_Pay_Date\"],
    )
    bundle = _ValidatedUnadjustedBundle(
        manifest=unsafe_manifest,
        manifest_path=Path(manifest_path).resolve(),
        manifest_sha256=_sha256_bytes(unsafe_manifest_payload),
        prices=unsafe_prices,
        corporate_actions=unsafe_actions,
    )
    result = _merge_actions_for_execution(bundle.prices, bundle.corporate_actions)
"""


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", "-m", "pytest", str(TEST_RELATIVE)],
        cwd=root,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copytree(REPO / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        target_test = root / TEST_RELATIVE
        target_test.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / TEST_RELATIVE, target_test)

        control = run(root)
        if control.returncode:
            print("CONTROL FAILED")
            print(control.stdout)
            print(control.stderr)
            return 1

        module = root / "scripts/data.py"
        source = module.read_text(encoding="utf-8")
        if source.count(ORIGINAL) != 1:
            print(f"MUTATION SETUP FAILED: target occurred {source.count(ORIGINAL)} times")
            return 1
        module.write_text(source.replace(ORIGINAL, MUTANT), encoding="utf-8")
        mutant = run(root)
        if mutant.returncode == 0:
            print("SURVIVED: loader stamped an unvalidated bundle and all tests passed")
            return 1

        combined = mutant.stdout + mutant.stderr
        if "test_tampered_price_file_fails_hash_check" not in combined:
            print("KILLED FOR THE WRONG REASON")
            print(combined)
            return 1
        print("KILLED: unvalidated-stamp mutant failed the tampered-file oracle")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
