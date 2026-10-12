"""Queue Q112 / spec 059 FR-005: the PAPER evidence report.

Recorded fixtures only: synthetic seeded OHLCV, fake run records and fake broker snapshots, no
network. Rule 1: the modeled cost reads bars through the decision session only. Rule 5: the fill
session is the next NYSE session (weekend and holiday gaps). Rule 12: in-memory mutants via
``mutation_support_019.killed``, each after a clean control. EXAMPLE — NOT A RESULT.
"""
from datetime import date, datetime, timezone
import json

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401
from cost_model import CostConfig, estimate_fill_cost
from data import trading_days
from mutation_support_019 import killed
import paper_evidence as pe

SESSIONS = pd.DatetimeIndex(trading_days(date(2026, 6, 1), date(2026, 9, 30)))
DECIDED = date(2026, 9, 4)  # Friday; the fill session is Tuesday 2026-09-08 (Labor Day is a holiday)
FILLED = date(2026, 9, 8)
CLOCK = lambda: datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)  # noqa: E731


def history(seed=7):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, .01, len(SESSIONS))))
    open_ = close * np.exp(rng.normal(0, .004, len(SESSIONS)))
    high = np.maximum(open_, close) * (1 + rng.uniform(.001, .01, len(SESSIONS)))
    low = np.minimum(open_, close) * (1 - rng.uniform(.001, .01, len(SESSIONS)))
    frame = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                          "Volume": rng.uniform(1e6, 2e6, len(SESSIONS))}, index=SESSIONS)
    frame.attrs["volume_basis"] = "provider_nominal"
    return frame


def run(profile, session, actions, mode="submit"):
    return {"profile": profile, "mode": mode, "session": session.isoformat(), "actions": actions}


def sent(cid, delta, notional, ticker="SPY", outcome="SUBMITTED"):
    return {"ticker": ticker, "delta_quantity": delta, "notional": notional, "client_order_id": cid, "outcome": outcome}


def filled(price, qty):
    return {"status": "filled", "filled_avg_price": price, "filled_qty": qty}


def ten_sessions(profile):
    days = trading_days(date(2026, 8, 3), date(2026, 8, 14))
    assert len(days) == 10
    return [run(profile, d, []) for d in days]


def rows_for(actions, snapshots, hist=None):
    hist = history() if hist is None else hist
    return pe.evidence_rows([run("paper_small", DECIDED, actions)], snapshots, {"SPY": hist}, {})


def check_buy_and_sell_costs():
    hist = history()
    open_ = float(hist.at[pd.Timestamp(FILLED), "Open"])
    buy, sell = rows_for([sent("b", 3.0, 300.0), sent("s", -2.0, 200.0)],
                         {"b": filled(open_ * 1.002, 3.0), "s": filled(open_ * 0.999, 2.0)}, hist)
    assert (buy.side, buy.fill_session, buy.intended_price) == ("buy", FILLED, 100.0), "112 ROW"
    assert buy.realized_cost == pytest.approx(0.002) and sell.realized_cost == pytest.approx(0.001), \
        "112 REALIZED: adverse fraction against the fill-session open, sign by side"
    oracle = estimate_fill_cost(hist, as_of=pd.Timestamp(DECIDED), quantity=3.0, config=CostConfig(), split_sessions=())
    assert buy.modeled_cost == oracle.total, "112 MODELED: spec 046 estimate as of the decision session"
    assert buy.reconciled and sell.reconciled, "112 ROW"


def check_modeled_ignores_later_bars():
    hist = history()
    base = rows_for([sent("b", 3.0, 300.0)], {"b": filled(100.0, 3.0)}, hist)[0].modeled_cost
    later = hist.copy()
    after = later.index > pd.Timestamp(DECIDED)
    later.loc[after, ["High", "Volume"]] *= 3.0
    later.attrs = hist.attrs
    assert rows_for([sent("b", 3.0, 300.0)], {"b": filled(100.0, 3.0)}, later)[0].modeled_cost == base, \
        "112 LOOKAHEAD: bars after t change the modeled cost"
    earlier = hist.copy()
    earlier.loc[pd.Timestamp(DECIDED), "Volume"] *= 3.0
    earlier.attrs = hist.attrs
    assert rows_for([sent("b", 3.0, 300.0)], {"b": filled(100.0, 3.0)}, earlier)[0].modeled_cost != base, \
        "112 LOOKAHEAD: the bar at t must be read (non-vacuity)"


