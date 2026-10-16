"""Spec 058 T015 (queue Q133): run the preregistered 058-edge family once, in declared order.

`--dry-run`: preflight + panel load + panel summary. Computes no return (an inspected but unrecorded
result would breach the ledger rule). `--record-trial`: the real run under
`production_recording(reason="058 T015")`: 15 candidates in declared order, then B-BH, then B-RND
(15 x 20 preregistered seeds). The first error is recorded `errored` by `research_attempt` and stops
the run, so a partial family is visible, never silently completed. Statistics come afterwards from
`generate_gate3_evidence.py` (T017). Writes the ledger plus a private run summary at `--out` only.

Panel: D-10 B (`data_sources.load_058_panel`) — back-adjusted in repo from Tiingo raw OHLC and
T009-checked actions; action-mismatch sessions are spliced to zero return; P&L on the adjusted
basis; costs on raw nominal bars (spec 046 primary, Y = 1.0) with the fill quantity converted by
notional at the decision close.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import pandas as pd

import edge_walk_forward as wf
from cost_model import CostConfig, estimate_fill_cost
from data_sources import PanelRefused, load_058_panel
from trial_registry import ROOT, TrialLedger, production_recording, verify_family

RUN_ORDER = ("H1-3", "H1-6", "H1-12", "H2-100", "H2-200", "H3-3", "H3-5", "H4", "H5", "H6-6", "H6-12",
             "H7", "H8", "H9", "H10")
COMMISSION_PER_FILL = 0.0  # US ETF retail commission; spread and impact carry the cost (spec 046)
STARTING_CAPITAL = 100_000.0
DATA_CHECK_GLOB = "docs/implementation/spec-058/data-check-*.json"
T008_MANIFEST = "docs/implementation/spec-058/t008-tiingo-20261009.json"


class PreflightRefused(RuntimeError):
    """A named T015 precondition failed before any ledger byte."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def costs() -> dict:
    config = CostConfig()
    if config.role != "primary" or config.impact_coef != 1.0:
        raise PreflightRefused("cost_config_not_primary")
    return {"commission": COMMISSION_PER_FILL,
            "slippage": {"model": wf.COST_MODEL, "source": "spec 046 primary", "config": config.as_mapping()}}


def fill_cost(panel, config: CostConfig | None = None):
    """`FillCost` on the adjusted share basis: Q_nominal = Q_adj * adj_close_t / raw_close_t (same dollars)."""
    config = config or CostConfig()

    def cost(ticker: str, as_of: pd.Timestamp, quantity: float) -> float:
        nominal = quantity * float(panel.closes.at[as_of, ticker]) / float(panel.raw_closes.at[as_of, ticker])
        return estimate_fill_cost(panel.cost_history[ticker], as_of=as_of, quantity=nominal, config=config,
                                  split_sessions=panel.split_sessions[ticker]).total
    return cost


def data_dict(panel, data_check_name: str) -> dict:
    return {"sha256": panel.panel_hash, "price_basis": "unadjusted_dollars", "corporate_actions_verified": True,
            "adjustment": "058 D-10 B: in-repo back-adjust of raw Tiingo OHLC; T009 action mismatches spliced "
                          "to zero return; exclusions not tradable", "data_check": data_check_name,
            "cost_basis": "raw provider_nominal OHLCV"}


def workspace_clean(root: Path = ROOT) -> bool:
    """True only when `git status` reports no change under scripts/ (Camden's run; any failure = unknown)."""
    try:
        out = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "scripts"],
                             capture_output=True, text=True, timeout=30, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return out.strip() == ""


def preflight(panel, *, data_check: dict, ledger: TrialLedger, root: Path = ROOT, rerun: str | None = None,
              clean=workspace_clean) -> dict:
    """All refusals are named and happen before any ledger write."""
    try:
        declared = verify_family(wf.FAMILY, root=root)["declaration"]
    except ValueError as error:
        raise PreflightRefused("family_unverified") from error
    if declared["gate3"]["risk_free"] != wf.RISK_FREE:
        raise PreflightRefused("risk_free_mismatch")
    if data_check.get("status") not in ("VERIFIED", "EXCLUSIONS"):
        raise PreflightRefused("data_check_missing")
    if data_check.get("panel_hash") != panel.panel_hash:
        raise PreflightRefused("panel_hash_mismatch")
    prior = [e for e in ledger.verify()["events"]
             if e["event_type"] == "started" and e["family"] == wf.FAMILY and e["role"] in ("candidate", "synthetic_test")]
    if prior and not (isinstance(rerun, str) and rerun.strip()):
        raise PreflightRefused("family_already_run")
    if not clean(root):
        raise PreflightRefused("workspace_dirty")
    return {"prior_candidates": len(prior), "n_family_after": len(prior) + len(RUN_ORDER),
            "cap": declared["n_family_cap"], "costs": costs()}


