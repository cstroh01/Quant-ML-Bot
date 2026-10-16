"""Spec 058 T016 (HUMAN GATE, D-3/D-4/D-7): select by the §5 rule, spend the holdout once, run it once.

`--dry-run`: preflight and the §5 selection table from the verified ledger (research-window family DSR
per candidate; T015 results only). Opens no sealed row and writes nothing.
`--record-holdout`: under `production_recording(reason="058 T016")`, in this order:
  1. the selection is recomputed from the verified ledger (highest family DSR; ties to declared order);
  2. one `holdout` start is appended to the ledger — the spend record, bound to the selected
     configuration — before any sealed byte is parsed (D-7); a second spend is refused by the ledger;
  3. the holdout panel and its counts-only data check are built (`load_058_holdout_panel`);
  4. the selected configuration's book is built on the whole panel (row t reads data through t only),
     filled at the next open with spec 046 costs, and its daily net log returns on sessions
     >= 2023-10-02 are recorded as the holdout trial's sidecar with the D-4 statistics.
Any error after step 2 finishes the holdout trial `errored`: the holdout is spent either way.

D-4: pass only if the holdout annualized net Sharpe (excess of the declared risk-free rate) is > 0 AND
the one-sided HAC t (declared gate3 `hac_lags`, `horizon`, `risk_free`) is >= 1.645.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

import edge_walk_forward as wf
import generate_gate3_evidence as gate3
from data_sources import HOLDOUT_START, RESEARCH_END, load_058_holdout_panel
from portfolio_backtest import run_portfolio_backtest
from run_058_t015 import COMMISSION_PER_FILL, RUN_ORDER, STARTING_CAPITAL, T008_MANIFEST, _latest_data_check, costs, \
    fill_cost, workspace_clean
from selection_bias import build_matrix, counted_dsr, hac_t_stat, trial_counts
from trial_registry import ROOT, TrialLedger, production_recording, verify_family

FAMILY = wf.FAMILY
RUNNER = "run_058_t016.holdout"
T008_ALPACA_MANIFEST = "docs/implementation/spec-058/t008-alpaca-20261009.json"
ONE_SIDED_T = 1.645
SELECTION_RULE = "highest research-window DSR at N_family; ties to the lower ID (declared run order)"


class T016Refused(RuntimeError):
    """A named T016 precondition failed; if raised before the spend, nothing was written."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def selection(ledger: TrialLedger, root: Path = ROOT) -> dict:
    """The §5 selection from the verified ledger: one row per completed candidate, and the winner.

    Refuses unless the family verifies and every declared configuration has exactly one completed
    candidate trial with a defined family DSR.
    """
    policy = verify_family(FAMILY, root=root)["declaration"]["gate3"]
    events = ledger.verify()["events"]
    completed = [e for e in events if e["event_type"] == "completed" and e["family"] == FAMILY and e["role"] == "candidate"]
    by_config = {}
    for e in completed:
        by_config.setdefault(e["config"]["model"]["name"], []).append(e)
    if sorted(by_config) != sorted(RUN_ORDER) or any(len(v) != 1 for v in by_config.values()):
        raise T016Refused("candidates_incomplete_or_duplicated")
    trials = []
    for e in events:
        side = e.get("sidecar")
        if e["event_type"] == "completed" and side and e["family"] == FAMILY and e["role"] == "candidate":
            lines = (root / side["path"]).read_text(encoding="utf-8").splitlines()
            trials.append({**e, "returns": [json.loads(line) for line in lines]})
    matrix = build_matrix(trials, family={"id": FAMILY, **{k: policy[k] for k in
                                                          ("alignment", "min_coverage", "objective", "risk_free")}})
    counts = trial_counts(gate3._current_backfill(root) or {}, ledger, family=FAMILY)
    rows = []
    for order, config_id in enumerate(RUN_ORDER):
        event = by_config[config_id][0]
        dsr = counted_dsr(matrix, selected_trial=event["trial_id"], counts=counts)
        family_dsr = (dsr.get("family") or {}).get("value")
        if family_dsr is None or not math.isfinite(family_dsr):
            raise T016Refused(f"family_dsr_undefined:{config_id}")
        rows.append({"order": order, "config": config_id, "trial_id": event["trial_id"],
                     "config_hash": event["config_hash"], "family_dsr": family_dsr,
                     "lifetime_dsr": (dsr.get("lifetime") or {}).get("value")})
    winner = pick(rows)
    return {"rule": SELECTION_RULE, "rows": rows, "selected": winner,
            "n_family": counts["family"]["n_dsr"], "ledger_head_hash": counts["ledger_head_hash"]}


