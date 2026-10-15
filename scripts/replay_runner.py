"""Historical replay of the PAPER pipeline (spec 059 FR-006; SCOPE §11.3 item 5; queue Q111).

Drives ``exec/paper_loop.run_once``, the same planner, safety gate, PAPER safety config, budget
bounding, durable intents and reconciliation the cloud loop runs, with a simulated broker over the
preregistered windows 2020-02-03..2020-04-30 and calendar 2022. Opens no socket, reads no
credential, writes only into a fresh temporary state folder per window.

The simulated broker queues each order before the open of session D and fills it at D's open, the
loop's market-on-open convention; it reports positions, cash and equity marked at the previous
close, the broker truth the loop sees at 08:30 New York. Nothing here is a performance result:
this tests the code path, not real fills under stress (spec 059 §7). EXAMPLE — NOT A RESULT.

Guarantees: one record per session; any exception other than the loop's own ``RunAborted`` is
reported as an unhandled error and ends that window; every DENIED order and every gate halt is
reported; ``PASS`` only when no window has an unhandled error, an aborted session or a denial.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import date, datetime, time
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from zoneinfo import ZoneInfo

import pandas as pd

from _project import project_root
from data import trading_days

ROOT = project_root()
if str(ROOT / "exec") not in sys.path:
    sys.path.insert(0, str(ROOT / "exec"))

import paper_loop  # noqa: E402
from live_safety_gate import BrokerSnapshot, LiveSafetyGate  # noqa: E402
from mode_config import load_profiles  # noqa: E402

NY = ZoneInfo("America/New_York")
WINDOWS = ((date(2020, 2, 3), date(2020, 4, 30)), (date(2022, 1, 3), date(2022, 12, 30)))
REPLAY_ACCOUNT = "REPLAY-SIMULATED"
LABEL = "EXAMPLE — NOT A RESULT. Replay of the PAPER code path with a simulated broker; not real fills."


@dataclass
class SimulatedBroker:
    """Fills queued market orders at the next session's open; marks at the last close."""

    opens: pd.DataFrame
    closes: pd.DataFrame
    cash: float
    holdings: dict[str, float] = field(default_factory=dict)
    queued: list = field(default_factory=list)
    orders: dict[str, dict] = field(default_factory=dict)
    session: date | None = None

    def at(self, session: date) -> None:
        self.session = session

    @property
    def _stamp(self) -> datetime:
        return datetime.combine(self.session, time(8, 30), NY)

    def _mark(self) -> float:
        previous = self.closes.loc[self.closes.index < pd.Timestamp(self.session)].iloc[-1]
        return self.cash + sum(q * float(previous[t]) for t, q in self.holdings.items())

    def clock(self) -> dict:
        return {"timestamp": self._stamp.isoformat(), "is_open": False}

    def account(self) -> dict:
        return {"equity": str(self._mark()), "cash": str(self.cash), "status": "ACTIVE",
                "account_number": REPLAY_ACCOUNT}

    def positions(self) -> dict:
        return {t: q for t, q in self.holdings.items() if q}

    def fractionable(self, symbol: str) -> bool:
        return True

    def snapshot(self, prices, *, parse_time) -> BrokerSnapshot:
        return BrokerSnapshot(as_of=self._stamp, status="OK", equity=self._mark(), external_cash_flow=0.0,
                              positions=self.positions(), prices=dict(prices))

    def submit_market_on_open(self, intent) -> dict:
        self.queued.append(intent)
        self.orders[intent.client_order_id] = {"client_order_id": intent.client_order_id, "status": "accepted",
                                               "symbol": intent.instrument, "filled_qty": 0.0,
                                               "filled_avg_price": None, "filled_at": None}
        return {"id": intent.client_order_id}

    def order_snapshot(self, cid: str) -> dict | None:
        return self.orders.get(cid)

    def order_status(self, cid: str) -> str | None:
        return self.orders[cid]["status"] if cid in self.orders else None

    def open_market(self) -> None:
        """Fill every queued order at this session's open (sells first, as the loop sent them)."""
        price_row = self.opens.loc[pd.Timestamp(self.session)]
        for intent in self.queued:
            price = float(price_row[intent.instrument])
            self.holdings[intent.instrument] = self.holdings.get(intent.instrument, 0.0) + intent.delta_quantity
            self.cash -= intent.delta_quantity * price
            self.orders[intent.client_order_id].update(status="filled", filled_qty=abs(intent.delta_quantity),
                                                       filled_avg_price=price, filled_at=self._stamp.isoformat())
        self.queued = []