def run_family(panel, *, data_check_name: str, progress=print) -> list[dict]:
    """Every configuration in declared order; the first exception stops the run (already recorded)."""
    kwargs = {"fill_cost": fill_cost(panel), "costs": costs(), "data": data_dict(panel, data_check_name),
              "starting_capital": STARTING_CAPITAL}
    receipts = []
    for config_id in (*RUN_ORDER, "B-BH"):
        started = time.monotonic()
        receipts.append({"config": config_id, "receipt": wf.run_configuration(config_id, panel.opens, panel.closes, **kwargs)})
        progress(f"{config_id} recorded in {time.monotonic() - started:.0f}s")
    for config_id in RUN_ORDER:
        for seed in wf.BRND_SEEDS:
            receipts.append({"config": "B-RND", "candidate": config_id, "seed": seed,
                             "receipt": wf.run_brnd(config_id, seed, panel.opens, panel.closes, **kwargs)})
        progress(f"B-RND {config_id} x {len(wf.BRND_SEEDS)} recorded")
    return receipts


def ledger_progress(events: list[dict]) -> dict:
    """058-edge progress from ledger events: completed configs, completed B-RND pairs, dangling starts.

    A dangling start has no terminal event (an interrupted run). Pairs are (candidate, seed).
    """
    terminal = {e["trial_id"]: e["event_type"] for e in events if e["event_type"] != "started"}
    done, pairs, dangling, starts = {}, set(), [], {}
    for e in events:
        if e["event_type"] != "started" or e["family"] != wf.FAMILY:
            continue
        model = e["config"]["model"]
        key = ("B-RND", model["params"]["candidate"], int(model["params"]["seed"])) if model["name"] == "B-RND" \
            else (model["name"],)
        starts.setdefault(key, []).append(e["trial_id"])
        outcome = terminal.get(e["trial_id"])
        if outcome is None:
            dangling.append({"trial_id": e["trial_id"], "key": key})
        elif outcome == "completed":
            if model["name"] == "B-RND":
                pairs.add(key[1:])
            else:
                done[key[0]] = done.get(key[0], 0) + 1
    return {"configs": done, "brnd_pairs": pairs, "dangling": dangling, "starts": starts}


def resume_preflight(panel, *, data_check: dict, ledger: TrialLedger, reason: str | None, root: Path = ROOT,
                     clean=workspace_clean) -> dict:
    """Resume only an interrupted T015: every candidate and B-BH completed exactly once, nothing else run.

    Refuses (named) before any ledger byte. The remaining work is the B-RND pairs without a completed
    record; dangling starts are closed `abandoned` with `reason`, never deleted.
    """
    if not (isinstance(reason, str) and reason.strip()):
        raise PreflightRefused("resume_reason_missing")
    try:
        verify_family(wf.FAMILY, root=root)
    except ValueError as error:
        raise PreflightRefused("family_unverified") from error
    if data_check.get("status") not in ("VERIFIED", "EXCLUSIONS"):
        raise PreflightRefused("data_check_missing")
    if data_check.get("panel_hash") != panel.panel_hash:
        raise PreflightRefused("panel_hash_mismatch")
    events = ledger.verify()["events"]
    hashes = {e["config"]["data"].get("sha256") for e in events
              if e["event_type"] == "started" and e["family"] == wf.FAMILY}
    if hashes != {panel.panel_hash}:
        raise PreflightRefused("ledger_panel_mismatch")
    progress = ledger_progress(events)
    expected = {c: 1 for c in (*RUN_ORDER, "B-BH")}
    if progress["configs"] != expected:
        raise PreflightRefused("configs_not_complete_once")
    extra = [k for k in progress["starts"] if k[0] != "B-RND" and k[0] not in expected]
    if extra or any(len(v) != 1 for k, v in progress["starts"].items() if k[0] != "B-RND"):
        raise PreflightRefused("unexpected_config_starts")
    if not clean(root):
        raise PreflightRefused("workspace_dirty")
    remaining = [(c, s) for c in RUN_ORDER for s in wf.BRND_SEEDS if (c, s) not in progress["brnd_pairs"]]
    return {"dangling": progress["dangling"], "remaining": remaining,
            "brnd_completed": len(progress["brnd_pairs"]), "costs": costs()}


