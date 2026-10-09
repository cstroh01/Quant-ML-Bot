"""Rule 12 driver for 051 F01: each fail-closed guard removed must turn a test red."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "scripts" / "mode_config.py"
orig = p.read_text()
muts = {
    "state_dir compared raw": ('    if field == "state_dir":\n        return _canonical_dir(key)', '    if False:\n        return key'),
    "absolute state_dir allowed": ('        if raw_dir.startswith("/") or re.match(r"[A-Za-z]:", raw_dir) or _canonical_dir(raw_dir).startswith(".."):',
                                   '        if False:'),
    "nesting allowed": ("if key.startswith(other + \"/\") or other.startswith(key + \"/\"):", "if False:"),
    "namespace case-sensitive": ("return str(key).strip().casefold()", "return key"),
    "infinite budget": ("math.isfinite(self.bot_budget_usd) and ", ""),
    "negative deployed": ("if deployed_today_usd < 0 or min_notional_usd < 0:", "if False:"),
    "NaN day state": ("        if not math.isfinite(value):\n            raise ValueError(f\"{name} must be finite\")\n    if deployed",
                      "        pass\n    if deployed"),
    "NaN equity": ('    for name, value in (("bot_owned_value", bot_owned_value), ("bot_cash", bot_cash)):\n        if not math.isfinite(value):',
                   '    for name, value in (("bot_owned_value", bot_owned_value), ("bot_cash", bot_cash)):\n        if False:'),
    "NaN target liquidates": ("        if not math.isfinite(float(target)):", "        if False:"),
    "NaN portfolio fails open": ("        return sorted(proposed_buy_qty)", "        return []"),
    "NaN price fails open": ("            refused.append(ticker)\n            continue", "            continue"),
}
killed = 0
for name, (a, b) in muts.items():
    assert orig.count(a) == 1, name
    p.write_text(orig.replace(a, b))
    r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_051_finite_inputs.py", "-q",
                        "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
    ok = r.returncode != 0
    killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
p.write_text(orig)
print(f"{killed}/{len(muts)} killed")
sys.exit(0 if killed == len(muts) else 1)
