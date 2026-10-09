"""Rule 12 driver for 056 F01: calendar, finiteness and period-key guards must each go red."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "scripts" / "data_sources.py"
orig = p.read_text()
muts = {
    "non-session label accepted": ("            if trading_days(label, label) != [label]:", "            if False:"),
    "unclosed session accepted": ("            if datetime.combine(label, _time(16, 0), tzinfo=_NY) > self.fetched_at:", "            if False:"),
    "future calendar date accepted": ("        elif label > self.fetched_at.astimezone(_NY).date():", "        elif False:"),
    "unknown calendar accepted": ("        if self.label_calendar not in LABEL_CALENDARS:", "        if False:"),
    "NaN tolerance accepted": ("    if not (math.isfinite(tolerance_bps) and tolerance_bps >= 0):", "    if False:"),
    "infinite closes agree": ("col.map(math.isfinite) & (col > 0)", "col.notna()"),
    "facts keyed on end only": ('        key = (item["end"], item.get("start") or "")', '        key = (item["end"], "")'),
    "stray payload label accepted": ("            if stray:", "            if False:"),
}
killed = 0
for name, (a, b) in muts.items():
    assert orig.count(a) == 1, name
    p.write_text(orig.replace(a, b))
    r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_056_manifest.py", "tests/test_056_checks.py",
                        "tests/test_056_adapters_prices.py", "-q", "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
    ok = r.returncode != 0
    killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
p.write_text(orig)
print(f"{killed}/{len(muts)} killed")
sys.exit(0 if killed == len(muts) else 1)