def resume_family(panel, *, ledger: TrialLedger, data_check_name: str, status: dict, reason: str,
                  progress=print) -> list[dict]:
    """Close dangling starts as abandoned, then run the remaining B-RND pairs in declared order."""
    receipts = [{"closed": d["trial_id"], "receipt": ledger.finish(d["trial_id"], "abandoned", reason=reason)}
                for d in status["dangling"]]
    kwargs = {"fill_cost": fill_cost(panel), "costs": costs(), "data": data_dict(panel, data_check_name),
              "starting_capital": STARTING_CAPITAL}
    for config_id, seed in status["remaining"]:
        receipts.append({"config": "B-RND", "candidate": config_id, "seed": seed,
                         "receipt": wf.run_brnd(config_id, seed, panel.opens, panel.closes, **kwargs)})
        if seed == wf.BRND_SEEDS[-1]:
            progress(f"B-RND {config_id} complete")
    return receipts


def _latest_data_check(root: Path) -> Path:
    found = sorted(root.glob(DATA_CHECK_GLOB))
    if not found:
        raise PreflightRefused("data_check_missing")
    return found[-1]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panel", type=Path, required=True, help="private T008 Tiingo raw folder (058-tiingo-...)")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--record-trial", action="store_true")
    p.add_argument("--resume", metavar="REASON",
                      help="finish an interrupted run: close dangling starts as abandoned, run missing B-RND pairs")
    p.add_argument("--rerun", help="reason; required if any 058-edge candidate is already in the ledger")
    p.add_argument("--out", type=Path, help="private run summary (outside the repo)")
    a = p.parse_args(argv)
    try:
        check_path = _latest_data_check(ROOT)
        data_check = json.loads(check_path.read_text(encoding="utf-8"))
        manifest = json.loads((ROOT / T008_MANIFEST).read_text(encoding="utf-8"))
        panel = load_058_panel(a.panel, tiingo_manifest=manifest, data_check=data_check)
        if a.resume is not None:
            status = resume_preflight(panel, data_check=data_check, ledger=TrialLedger(), reason=a.resume)
        else:
            status = preflight(panel, data_check=data_check, ledger=TrialLedger(), rerun=a.rerun)
    except (PreflightRefused, PanelRefused) as error:
        print(f"T015 refused: {getattr(error, 'reason', error)}", file=sys.stderr)
        return 2
    summary = {"data_check": check_path.name, "panel_hash": panel.panel_hash, "tickers": panel.summary,
               "sessions": [str(panel.closes.index[0].date()), str(panel.closes.index[-1].date())], **status}
    if a.dry_run and a.resume is not None:
        print(json.dumps({k: v for k, v in summary.items() if k not in ("remaining", "tickers")}, indent=1, default=str))
        print(f"T015 resume plan: {len(status['remaining'])} B-RND pair(s) to run, first "
              f"{status['remaining'][:1]}, last {status['remaining'][-1:]}")
        return 0
    if a.dry_run:
        print(json.dumps(summary, indent=1, default=str))
        return 0
    if a.resume is not None:
        print(f"T015 resume: {len(status['dangling'])} dangling start(s) to close, "
              f"{len(status['remaining'])} B-RND pair(s) to run, {status['brnd_completed']} already complete")
        if a.out is None or ROOT in a.out.resolve().parents:
            print("T015 refused: --out must be a private path outside the repo", file=sys.stderr)
            return 2
        with production_recording(reason="058 T015 resume"):
            receipts = resume_family(panel, ledger=TrialLedger(), data_check_name=check_path.name, status=status,
                                     reason=a.resume)
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "t015-resume-summary.json").write_text(json.dumps({**summary, "receipts": receipts}, indent=1,
                                                                   default=str), encoding="utf-8")
        print(f"T015 resume recorded {len(receipts)} events; summary at {a.out / 't015-resume-summary.json'}")
        return 0
    if a.out is None or ROOT in a.out.resolve().parents:
        print("T015 refused: --out must be a private path outside the repo", file=sys.stderr)
        return 2
    with production_recording(reason="058 T015"):
        receipts = run_family(panel, data_check_name=check_path.name)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "t015-run-summary.json").write_text(json.dumps({**summary, "receipts": receipts}, indent=1, default=str),
                                                 encoding="utf-8")
    print(f"T015 recorded {len(receipts)} trials; summary at {a.out / 't015-run-summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
