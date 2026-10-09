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

Paper only (``alpaca_paper.PAPER_BASE_URL``). Orders are market orders queued
before the open (``time_in_force=day``), approximating the next-open fill the
backtest assumes, so the run refuses to submit while the market is open. Nothing this loop produces is a performance result
(Rules 11, 15, 16); it is the spec 049 mechanics prototype.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "exec"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402
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
from mode_config import BuyRequest, ModeProfile, bound_buys, load_profiles  # noqa: E402

NY = ZoneInfo("America/New_York")
UNIVERSE = ("AAPL", "AMZN", "GOOGL", "MSFT", "NVDA")
GATE_DB = ROOT / "data" / "live_safety" / "paper-gate.sqlite"
RUN_LOG_DIR = ROOT / "data" / "live_safety" / "paper-runs"
# Conservative executable price for the gate: last close plus an overnight
# gap allowance. A larger gap than this is not caught by the reservation math.
GAP_ALLOWANCE = 0.05
# Market-on-open orders must reach the broker before this New York time.
PRE_OPEN_CUTOFF = time(9, 28)

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

    placeholder = True

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
    profile: ModeProfile | None = None,
) -> dict:
    """One loop iteration. Returns the run record; raises ``RunAborted``."""
    clock = client.clock()
    broker_now = parse_broker_time(clock["timestamp"])
    today = broker_now.astimezone(NY).date()
    if submit:
        if clock.get("is_open"):
            raise RunAborted("market is open; market-on-open orders must be sent before the open.")
        if not trading_days(today, today):
            raise RunAborted(f"{today} is not an NYSE session; submit only on a session morning.")
        ny_time = broker_now.astimezone(NY).time()
        if ny_time >= PRE_OPEN_CUTOFF:
            raise RunAborted(f"{ny_time:%H:%M} ET is past the {PRE_OPEN_CUTOFF:%H:%M} market-on-open cutoff.")

    reconciliation = reconcile_pending(gate, client, now_fn()) if submit else []

    expected = previous_session(today)
    completed = closes.loc[closes.index < pd.Timestamp(today)]
    if completed.empty:
        raise RunAborted("no completed session in the price panel.")
    session = completed.index[-1]
    if session.date() != expected:
        raise RunAborted(f"last completed bar is {session.date()}, expected {expected}; data is stale.")
    missing = sorted(t for t in completed.columns if not np.isfinite(completed.at[session, t]))
    if missing:
        raise RunAborted(f"no close on {expected} for {', '.join(missing)}; data is incomplete.")

    account = client.account()
    equity = float(account["equity"])
    positions = client.positions()
    # Spec 051: with a profile, size against the bot budget, never the broker balance.
    sizing_equity = min(profile.bot_budget_usd, equity) if profile is not None else equity
    decision, orders = plan_next_open(
        completed, session, equity=sizing_equity, positions=positions, entries_halted=False
    )
    last = completed.loc[session]
    budget_refusals = []
    if profile is not None:
        buys = [o for o in orders if o.delta_quantity > 0]
        accepted, refused = bound_buys(
            profile, [BuyRequest(o.ticker, o.delta_quantity, float(last[o.ticker]), False) for o in buys],
            settled_cash=float(account.get("cash", 0.0)), deployed_today_usd=0.0, min_notional_usd=1.0)
        sized = {a.ticker: a.quantity for a in accepted}
        orders = [o for o in orders if o.delta_quantity < 0] + [
            dataclasses.replace(o, delta_quantity=sized[o.ticker]) for o in buys if o.ticker in sized]
        budget_refusals = [{"ticker": t, "outcome": "BUDGET_REFUSED", "reason": r} for t, r in refused]
    gate_prices = {t: float(last[t]) * (1.0 + GAP_ALLOWANCE) for t in completed.columns if pd.notna(last[t])}

    placeholder = bool(getattr(client, "placeholder", False))
    actions = list(budget_refusals)
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
        "mode": "offline_example" if placeholder else ("submit" if submit else "dry_run"),
        "equity_source": "placeholder, not an account" if placeholder else "broker",
        "session": str(session.date()),
        "equity": equity,
        "safety_config_version": PAPER_SAFETY_CONFIG.version,
        "profile": profile.name if profile is not None else None,
        "reconciliation": reconciliation,
        "decision": json.loads(decision.to_json(orient="index")),
        "actions": actions,
        "disclosure": "Paper mechanics prototype. Not a performance result (SCOPE §6; spec 049).",
    }