def replay_profile(budget: float, daily_deploy_fraction: float, name: str = "paper_replay"):
    """A PAPER profile shaped like a real one, bound to the simulated account only."""
    return load_profiles([{
        "name": name, "mode": "PAPER", "broker": "alpaca_paper",
        "account_fingerprint": hashlib.sha256(REPLAY_ACCOUNT.encode()).hexdigest(),
        "credential_refs": ["PAPER_REPLAY_KEY_ID", "PAPER_REPLAY_SECRET"], "state_dir": "state/paper_replay",
        "log_namespace": name, "bot_budget_usd": budget, "daily_deploy_fraction": daily_deploy_fraction,
        "instruments": ["etf"], "fractional": True,
        "safety_config_version": paper_loop.ALLOCATION_SAFETY_CONFIG.version}])[name]


def replay_window(opens: pd.DataFrame, closes: pd.DataFrame, start: date, end: date, *, profile,
                  config=None) -> dict:
    """Replay every NYSE session in [start, end]; returns the window's record (see module guarantees)."""
    config = config if config is not None else paper_loop.ALLOCATION_SAFETY_CONFIG
    broker = SimulatedBroker(opens=opens, closes=closes, cash=float(profile.bot_budget_usd))
    sessions = [d for d in trading_days(start, end) if pd.Timestamp(d) in closes.index]
    report = {"window": [start.isoformat(), end.isoformat()], "sessions": 0, "orders": 0, "denied": [],
              "aborted": [], "errors": [], "decisions_executed": [], "safety_config_version": config.version}
    with tempfile.TemporaryDirectory(prefix="qmb-replay-") as tmp:
        state = Path(tmp)
        gate = LiveSafetyGate(state / "gate.sqlite", config)
        planner = paper_loop.AllocationPlanner(state / paper_loop.ALLOCATION_STATE,
                                               {t: True for t in closes.columns})
        durable = paper_loop.Durable(intents_dir=state, persist=lambda: None)
        try:
            for session in sessions:
                broker.at(session)
                stamp = datetime.combine(session, time(8, 30, 1), NY)
                visible = closes.loc[closes.index < pd.Timestamp(session)]
                try:
                    record = paper_loop.run_once(client=broker, gate=gate, closes=visible, submit=True,
                                                 now_fn=lambda stamp=stamp: stamp, profile=profile,
                                                 durable=durable, planner=planner)
                except paper_loop.RunAborted as exc:
                    report["aborted"].append({"session": session.isoformat(), "reason": str(exc)})
                except Exception as exc:  # noqa: BLE001 - the point is to surface it
                    report["errors"].append({"session": session.isoformat(), "error": f"{type(exc).__name__}: {exc}"})
                    break
                else:
                    sent = [a for a in record["actions"] if a.get("outcome") == "SUBMITTED"]
                    report["orders"] += len(sent)
                    report["denied"] += [{"session": session.isoformat(), "ticker": a["ticker"], "reason": a.get("reason")}
                                         for a in record["actions"] if a.get("outcome") == "DENIED"]
                    if record.get("decision_executed"):
                        report["decisions_executed"].append(record["decision_executed"])
                report["sessions"] += 1
                try:
                    broker.open_market()
                except Exception as exc:  # noqa: BLE001 - e.g. no open price for a queued order
                    report["errors"].append({"session": session.isoformat(),
                                             "error": f"fill at open failed: {type(exc).__name__}: {exc}"})
                    break
        finally:
            gate.close()
    report["ending_equity_label"] = "simulated mark, not a result"
    return report


def verdict(windows: list[dict]) -> bool:
    return all(not w["errors"] and not w["aborted"] and not w["denied"] for w in windows)


def _panel(history_dir: Path, column: str, tickers) -> pd.DataFrame:
    frames = {t: pd.read_csv(history_dir / f"{t}.csv", index_col="Date", parse_dates=["Date"])[column] for t in tickers}
    return pd.DataFrame(frames).sort_index()


def main(argv: list[str] | None = None) -> int:
    """Print the JSON report; exit 0 only on PASS."""
    from signals import ALLOCATION_SLEEVES
    parser = argparse.ArgumentParser(description="Replay the PAPER pipeline over §11.3.5's windows (offline)")
    parser.add_argument("--history-dir", type=Path, required=True,
                        help="<TICKER>.csv with Date,Open,Close for the 8 sleeves (split-consistent prices)")
    parser.add_argument("--budget", type=float, default=5000.0)
    parser.add_argument("--daily-deploy-fraction", type=float, default=1.0)
    args = parser.parse_args(argv)
    opens = _panel(args.history_dir, "Open", ALLOCATION_SLEEVES)
    closes = _panel(args.history_dir, "Close", ALLOCATION_SLEEVES)
    profile = replay_profile(args.budget, args.daily_deploy_fraction)
    windows = [replay_window(opens, closes, s, e, profile=profile) for s, e in WINDOWS]
    passed = verdict(windows)
    print(json.dumps({"label": LABEL, "verdict": "PASS" if passed else "FAIL", "windows": windows}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
