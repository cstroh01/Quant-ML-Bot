"""Daily paper-trading loop (spec 049). Read line by line (Rule 7).

One run, before the open on a trading day:

1. Reconcile: every open safety-gate reservation is looked up at the broker
   by client order ID; a terminal one is released. Unknown stays open.
2. Data: Alpaca raw SIP daily bars for the 8 spec 059 sleeves (spec 056's
   primary source; spec 059 D-9) through the last completed session. The run
   aborts unless that session is exactly the previous NYSE session, so a
   missing bar can never produce a stale trade, and aborts on a one-day move
   larger than ``MAX_DAILY_LOG_MOVE`` (an unadjusted split would size wrongly).
3. Decide: ``paper_targets.plan_allocation`` (spec 061; no edge claimed),
   held between monthly decisions. ``plan_next_open`` (the spec 049 trend
   prototype) remains as ``TrendPlanner`` for its tests.
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
import hashlib
import json
import os
import shlex
import subprocess
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

from data_sources import SourceFetchError  # noqa: E402
from source_diagnostics import DiagnosticAlpacaDailyBars as AlpacaDailyBars  # noqa: E402
from allocation_policy import DISCLOSURE as ALLOCATION_DISCLOSURE, policy_evidence  # noqa: E402
from alpaca_paper import (  # noqa: E402
    TERMINAL_STATUSES,
    AlpacaPaperClient,
    BrokerError,
    SubmissionUnknown,
)
from data import trading_days  # noqa: E402
from live_safety_gate import LiveSafetyGate, OrderIntent, SafetyConfig  # noqa: E402
from order_gateway import OrderDeniedError, submit_order  # noqa: E402
from paper_targets import plan_allocation, plan_next_open  # noqa: E402
from signals import ALLOCATION_SLEEVES  # noqa: E402
from mode_config import BuyRequest, ModeProfile, bound_buys, load_profiles  # noqa: E402
from ops_runtime import client_order_id, open_intents, record_intent, require_storage_identifier  # noqa: E402

NY = ZoneInfo("America/New_York")
UNIVERSE = ("AAPL", "AMZN", "GOOGL", "MSFT", "NVDA")  # spec 049 trend prototype only (TrendPlanner)
# Spec 059 D-9: years of bars per sleeve; the 60-session EWMA's weight beyond ~500 sessions is < 1e-6.
HISTORY_DAYS = 3 * 365
# A larger one-day close-to-close move is treated as an unadjusted split or a bad print: refuse.
MAX_DAILY_LOG_MOVE = 0.25
ALLOCATION_STATE = "allocation-state.json"
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

# Spec 059 allocation limits (Camden, chat, 2026-10-14 23:32 CT: "alloc config yes", accepting the
# proposed values). The 2026-09-29 limits deny the allocation: inverse-vol puts ~20-35% in TIP/IEF and
# gross runs to 0.95. Position 0.40 covers the largest bond sleeve; gross 1.00 is the allocation's own
# cap; daily loss 0.03 and a 0.15 / 63-session drawdown fit a 10%-vol book (2% fires on ordinary stress
# days, 8% would latch in the 2020/2022 replays). Configuration, not results. Camden-owned (Rule 7a).
ALLOCATION_SAFETY_CONFIG = SafetyConfig(
    version="2026-10-14-alloc-v1",
    max_position_pct=0.40,
    max_gross_pct=1.00,
    daily_loss_pct=0.03,
    rolling_drawdown_pct=0.15,
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

    def fractionable(self, symbol: str) -> bool:
        return True


@dataclasses.dataclass(frozen=True)
class Durable:
    """Spec 055 F03: where order intents live and how to make them durable before each send.

    ``persist`` must leave the intents log AND the gate's reservations durable off this machine
    (the workflow pushes the state branch) or raise; nothing is sent until it returns.
    """

    intents_dir: Path
    persist: Callable[[], None]


class PersistFailed(RuntimeError):
    """State could not be made durable; the order was not sent."""


class RunAborted(RuntimeError):
    """The run stopped before acting. The reason is in the message."""


@dataclasses.dataclass(frozen=True)
class Plan:
    """What a planner wants at the next open: the decision record, the orders, and for the
    allocation the decision session they serve (``pending`` until fully executed)."""

    decision: pd.DataFrame
    orders: list
    fractionable: Mapping[str, bool]
    decision_session: str | None = None
    pending: bool = False
    deferred: bool = False  # buys held back until this run's sells fill: the decision is not done
    allocation: dict | None = None


class TrendPlanner:
    """The spec 049 mechanics prototype (trend state, spec 017 sizing). Whole shares; nothing to record."""

    def plan(self, closes: pd.DataFrame, session: pd.Timestamp, *, equity: float, positions: dict) -> Plan:
        decision, orders = plan_next_open(closes, session, equity=equity, positions=positions, entries_halted=False)
        return Plan(decision, orders, {})

    def complete(self, decision_session: str) -> None:
        return None


class AllocationPlanner:
    """Spec 059 FR-004: trade the preregistered allocation, held between monthly decisions.

    The last fully executed decision session lives in ``state_path`` (inside the profile's durable
    state folder), so a decision is traded once and a partly executed one is finished next run.
    """

    def __init__(self, state_path: Path, fractionable: Mapping[str, bool]) -> None:
        self.state_path = Path(state_path)
        self.fractionable = dict(fractionable)

    def executed_decision(self) -> str | None:
        if not self.state_path.exists():
            return None
        try:
            saved = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(saved, dict) or saved.get("allocation") != policy_evidence():
                raise RunAborted("allocation policy mismatch; inspect existing state before trading; do not delete it")
            value = saved["executed_decision"]
        except (ValueError, KeyError, TypeError) as exc:
            raise RunAborted(f"allocation state {self.state_path.name} is unreadable ({type(exc).__name__}); "
                             "inspect it before trading") from None
        if not isinstance(value, str) or not value:
            raise RunAborted(f"allocation state {self.state_path.name} names no decision; inspect it before trading")
        return value

    def plan(self, closes: pd.DataFrame, session: pd.Timestamp, *, equity: float, positions: dict) -> Plan:
        executed = self.executed_decision()
        try:
            decision, orders, chosen = plan_allocation(closes, session, equity=equity, positions=positions,
                                                       fractionable=self.fractionable, executed_decision=executed)
        except ValueError as exc:
            raise RunAborted(f"allocation: {exc}") from None
        return Plan(decision, orders, self.fractionable, chosen, pending=chosen is not None and chosen != executed,
                    deferred=bool(decision.attrs.get("deferred_buys")), allocation=policy_evidence())

    def complete(self, decision_session: str) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_name(self.state_path.name + ".tmp")
        temporary.write_text(json.dumps({"executed_decision": decision_session,
                                         "allocation": policy_evidence(),
                                         "recorded_at_utc": datetime.now(timezone.utc).isoformat()}),
                             encoding="utf-8")
        os.replace(temporary, self.state_path)


def fetch_sleeve_closes(now: datetime, *, key_env: str = "APCA_API_KEY_ID", secret_env: str = "APCA_API_SECRET_KEY",
                        fetcher: Any = None, symbols: tuple[str, ...] = ALLOCATION_SLEEVES) -> tuple[pd.DataFrame, list]:
    """Spec 059 D-9: raw SIP daily closes per sleeve (spec 056 adapter) and their source manifests.

    Sessions whose 16:00 New York close is at least 16 minutes before ``now`` only. Raises
    ``RunAborted`` on any fetch failure or a one-day log move above ``MAX_DAILY_LOG_MOVE``.
    """
    fetcher = fetcher if fetcher is not None else AlpacaDailyBars(key_env=key_env, secret_env=secret_env)
    end = now - timedelta(minutes=16)
    columns, manifests = {}, []
    for symbol in symbols:
        try:
            frame, manifest = fetcher.fetch(symbol, end - timedelta(days=HISTORY_DAYS), end)
        except SourceFetchError as exc:
            raise RunAborted(f"bars for {symbol}: {exc}") from None
        columns[symbol] = frame["close"].astype(float)
        manifests.append(dataclasses.asdict(manifest) if dataclasses.is_dataclass(manifest) else dict(manifest))
    closes = pd.DataFrame(columns).sort_index()
    moves = np.log(closes / closes.shift(1)).abs()
    jumps = sorted({t for t in closes.columns if (moves[t] > MAX_DAILY_LOG_MOVE).any()})
    if jumps:
        raise RunAborted(f"one-day move above {MAX_DAILY_LOG_MOVE} in {jumps}: possible unadjusted split "
                         "or bad print; verify corporate actions before trading")
    return closes, manifests


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


FILLS_LOG = "fills.jsonl"


def reconcile_pending(gate: Any, client: Any, now: datetime, fills_path: Path | None = None) -> list[dict]:
    """Release reservations the broker reports terminal. Unknown stays open.

    With ``fills_path`` (spec 059 FR-005, queue Q117), each order released here appends its broker
    snapshot (status, filled quantity and average price) as one JSONL line, the ``--fills`` input of
    ``scripts/paper_evidence.py``. The line is written before the reservation is released, so a crash
    between the two re-records the same snapshot rather than losing it; readers key by order id.
    """
    report = []
    for row in gate.pending_orders():
        if row["terminal"]:
            continue
        cid = row["client_order_id"]
        if hasattr(client, "order_snapshot"):
            snapshot = client.order_snapshot(cid)
            status = None if snapshot is None else snapshot["status"]
        else:
            snapshot, status = None, client.order_status(cid)
        recorded = False
        if status in TERMINAL_STATUSES:
            if fills_path is not None and snapshot is not None:
                fills_path.parent.mkdir(parents=True, exist_ok=True)
                with fills_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({**snapshot, "recorded_at_utc": now.isoformat()}, sort_keys=True) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                recorded = True
            gate.record_order_outcome(cid, terminal=True, reason=status, now=now)
        report.append({"client_order_id": cid, "broker_status": status, "fill_recorded": recorded})
    return report


def run_once(
    *,
    client: Any,
    gate: Any,
    closes: pd.DataFrame,
    submit: bool,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    profile: ModeProfile | None = None,
    durable: Durable | None = None,
    planner: Any = None,
    submit_before: datetime | None = None,
    evidence_scope: str = "qualifying",
) -> dict:
    """One loop iteration. Returns the run record; raises ``RunAborted``.

    Spec 055 F03: client ids are deterministic per (profile, session, ticker, side); a submit run
    refuses while any earlier reservation has no broker record (unknown exposure); a profile's
    credentials must belong to its fingerprinted account; with ``durable``, each order's intent and
    reservation are persisted before the broker sees it, and today's earlier buy intents count
    against the daily deploy cap.
    """
    if evidence_scope not in ("qualifying", "drill"):
        raise RunAborted("evidence_scope must be qualifying or drill")
    if submit:
        _check_submit_deadline(submit_before, now_fn)
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

    fills_path = durable.intents_dir / FILLS_LOG if durable is not None else None
    reconciliation = reconcile_pending(gate, client, now_fn(), fills_path) if submit else []
    if durable is not None and any(r["fill_recorded"] for r in reconciliation):
        try:
            durable.persist()
        except Exception as exc:  # noqa: BLE001 - evidence not durable: add no exposure on top of it
            raise RunAborted(f"recorded fills not persisted ({type(exc).__name__}); no new orders") from None
    unresolved = [r["client_order_id"] for r in reconciliation if r["broker_status"] is None]
    if unresolved:
        raise RunAborted(f"{len(unresolved)} unresolved reservation(s) the broker has no record of: "
                         f"{unresolved}; reconcile by hand before any new exposure.")

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
    if profile is not None and not getattr(client, "placeholder", False):
        number = str(account.get("account_number", "")).strip()
        if not number or hashlib.sha256(number.encode()).hexdigest() != profile.account_fingerprint:
            raise RunAborted(f"{profile.name}: credentials reach an account whose fingerprint does not match "
                             "the profile; refusing to trade the wrong account.")
    equity = float(account["equity"])
    positions = client.positions()
    # Spec 051: with a profile, size against the bot budget, never the broker balance.
    sizing_equity = min(profile.bot_budget_usd, equity) if profile is not None else equity
    planner = planner if planner is not None else TrendPlanner()
    plan = planner.plan(completed, session, equity=sizing_equity, positions=positions)
    decision, orders = plan.decision, plan.orders
    last = completed.loc[session]
    budget_refusals = []
    shrunk = False
    if profile is not None:
        buys = [o for o in orders if o.delta_quantity > 0]
        accepted, refused = bound_buys(
            profile, [BuyRequest(o.ticker, o.delta_quantity, float(last[o.ticker]),
                                 bool(plan.fractionable.get(o.ticker, False))) for o in buys],
            settled_cash=float(account.get("cash", 0.0)),
            deployed_today_usd=_deployed_today(durable, today), min_notional_usd=1.0)
        sized = {a.ticker: a.quantity for a in accepted}
        shrunk = any(float(sized[o.ticker]) < float(o.delta_quantity) for o in buys if o.ticker in sized)
        orders = [o for o in orders if o.delta_quantity < 0] + [
            dataclasses.replace(o, delta_quantity=sized[o.ticker]) for o in buys if o.ticker in sized]
        budget_refusals = [{"ticker": t, "outcome": "BUDGET_REFUSED", "reason": r} for t, r in refused]
    gate_prices = {t: float(last[t]) * (1.0 + GAP_ALLOWANCE) for t in completed.columns if pd.notna(last[t])}

    placeholder = bool(getattr(client, "placeholder", False))
    actions = list(budget_refusals)
    halted_by_persist = False
    for order in orders:
        record = {"ticker": order.ticker, "delta_quantity": order.delta_quantity, "target_weight": order.target_weight}
        if not submit:
            actions.append({**record, "outcome": "DRY_RUN"})
            continue
        side = "buy" if order.delta_quantity > 0 else "sell"
        owner = profile.name if profile is not None else "default"
        intent = OrderIntent(client_order_id(owner, today, order.ticker, side), order.ticker, order.delta_quantity)
        record["client_order_id"] = intent.client_order_id
        record["notional"] = abs(order.delta_quantity) * float(last[order.ticker])
        if halted_by_persist:
            record.update(outcome="NOT_SENT", reason="an earlier persist failed this run")
            actions.append(record)
            continue
        snapshot = client.snapshot(gate_prices, parse_time=parse_broker_time)
        send = _durable_send(client, durable, today, side, record["notional"], before=submit_before, now_fn=now_fn)
        try:
            submit_order(gate, snapshot=snapshot, intent=intent, now=now_fn(), submit=send)
            record["outcome"] = "SUBMITTED"
        except RunAborted:
            gate.record_order_outcome(intent.client_order_id, terminal=True, reason="NOT_SENT_CUTOFF", now=now_fn())
            raise
        except PersistFailed as exc:
            gate.record_order_outcome(intent.client_order_id, terminal=True, reason="NOT_SENT_PERSIST_FAILED",
                                      now=now_fn())
            record.update(outcome="NOT_SENT", reason=str(exc))
            halted_by_persist = True
        except OrderDeniedError as exc:
            record.update(outcome="DENIED", reason=exc.decision.reason)
        except SubmissionUnknown as exc:
            record.update(outcome="UNKNOWN", reason=str(exc))  # reservation stays open
        except BrokerError as exc:
            gate.record_order_outcome(intent.client_order_id, terminal=True, reason="BROKER_REFUSED", now=now_fn())
            record.update(outcome="REFUSED", reason=str(exc))
        actions.append(record)

    # Spec 059: a decision is executed only when every order it needed was sent and none was shrunk.
    executed = None
    if submit and plan.pending and not plan.deferred and not shrunk and all(a.get("outcome") == "SUBMITTED" for a in actions):
        planner.complete(plan.decision_session)
        executed = plan.decision_session
        if durable is not None:
            try:
                durable.persist()
            except Exception as exc:  # noqa: BLE001 - orders are already sent; report, never resend
                executed = f"{plan.decision_session} (state persist failed: {type(exc).__name__})"

    return {
        "run_at_utc": now_fn().isoformat(),
        "mode": "offline_example" if placeholder else ("submit" if submit else "dry_run"),
        "equity_source": "placeholder, not an account" if placeholder else "broker",
        "session": str(session.date()),
        "equity": equity,
        "safety_config_version": getattr(getattr(gate, "_config", None), "version", None),
        "profile": profile.name if profile is not None else None,
        "reconciliation": reconciliation,
        "decision": json.loads(decision.to_json(orient="index")),
        "decision_session": plan.decision_session,
        "decision_executed": executed,
        "allocation": plan.allocation,
        "evidence_scope": evidence_scope,
        "actions": actions,
        "disclosure": (ALLOCATION_DISCLOSURE if plan.allocation else
                       "Paper mechanics prototype. Not a performance result (SCOPE §6; spec 049)."),
    }


def _deployed_today(durable: Durable | None, today: date) -> float:
    """Buy notional already recorded for ``today`` by earlier invocations (sent or not: conservative)."""
    if durable is None:
        return 0.0
    return sum(float(row["intent"].get("notional", 0.0)) for row in open_intents(durable.intents_dir)
               if row["intent"].get("session") == today.isoformat() and row["intent"].get("side") == "buy")


def _check_submit_deadline(before: datetime | None, now_fn: Callable[[], datetime]) -> None:
    if before is None:
        return
    now = now_fn()
    if before.utcoffset() is None or now.utcoffset() is None:
        raise RunAborted("supervised submission cutoff and clock must be timezone-aware")
    if now >= before:
        raise RunAborted("supervised submission cutoff reached; no order sent")


def _durable_send(client: Any, durable: Durable | None, today: date, side: str, notional: float,
                  *, before: datetime | None = None, now_fn: Callable[[], datetime] | None = None):
    """The gateway's submit callable: record the intent, persist, and only then call the broker.

    Runs after the gate has reserved the order (``submit_order`` calls it only on ALLOW), so the
    persisted state holds both the reservation and the intent before the broker sees anything.
    """
    clock = now_fn or (lambda: datetime.now(timezone.utc))
    if before is not None and before.utcoffset() is None:
        raise RunAborted("supervised submission cutoff must be timezone-aware")
    def send(intent: OrderIntent):
        _check_submit_deadline(before, clock)
        if durable is not None:
            record_intent(durable.intents_dir, intent.client_order_id,
                          {"session": today.isoformat(), "ticker": intent.instrument, "side": side,
                           "qty": abs(float(intent.delta_quantity)), "notional": notional})
            try:
                durable.persist()
            except Exception as exc:  # noqa: BLE001 - any persist failure means "do not send"
                raise PersistFailed(f"state not persisted ({type(exc).__name__}); order not sent") from None
        _check_submit_deadline(before, clock)
        return client.submit_market_on_open(intent)
    return send


def persist_command(command: str) -> Callable[[], None]:
    """A ``Durable.persist`` that runs ``command`` (e.g. ops/persist_state.sh) and raises on non-zero."""
    def persist() -> None:
        result = subprocess.run(shlex.split(command), capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"persist command exited {result.returncode}")
    return persist


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
    root = ROOT / "data" / "live_safety"
    try:
        namespace = require_storage_identifier(profile.log_namespace, "log_namespace")
    except ValueError as exc:
        raise RunAborted(f"{profile.name}: {exc}") from None
    base = root / namespace
    # The root itself may be a link (the workflow links data/live_safety to durable state); the profile
    # folder may not: a symlink or junction to a sibling would make two profiles share one gate DB.
    if base.resolve() != root.resolve() / namespace:
        raise RunAborted(f"{profile.name}: log_namespace resolves to {base.resolve()}, "
                         f"not {root.resolve() / namespace}; refusing a redirected state folder")
    # Nor may either leaf: a link on the DB file or run-log dir would send writes into a sibling profile.
    gate, runs = base / "paper-gate.sqlite", base / "paper-runs"
    if gate.resolve() != base.resolve() / gate.name:
        raise RunAborted(f"{profile.name}: paper-gate.sqlite resolves to {gate.resolve()}; refusing a redirected gate DB")
    if runs.resolve() != base.resolve() / runs.name:
        raise RunAborted(f"{profile.name}: paper-runs resolves to {runs.resolve()}; refusing a redirected run log")
    return gate, runs


def profile_credential_names(profile: ModeProfile) -> tuple[str, str]:
    """The env names (never values) of this profile's one *_KEY_ID and one *_SECRET."""
    key = [r for r in profile.credential_refs if r.endswith("_KEY_ID")]
    secret = [r for r in profile.credential_refs if r.endswith("_SECRET")]
    if len(key) != 1 or len(secret) != 1:
        raise RunAborted(f"{profile.name}: credential_refs must name one *_KEY_ID and one *_SECRET")
    return key[0], secret[0]


