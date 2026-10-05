"""Daily paper-trading loop (spec 049). Read line by line (Rule 7).

One run, before the open on a trading day:

1. Reconcile: every open safety-gate reservation is looked up at the broker
   by client order ID; a terminal one is released. Unknown stays open.
2. Data: free daily bars (``data.download_market_data``) through the last
   completed session. The run aborts unless that session is exactly the
   previous NYSE session, so a missing bar can never produce a stale trade.
3. Decide: ``paper_targets.plan_next_open`` (trend state, spec 017 sizing).
4. Act: each order goes through ``order_gateway.submit_order`` with a fresh
   broker snapshot, sells first. Without ``--submit`` nothing reaches the
   broker and the gate reserves nothing.
5. Log: one JSON line per run under ``data/live_safety/paper-runs/``.

Paper only (``alpaca_paper.PAPER_BASE_URL``). Orders are market-on-open, the
same next-open fill the backtest assumes, so the run refuses to submit while
the market is open. Nothing this loop produces is a performance result
(Rules 11, 15, 16); it is the spec 049 mechanics prototype.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "exec"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pandas as pd  # noqa: E402

from alpaca_paper import (  # noqa: E402
    TERMINAL_STATUSES,
    AlpacaPaperClient,
    BrokerError,
    SubmissionUnknown,
)
from data import download_market_data, trading_days  # noqa: E402
from live_safety_gate import LiveSafetyGate, OrderIntent, SafetyConfig, new_client_order_id  # noqa: E402
from order_gateway import OrderDeniedError, submit_order  # noqa: E402
from paper_targets import close_panel, plan_next_open  # noqa: E402

NY = ZoneInfo("America/New_York")
UNIVERSE = ("AAPL", "AMZN", "GOOGL", "MSFT", "NVDA")
GATE_DB = ROOT / "data" / "live_safety" / "paper-gate.sqlite"
RUN_LOG_DIR = ROOT / "data" / "live_safety" / "paper-runs"
# Conservative executable price for the gate: last close plus an overnight
# gap allowance. A larger gap than this is not caught by the reservation math.
GAP_ALLOWANCE = 0.05

# Camden's provisional limits, ADR 0002 item 5 (2026-09-29). Configuration,
# not results. Moves to the private companion repo at the ADR 0001 split.
PAPER_SAFETY_CONFIG = SafetyConfig(
    version="2026-09-29-v1",
    max_position_pct=0.10,
    max_gross_pct=0.60,
    daily_loss_pct=0.02,
    rolling_drawdown_pct=0.08,
    rolling_window_sessions=63,
    max_snapshot_age_seconds=60,
    max_clock_skew_seconds=5,
)


class OfflineClient:
    """No-network stand-in for a dry run before credentials exist.

    $100,000 of equity, no positions, the clock set to ``now`` with the market
    closed. It cannot submit. Its numbers are placeholders, not an account.
    """

    def __init__(self, now: datetime) -> None:
        self._now = now

    def clock(self) -> dict:
        return {"timestamp": self._now.isoformat(), "is_open": False}

    def account(self) -> dict:
        return {"equity": "100000", "status": "ACTIVE"}

    def positions(self) -> dict:
        return {}


class RunAborted(RuntimeError):
    """The run stopped before acting. The reason is in the message."""


def parse_broker_time(text: str) -> datetime:
    """Alpaca RFC 3339 timestamp to an aware datetime (nanoseconds dropped)."""
    head, sep, tail = text.partition(".")
    if sep:
        n = 0
        while n < len(tail) and tail[n].isdigit():
            n += 1
        digits, zone = tail[:n], tail[n:]
        text = f"{head}.{digits[:6]}{zone}"
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("broker timestamp has no zone.")
    return value


def previous_session(today: date) -> date:
    """The last NYSE session strictly before ``today``."""
    sessions = trading_days(today - timedelta(days=10), today - timedelta(days=1))
    if not sessions:
        raise RunAborted("no NYSE session in the 10 days before today.")
    return sessions[-1]


def load_env_file(path: Path, environ: dict) -> None:
    """KEY=VALUE lines into ``environ`` without overwriting. Values never echoed."""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def reconcile_pending(gate: Any, client: Any, now: datetime) -> list[dict]:
    """Release reservations the broker reports terminal. Unknown stays open."""
    report = []
    for row in gate.pending_orders():
        if row["terminal"]:
            continue
        status = client.order_status(row["client_order_id"])
        if status in TERMINAL_STATUSES:
            gate.record_order_outcome(row["client_order_id"], terminal=True, reason=status, now=now)
        report.append({"client_order_id": row["client_order_id"], "broker_status": status})
    return report


def run_once(
    *,
    client: Any,
    gate: Any,
    closes: pd.DataFrame,
    submit: bool,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict:
    """One loop iteration. Returns the run record; raises ``RunAborted``."""
    clock = client.clock()
    broker_now = parse_broker_time(clock["timestamp"])
    today = broker_now.astimezone(NY).date()
    if submit and clock.get("is_open"):
        raise RunAborted("market is open; market-on-open orders must be sent before the open.")

    reconciliation = reconcile_pending(gate, client, now_fn()) if submit else []

    expected = previous_session(today)
    completed = closes.loc[closes.index < pd.Timestamp(today)]
    if completed.empty:
        raise RunAborted("no completed session in the price panel.")
    session = completed.index[-1]
    if session.date() != expected:
        raise RunAborted(f"last completed bar is {session.date()}, expected {expected}; data is stale.")

    account = client.account()
    equity = float(account["equity"])
    positions = client.positions()
    decision, orders = plan_next_open(
        completed, session, equity=equity, positions=positions, entries_halted=False
    )
    last = completed.loc[session]
    gate_prices = {t: float(last[t]) * (1.0 + GAP_ALLOWANCE) for t in completed.columns if pd.notna(last[t])}

    actions = []
    for order in orders:
        record = {"ticker": order.ticker, "delta_quantity": order.delta_quantity, "target_weight": order.target_weight}
        if not submit:
            actions.append({**record, "outcome": "DRY_RUN"})
            continue
        intent = OrderIntent(new_client_order_id(), order.ticker, order.delta_quantity)
        record["client_order_id"] = intent.client_order_id
        snapshot = client.snapshot(gate_prices, parse_time=parse_broker_time)
        try:
            submit_order(gate, snapshot=snapshot, intent=intent, now=now_fn(), submit=client.submit_market_on_open)
            record["outcome"] = "SUBMITTED"
        except OrderDeniedError as exc:
            record.update(outcome="DENIED", reason=exc.decision.reason)
        except SubmissionUnknown as exc:
            record.update(outcome="UNKNOWN", reason=str(exc))  # reservation stays open
        except BrokerError as exc:
            gate.record_order_outcome(intent.client_order_id, terminal=True, reason="BROKER_REFUSED", now=now_fn())
            record.update(outcome="REFUSED", reason=str(exc))
        actions.append(record)

    return {
        "run_at_utc": now_fn().isoformat(),
        "mode": "submit" if submit else "dry_run",
        "session": str(session.date()),
        "equity": equity,
        "safety_config_version": PAPER_SAFETY_CONFIG.version,
        "reconciliation": reconciliation,
        "decision": json.loads(decision.to_json(orient="index")),
        "actions": actions,
        "disclosure": "Paper mechanics prototype. Not a performance result (SCOPE §6; spec 049).",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--submit", action="store_true", help="send orders to Alpaca paper")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--offline", action="store_true", help="dry run with no broker and no credentials")
    parser.add_argument("--period", default="2y")
    args = parser.parse_args(argv)
    if args.offline and args.submit:
        parser.error("--offline cannot --submit")

    if args.offline:
        client: Any = OfflineClient(datetime.now(timezone.utc))
    else:
        if args.env_file.exists():
            load_env_file(args.env_file, os.environ)  # type: ignore[arg-type]
        client = AlpacaPaperClient()
    closes = close_panel(download_market_data(list(UNIVERSE), period=args.period, force_refresh=True))
    GATE_DB.parent.mkdir(parents=True, exist_ok=True)
    gate = LiveSafetyGate(GATE_DB, PAPER_SAFETY_CONFIG)
    try:
        record = run_once(client=client, gate=gate, closes=closes, submit=args.submit)
    except RunAborted as exc:
        record = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "aborted": str(exc)}
    finally:
        gate.close()
    RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (RUN_LOG_DIR / "runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    print(json.dumps({k: record[k] for k in record if k != "decision"}, indent=2, default=str))
    return 1 if "aborted" in record else 0


if __name__ == "__main__":
    raise SystemExit(main())