def load_paper_profile(path: Path | None, name: str) -> ModeProfile:
    """The named spec 051 profile; this loop only ever runs PAPER at Alpaca paper."""
    if path is None:
        raise RunAborted("--profile needs --profiles-file")
    profiles = load_profiles(json.loads(Path(path).read_text(encoding="utf-8")))
    if name not in profiles:
        raise RunAborted(f"profile {name!r} not in {path}")
    profile = profiles[name]
    if profile.mode != "PAPER" or profile.broker != "alpaca_paper":
        raise RunAborted(f"{name}: the paper loop runs PAPER alpaca_paper profiles only")
    return profile


def state_paths(profile: ModeProfile | None) -> tuple[Path, Path]:
    """Gate DB and run-log directory; namespaced per profile so profiles never share state."""
    if profile is None:
        return GATE_DB, RUN_LOG_DIR
    base = ROOT / "data" / "live_safety" / profile.log_namespace
    return base / "paper-gate.sqlite", base / "paper-runs"


def profile_environ(profile: ModeProfile, environ: Any) -> dict:
    """Alpaca credentials for this profile only, taken from the env names it lists."""
    key = [r for r in profile.credential_refs if r.endswith("_KEY_ID")]
    secret = [r for r in profile.credential_refs if r.endswith("_SECRET")]
    if len(key) != 1 or len(secret) != 1:
        raise RunAborted(f"{profile.name}: credential_refs must name one *_KEY_ID and one *_SECRET")
    return {"APCA_API_KEY_ID": environ.get(key[0], ""), "APCA_API_SECRET_KEY": environ.get(secret[0], "")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--submit", action="store_true", help="send orders to Alpaca paper")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--offline", action="store_true", help="dry run with no broker and no credentials")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--profile", help="spec 051 PAPER profile name (requires --profiles-file)")
    parser.add_argument("--profiles-file", type=Path, help="private JSON list of spec 051 profiles")
    args = parser.parse_args(argv)
    if args.offline and args.submit:
        parser.error("--offline cannot --submit")

    profile = load_paper_profile(args.profiles_file, args.profile) if args.profile else None
    gate_db, run_log_dir = state_paths(profile)
    if args.offline:
        client: Any = OfflineClient(datetime.now(timezone.utc))
    else:
        if args.env_file.exists():
            load_env_file(args.env_file, os.environ)  # type: ignore[arg-type]
        client = AlpacaPaperClient(environ=profile_environ(profile, os.environ)) if profile else AlpacaPaperClient()
    closes = close_panel(download_market_data(list(UNIVERSE), period=args.period, force_refresh=True))
    gate_db.parent.mkdir(parents=True, exist_ok=True)
    gate = LiveSafetyGate(gate_db, PAPER_SAFETY_CONFIG)
    try:
        record = run_once(client=client, gate=gate, closes=closes, submit=args.submit, profile=profile)
    except RunAborted as exc:
        record = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "aborted": str(exc)}
    finally:
        gate.close()
    run_log_dir.mkdir(parents=True, exist_ok=True)
    with (run_log_dir / "runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    print(json.dumps({k: record[k] for k in record if k != "decision"}, indent=2, default=str))
    return 1 if "aborted" in record else 0


if __name__ == "__main__":
    raise SystemExit(main())