def pick(rows: list[dict]) -> dict:
    """§5: the highest family DSR; a tie goes to the lower declared ID (earlier in RUN_ORDER)."""
    return max(rows, key=lambda r: (r["family_dsr"], -r["order"]))


def holdout_config(selected_start: dict, *, chosen: dict, holdout_end: date, data_check_name: str) -> dict:
    """The spend record's config: the selected trial's config verbatim, re-pointed at the sealed window."""
    config = {k: v for k, v in selected_start["config"].items()}
    config.update(runner=RUNNER, date_range=[str(HOLDOUT_START), str(holdout_end)],
                  cv={"scheme": "single_sealed_holdout", "folds": 0, "purge": 0, "embargo": 0},
                  holdout={"family": FAMILY, "selected_trial_id": chosen["selected"]["trial_id"],
                           "selected_config": chosen["selected"]["config"],
                           "selected_config_hash": chosen["selected"]["config_hash"],
                           "selection_rule": chosen["rule"], "selection_table": chosen["rows"],
                           "n_family": chosen["n_family"], "ledger_head_at_selection": chosen["ledger_head_hash"],
                           "research_end": str(RESEARCH_END), "holdout_start": str(HOLDOUT_START),
                           "holdout_end": str(holdout_end), "data_check": data_check_name,
                           "d4": {"annualized_net_sharpe_gt": 0.0, "one_sided_hac_t_ge": ONE_SIDED_T}})
    return config


def holdout_returns(config_id: str, panel, *, start: date = HOLDOUT_START) -> list[dict]:
    """Daily net log returns on sessions >= `start` of one continuous costed run over the whole panel.

    The book row t reads closes through t only (`target_book`); fills are at the next open. Starting
    the run at the panel's first session keeps the research runs' capital path, so the holdout rows are
    exactly what the T015 runner would have produced had the panel not been sealed.
    """
    book = wf.target_book(config_id, panel.closes)
    result = run_portfolio_backtest(panel.opens, panel.closes, book, starting_capital=STARTING_CAPITAL,
                                    commission_per_fill=COMMISSION_PER_FILL, fill_cost=fill_cost(panel))
    if (result.equity <= 0).any():
        raise ValueError("equity reached zero; log returns are undefined")
    daily = np.log(result.equity / result.equity.shift(1)).dropna()
    daily = daily.loc[daily.index >= pd.Timestamp(start)]
    return [{"session": s.strftime("%Y-%m-%d"), "log_return": float(v)} for s, v in daily.items()]


def d4(returns: list[dict], policy: dict) -> dict:
    """D-4 verdict: annualized net Sharpe of excess log returns > 0 and one-sided HAC t >= 1.645."""
    rf = policy["risk_free"]
    excess = pd.Series([r["log_return"] for r in returns], dtype=float) - math.log1p(rf["annual_rate"]) / rf["days_per_year"]
    sd = float(excess.std(ddof=1))
    sharpe = float(excess.mean() / sd * math.sqrt(rf["days_per_year"])) if sd > 0 else float("nan")
    t = hac_t_stat([r["log_return"] for r in returns], horizon=policy["horizon"], lags=policy["hac_lags"],
                   annual_risk_free=rf["annual_rate"], days_per_year=rf["days_per_year"])
    passed = math.isfinite(sharpe) and sharpe > 0 and t.get("value") is not None and t["value"] >= ONE_SIDED_T
    return {"sessions": len(returns), "first_session": returns[0]["session"] if returns else None,
            "last_session": returns[-1]["session"] if returns else None,
            "annualized_net_excess_sharpe": sharpe, "hac_t": t, "one_sided_threshold": ONE_SIDED_T,
            "pass": bool(passed)}


