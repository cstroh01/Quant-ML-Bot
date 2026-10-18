"""PAPER evidence report (spec 059 FR-005; SCOPE §11.3 item 4; queue Q112).

Reads recorded PAPER state only; opens no socket and reads no credential. Inputs:

- the paper loop's run records (``runs.jsonl``, one JSON object per run, as ``exec/paper_loop.py``
  returns them): ``profile``, ``mode``, ``session`` (the decision session t) and ``actions``;
- broker order snapshots (JSONL), one per ``client_order_id``: ``status`` and, for a fill,
  ``filled_avg_price`` and ``filled_qty``. The loop does not capture these yet (Queue proposal);
- nominal daily OHLCV per ticker, for the fill session's open and spec 046's modeled cost.

Guarantees: one row per action of a submit run. An order that reached or may have reached the
broker (outcome SUBMITTED or UNKNOWN) is reconciled only when its snapshot is terminal and either
filled exactly the intended quantity at a positive price or filled nothing; an action that never
reached the broker is shown, labelled, and needs no reconciliation. Realized cost is the adverse
fraction of the fill price against the fill session's open, the basis spec 046 prices; modeled
cost is ``cost_model.estimate_fill_cost`` from bars through t only (Rule 1), or the model's refusal
reason, never a zero. PASS is printed only when every required profile has at least
``MIN_SESSIONS`` completed submit sessions and at least one fill, every sent order is reconciled,
and every fill carries both a realized and a modeled cost (SCOPE §11.3 item 4: compared per order).
"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import pandas as pd

from cost_model import CostConfig, CostUnavailable, estimate_fill_cost
from data import trading_days
from disclosure import LIMITATIONS
from trial_registry import ROOT, source_identity
from allocation_policy import policy_evidence

REQUIRED_PROFILES = ("paper_large", "paper_small")
MIN_SESSIONS = 10
SENT_OUTCOMES = frozenset({"SUBMITTED", "UNKNOWN"})
TERMINAL = frozenset({"filled", "canceled", "expired", "rejected"})
DISCLOSURE = ("PAPER mechanics evidence, not a performance result. Costs are modeled, not calibrated. "
              "Only qualifying spec 061 records count; old/missing policies and drills are excluded.")


def qualifying_run(run: Mapping) -> bool:
    return (run.get("mode") == "submit" and run.get("allocation") == policy_evidence()
            and run.get("evidence_scope") == "qualifying")


@dataclass(frozen=True)
class OrderRow:
    """One sent order: what was intended, what the broker reports, and both cost measures."""

    profile: str
    decision_session: date
    fill_session: date
    ticker: str
    side: str
    quantity: float
    client_order_id: str
    intended_price: float
    status: str
    reconciled: bool
    fill_price: float | None
    open_price: float | None
    realized_cost: float | None
    modeled_cost: float | None
    note: str


def next_session(session: date) -> date:
    """The NYSE session after ``session`` (the market-on-open fill session)."""
    return trading_days(session + timedelta(days=1), session + timedelta(days=15))[0]


def _reconcile(snapshot: Mapping | None, quantity: float) -> tuple[str, bool, float | None, str]:
    if snapshot is None:
        return "no broker record", False, None, "no broker snapshot for this order"
    status = str(snapshot.get("status", "")).lower()
    if status not in TERMINAL:
        return status or "unknown", False, None, "broker status is not terminal"
    price, filled = snapshot.get("filled_avg_price"), snapshot.get("filled_qty")
    if status != "filled":
        try:
            partial = float(filled or 0) != 0
        except (TypeError, ValueError):
            partial = True
        return (status, False, None, f"{status} after a partial fill") if partial else (status, True, None, "")
    try:
        price, filled = float(price), float(filled)
    except (TypeError, ValueError):
        return status, False, None, "filled without a numeric price and quantity"
    if not (math.isfinite(price) and price > 0):
        return status, False, None, "filled at a non-positive price"
    if not math.isclose(filled, quantity, rel_tol=1e-9, abs_tol=1e-9):
        return status, False, price, f"filled {filled:g} of {quantity:g}"
    return status, True, price, ""


def evidence_rows(runs: Iterable[Mapping], snapshots: Mapping[str, Mapping],
                  histories: Mapping[str, pd.DataFrame], split_sessions: Mapping[str, Iterable],
                  config: CostConfig | None = None) -> list[OrderRow]:
    """One ``OrderRow`` per sent order in submit runs, in input order."""
    config = CostConfig() if config is None else config
    rows = []
    for run in runs:
        if not qualifying_run(run):
            continue
        decided = date.fromisoformat(run["session"])
        filled_on = next_session(decided)
        for action in run.get("actions", []):
            outcome = action.get("outcome")
            if outcome not in SENT_OUTCOMES:  # never reached the broker: shown, nothing to reconcile
                rows.append(OrderRow(run["profile"], decided, filled_on, action.get("ticker", "-"), "-",
                                     abs(float(action.get("delta_quantity") or 0.0)), action.get("client_order_id", "-"),
                                     math.nan, f"not sent: {outcome}", True, None, None, None, None,
                                     str(action.get("reason", ""))))
                continue
            ticker, delta = action["ticker"], float(action["delta_quantity"])
            quantity = abs(delta)
            sign = 1.0 if delta > 0 else -1.0
            status, reconciled, fill, note = _reconcile(snapshots.get(action["client_order_id"]), quantity)
            history = histories.get(ticker)
            open_price = realized = modeled = None
            notes = [note] if note else []
            if history is None:
                notes.append("no price history")
            else:
                stamp = pd.Timestamp(filled_on)
                if stamp in history.index and math.isfinite(float(history.at[stamp, "Open"])):
                    open_price = float(history.at[stamp, "Open"])
                    if fill is not None:
                        realized = sign * (fill - open_price) / open_price
                else:
                    notes.append(f"no open for {filled_on}")
                try:
                    modeled = estimate_fill_cost(history, as_of=pd.Timestamp(decided), quantity=quantity,
                                                 config=config, split_sessions=split_sessions.get(ticker, ())).total
                except CostUnavailable as refusal:
                    notes.append(f"model refused: {refusal.reason}")
            rows.append(OrderRow(run["profile"], decided, filled_on, ticker, "buy" if sign > 0 else "sell", quantity,
                                 action["client_order_id"], float(action["notional"]) / quantity, status, reconciled,
                                 fill, open_price, realized, modeled, "; ".join(notes)))
    return rows


def completed_sessions(runs: Iterable[Mapping]) -> dict[str, list[date]]:
    """Distinct decision sessions with a submit run, per profile, ascending."""
    seen: dict[str, set[date]] = {}
    for run in runs:
        if qualifying_run(run) and run.get("profile"):
            seen.setdefault(run["profile"], set()).add(date.fromisoformat(run["session"]))
    return {profile: sorted(sessions) for profile, sessions in seen.items()}


def verdict(rows: list[OrderRow], sessions: Mapping[str, list[date]],
            profiles: tuple[str, ...] = REQUIRED_PROFILES, minimum: int = MIN_SESSIONS) -> tuple[bool, list[str]]:
    """(passed, reasons). Passed only with ``minimum`` sessions per profile and every row reconciled."""
    reasons = [f"{p}: {len(sessions.get(p, []))} of {minimum} completed sessions"
               for p in profiles if len(sessions.get(p, [])) < minimum]
    reasons += [f"{p}: no filled order" for p in profiles
                if not any(r.profile == p and r.fill_price is not None and r.reconciled for r in rows)]
    reasons += [f"{r.profile} {r.client_order_id}: not reconciled ({r.status}; {r.note})" for r in rows if not r.reconciled]
    reasons += [f"{r.profile} {r.client_order_id}: fill without both costs ({r.note})" for r in rows
                if r.fill_price is not None and (r.realized_cost is None or r.modeled_cost is None)]
    return not reasons, reasons


def _fmt(value: float | None, spec: str) -> str:
    return "n/a" if value is None or (isinstance(value, float) and math.isnan(value)) else format(value, spec)


def render(rows: list[OrderRow], sessions: Mapping[str, list[date]], *, inputs: Mapping[str, str],
           clock: Callable[[], datetime], commit: str = "unknown") -> str:
    """The report text: provenance, per-order table, sessions, verdict, limitations (Rules 11, 16)."""
    run_at = clock()
    if run_at.tzinfo is None:
        raise ValueError("clock must return a timezone-aware datetime")
    passed, reasons = verdict(rows, sessions)
    lines = ["# PAPER evidence (spec 059 FR-005, SCOPE §11.3 item 4)", DISCLOSURE,
             f"run (UTC): {run_at.astimezone(timezone.utc):%Y-%m-%d %H:%M:%S}Z", f"commit: {commit}"]
    lines += [f"input: {name} sha256={digest}" for name, digest in sorted(inputs.items())]
    lines += ["", "profile | decided | filled | ticker | side | qty | intended | fill | open | realized | modeled | status | reconciled | note"]
    lines += [" | ".join([str(r.profile), str(r.decision_session), str(r.fill_session), r.ticker, r.side, f"{r.quantity:g}",
                          _fmt(r.intended_price, ".4f"), _fmt(r.fill_price, ".4f"), _fmt(r.open_price, ".4f"),
                          _fmt(r.realized_cost, ".6f"), _fmt(r.modeled_cost, ".6f"), r.status,
                          "yes" if r.reconciled else "NO", r.note or "-"]) for r in rows]
    lines += ["", "completed submit sessions:"]
    lines += [f"- {p}: {len(sessions.get(p, []))}" for p in sorted(set(REQUIRED_PROFILES) | set(sessions))]
    lines += ["", "PAPER EVIDENCE: PASS" if passed else "PAPER EVIDENCE: NOT PASSED"]
    lines += [f"- {reason}" for reason in reasons]
    lines += ["", "Limitations (docs/SCOPE-V1.md §6):"] + [f"- {item}" for item in LIMITATIONS]
    return "\n".join(lines) + "\n"


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _history(path: Path, volume_basis: str) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col="Date", parse_dates=["Date"])
    frame.attrs["volume_basis"] = volume_basis
    return frame


def main(argv: list[str] | None = None) -> int:
    """Print the report; exit 0 only on PASS."""
    parser = argparse.ArgumentParser(description="PAPER evidence report (offline)")
    parser.add_argument("--runs", type=Path, action="append", required=True, help="paper loop runs.jsonl; repeat per profile")
    parser.add_argument("--fills", type=Path, required=True, help="broker order snapshots JSONL keyed by client_order_id")
    parser.add_argument("--history-dir", type=Path, required=True, help="<TICKER>.csv with Date,Open,High,Low,Close,Volume")
    parser.add_argument("--volume-basis", required=True, choices=sorted({"nominal_reconstructed", "provider_nominal"}))
    parser.add_argument("--splits", type=Path, help="JSON {ticker: [split session, ...]}")
    args = parser.parse_args(argv)
    runs = [record for path in args.runs for record in _jsonl(path)]
    snapshots = {row["client_order_id"]: row for row in _jsonl(args.fills)}
    tickers = {a["ticker"] for r in runs for a in r.get("actions", [])}
    csvs = {t: args.history_dir / f"{t}.csv" for t in sorted(tickers) if (args.history_dir / f"{t}.csv").exists()}
    histories = {t: _history(path, args.volume_basis) for t, path in csvs.items()}
    splits = json.loads(args.splits.read_text(encoding="utf-8")) if args.splits else {}
    sources = [*args.runs, args.fills, *csvs.values(), *([args.splits] if args.splits else [])]
    inputs = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    rows = evidence_rows(runs, snapshots, histories, splits)
    sessions = completed_sessions(runs)
    commit = source_identity(ROOT)["git_sha"] or "unknown"
    sys.stdout.write(render(rows, sessions, inputs=inputs, clock=lambda: datetime.now(timezone.utc), commit=commit))
    return 0 if verdict(rows, sessions)[0] else 1


if __name__ == "__main__":
    sys.exit(main())
