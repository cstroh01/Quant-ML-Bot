"""Rule 12 driver for 052 F01: listing-gated activity and fail-closed eligibility must each go red."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "scripts" / "asset_registry.py"
orig = p.read_text()
muts = {
    "any fact activates": ('state.setdefault(fact.instrument_id, {"active": False})', 'state.setdefault(fact.instrument_id, {"active": True})'),
    "quote age unchecked": ('    if quote.quoted_at.tzinfo is None or not (0 <= (now - quote.quoted_at).total_seconds() <= max_quote_age_seconds):',
                            '    if quote.quoted_at.tzinfo is None:'),
    "future quote accepted": ("not (0 <= (now - quote.quoted_at)", "not (-1e9 <= (now - quote.quoted_at)"),
    "NaN spread passes": ("    if not _finite(quote.spread_bps):\n        reasons.append(\"spread_unknown\")\n    elif", "    if"),
    "NaN adv passes": ("    if not _finite(quote.adv_shares):\n        reasons.append(\"adv_unknown\")\n    elif", "    if"),
    "NaN minimum passes": ("    if not _finite(quote.min_notional_usd):\n        reasons.append(\"broker_minimum_unknown\")\n    elif", "    if"),
    "invalid order passes": ('        reasons.append("order_invalid")\n        return reasons', "        pass"),
    "NaN close passes": ("    if not _finite(last) or last < limits.min_price:", "    if last < limits.min_price:"),
    "non-finite volume skipped": ("bool(dollar.map(_finite).all())", "bool(dollar.notna().all())"),
    "negative volume skipped": ('bool((window["Volume"] >= 0).all())', "True"),
    "NaN participation cap": ("        if not (_finite(self.max_participation) and 0 < self.max_participation <= 1):", "        if False:"),
    "NaN spread limit": ("            if not (_finite(value) and value >= 0):", "            if False:"),
}
killed = 0
for name, (a, b) in muts.items():
    assert orig.count(a) == 1, name
    p.write_text(orig.replace(a, b))
    r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_052_registry.py", "tests/test_052_membership.py",
                        "tests/test_052_eligibility.py", "tests/test_052_acceptance.py", "-q", "-p", "no:cacheprovider"],
                       capture_output=True, cwd=ROOT)
    ok = r.returncode != 0
    killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
p.write_text(orig)
print(f"{killed}/{len(muts)} killed")
sys.exit(0 if killed == len(muts) else 1)
