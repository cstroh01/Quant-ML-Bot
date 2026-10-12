"""Rule 12 driver for spec 046 U2 (T007/T008): Rule 13 costs in the harness and metrics reconciliation.

Run: python tests/mutation/run_046_u2_mutants.py. One-site mutants of `scripts/backtest_harness.py` and
`scripts/metrics.py` in an isolated copy; a kill is a FAILURE (never an error) in the named test whose
message carries the witness. Same control and byte-identity checks as run_058_t007_mutants.py.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree

from driver_support import copy_into, guarded, run_pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS, METRICS = "scripts/backtest_harness.py", "scripts/metrics.py"
TEST = "tests/test_046_cost_wiring.py"
COPIED = ("scripts", "tests/context.py", TEST)
COLLECTED = 16
CUTOFF = "past = history.iloc[:i]\n"
# (name, file, exact old fragment, mutant fragment, failing test, witness in its message)
MUTANTS = (
    ("M5 flat 5 bps executed under the model label", HARNESS, "return est.total, dict(",
     "return 5 / 10000., dict(", "test_buy_and_sell_charge_the_model_on_the_right_cutoff_and_quantity",
     "046 U2 buy fraction"),
    ("M8 sell pays the buy sign", HARNESS, "fill = quote * (1 - fraction)", "fill = quote * (1 + fraction)",
     "test_buy_and_sell_charge_the_model_on_the_right_cutoff_and_quantity", "046 U2 sell cash"),
    ("M8 exit charged on the entry quantity", HARNESS, "fraction, detail = cost(i, quantity)",
     "fraction, detail = cost(i, entry[4])", "test_exit_quantity_is_the_held_post_split_quantity",
     "046 U2 held exit quantity"),
    ("M8 metrics reconcile via flat bps", METRICS, "entry_price = event.Price * (1 + fill_fraction(event, event.Quantity))",
     "entry_price = event.Price * (1 + slippage_bps / 10000)",
     "test_metrics_reconcile_recorded_model_costs_and_refuse_a_forged_fraction", "046 U2 reconcile"),
    ("metrics accept a forged fraction", METRICS, "if not ok or abs(", "if False and abs(",
     "test_metrics_reconcile_recorded_model_costs_and_refuse_a_forged_fraction", ""),
    ("metrics accept any flat rate", METRICS, "ok = f == slippage_bps / 10000", "ok = True",
     "test_metrics_hold_flat_runs_to_their_declared_rate", ""),
    ("refused order falls back to a zero-cost fill", HARNESS, "                fraction = None\n",
     "                fraction, detail = 0., None\n",
     "test_warmup_and_split_window_refuse_the_order_without_a_flat_fallback", "046 U2 refusal"),
    ("affordability ignores the modeled cost", HARNESS, "fill = row.Open * (1 + (fraction or 0.))",
     "fill = row.Open", "test_affordability_includes_the_modeled_cost", "046 U2 affordability"),
    ("estimate sees the fill session (Rule 1)", HARNESS,
     CUTOFF + '        past.attrs["volume_basis"] = prices.attrs["volume_basis"]\n'
     "        est = estimate_fill_cost(past, as_of=dates.iloc[i - 1],",
     CUTOFF.replace("[:i]", "[:i + 1]") + '        past.attrs["volume_basis"] = prices.attrs["volume_basis"]\n'
     "        est = estimate_fill_cost(past, as_of=dates.iloc[i],",
     "test_future_bars_do_not_move_a_fill_fraction", "046 U2 future bars"),
    ("liquidation uses the same-session bar", HARNESS, 'sell(len(prices) - 1, row.Date, "close"',
     'sell(len(prices), row.Date, "close"',
     "test_terminal_liquidation_uses_the_preceding_session_estimate", "046 U2 liquidation"),
    ("split on the fill session not refused", HARNESS, "if i < len(prices) and prices.Split.iloc[i] != 1:", "if False:",
     "test_a_split_on_the_fill_session_refuses", "046 U2 fill-session split"),
    ("refused liquidation not flagged", HARNESS, "liquidation_refused = bool(quantity and liquidate)",
     "liquidation_refused = False", "test_a_refused_liquidation_is_flagged_and_still_reconciles",
     "046 U2 refused liquidation"),
    ("slippage dollars checked at a fixed tolerance", METRICS, "> RECONCILIATION_TOLERANCE * max(1., notional)",
     "> RECONCILIATION_TOLERANCE", "test_large_notional_fills_still_reconcile[flat]", "046 U2 large notional"),
    ("flat diagnostic stamped with the model label", HARNESS,
     "cost_label=MODEL if cost_config is not None else FLAT_LABEL,", "cost_label=MODEL,",
     "test_model_and_flat_runs_are_labelled_and_never_mixed", "046 U2 labels"),
)
FAILURE = ("AssertionError", "assert ", "Failed:")


def tree_digest(relatives) -> dict[str, str]:
    paths = [p for r in relatives for p in ([ROOT / r] if (ROOT / r).is_file() else sorted((ROOT / r).rglob("*")))]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def run_copy(mutant) -> list[tuple[str, str, str]]:
    """(kind, test name, message) for every failure/error; raises unless COLLECTED were collected."""
    with tempfile.TemporaryDirectory(prefix="u2-") as temporary:
        root = copy_into(Path(temporary), COPIED)
        if mutant is not None:
            path = root / mutant[1]
            text = path.read_text(encoding="utf-8")
            assert text.count(mutant[2]) == 1, f"{mutant[0]}: expected one site, found {text.count(mutant[2])}"
            path.write_text(text.replace(mutant[2], mutant[3]), encoding="utf-8")
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        xml = root / "r.xml"
        result = run_pytest(root, TEST, "-q", "-p", "no:cacheprovider", f"--junitxml={xml}")
        assert xml.exists(), f"no JUnit report: {result.stderr[-800:]}"
        suite = ElementTree.parse(xml).getroot().iter("testsuite")
        assert sum(int(s.get("tests", 0)) for s in suite) == COLLECTED, f"collection: {result.stdout[-800:]}"
        cases = ElementTree.parse(xml).getroot().iter("testcase")
        return [(kind, case.get("name", ""), el.get("message") or "")
                for case in cases for kind in ("failure", "error") for el in case.findall(kind)]


def main() -> int:
    watched = [HARNESS, METRICS, TEST]
    sources = tree_digest(watched)
    ledger = tree_digest(["docs/trials"])
    with guarded():
        control = run_copy(None)
        assert not control, f"unchanged copy is not green: {control}"
        print(f"CONTROL green (unchanged copy, {COLLECTED} collected)")
        killed = 0
        for mutant in MUTANTS:
            results = run_copy(mutant)
            ok = not any(k == "error" for k, _, _ in results) and any(
                k == "failure" and name == mutant[4] and msg.startswith(FAILURE) and mutant[5] in msg
                for k, name, msg in results)
            killed += ok
            print("KILLED  " if ok else "SURVIVED", f"{mutant[0]} -> {mutant[4]}")
    assert tree_digest(watched) == sources, "sources changed"
    assert tree_digest(["docs/trials"]) == ledger, "docs/trials changed"
    print(f"{killed}/{len(MUTANTS)} killed; sources and docs/trials ({len(ledger)} files) byte-identical")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
