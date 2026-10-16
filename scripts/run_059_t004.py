"""Spec 059 T004 run command (D-11): the FR-003 research-window allocation report on the 058 panel.

ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED. Camden runs `--record-trial` once, after 058 T015's ledger
lines are merged and `amend_family.py 059-allocation --record` has frozen D-11. P&L is on the 058 D-10 B
back-adjusted panel (the bodies, data check and panel hash T015 used); every fill's cost is spec 046's
primary model on raw nominal bars, quantity converted by notional at the decision close
(`run_058_t015.fill_cost`). Commission $0 per fill. Every series is started in the ledger before any
is evaluated: A1 (candidate, N_family 1 of 2), B-BH, then B-RND over the preregistered seeds.

Usage (repo root):
  python scripts/run_059_t004.py --panel <058-tiingo raw folder> --dry-run
  python scripts/run_059_t004.py --panel <058-tiingo raw folder> --record-trial --out <private folder>
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

import run_058_t015 as t015
from allocation_report import LABEL, allocation_report, render
from cost_model import CostConfig
from data_sources import PanelRefused, load_058_panel
from signals import ALLOCATION_SLEEVES
from trial_registry import ROOT, TrialLedger, production_recording, verify_family
from trial_runner import research_attempt

FAMILY = "059-allocation"
RUNNER = "run_059_t004"
STARTING_CAPITAL = 100_000.0
COMMISSION_PER_FILL = 0.0
PreflightRefused = t015.PreflightRefused


def declared() -> dict:
    """The frozen 059 declaration with D-11 (amendment) applied; refuses if D-11 is not frozen yet."""
    try:
        declaration = verify_family(FAMILY)["declaration"]
    except ValueError as error:
        raise PreflightRefused("family_unverified") from error
    if "research_data" not in declaration or "random_seeds" not in declaration:
        raise PreflightRefused("d11_not_frozen")
    return declaration


def preflight(panel, *, data_check: dict, ledger: TrialLedger, declaration: dict, root: Path = ROOT,
              clean=t015.workspace_clean) -> dict:
    """Named refusals, all before any ledger byte."""
    if data_check.get("status") not in ("VERIFIED", "EXCLUSIONS"):
        raise PreflightRefused("data_check_missing")
    if data_check.get("panel_hash") != panel.panel_hash:
        raise PreflightRefused("panel_hash_mismatch")
    if declaration["research_data"]["panel_hash"] != panel.panel_hash:
        raise PreflightRefused("panel_not_declared")
    missing = [t for t in ALLOCATION_SLEEVES if t not in panel.closes.columns]
    if missing:
        raise PreflightRefused(f"sleeves_missing:{','.join(missing)}")
    prior = [e for e in ledger.verify()["events"]
             if e["event_type"] == "started" and e["family"] == FAMILY and e["role"] in ("candidate", "synthetic_test")]
    if prior:
        raise PreflightRefused("research_report_already_run")
    if not clean(root):
        raise PreflightRefused("workspace_dirty")
    seeds = list(declaration["random_seeds"])
    if len(seeds) < 2 or len(set(seeds)) != len(seeds):
        raise PreflightRefused("seeds_invalid")
    return {"prior_candidates": 0, "n_family_after": 1, "cap": declaration["n_family_cap"], "seeds": seeds,
            "costs": t015.costs()}


def daily_rows(equity: pd.Series) -> list[dict]:
    """Funded-account daily log returns, one row per session after the first."""
    daily = np.log(equity / equity.shift(1)).dropna()
    return [{"session": s.strftime("%Y-%m-%d"), "log_return": float(v)} for s, v in daily.items()]


def trial_config(series: str, panel, *, data: dict, costs: dict, seed: int | None) -> dict:
    closes = panel.closes[list(ALLOCATION_SLEEVES)]
    return {"runner": RUNNER, "data": data, "universe": list(ALLOCATION_SLEEVES),
            "date_range": [closes.index[0].strftime("%Y-%m-%d"), closes.index[-1].strftime("%Y-%m-%d")],
            "features": [], "transforms": [], "target": {"label": "next_open_fill_daily_log_return", "horizon": 1},
            "model": {"name": series, "params": {"spec": "059 §3", "label": LABEL}},
            "cv": None, "seed": seed, "initial_capital": STARTING_CAPITAL, "commission": costs["commission"],
            "slippage": costs["slippage"], "liquidation": False, "risk_free": dict(t015.wf.RISK_FREE)}


def series_plan(seeds: list[int]) -> list[tuple[str, str, int | None]]:
    """(series, ledger role, seed) in run order: A1 is the family's one candidate; baselines never count."""
    return [("A1", "candidate", None), ("B-BH", "buy_and_hold_baseline", None),
            *[("B-RND", "random_signal_baseline", seed) for seed in seeds]]


