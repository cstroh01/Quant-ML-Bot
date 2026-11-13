"""Rule 12 driver for 053 fold-local tests: the two mutants Codex found surviving must now die."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "scripts" / "model_registry.py"
orig = p.read_text()
orig_bytes = p.read_bytes()
muts = {
    "fit on train+test": ("pipeline.fit(train[feature_cols], train[label_col])",
                          "both = pd.concat([train, test]); pipeline.fit(both[feature_cols], both[label_col])"),
    "embargo shortened 2->1": ("label_horizon=label_horizon, embargo_bars=embargo_bars):",
                               "label_horizon=label_horizon, embargo_bars=embargo_bars - 1):"),
    "scaler outside fold": ("pipeline.fit(train[feature_cols], train[label_col])",
                            "pipeline.fit(train[feature_cols], train[label_col]); pipeline[0].fit(data[feature_cols])"),
}
for name, (a, _b) in muts.items():  # every anchor is checked before any mutant is written
    assert orig.count(a) == 1, name
killed = 0
try:
    for name, (a, b) in muts.items():
        p.write_text(orig.replace(a, b))
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_053_fold_local.py", "-q",
                            "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
        ok = r.returncode != 0
        killed += ok
        print(("KILLED  " if ok else "SURVIVED"), name)
finally:
    p.write_bytes(orig_bytes)  # a crash never leaves a mutant; exact bytes: write_text leaves CRLF on Windows, which item 1 counts as a change
print(f"{killed}/{len(muts)} killed")
sys.exit(0 if killed == len(muts) else 1)
