"""061 T003: Camden's one-command freeze and fresh costed buffered-allocation trial.

--dry-run verifies inputs without freezing or evaluating. --record-trial is a
HUMAN GATE: freeze the new family, start every series, evaluate once, verify.
Never updates execution, historical trials, 058, arming or profiles.json.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

import run_058_t015 as t015
from allocation_report import LABEL, RANDOM_ACTIVITY, series_stats
from buffered_allocation import CASH_RESERVE, buffered_weights
from data_sources import RESEARCH_END, load_058_panel, sealed_sessions
from disclosure import LIMITATIONS
from portfolio_backtest import run_portfolio_backtest
from portfolio_risk import equal_weight_book
from run_059_t004 import daily_rows, trial_config
from signals import ALLOCATION_SLEEVES, decision_sessions, random_selections
from trial_registry import (DECLARED_FAMILIES, ROOT, TrialLedger, canonical_json,
                            declare_family, digest, immutable_write,
                            production_recording, serialized, verify_family)
from trial_runner import current_ledger, research_attempt

FAMILY = "061-buffered-allocation"
RUNNER = "run_061_buffered_trial"
SOURCE = DECLARED_FAMILIES[FAMILY]


def source_declaration(root: Path = ROOT) -> dict:
    """Refuse stale spec/weights bindings before freezing or starting any trial."""
    declaration = json.loads((root / SOURCE).read_text(encoding="utf-8"))
    for name, sha in declaration["source_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha:
            raise ValueError(f"declaration source binding changed: {name}")
    if (declaration["family"] != FAMILY or declaration["cash_reserve"] != CASH_RESERVE
            or declaration["universe"] != list(ALLOCATION_SLEEVES)
            or declaration["n_family_cap"] != 1 or declaration["costs"] != t015.costs()):
        raise ValueError("declaration does not bind the buffered allocation")
    return declaration


def preflight(panel, check: dict, declaration: dict, ledger: TrialLedger) -> dict:
    """Read-only; reject wrong data, holdout, used family and altered configuration."""
    if check.get("status") not in ("VERIFIED", "EXCLUSIONS"):
        raise ValueError("data_check_missing")
    if check.get("panel_hash") != panel.panel_hash or declaration["panel_hash"] != panel.panel_hash:
        raise ValueError("panel_not_declared")
    if sealed_sessions(panel.closes.index).any():
        raise ValueError(f"holdout forbidden; research end {RESEARCH_END}")
    if any(t not in panel.closes for t in ALLOCATION_SLEEVES):
        raise ValueError("sleeves_missing")
    seeds = declaration["random_seeds"]
    if seeds != list(range(20261015, 20261035)):
        raise ValueError("seeds_not_declared")
    state = ledger.verify()
    if any(e["family"] == FAMILY for e in state["events"]):
        raise ValueError("research_report_already_started; no automatic rerun")
    weights = buffered_weights(panel.closes)
    return {"ledger_head_before": state["head"], "declaration_hash": digest(declaration),
            "weights_sha256": digest(weight_rows(weights)), "costs": t015.costs()}


def weight_rows(weights: pd.DataFrame) -> list[dict]:
    return [{"session": str(day.date()), "weights": {t: float(row[t]) for t in ALLOCATION_SLEEVES}}
            for day, row in weights.iterrows()]


def run_report(panel, *, declaration: dict, data: dict) -> dict:
    """Verified freeze and fresh ledger starts precede all accounting/statistics."""
    ledger = current_ledger(RUNNER)
    with serialized(ledger.path.with_name("061-buffered-allocation.run")):
        return _run_report(panel, declaration=declaration, data=data, ledger=ledger)


def _run_report(panel, *, declaration: dict, data: dict, ledger: TrialLedger) -> dict:
    frozen = verify_family(FAMILY, root=ledger.root)
    if frozen["declaration"] != declaration:
        raise ValueError("frozen declaration differs")
    preflight(panel, {"status": "VERIFIED", "panel_hash": panel.panel_hash}, declaration, ledger)
    closes = panel.closes.loc[:, list(ALLOCATION_SLEEVES)]
    opens = panel.opens.loc[:, list(ALLOCATION_SLEEVES)]
    decisions = decision_sessions(closes.index, cadence="monthly")
    candidate = buffered_weights(closes)
    draws = random_selections(closes, decision_mask=decisions, seeds=declaration["random_seeds"], **RANDOM_ACTIVITY)
    plan = [("B7-EW", "candidate", None, candidate),
            ("B-BH", "buy_and_hold_baseline", None,
             equal_weight_book(closes.notna(), max_gross=1.0).loc[decisions]),
            *[("B-RND", "random_signal_baseline", seed,
               equal_weight_book(draw, max_gross=1.0 - CASH_RESERVE).loc[decisions])
              for seed, draw in draws.items()]]
    costs, results = t015.costs(), []
    metadata = {"frequency": "daily", "return_convention": "funded_account_log", "net_costs": True,
                "oos": False, "cv": None, "costs": costs, "label": LABEL,
                "evaluation": "post-hoc allocation; single in-sample research pass, no fitted parameters"}
    with ExitStack() as stack:
        attempts = []
        for name, role, seed, weights in plan:
            config = trial_config(name, panel, data=data, costs=costs, seed=seed)
            config.update(runner=RUNNER)
            config["model"] = {"name": name, "params": {"spec": "061", "label": LABEL,
                "cash_reserve": CASH_RESERVE if name != "B-BH" else 0.0,
                "declaration_hash": digest(declaration), "weights_sha256": digest(weight_rows(weights))}}
            attempts.append(stack.enter_context(research_attempt(config, role=role, family=FAMILY)))
        for (name, role, seed, weights), attempt in zip(plan, attempts):
            backtest = run_portfolio_backtest(opens, closes, weights, starting_capital=100_000.0,
                                              commission_per_fill=0.0, fill_cost=t015.fill_cost(panel))
            attempt.returns(daily_rows(backtest.equity), metadata)
            results.append({"series": name, "role": role, "seed": seed,
                            "stats": series_stats(backtest.equity), "receipt": attempt.receipt,
                            "fills": len(backtest.fills), "skipped_orders": len(backtest.skipped)})
    sharpes = [r["stats"]["sharpe"] for r in results[2:] if r["stats"]["sharpe"] is not None]
    return {"label": LABEL, "post_hoc": True, "declaration_hash": digest(declaration),
            "panel_hash": panel.panel_hash, "window": [str(closes.index[0].date()), str(closes.index[-1].date())],
            "costs": costs, "series": results, "candidate_weights": weight_rows(candidate),
            "random_dispersion": {"seeds": declaration["random_seeds"],
                "mean_sharpe": float(np.mean(sharpes)) if sharpes else None,
                "std_sharpe": float(np.std(sharpes, ddof=1)) if len(sharpes) > 1 else None},
            "limitations": [*LIMITATIONS, "Chosen after T004; in-sample, no edge claim.",
                "Random baseline matches monthly cadence, not exact turnover; 7% is a target cash reserve.",
                "Research capital $100,000; does not establish $200-account executability."],
            "ledger_head_after": ledger.verify()["head"]}


def render(report: dict) -> str:
    lines = ["# 061 fresh buffered allocation trial", LABEL,
             "Post-hoc selection after 059 T004; single in-sample research pass, no fitted parameters.",
             "CV folds/purge/embargo: not applicable. Cash target 7%, before costs; monthly rebalance.",
             f"Panel: {report['panel_hash']}; window: {report['window']}",
             f"Declaration: {report['declaration_hash']}; ledger head: {report['ledger_head_after']}",
             f"Costs (identical for all series): {json.dumps(report['costs'], sort_keys=True)}", ""]
    for row in report["series"]:
        lines.append(f"- {row['series']} seed={row['seed']}: {json.dumps(row['stats'])}; "
                     f"fills={row['fills']}, skipped={row['skipped_orders']}; receipt={json.dumps(row['receipt'])} [{LABEL}]")
    lines.extend([f"Random seed dispersion: {json.dumps(report['random_dispersion'])} [{LABEL}]", ""])
    return "\n".join(lines + [f"- Limitation: {line}" for line in report["limitations"]]) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--record-trial", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        declaration = source_declaration()
        check_path = t015._latest_data_check(ROOT)
        check = json.loads(check_path.read_text(encoding="utf-8"))
        manifest = json.loads((ROOT / t015.T008_MANIFEST).read_text(encoding="utf-8"))
        panel = load_058_panel(args.panel, tiingo_manifest=manifest, data_check=check)
        status = preflight(panel, check, declaration, TrialLedger())
        if args.dry_run:
            print(json.dumps({"status": "PREFLIGHT_ONLY", "no_evaluation": True, **status}, indent=2))
            return 0
        if args.out is None or args.out.resolve().is_relative_to(ROOT) or args.out.exists():
            raise ValueError("--out must be a new private directory outside the repository")
        with production_recording(reason="Camden: 061 T005 fresh 7%-reserve costed trial"):
            if not (ROOT / "docs/trials/families" / f"{FAMILY}.json").exists():
                declare_family(FAMILY)
            report = run_report(panel, declaration=declaration, data=t015.data_dict(panel, check_path.name))
        args.out.mkdir(parents=True)
        immutable_write(args.out / "report.json", canonical_json(report))
        immutable_write(args.out / "report.md", render(report).encode("utf-8"))
        print(f"Recorded fresh B7-EW candidate and 21 comparison trials; {LABEL}")
        print(f"Verified ledger head: {report['ledger_head_after']}; report: {args.out / 'report.json'}")
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(f"061 refused/failed; do not retry: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
