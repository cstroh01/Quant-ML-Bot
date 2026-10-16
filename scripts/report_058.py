"""Spec 058 T017/T018 publication (FR-006): every candidate, both baselines, Gate 3, the holdout, D-4.

Reads the verified ledger only; computes no new trial. Prints Markdown with: the source and ledger
head (Rule 11), the 15 candidates (annualized net excess Sharpe, HAC t, family-N and lifetime-N DSR,
B-RND mean/std/max Sharpe for that candidate's seeds), B-BH, PBO at S = 16, folds/purge/embargo,
commission and slippage, the §5 selection, the research-window Gate 3 status, the holdout D-4
result (or "not run"), the combined T017 verdict, the preregistration disclosures and the limitations
register. The verdict is PASS only if the research-window Gate 3 passed AND D-4 passed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import sys

import generate_gate3_evidence as gate3
from disclosure import LIMITATIONS
from run_058_t015 import RUN_ORDER
from selection_bias import build_matrix, counted_dsr, hac_t_stat, matrix_pbo, trial_counts
from trial_registry import ROOT, TrialLedger, verify_family

FAMILY = "058-edge"
DISCLOSURES = (
    "H1-12 and H5 produced byte-identical return series: H5 is H4's inverse-volatility weights gated by the "
    "H1 12-month signal, which under this implementation is the same book as volatility-targeted H1-12. Both "
    "stay in N_family (15), the conservative count.",
    "Holdout (sessions >= 2023-10-02) corporate actions are Tiingo single-source; the T009 cross-source action "
    "fetch ended 2023-09-29. Holdout closes are cross-checked against Alpaca raw SIP at 10 bps.",
    "B-RND for H4 and H9 coincide: both candidates hold every eligible asset at nearly every decision, so the "
    "activity-matched random selection is nearly always fully invested.",
)


def _sharpe(log_returns: list[float], policy: dict) -> float:
    rf = policy["risk_free"]
    excess = [r - math.log1p(rf["annual_rate"]) / rf["days_per_year"] for r in log_returns]
    sd = statistics.stdev(excess) if len(excess) > 1 else 0.0
    return statistics.fmean(excess) / sd * math.sqrt(rf["days_per_year"]) if sd > 0 else float("nan")


def collect(root: Path = ROOT) -> dict:
    """Everything the report prints, from one verified ledger read."""
    policy = verify_family(FAMILY, root=root)["declaration"]["gate3"]
    ledger = TrialLedger(root)
    state = ledger.verify()
    events = [e for e in state["events"] if e["family"] == FAMILY]
    completed = [e for e in events if e["event_type"] == "completed"]
    returns = {e["trial_id"]: [json.loads(line)["log_return"] for line in
                               (root / e["sidecar"]["path"]).read_text(encoding="utf-8").splitlines()]
               for e in completed}
    trials = [{**e, "returns": [json.loads(line) for line in (root / e["sidecar"]["path"]).read_text(encoding="utf-8").splitlines()]}
              for e in completed if e["role"] == "candidate"]
    matrix = build_matrix(trials, family={"id": FAMILY, **{k: policy[k] for k in
                                                          ("alignment", "min_coverage", "objective", "risk_free")}})
    counts = trial_counts(gate3._current_backfill(root) or {}, ledger, family=FAMILY)
    brnd = defaultdict(list)
    for e in completed:
        if e["role"] == "random_signal_baseline":
            brnd[e["config"]["model"]["params"]["candidate"]].append(_sharpe(returns[e["trial_id"]], policy))
    rows = []
    for config_id in RUN_ORDER:
        e = next(x for x in completed if x["role"] == "candidate" and x["config"]["model"]["name"] == config_id)
        dsr = counted_dsr(matrix, selected_trial=e["trial_id"], counts=counts)
        t = hac_t_stat(returns[e["trial_id"]], horizon=policy["horizon"], lags=policy["hac_lags"],
                       annual_risk_free=policy["risk_free"]["annual_rate"], days_per_year=policy["risk_free"]["days_per_year"])
        seeds = brnd.get(config_id, [])
        rows.append({"config": config_id, "trial_id": e["trial_id"], "sharpe": _sharpe(returns[e["trial_id"]], policy),
                     "hac_t": t.get("value"), "family_dsr": (dsr.get("family") or {}).get("value"),
                     "lifetime_dsr": (dsr.get("lifetime") or {}).get("value"),
                     "brnd": {"n": len(seeds), "mean": statistics.fmean(seeds) if seeds else None,
                              "std": statistics.stdev(seeds) if len(seeds) > 1 else None,
                              "max": max(seeds) if seeds else None}})
    bbh = next(e for e in completed if e["role"] == "buy_and_hold_baseline")
    holdout = next((e for e in events if e["role"] == "holdout" and e["event_type"] != "started"), None)
    spend = next((e for e in events if e["role"] == "holdout" and e["event_type"] == "started"), None)
    first = next(e for e in completed if e["role"] == "candidate")
    return {"policy": policy, "rows": rows, "bbh_sharpe": _sharpe(returns[bbh["trial_id"]], policy),
            "pbo": matrix_pbo(matrix), "counts": counts, "head": state["head"], "cv": first["config"]["cv"],
            "costs": {"commission": first["config"]["commission"], "slippage": first["config"]["slippage"]},
            "data": first["config"]["data"], "window": first["config"]["date_range"],
            "observations": len(matrix.get("dates") or []), "spend": spend, "holdout": holdout}


def verdict(info: dict) -> dict:
    """§5 selection, research Gate 3 (DSR >= 0.95 at N_family and HAC t >= 3.0), D-4, combined."""
    selected = max(info["rows"], key=lambda r: (r["family_dsr"], -RUN_ORDER.index(r["config"])))
    research = (selected["family_dsr"] is not None and selected["family_dsr"] >= gate3.DSR_THRESHOLD
                and selected["hac_t"] is not None and selected["hac_t"] >= gate3.T_THRESHOLD)
    holdout = info["holdout"]
    d4 = holdout["sidecar"]["metadata"]["d4"] if holdout and holdout["event_type"] == "completed" else None
    if info["spend"] and d4 is None:
        holdout_state = f"holdout spent, trial {info['spend']['trial_id']} " + (
            f"ended {holdout['event_type']} ({holdout.get('reason')})" if holdout else "still open")
    else:
        holdout_state = "completed" if d4 else "not run"
    return {"selected": selected, "research_gate3_pass": research, "d4": d4, "holdout_state": holdout_state,
            "pass": bool(research and d4 and d4["pass"])}


def render(info: dict, v: dict, *, generated_at: datetime) -> str:
    f = lambda x, s=".3f": "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, s)
    cv, costs = info["cv"], info["costs"]
    lines = ["# Spec 058 edge research — results (T017/T018)", "",
             f"Generated {generated_at.astimezone(timezone.utc):%Y-%m-%dT%H:%M:%SZ} from the verified trial ledger, "
             f"head `{info['head']}`. Panel `{info['data']['sha256']}` ({info['data'].get('data_check')}).", "",
             f"**Verdict: {'PASS' if v['pass'] else 'FAIL'}.** Research-window Gate 3: "
             f"{'passed' if v['research_gate3_pass'] else 'failed'} (needs family DSR ≥ {gate3.DSR_THRESHOLD} and HAC t ≥ "
             f"{gate3.T_THRESHOLD}). Holdout D-4: " + (("passed" if v["d4"]["pass"] else "failed") if v["d4"] else v["holdout_state"]) + ".",
             "A FAIL is a valid, published outcome (spec 058 §6). It promotes nothing; LIVE trades only the spec 059 "
             "allocation, which claims no edge.", "",
             f"Research window {info['window'][0]} to {info['window'][1]}, {info['observations']} aligned sessions. "
             f"Walk-forward: {cv['folds']} folds, initial train {cv['initial_train_months']} months, test {cv['test_months']} "
             f"months, purge {cv['purge']}, embargo {cv['embargo']} sessions. Commission {costs['commission']} per fill; "
             f"slippage {costs['slippage']['model']} ({costs['slippage'].get('source')}). Sharpe is annualized daily net log "
             f"return in excess of {info['policy']['risk_free']['annual_rate']} annual; HAC lags {info['policy']['hac_lags']}.",
             f"N_family {info['counts']['family']['n_dsr']} (cap {info['counts']['family']['cap']}); lifetime N "
             f"{info['counts']['n_current']}. PBO (S = 16): {f(info['pbo'].get('value'))}.", "",
             "| Config | Sharpe | HAC t | DSR (N_family) | DSR (lifetime) | B-RND mean ± std (max), seeds |",
             "|---|---:|---:|---:|---:|---|"]
    for r in info["rows"]:
        mark = " **(selected)**" if r["config"] == v["selected"]["config"] else ""
        b = r["brnd"]
        lines.append(f"| {r['config']}{mark} | {f(r['sharpe'])} | {f(r['hac_t'], '.2f')} | {f(r['family_dsr'], '.4f')} | "
                     f"{f(r['lifetime_dsr'], '.2e')} | {f(b['mean'])} ± {f(b['std'])} ({f(b['max'])}), {b['n']} |")
    lines += [f"| B-BH (equal-weight buy-and-hold) | {f(info['bbh_sharpe'])} | | | | |", "",
              "Selection (§5, fixed before T015): the highest research-window family DSR; ties to the lower ID.", ""]
    if v["d4"]:
        d = v["d4"]
        lines += [f"Holdout ({d['first_session']} to {d['last_session']}, {d['sessions']} sessions, run once, "
                  f"trial `{info['holdout']['trial_id']}`): Sharpe {f(d['annualized_net_excess_sharpe'])}, "
                  f"one-sided HAC t {f(d['hac_t'].get('value'), '.2f')} (needs > 0 and ≥ {d['one_sided_threshold']}).", ""]
    else:
        lines += [f"Holdout: {v['holdout_state']}.", ""]
    lines += ["Disclosures:"] + [f"- {d}" for d in DISCLOSURES]
    lines += ["", "Limitations (Rule 16), docs/SCOPE-V1.md §6:"] + [f"- {item}" for item in LIMITATIONS]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, help="write the Markdown here (default: stdout)")
    args = p.parse_args(argv)
    info = collect()
    text = render(info, verdict(info), generated_at=datetime.now(timezone.utc))
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