def profile_environ(profile: ModeProfile, environ: Any) -> dict:
    """Alpaca credentials for this profile only, taken from the env names it lists."""
    key, secret = profile_credential_names(profile)
    return {"APCA_API_KEY_ID": environ.get(key, ""), "APCA_API_SECRET_KEY": environ.get(secret, "")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--submit", action="store_true", help="send orders to Alpaca paper")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--offline", action="store_true", help="dry run with no broker and no credentials")
    parser.add_argument("--period", default="2y", help="ignored since spec 059 D-9 (kept for old invocations)")
    parser.add_argument("--profile", help="spec 051 PAPER profile name (requires --profiles-file)")
    parser.add_argument("--profiles-file", type=Path, help="private JSON list of spec 051 profiles")
    parser.add_argument("--persist-command",
                        help="spec 055 F03: run before each broker send to make intents and reservations durable")
    args = parser.parse_args(argv)
    if args.offline and args.submit:
        parser.error("--offline cannot --submit")
    raw_deadline = os.environ.get("QMB_INITIAL_SUBMIT_BEFORE")
    try:
        deadline = datetime.fromisoformat(raw_deadline.replace("Z", "+00:00")) if raw_deadline else None
    except ValueError:
        raise RunAborted("invalid supervised submission cutoff") from None
    if args.submit:
        _check_submit_deadline(deadline, lambda: datetime.now(timezone.utc))
    evidence_scope = os.environ.get("QMB_EVIDENCE_SCOPE", "qualifying")

    profile = load_paper_profile(args.profiles_file, args.profile) if args.profile else None
    if args.submit and profile is not None and not args.persist_command:
        raise RunAborted("--submit with --profile requires --persist-command (spec 055 F03)")  # before any network
    gate_db, run_log_dir = state_paths(profile)
    if args.offline:
        client: Any = OfflineClient(datetime.now(timezone.utc))
    else:
        if args.env_file.exists():
            load_env_file(args.env_file, os.environ)  # type: ignore[arg-type]
        client = AlpacaPaperClient(environ=profile_environ(profile, os.environ)) if profile else AlpacaPaperClient()
    gate_db.parent.mkdir(parents=True, exist_ok=True)
    gate = LiveSafetyGate(gate_db, ALLOCATION_SAFETY_CONFIG)  # main() trades only the spec 059 allocation
    manifests: list = []
    try:
        keys = profile_credential_names(profile) if profile else ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")
        closes, manifests = fetch_sleeve_closes(datetime.now(timezone.utc), key_env=keys[0], secret_env=keys[1])
        planner = AllocationPlanner(gate_db.parent / ALLOCATION_STATE,
                                    {s: bool(client.fractionable(s)) for s in ALLOCATION_SLEEVES})
        durable = (Durable(intents_dir=gate_db.parent, persist=persist_command(args.persist_command))
                   if args.persist_command else None)
        record = run_once(client=client, gate=gate, closes=closes, submit=args.submit, profile=profile,
                          durable=durable, planner=planner, submit_before=deadline, evidence_scope=evidence_scope)
        record["sources"] = manifests
    except (RunAborted, BrokerError) as exc:
        record = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "aborted": str(exc), "sources": manifests}
    finally:
        gate.close()
    run_log_dir.mkdir(parents=True, exist_ok=True)
    with (run_log_dir / "runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    print(json.dumps({k: record[k] for k in record if k != "decision"}, indent=2, default=str))
    return 1 if "aborted" in record else 0


if __name__ == "__main__":
    raise SystemExit(main())