def preflight(ledger: TrialLedger, *, root: Path = ROOT, clean=workspace_clean) -> dict:
    """Named refusals before any ledger byte: family verified, T015 complete, holdout unspent, clean tree."""
    try:
        verify_family(FAMILY, root=root)
    except ValueError as error:
        raise T016Refused("family_unverified") from error
    events = ledger.verify()["events"]
    if any(e["role"] == "holdout" and e["family"] == FAMILY for e in events):
        raise T016Refused("holdout_already_spent")
    dangling = {e["trial_id"] for e in events if e["family"] == FAMILY and e["event_type"] == "started"} - \
               {e["trial_id"] for e in events if e["family"] == FAMILY and e["event_type"] != "started"}
    if dangling:
        raise T016Refused("family_has_dangling_starts")
    if not clean(root):
        raise T016Refused("workspace_dirty")
    return selection(ledger, root)


def record_holdout(*, panel_dir: Path, alpaca_dir: Path, holdout_end: date, ledger: TrialLedger | None = None,
                   root: Path = ROOT, clean=workspace_clean) -> dict:
    """Steps 1-4 of the module docstring. Returns {selection, receipt, d4, data_check}."""
    ledger = ledger or TrialLedger(root)
    chosen = preflight(ledger, root=root, clean=clean)
    data_check_path = _latest_data_check(root)
    data_check = json.loads(data_check_path.read_text(encoding="utf-8"))
    policy = verify_family(FAMILY, root=root)["declaration"]["gate3"]
    selected_start = next(e for e in ledger.verify()["events"]
                          if e["trial_id"] == chosen["selected"]["trial_id"] and e["event_type"] == "started")
    config = holdout_config(selected_start, chosen=chosen, holdout_end=holdout_end, data_check_name=data_check_path.name)
    trial_id = ledger.start(config, role="holdout", family=FAMILY, runner=RUNNER)
    spend = next(e for e in ledger.verify()["events"] if e["trial_id"] == trial_id)
    try:
        panel, check = load_058_holdout_panel(
            panel_dir, alpaca_dir, tiingo_manifest=json.loads((root / T008_MANIFEST).read_text(encoding="utf-8")),
            alpaca_manifest=json.loads((root / T008_ALPACA_MANIFEST).read_text(encoding="utf-8")),
            data_check=data_check, ledger=ledger, config_hash=spend["config_hash"], holdout_end=holdout_end)
        rows = holdout_returns(chosen["selected"]["config"], panel)
        verdict = d4(rows, policy)
        receipt = ledger.finish(trial_id, "completed", returns=rows, metadata={
            "frequency": "daily", "return_convention": "funded_account_log", "net_costs": True, "oos": True,
            "holdout": True, "costs": {"commission": COMMISSION_PER_FILL, "slippage": costs()["slippage"]},
            "d4": verdict, "holdout_panel_hash": panel.panel_hash, "holdout_data_check": check})
    except Exception as error:
        ledger.finish(trial_id, "errored", reason=f"{type(error).__name__}: {error}"[:500])
        raise
    return {"selection": chosen, "receipt": receipt, "d4": verdict, "data_check": check}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panel", type=Path, required=True, help="private T008 Tiingo raw folder (058-tiingo-...)")
    p.add_argument("--alpaca", type=Path, required=True, help="private T008 Alpaca raw folder (058-alpaca-...)")
    p.add_argument("--holdout-end", type=date.fromisoformat, required=True, help="last holdout session, fixed before the run")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--record-holdout", action="store_true")
    args = p.parse_args(argv)
    ledger = TrialLedger(ROOT)
    try:
        if args.dry_run:
            report = preflight(ledger, clean=lambda _root: True)  # dry run: nothing is written, so a dirty tree is reported, not refused
            report["workspace_clean"] = workspace_clean(ROOT)
            print(json.dumps(report, indent=2, default=str))
            return 0
        with production_recording(reason="058 T016"):
            out = record_holdout(panel_dir=args.panel, alpaca_dir=args.alpaca, holdout_end=args.holdout_end, ledger=ledger)
    except T016Refused as refused:
        print(f"T016 REFUSED: {refused.reason}")
        return 2
    print(json.dumps({"selected": out["selection"]["selected"], "d4": out["d4"],
                      "data_check_totals": out["data_check"]["totals"],
                      "receipt": {k: out["receipt"][k] for k in ("trial_id", "event_type", "record_hash")}},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
