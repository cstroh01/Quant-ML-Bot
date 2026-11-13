"""Rule 12 driver for 056 F01: calendar, finiteness and period-key guards must each go red.

The original bytes of scripts/data_sources.py are restored after every mutant (try/finally). Writing
it back as text left CRLF on Windows; eol=lf hides that from version control, but spec 061's
declaration pins the file's SHA-256, so a later driver's clean control failed (2026-11-12).
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "scripts" / "data_sources.py"
orig_bytes = p.read_bytes()
orig = orig_bytes.decode("utf-8").replace("\r\n", "\n")
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
for name, (a, _) in muts.items():  # every anchor is checked before any mutant is written
    assert orig.count(a) == 1, f"{name}: expected one site, found {orig.count(a)}"
killed = 0
try:
    for name, (a, b) in muts.items():
        p.write_bytes(orig.replace(a, b).encode("utf-8"))
        try:
            r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_056_manifest.py", "tests/test_056_checks.py",
                                "tests/test_056_adapters_prices.py", "-q", "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
        finally:
            p.write_bytes(orig_bytes)
        ok = r.returncode != 0
        killed += ok
        print(("KILLED  " if ok else "SURVIVED"), name)
finally:
    p.write_bytes(orig_bytes)
assert p.read_bytes() == orig_bytes, "scripts/data_sources.py not restored"
print(f"{killed}/{len(muts)} killed")
sys.exit(0 if killed == len(muts) else 1)