def check_reconciliation_rules():
    cases = {"none": None, "open": {"status": "accepted"}, "part": filled(100.0, 1.0),
             "nopx": {"status": "filled", "filled_qty": 3.0}, "cxl": {"status": "canceled"}, "ok": filled(100.0, 3.0)}
    rows = rows_for([sent(c, 3.0, 300.0) for c in cases], {c: s for c, s in cases.items() if s is not None})
    got = {r.client_order_id: r.reconciled for r in rows}
    assert got == {"none": False, "open": False, "part": False, "nopx": False, "cxl": True, "ok": True}, \
        f"112 RECONCILE {got}"
    assert {r.client_order_id: r.fill_price for r in rows}["cxl"] is None, "112 RECONCILE: canceled has no fill"


def check_pass_needs_ten_sessions_each():
    runs = ten_sessions("paper_large") + ten_sessions("paper_small")
    sessions = pe.completed_sessions(runs)
    assert pe.verdict([], sessions) == (True, []), "112 PASS: ten sessions each, nothing unreconciled"
    short = runs[:-1] + [run("paper_small", date(2026, 8, 3), [])]  # a duplicate session counts once
    passed, reasons = pe.verdict([], pe.completed_sessions(short))
    assert not passed and reasons == ["paper_small: 9 of 10 completed sessions"], f"112 PASS WITH 9 {reasons}"
    dry = runs[:-1] + [run("paper_small", date(2026, 8, 17), [], mode="dry_run")]
    assert not pe.verdict([], pe.completed_sessions(dry))[0], "112 DRY RUN: a dry run is not a completed session"


def check_unreconciled_order_blocks_pass():
    sessions = pe.completed_sessions(ten_sessions("paper_large") + ten_sessions("paper_small"))
    rows = rows_for([sent("b", 3.0, 300.0)], {"b": {"status": "accepted"}})
    passed, reasons = pe.verdict(rows, sessions)
    assert not passed and "not reconciled" in reasons[0], "112 UNRECONCILED"


def test_buy_and_sell_costs():
    check_buy_and_sell_costs()


def test_modeled_cost_reads_only_bars_through_the_decision_session():
    check_modeled_ignores_later_bars()


def test_reconciliation_rules():
    check_reconciliation_rules()


def test_pass_needs_ten_completed_sessions_per_profile():
    check_pass_needs_ten_sessions_each()


def test_an_unreconciled_order_blocks_pass():
    check_unreconciled_order_blocks_pass()


@pytest.mark.parametrize("decided, expected", [(date(2026, 9, 4), date(2026, 9, 8)),    # weekend + Labor Day
                                               (date(2026, 11, 25), date(2026, 11, 27)),  # Thanksgiving
                                               (date(2026, 9, 8), date(2026, 9, 9))])     # ordinary day
def test_fill_session_is_the_next_nyse_session(decided, expected):
    assert pe.next_session(decided) == expected


def test_only_sent_orders_in_submit_runs_are_rows():
    actions = [sent("a", 1.0, 100.0), sent("u", 1.0, 100.0, outcome="UNKNOWN"),
               sent("d", 1.0, 100.0, outcome="DENIED"), sent("r", 1.0, 100.0, outcome="REFUSED")]
    runs = [run("paper_small", DECIDED, actions), run("paper_small", DECIDED, [sent("x", 1.0, 100.0)], mode="dry_run")]
    rows = pe.evidence_rows(runs, {}, {"SPY": history()}, {})
    assert [r.client_order_id for r in rows] == ["a", "u"]