def run_report(panel, *, seeds: list[int], data: dict) -> tuple[dict, list[dict]]:
    """Start every series, then evaluate once; each attempt finishes completed or errored."""
    costs = t015.costs()
    bars = {t: pd.DataFrame({"Open": panel.opens[t], "Close": panel.closes[t]}) for t in ALLOCATION_SLEEVES}
    plan = series_plan(seeds)
    metadata = {"frequency": "daily", "return_convention": "funded_account_log", "net_costs": True, "oos": False,
                "cv": None, "costs": {"commission": costs["commission"], "slippage": costs["slippage"]},
                "evaluation": "single pass over the research window; no fitted parameters (spec 059 §3)",
                "label": LABEL}
    with ExitStack() as stack:
        attempts = [stack.enter_context(research_attempt(trial_config(name, panel, data=data, costs=costs, seed=seed),
                                                         role=role, family=FAMILY))
                    for name, role, seed in plan]
        equity: dict = {}
        report = allocation_report(bars, commission_per_fill=COMMISSION_PER_FILL, cost_config=CostConfig(),
                                   split_sessions=panel.split_sessions, seeds=seeds,
                                   starting_capital=STARTING_CAPITAL, fill_cost=t015.fill_cost(panel),
                                   equity_out=equity)
        keys = ["allocation", "buy_and_hold", *seeds]
        for attempt, key in zip(attempts, keys):
            attempt.returns(daily_rows(equity[key]), metadata)
    receipts = [{"series": name, "seed": seed, "receipt": a.receipt} for (name, _, seed), a in zip(plan, attempts)]
    return report, receipts


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--panel", type=Path, required=True, help="private T008 Tiingo raw folder (058-tiingo-...)")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--record-trial", action="store_true")
    p.add_argument("--out", type=Path, help="private run summary (outside the repo)")
    a = p.parse_args(argv)
    try:
        declaration = declared()
        check_path = t015._latest_data_check(ROOT)
        data_check = json.loads(check_path.read_text(encoding="utf-8"))
        manifest = json.loads((ROOT / t015.T008_MANIFEST).read_text(encoding="utf-8"))
        panel = load_058_panel(a.panel, tiingo_manifest=manifest, data_check=data_check)
        status = preflight(panel, data_check=data_check, ledger=TrialLedger(), declaration=declaration)
    except (PreflightRefused, PanelRefused) as error:
        print(f"T004 refused: {getattr(error, 'reason', error)}", file=sys.stderr)
        return 2
    sessions = panel.closes[list(ALLOCATION_SLEEVES)].dropna(how="all").index
    summary = {"label": LABEL, "data_check": check_path.name, "panel_hash": panel.panel_hash,
               "sessions": [str(sessions[0].date()), str(sessions[-1].date())],
               "sleeves": {t: panel.summary.get(t) for t in ALLOCATION_SLEEVES}, **status}
    if a.dry_run:
        print(json.dumps(summary, indent=1, default=str))
        return 0
    if a.out is None or ROOT in a.out.resolve().parents:
        print("T004 refused: --out must be a private path outside the repo", file=sys.stderr)
        return 2
    with production_recording(reason="059 T004"):
        report, receipts = run_report(panel, seeds=status["seeds"], data=t015.data_dict(panel, check_path.name))
    stamp = [f"source: 058 D-10 B panel sha256={panel.panel_hash} (private T008 Tiingo bodies; {check_path.name})",
             f"ledger head after run: {TrialLedger().verify()['head']}"]
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "t004-report.json").write_text(json.dumps({**summary, "report": report, "receipts": receipts},
                                                       indent=1, default=str), encoding="utf-8")
    (a.out / "t004-report.md").write_text("\n".join(render(report, stamp)) + "\n", encoding="utf-8")
    print(f"T004 recorded {len(receipts)} trials; report at {a.out / 't004-report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