def test_model_refusal_is_reported_never_zero():
    short = history().loc[:pd.Timestamp(date(2026, 6, 15))]
    short.attrs["volume_basis"] = "provider_nominal"
    row = pe.evidence_rows([run("paper_small", date(2026, 6, 12), [sent("b", 1.0, 100.0)])],
                           {"b": filled(100.0, 1.0)}, {"SPY": short}, {})[0]
    assert row.modeled_cost is None and "model refused: warmup" in row.note


def test_render_carries_provenance_verdict_and_limitations():
    runs = ten_sessions("paper_large") + ten_sessions("paper_small")
    text = pe.render([], pe.completed_sessions(runs), inputs={"runs.jsonl": "ab" * 32}, clock=CLOCK)
    assert "input: runs.jsonl sha256=" + "ab" * 32 in text and "run (UTC): 2026-10-01 12:00:00Z" in text
    assert "PAPER EVIDENCE: PASS" in text and "Costs are modeled, not calibrated." in text
    assert "Survivorship bias." in text and "not a performance result" in text
    with pytest.raises(ValueError):
        pe.render([], {}, inputs={}, clock=lambda: datetime(2026, 10, 1))


def test_cli_end_to_end_exits_nonzero_until_pass(tmp_path, capsys):
    hist = history()
    hist.index.name = "Date"
    (tmp_path / "hist").mkdir()
    hist.to_csv(tmp_path / "hist" / "SPY.csv")
    runs = ten_sessions("paper_large") + ten_sessions("paper_small") + [run("paper_small", DECIDED, [sent("b", 3.0, 300.0)])]
    (tmp_path / "runs.jsonl").write_text("\n".join(json.dumps(r) for r in runs))
    fills = tmp_path / "fills.jsonl"
    argv = ["--runs", str(tmp_path / "runs.jsonl"), "--fills", str(fills), "--history-dir", str(tmp_path / "hist"),
            "--volume-basis", "provider_nominal"]
    fills.write_text(json.dumps({"client_order_id": "b", "status": "accepted"}))
    assert pe.main(argv) == 1 and "PAPER EVIDENCE: NOT PASSED" in capsys.readouterr().out
    fills.write_text(json.dumps({"client_order_id": "b", **filled(101.0, 3.0)}))
    assert pe.main(argv) == 0
    out = capsys.readouterr().out
    assert "PAPER EVIDENCE: PASS" in out and "| SPY | buy | 3 | 100.0000 | 101.0000 |" in out


# Rule 12 (spec 059 §5 names "paper-evidence PASS with 9 sessions"). Each is a plausible slip.
@pytest.mark.parametrize("old, new, check", [
    ("for p in profiles if len(sessions.get(p, [])) < minimum]", "for p in profiles if len(sessions.get(p, [])) < minimum - 1]",
     check_pass_needs_ten_sessions_each),
    ('if run.get("mode") == "submit" and run.get("profile"):', 'if run.get("profile"):', check_pass_needs_ten_sessions_each),
    ("as_of=pd.Timestamp(decided)", "as_of=pd.Timestamp(filled_on)", check_buy_and_sell_costs),
    ("realized = sign * (fill - open_price) / open_price", "realized = (fill - open_price) / open_price",
     check_buy_and_sell_costs),
    ("if not math.isclose(filled, quantity, rel_tol=1e-9, abs_tol=1e-9):", "if filled <= 0:", check_reconciliation_rules),
    ("    if status not in TERMINAL:", "    if not status:", check_reconciliation_rules),
    ('for r in rows if not r.reconciled]', 'for r in rows if r.status == "no broker record"]',
     check_unreconciled_order_blocks_pass),
], ids=["pass-with-9", "dry-run-counted", "model-reads-t+1", "sell-sign-dropped", "partial-fill-accepted",
        "open-status-reconciled", "verdict-skips-open-orders"])
def test_mutant_is_caught(old, new, check):
    killed(pe, old, new, check)
