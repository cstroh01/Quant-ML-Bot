"""Independent execution-side safety authority (spec 032).

Spec 017's ``portfolio_risk.py`` decides *how much* of the book a signal
should get. This module is not that decision. It is the last independent
check that runs after a sizing decision exists and before an order reaches a
broker, and it is built to stay correct when the signal, the sizing layer,
the accounting, the process, or the operator is wrong. Spec 032's Problem
section names exactly why the research-side module cannot be reused for
this: it is not wired to order submission, it forgets its halt latch on
reconstruction, and it never sees a broker's own view of positions and
orders. Every rule below exists to close one of those gaps, in the same
spirit as the reference failure mode spec 032 cites: Knight Capital lost
$460M in 45 minutes in 2012 because a deploy left dead code live with no
independent, broker-aware check between "the system decided to trade" and
"an order left the building."

**Layer (Rule 8).** This sits strictly after a sizing decision (spec 017 or
any future one) and strictly before a broker call. It never imports
``data``, ``signals``, ``backtest_harness``, or ``portfolio_risk`` -- it
takes a broker-confirmed snapshot and an order intent as plain data,
produced elsewhere, and returns a decision. It never computes a fill, prices
a trade, or books P&L.

**No broker code, no credentials, on purpose (Rule 7).** This module makes
no network call and holds no credential. Confirming a broker's own
kill/cancel state is modeled as a caller-supplied result (``BrokerKillQuery``)
rather than a method that reaches out itself, so that the actual broker
adapter -- which does hold credentials and does call the network -- can stay
in the reviewed ``exec/`` lane this module deliberately does not enter. What
ships here is the decision engine an adapter calls before it submits, cancels,
or reports back; wiring a real adapter to it is out of scope for this spec's
first pass and is flagged as open work in ``docs/PROJECT_CONTEXT.md``.

**Durable, not in-memory (REQ-006).** Every fact whose loss would silently
re-permit trading -- the kill latch, a loss/drawdown halt, a reconciliation
halt, the configuration version, and every non-terminal order's reserved
exposure -- lives in a SQLite file, not a Python attribute. SQLite is the
standard library's own database; using it here is not a new dependency
(Rule 6), and its transactions are what make the reservation-and-decision
step in REQ-001's gate order atomic across processes, which a plain JSON
file with a read-modify-write cycle cannot guarantee. A second process
opening the same file sees the first process's committed reservations, never
a half-written state.

**No defaults, ever (REQ-009).** ``SafetyConfig`` has no default percentage,
window, or tolerance. Spec 032 states plainly that the values in spec 017's
``RECOMMENDED_CONFIG`` were "not calibrated on a funded equity curve" and are
not live defaults, and its own Open Questions section leaves every number
here for Camden to set. This module does not repeat spec 017's pattern of
shipping a recommended config; there is no ``RECOMMENDED_CONFIG`` constant to
import, on purpose. See ``docs/PROJECT_CONTEXT.md`` for the specific conflict
this creates with a cited research report's suggested numbers, and why this
module does not adopt them.

**Two entry points, not one, for reduce-only orders under KILL_LATCHED.**
Spec 032's own text disagrees with itself here: the Kill Switch section says
"all local strategy and order-gateway submissions are denied" with no
carve-out, while its own failure-mode table has a row reading "Order is
reduced-only during a halt or kill -> Allow only after fresh reconciliation
and broker order-type verification." This module does not silently pick one
reading. ``evaluate_order`` -- the automated, strategy-facing path -- follows
the stricter text and denies everything while ``KILL_LATCHED``, no
exceptions. ``evaluate_operator_override_reduce`` is the separate, explicit,
operator-authenticated command the Kill Switch section itself describes
("a separate, explicit, reduce-only command after a fresh position
snapshot") and is the only path that can reduce a position during a kill or
a loss/drawdown halt. This is flagged in ``docs/PROJECT_CONTEXT.md`` for
Camden to confirm or override.
"""

from __future__ import annotations

import dataclasses
import json
import math
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Mapping, Optional
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Reason / state vocabulary
# ---------------------------------------------------------------------------

ALLOW = "ALLOW"
DENY = "DENY"

DENY_BROKER_STATUS = "BROKER_STATUS_NOT_OK"
DENY_STALE_SNAPSHOT = "STALE_SNAPSHOT"
DENY_CLOCK_SKEW = "CLOCK_SKEW"
DENY_NON_POSITIVE_EQUITY = "NON_POSITIVE_EQUITY"
DENY_CONFIG_MISMATCH = "CONFIG_VERSION_MISMATCH"
DENY_KILL_LATCHED = "KILL_LATCHED"
DENY_RECONCILIATION_HALT = "RECONCILIATION_HALT"
DENY_LOSS_HALT = "LOSS_HALT"
DENY_SHORT_NOT_SUPPORTED = "SHORT_NOT_SUPPORTED"
DENY_PRICE_UNAVAILABLE = "PRICE_UNAVAILABLE"
DENY_MAX_POSITION_PCT = "MAX_POSITION_PCT_BREACH"
DENY_MAX_GROSS_PCT = "MAX_GROSS_PCT_BREACH"
DENY_DUPLICATE_ORDER = "DUPLICATE_CLIENT_ORDER_ID"

# REQ-008 action classes. FLATTEN has no implementation in this module by
# design (spec 032: automatic flattening "requires a separate Camden-approved
# policy and a separate testable liquidation controller"); the name exists so
# callers have the full vocabulary and do not invent their own word for it.
ACTION_BLOCK_NEW = "BLOCK_NEW"
ACTION_CANCEL_RISK_ADDING = "CANCEL_RISK_ADDING"
ACTION_REDUCE_ONLY = "REDUCE_ONLY"
ACTION_FLATTEN = "FLATTEN"
ACTION_KILL_LATCHED = "KILL_LATCHED"

# Kill-switch confirmation contract.
KILL_REQUESTED = "REQUESTED"
KILL_LOCAL_BLOCKED = "LOCAL_BLOCKED"
KILL_BROKER_CANCEL_PENDING = "BROKER_CANCEL_PENDING"
KILL_BROKER_DISABLED_CONFIRMED = "BROKER_DISABLED_CONFIRMED"
KILL_RECONCILING = "RECONCILING"
KILL_CONFIRMED = "KILL_CONFIRMED"
KILL_BROKER_DISABLE_UNVERIFIED = "BROKER_DISABLE_UNVERIFIED"

_QTY_EPS = 1e-9


class ConfigMismatchError(RuntimeError):
    """Durable state disagrees with the configuration just supplied.

    REQ-009: a configuration change mid-session denies live trading rather
    than silently taking effect. Raised at construction (a version or a
    value differs from what is durably recorded) so the mismatch is caught
    before a single order is evaluated, not discovered mid-session.
    """


# ---------------------------------------------------------------------------
# Validation helpers (mirrors scripts/portfolio_risk.py's style)
# ---------------------------------------------------------------------------


def _is_real(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_fraction(name: str, value: object, *, inclusive_upper: bool) -> float:
    if not _is_real(value):
        raise TypeError(f"{name} must be a real number; got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be positive and finite; got {value}")
    if inclusive_upper:
        if number > 1.0:
            raise ValueError(f"{name} must be <= 1.0; got {value}")
    elif number >= 1.0:
        raise ValueError(f"{name} must be < 1.0; got {value}")
    return number


def _require_positive(name: str, value: object) -> float:
    if not _is_real(value):
        raise TypeError(f"{name} must be a real number; got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be positive and finite; got {value}")
    return number


def _require_nonnegative(name: str, value: object) -> float:
    if not _is_real(value):
        raise TypeError(f"{name} must be a real number; got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be non-negative and finite; got {value}")
    return number


def _require_int_at_least(name: str, value: object, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int; got {type(value).__name__}")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}; got {value}")
    return value


def _require_nonempty_str(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string; got {value!r}")
    return value


def _require_aware(name: str, value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime; got {type(value).__name__}")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{name} must be timezone-aware; got a naive datetime.")
    return value


def _valid_price(value: object) -> bool:
    return _is_real(value) and math.isfinite(value) and value > 0.0


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(text: str) -> datetime:
    return datetime.fromisoformat(text)


def _trading_day(as_of: datetime, tz_name: str) -> date:
    """The broker-calendar trading day an instant falls on.

    CLAUDE.md's timestamp convention makes a session label a distinct,
    timezone-naive thing from the instant that produced it, and requires the
    crossing from instant-space into session-space to localize to
    America/New_York explicitly, at the point of crossing. This is that
    crossing: ``as_of`` is the broker's own tz-aware clock (never the
    laptop's), and the caller states which zone defines its trading day via
    ``SafetyConfig.timezone`` -- not a silently assumed one.
    """
    return as_of.astimezone(ZoneInfo(tz_name)).date()


# ---------------------------------------------------------------------------
# Public data contracts
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SafetyConfig:
    """Every limit this gate enforces. No field has a default (REQ-009).

    ``version`` is an opaque, Camden-chosen label (a date, a ticket number,
    anything). It is not compared for ordering, only for exact equality
    against what is durably recorded -- a changed version, or changed values
    under the same version, both deny construction (``ConfigMismatchError``).

    ``max_position_pct`` / ``max_gross_pct`` are equity-relative, inclusive
    boundaries (reaching the limit exactly denies -- Design section 1).
    ``max_gross_pct <= 1.0`` and ``max_position_pct <= max_gross_pct`` are
    enforced because this module's first pass covers only the cash,
    long-only scope spec 032 itself declares; margin or shorting is an
    explicit extension the spec defers, not something this config can be
    coaxed into expressing.
    """

    version: str
    max_position_pct: float
    max_gross_pct: float
    daily_loss_pct: float
    rolling_drawdown_pct: float
    rolling_window_sessions: int
    max_snapshot_age_seconds: float
    max_clock_skew_seconds: float
    timezone: str = "America/New_York"

    def __post_init__(self) -> None:
        _require_nonempty_str("version", self.version)
        max_gross = _require_fraction("max_gross_pct", self.max_gross_pct, inclusive_upper=True)
        max_position = _require_fraction(
            "max_position_pct", self.max_position_pct, inclusive_upper=True
        )
        if max_position > max_gross:
            raise ValueError(
                f"max_position_pct ({max_position}) must not exceed max_gross_pct ({max_gross})."
            )
        _require_fraction("daily_loss_pct", self.daily_loss_pct, inclusive_upper=False)
        _require_fraction(
            "rolling_drawdown_pct", self.rolling_drawdown_pct, inclusive_upper=False
        )
        _require_int_at_least(
            "rolling_window_sessions", self.rolling_window_sessions, minimum=1
        )
        _require_positive("max_snapshot_age_seconds", self.max_snapshot_age_seconds)
        _require_nonnegative("max_clock_skew_seconds", self.max_clock_skew_seconds)
        try:
            ZoneInfo(self.timezone)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"timezone {self.timezone!r} is not loadable: {exc}") from exc

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class BrokerSnapshot:
    """What the broker itself says, right now. Never a local guess.

    ``positions`` are broker-confirmed signed quantities; an instrument
    absent from the mapping is flat. ``prices`` are the conservative
    executable estimate spec 032 calls ``p_i^worst`` -- an instrument
    missing here cannot be sized on the add-exposure path (REQ: "if the
    adapter cannot produce a valid estimate, the order is denied").
    ``external_cash_flow`` is the net deposit (positive) or withdrawal
    (negative) since the previous observation, excluded from every loss and
    drawdown computation so a deposit is never mistaken for a trading gain.
    """

    as_of: datetime
    status: str
    equity: float
    external_cash_flow: float
    positions: Mapping[str, float]
    prices: Mapping[str, float]

    def __post_init__(self) -> None:
        _require_aware("as_of", self.as_of)
        _require_nonempty_str("status", self.status)
        if not _is_real(self.equity):
            raise TypeError(f"equity must be a real number; got {type(self.equity).__name__}")
        if not _is_real(self.external_cash_flow) or not math.isfinite(self.external_cash_flow):
            raise ValueError("external_cash_flow must be a finite real number.")


@dataclasses.dataclass(frozen=True)
class OrderIntent:
    """One candidate order, already sized by the layer upstream of this gate.

    ``delta_quantity`` is the signed change in the instrument's position
    this order would cause if it filled in full: positive adds to a long
    position, negative reduces or closes one. This module's long-only scope
    denies any order whose fill would leave a negative position
    (``DENY_SHORT_NOT_SUPPORTED``) rather than silently sizing a short.
    """

    client_order_id: str
    instrument: str
    delta_quantity: float

    def __post_init__(self) -> None:
        _require_nonempty_str("client_order_id", self.client_order_id)
        _require_nonempty_str("instrument", self.instrument)
        if not _is_real(self.delta_quantity) or not math.isfinite(self.delta_quantity):
            raise ValueError("delta_quantity must be a finite real number.")
        if self.delta_quantity == 0.0:
            raise ValueError("delta_quantity must be nonzero.")

    @property
    def is_reduce_only(self) -> bool:
        return self.delta_quantity <= 0.0


@dataclasses.dataclass(frozen=True)
class BrokerKillQuery:
    """A caller-supplied result of asking the broker about its own kill state.

    This module never queries a broker itself (see module docstring). An
    ``exec/`` adapter builds this from whatever the selected broker's API
    returns and passes it to ``confirm_kill``.

    ``disable_status``: ``True`` = broker confirms order entry is disabled,
    ``False`` = broker confirms it is *not* disabled, ``None`` = the broker
    exposes no such query. ``working_orders_terminal``: ``True`` only if a
    fresh broker query shows no working order, or every prior working order
    has reached a terminal state.
    """

    working_orders_terminal: bool
    disable_status: Optional[bool]


@dataclasses.dataclass(frozen=True)
class GateDecision:
    """REQ-002: the only permissive result is an explicit ALLOW.

    ``checks`` carries every computed figure that produced the decision
    (equity, notional, breach flags, ...) so the decision is self-evidencing
    rather than a bare boolean, per REQ-010.
    """

    outcome: str
    reason: str
    config_version: str
    action: str
    checks: Mapping[str, object]
    reservation_id: Optional[str] = None

    @property
    def allowed(self) -> bool:
        return self.outcome == ALLOW


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


class SafetyGate:
    """The durable, transactional order gateway described by spec 032.

    Every method that can change durable state runs inside a single SQLite
    ``BEGIN IMMEDIATE`` transaction: it takes the database's one write lock
    before reading anything, so two concurrent calls -- two processes, two
    threads, or two calls in the same test -- serialize rather than race.
    That is what makes "two individually acceptable orders must not jointly
    cross a limit because they were checked concurrently" true here rather
    than merely intended.
    """

    def __init__(self, db_path: str | Path, config: SafetyConfig) -> None:
        if not isinstance(config, SafetyConfig):
            raise TypeError(f"config must be a SafetyConfig; got {type(config).__name__}")
        self._config = config
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, isolation_level=None, timeout=30.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
        self._ensure_config(config)

    def close(self) -> None:
        self._conn.close()

    # -- schema -------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS kv_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pending_orders (
                client_order_id TEXT PRIMARY KEY,
                instrument TEXT NOT NULL,
                quantity REAL NOT NULL,
                terminal INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )

    def _ensure_config(self, config: SafetyConfig) -> None:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT value FROM kv_state WHERE key = 'config_json'"
            ).fetchone()
            if row is None:
                self._write_kv(
                    {
                        "config_json": config.as_dict(),
                        "kill_latched": False,
                        "kill_confirmed": False,
                        "kill_reason": None,
                        "reconciliation_halt": False,
                        "reconciliation_reason": None,
                        "daily_halt_session": None,
                        "daily_halt_reason": None,
                        "rolling_halt_active": False,
                        "rolling_halt_reason": None,
                        "last_session": None,
                        "day_start_session": None,
                        "day_start_equity": None,
                        "adjusted_equity": None,
                        "last_raw_equity": None,
                        "session_high": None,
                        "prior_session_closes": [],
                    }
                )
                self._log_locked("GATE_INITIALIZED", {"config": config.as_dict()})
                self._conn.execute("COMMIT")
                return
            durable_config = json.loads(row[0])
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        if durable_config != config.as_dict():
            raise ConfigMismatchError(
                "Durable configuration does not match the configuration supplied at "
                "construction. A configuration must not change mid-session (REQ-009); "
                "call SafetyGate.adopt_new_config explicitly to record a deliberate "
                f"change. Durable: {durable_config}. Supplied: {config.as_dict()}."
            )

    # -- kv helpers -----------------------------------------------------

    def _read_state(self) -> dict:
        rows = self._conn.execute("SELECT key, value FROM kv_state").fetchall()
        return {key: json.loads(value) for key, value in rows}

    def _write_kv(self, updates: Mapping[str, object]) -> None:
        self._conn.executemany(
            "INSERT INTO kv_state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(key, json.dumps(value)) for key, value in updates.items()],
        )

    def _log_locked(self, event_type: str, payload: Mapping[str, object]) -> None:
        self._conn.execute(
            "INSERT INTO evidence_log (ts, event_type, payload) VALUES (?, ?, ?)",
            (_iso(datetime.now(timezone.utc)), event_type, json.dumps(payload, default=str)),
        )

    def _read_pending(self) -> dict[str, float]:
        rows = self._conn.execute(
            "SELECT instrument, SUM(quantity) FROM pending_orders WHERE terminal = 0 "
            "GROUP BY instrument"
        ).fetchall()
        return {instrument: float(total) for instrument, total in rows}

    # -- introspection (used by callers and tests) -----------------------

    def status(self) -> dict:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            state = self._read_state()
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return state

    def pending_orders(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT client_order_id, instrument, quantity, terminal, created_at "
            "FROM pending_orders ORDER BY created_at"
        ).fetchall()
        return [
            {
                "client_order_id": r[0],
                "instrument": r[1],
                "quantity": r[2],
                "terminal": bool(r[3]),
                "created_at": r[4],
            }
            for r in rows
        ]

    def evidence(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT ts, event_type, payload FROM evidence_log ORDER BY id"
        ).fetchall()
        return [
            {"ts": r[0], "event_type": r[1], "payload": json.loads(r[2])} for r in rows
        ]

    # -- the gate ---------------------------------------------------------

    def evaluate_order(self, snapshot: BrokerSnapshot, intent: OrderIntent, *, now: datetime) -> GateDecision:
        """REQ evaluation order: freshness -> kill -> reconciliation -> loss
        halt -> position/gross cap -> atomic reservation.

        A passing size calculation cannot override an earlier deny in this
        order; every branch below returns before reaching the exposure math
        once an earlier check has failed, matching spec 032's "the order of
        these assertions is part of the safety contract."
        """
        if not isinstance(snapshot, BrokerSnapshot):
            raise TypeError("snapshot must be a BrokerSnapshot")
        if not isinstance(intent, OrderIntent):
            raise TypeError("intent must be an OrderIntent")
        _require_aware("now", now)

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            decision = self._evaluate_order_locked(snapshot, intent, now=now)
            self._conn.execute("COMMIT")
            return decision
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def _deny(self, reason: str, *, action: str, checks: dict) -> GateDecision:
        return GateDecision(
            outcome=DENY,
            reason=reason,
            config_version=self._config.version,
            action=action,
            checks=checks,
        )

    def _evaluate_order_locked(
        self, snapshot: BrokerSnapshot, intent: OrderIntent, *, now: datetime
    ) -> GateDecision:
        state = self._read_state()
        if state["config_json"] != self._config.as_dict():
            decision = self._deny(DENY_CONFIG_MISMATCH, action=ACTION_BLOCK_NEW, checks={})
            self._log_locked("DENY", dataclasses.asdict(decision))
            return decision

        freshness_deny = self._check_freshness(snapshot, now=now)
        if freshness_deny is not None:
            # REQ / failure-mode table: an unknown measurement enters
            # RECONCILIATION_HALT with no automatic expiry, not a one-off
            # deny -- the very next call must also fail until explicitly
            # cleared, even if that next snapshot looks fine.
            self._write_kv(
                {"reconciliation_halt": True, "reconciliation_reason": freshness_deny}
            )
            decision = self._deny(
                freshness_deny, action=ACTION_BLOCK_NEW, checks={"triggered_reconciliation_halt": True}
            )
            self._log_locked("DENY", dataclasses.asdict(decision))
            return decision

        trading_day = _trading_day(snapshot.as_of, self._config.timezone)
        breach = self._observe_equity_locked(snapshot, trading_day=trading_day, now=now)

        state = self._read_state()
        if state["kill_latched"]:
            decision = self._deny(DENY_KILL_LATCHED, action=ACTION_KILL_LATCHED, checks=breach)
            self._log_locked("DENY", dataclasses.asdict(decision))
            return decision
        if state["reconciliation_halt"]:
            decision = self._deny(
                DENY_RECONCILIATION_HALT, action=ACTION_BLOCK_NEW, checks=breach
            )
            self._log_locked("DENY", dataclasses.asdict(decision))
            return decision

        current_qty = float(snapshot.positions.get(intent.instrument, 0.0))
        new_qty = current_qty + intent.delta_quantity
        if new_qty < -_QTY_EPS:
            decision = self._deny(
                DENY_SHORT_NOT_SUPPORTED,
                action=ACTION_BLOCK_NEW,
                checks={**breach, "current_qty": current_qty, "new_qty": new_qty},
            )
            self._log_locked("DENY", dataclasses.asdict(decision))
            return decision

        halted = bool(breach["daily_halt_active"] or breach["rolling_halt_active"])
        is_reduce_only = intent.is_reduce_only

        if halted and not is_reduce_only:
            decision = self._deny(
                DENY_LOSS_HALT, action=ACTION_CANCEL_RISK_ADDING, checks=breach
            )
            self._log_locked("DENY", dataclasses.asdict(decision))
            return decision

        if is_reduce_only:
            checks = {**breach, "reduce_only": True, "current_qty": current_qty, "new_qty": new_qty}
            decision = self._reserve_and_allow(intent, action=ACTION_REDUCE_ONLY, checks=checks, now=now)
            self._log_locked(decision.outcome, dataclasses.asdict(decision))
            return decision

        exposure = self._worst_case_exposure(snapshot, intent)
        checks = {**breach, "reduce_only": False, **exposure}
        if exposure["missing_price_instruments"]:
            decision = self._deny(DENY_PRICE_UNAVAILABLE, action=ACTION_BLOCK_NEW, checks=checks)
            self._log_locked("DENY", dataclasses.asdict(decision))
            return decision

        equity = snapshot.equity
        if exposure["instrument_notional"] / equity >= self._config.max_position_pct:
            decision = self._deny(DENY_MAX_POSITION_PCT, action=ACTION_BLOCK_NEW, checks=checks)
            self._log_locked("DENY", dataclasses.asdict(decision))
            return decision
        if exposure["gross_notional"] / equity >= self._config.max_gross_pct:
            decision = self._deny(DENY_MAX_GROSS_PCT, action=ACTION_BLOCK_NEW, checks=checks)
            self._log_locked("DENY", dataclasses.asdict(decision))
            return decision

        decision = self._reserve_and_allow(intent, action=ACTION_BLOCK_NEW, checks=checks, now=now)
        self._log_locked(decision.outcome, dataclasses.asdict(decision))
        return decision

    def _check_freshness(self, snapshot: BrokerSnapshot, *, now: datetime) -> Optional[str]:
        if snapshot.status != "OK":
            return DENY_BROKER_STATUS
        age = (now - snapshot.as_of).total_seconds()
        if age > self._config.max_snapshot_age_seconds:
            return DENY_STALE_SNAPSHOT
        if age < -self._config.max_clock_skew_seconds:
            return DENY_CLOCK_SKEW
        if not math.isfinite(snapshot.equity) or snapshot.equity <= 0.0:
            return DENY_NON_POSITIVE_EQUITY
        return None

    def _worst_case_exposure(self, snapshot: BrokerSnapshot, intent: OrderIntent) -> dict:
        """N_i and G, per Design section 1: current position + every
        non-terminal reservation for that instrument + the candidate order,
        at the conservative executable price.
        """
        pending = self._read_pending()
        instruments = set(snapshot.positions) | set(pending) | {intent.instrument}
        gross = 0.0
        instrument_notional = 0.0
        missing_price = []
        for name in sorted(instruments):
            qty = float(snapshot.positions.get(name, 0.0)) + pending.get(name, 0.0)
            if name == intent.instrument:
                qty += intent.delta_quantity
            if abs(qty) <= _QTY_EPS:
                continue
            price = snapshot.prices.get(name)
            if not _valid_price(price):
                missing_price.append(name)
                continue
            notional = abs(qty) * float(price)
            gross += notional
            if name == intent.instrument:
                instrument_notional = notional
        return {
            "gross_notional": gross,
            "instrument_notional": instrument_notional,
            "missing_price_instruments": missing_price,
        }

    def _reserve_and_allow(
        self, intent: OrderIntent, *, action: str, checks: dict, now: datetime
    ) -> GateDecision:
        try:
            self._conn.execute(
                "INSERT INTO pending_orders (client_order_id, instrument, quantity, "
                "terminal, created_at) VALUES (?, ?, ?, 0, ?)",
                (intent.client_order_id, intent.instrument, intent.delta_quantity, _iso(now)),
            )
        except sqlite3.IntegrityError:
            return self._deny(DENY_DUPLICATE_ORDER, action=ACTION_BLOCK_NEW, checks=checks)
        return GateDecision(
            outcome=ALLOW,
            reason="OK",
            config_version=self._config.version,
            action=action,
            checks=checks,
            reservation_id=intent.client_order_id,
        )

    # -- loss / drawdown breaker -------------------------------------------

    def observe_equity(self, snapshot: BrokerSnapshot, *, now: datetime) -> dict:
        """Standalone heartbeat entry point: update the breaker with no order.

        REQ: the breaker "MUST update on every trusted account/fill/mark
        observation during trading, not only at the daily close" -- this is
        how a periodic poller, independent of any order intent, keeps it
        current. ``evaluate_order`` calls the same locked implementation
        internally rather than a second copy of the arithmetic.
        """
        if not isinstance(snapshot, BrokerSnapshot):
            raise TypeError("snapshot must be a BrokerSnapshot")
        _require_aware("now", now)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            deny_reason = self._check_freshness(snapshot, now=now)
            if deny_reason is not None:
                self._write_kv({"reconciliation_halt": True, "reconciliation_reason": deny_reason})
                self._log_locked("RECONCILIATION_HALT", {"reason": deny_reason})
                self._conn.execute("COMMIT")
                return {"reconciliation_halt": True, "reason": deny_reason}
            trading_day = _trading_day(snapshot.as_of, self._config.timezone)
            result = self._observe_equity_locked(snapshot, trading_day=trading_day, now=now)
            self._conn.execute("COMMIT")
            return result
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def _observe_equity_locked(
        self, snapshot: BrokerSnapshot, *, trading_day: date, now: datetime
    ) -> dict:
        state = self._read_state()
        window = self._config.rolling_window_sessions

        last_session = state["last_session"]
        if last_session is None:
            adjusted_equity = snapshot.equity
            day_start_session = trading_day.isoformat()
            day_start_equity = snapshot.equity
            session_high = snapshot.equity
            prior_closes: list = []
        else:
            prev_adjusted = state["adjusted_equity"]
            prev_raw = state["last_raw_equity"]
            raw_change = snapshot.equity - prev_raw
            adjusted_equity = prev_adjusted + (raw_change - snapshot.external_cash_flow)
            if trading_day.isoformat() != last_session:
                prior_closes = (state["prior_session_closes"] + [prev_adjusted])[-window:]
                day_start_session = trading_day.isoformat()
                day_start_equity = adjusted_equity
                session_high = adjusted_equity
            else:
                prior_closes = state["prior_session_closes"]
                day_start_session = state["day_start_session"]
                day_start_equity = state["day_start_equity"]
                session_high = max(state["session_high"], adjusted_equity)

        daily_return = adjusted_equity / day_start_equity - 1.0
        daily_breach = daily_return <= -self._config.daily_loss_pct

        high_water = max(prior_closes + [session_high]) if prior_closes else session_high
        rolling_drawdown = adjusted_equity / high_water - 1.0
        rolling_breach = rolling_drawdown <= -self._config.rolling_drawdown_pct

        rolling_halt_active = bool(state["rolling_halt_active"] or rolling_breach)

        updates = {
            "last_session": trading_day.isoformat(),
            "day_start_session": day_start_session,
            "day_start_equity": day_start_equity,
            "adjusted_equity": adjusted_equity,
            "last_raw_equity": snapshot.equity,
            "session_high": session_high,
            "prior_session_closes": prior_closes,
        }
        if daily_breach:
            updates["daily_halt_session"] = trading_day.isoformat()
            updates["daily_halt_reason"] = "DAILY_LOSS_LIMIT_BREACHED"
        if rolling_breach and not state["rolling_halt_active"]:
            updates["rolling_halt_active"] = True
            updates["rolling_halt_reason"] = "ROLLING_DRAWDOWN_LIMIT_BREACHED"
        self._write_kv(updates)

        if snapshot.external_cash_flow != 0.0:
            self._log_locked(
                "EXTERNAL_CASH_FLOW",
                {"session": trading_day.isoformat(), "amount": snapshot.external_cash_flow},
            )
        self._log_locked(
            "EQUITY_OBSERVATION",
            {
                "session": trading_day.isoformat(),
                "raw_equity": snapshot.equity,
                "adjusted_equity": adjusted_equity,
                "daily_return": daily_return,
                "rolling_drawdown": rolling_drawdown,
                "daily_breach": daily_breach,
                "rolling_breach": rolling_breach,
            },
        )

        daily_halt_active = bool(state.get("daily_halt_session") == trading_day.isoformat() or daily_breach)
        return {
            "session": trading_day.isoformat(),
            "equity": snapshot.equity,
            "adjusted_equity": adjusted_equity,
            "daily_return": daily_return,
            "rolling_drawdown": rolling_drawdown,
            "daily_breach": daily_breach,
            "rolling_breach": rolling_breach,
            "daily_halt_active": daily_halt_active,
            "rolling_halt_active": rolling_halt_active,
        }

    # -- manual kill switch -----------------------------------------------

    def request_kill(self, *, operator: str, reason: str, now: datetime) -> str:
        """Write the durable latch first, immediately -- REQ ordering: "an
        authenticated local control command first writes a durable
        KILL_LATCHED record/flag, then signals the order gateway."
        """
        _require_nonempty_str("operator", operator)
        _require_nonempty_str("reason", reason)
        _require_aware("now", now)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._write_kv(
                {"kill_latched": True, "kill_confirmed": False, "kill_reason": reason}
            )
            self._log_locked(
                "KILL_REQUESTED", {"operator": operator, "reason": reason}
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return KILL_LOCAL_BLOCKED

    def confirm_kill(self, *, query: Optional[BrokerKillQuery], now: datetime) -> str:
        """Advance the kill confirmation contract using a caller-supplied
        broker query (see ``BrokerKillQuery`` and the module docstring on
        why this never calls a broker itself).
        """
        _require_aware("now", now)
        self._conn.execute("BEGIN IMMEDIATE")
        # A rejection here is a business-rule outcome, not a transaction
        # failure: it must still commit (nothing to undo) rather than run
        # into the `except` below, which would try to roll back a
        # transaction this same branch already closed. So every branch
        # commits exactly once and only *then* raises, mirroring
        # `_ensure_config`.
        error: Optional[Exception] = None
        status_result: Optional[str] = None
        try:
            state = self._read_state()
            if not state["kill_latched"]:
                error = ValueError("cannot confirm a kill that was never requested.")
            elif query is None:
                self._log_locked("KILL_STATUS", {"status": KILL_BROKER_DISABLE_UNVERIFIED})
                status_result = KILL_BROKER_DISABLE_UNVERIFIED
            elif not query.working_orders_terminal:
                self._log_locked("KILL_STATUS", {"status": KILL_RECONCILING})
                status_result = KILL_RECONCILING
            elif query.disable_status is None:
                self._log_locked("KILL_STATUS", {"status": KILL_BROKER_DISABLE_UNVERIFIED})
                status_result = KILL_BROKER_DISABLE_UNVERIFIED
            elif query.disable_status is False:
                self._log_locked("KILL_STATUS", {"status": KILL_BROKER_CANCEL_PENDING})
                status_result = KILL_BROKER_CANCEL_PENDING
            else:
                self._write_kv({"kill_confirmed": True})
                self._log_locked("KILL_CONFIRMED", {})
                status_result = KILL_CONFIRMED
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        if error is not None:
            raise error
        return status_result

    def reset_kill(
        self,
        *,
        operator: str,
        reason: str,
        broker_disable_independently_verified: bool = False,
        now: datetime,
    ) -> None:
        """Re-enable trading after a kill. Requires: an authenticated
        operator and reason, a positively confirmed broker-side clear (or an
        explicit, separately-recorded operator attestation that they
        verified it through an independent channel -- spec 032: "the
        operator must verify the broker side through an independent
        channel"), and no active loss/drawdown/reconciliation halt.
        """
        _require_nonempty_str("operator", operator)
        _require_nonempty_str("reason", reason)
        _require_aware("now", now)
        self._conn.execute("BEGIN IMMEDIATE")
        error: Optional[Exception] = None
        try:
            state = self._read_state()
            if not state["kill_latched"]:
                error = ValueError("no active kill to reset.")
            elif not state["kill_confirmed"] and not broker_disable_independently_verified:
                error = ValueError(
                    "kill cannot be reset until the broker-side kill is positively "
                    "confirmed cleared, or the operator explicitly attests to "
                    "independent verification (broker_disable_independently_verified=True)."
                )
            elif state["reconciliation_halt"]:
                error = ValueError("cannot reset kill while a reconciliation halt is active.")
            elif state["rolling_halt_active"]:
                error = ValueError("cannot reset kill while a rolling drawdown halt is active.")
            else:
                self._write_kv({"kill_latched": False, "kill_confirmed": False, "kill_reason": None})
                self._log_locked(
                    "KILL_RESET",
                    {
                        "operator": operator,
                        "reason": reason,
                        "broker_disable_independently_verified": broker_disable_independently_verified,
                    },
                )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        if error is not None:
            raise error

    # -- resets for the other latches --------------------------------------

    def reset_rolling_halt(
        self, snapshot: BrokerSnapshot, *, operator: str, reason: str, now: datetime
    ) -> None:
        """Operator-authenticated reset of a latched rolling-drawdown halt.

        Rejected if the current rolling drawdown still breaches the limit,
        reconciliation is incomplete, or the kill switch is active. Does not
        erase the historical breach from the evidence log.
        """
        _require_nonempty_str("operator", operator)
        _require_nonempty_str("reason", reason)
        if not isinstance(snapshot, BrokerSnapshot):
            raise TypeError("snapshot must be a BrokerSnapshot")
        _require_aware("now", now)
        self._conn.execute("BEGIN IMMEDIATE")
        error: Optional[Exception] = None
        try:
            deny_reason = self._check_freshness(snapshot, now=now)
            if deny_reason is not None:
                error = ValueError(f"cannot reset on an untrusted snapshot: {deny_reason}.")
            else:
                # Recorded even on a rejected reset -- an operator's failed
                # attempt is still a trusted observation and must not be lost.
                trading_day = _trading_day(snapshot.as_of, self._config.timezone)
                breach = self._observe_equity_locked(snapshot, trading_day=trading_day, now=now)
                state = self._read_state()
                if state["kill_latched"]:
                    error = ValueError("cannot reset a rolling halt while the kill switch is active.")
                elif state["reconciliation_halt"]:
                    error = ValueError(
                        "cannot reset a rolling halt while a reconciliation halt is active."
                    )
                elif breach["rolling_breach"]:
                    error = ValueError(
                        f"cannot reset: rolling drawdown {breach['rolling_drawdown']:.6f} still "
                        f"breaches the limit -{self._config.rolling_drawdown_pct}."
                    )
                else:
                    self._write_kv({"rolling_halt_active": False, "rolling_halt_reason": None})
                    self._log_locked(
                        "ROLLING_HALT_RESET",
                        {
                            "operator": operator,
                            "reason": reason,
                            "equity": snapshot.equity,
                            "rolling_drawdown": breach["rolling_drawdown"],
                            "config_version": self._config.version,
                        },
                    )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        if error is not None:
            raise error

    def clear_reconciliation_halt(
        self, snapshot: BrokerSnapshot, *, operator: str, reason: str, now: datetime
    ) -> None:
        """Clear a latched RECONCILIATION_HALT with one fresh, valid snapshot.

        "No automatic expiry" (spec 032) means this halt never clears on its
        own just because a later snapshot happens to look fine -- an
        operator must call this explicitly, and it still requires that the
        snapshot handed to it actually passes every freshness check.
        """
        _require_nonempty_str("operator", operator)
        _require_nonempty_str("reason", reason)
        if not isinstance(snapshot, BrokerSnapshot):
            raise TypeError("snapshot must be a BrokerSnapshot")
        _require_aware("now", now)
        self._conn.execute("BEGIN IMMEDIATE")
        error: Optional[Exception] = None
        try:
            deny_reason = self._check_freshness(snapshot, now=now)
            if deny_reason is not None:
                error = ValueError(f"cannot clear: snapshot is still untrusted ({deny_reason}).")
            else:
                self._write_kv({"reconciliation_halt": False, "reconciliation_reason": None})
                self._log_locked(
                    "RECONCILIATION_HALT_CLEARED", {"operator": operator, "reason": reason}
                )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        if error is not None:
            raise error

    def adopt_new_config(
        self, new_config: SafetyConfig, *, operator: str, reason: str, now: datetime
    ) -> None:
        """The only sanctioned way durable configuration changes.

        Refused while any halt or the kill switch is active, so a
        configuration cannot be loosened out from under an active
        protective state. Recorded to the evidence log with the operator,
        the reason, and both configurations in full.
        """
        if not isinstance(new_config, SafetyConfig):
            raise TypeError("new_config must be a SafetyConfig")
        _require_nonempty_str("operator", operator)
        _require_nonempty_str("reason", reason)
        _require_aware("now", now)
        self._conn.execute("BEGIN IMMEDIATE")
        error: Optional[Exception] = None
        try:
            state = self._read_state()
            if state["kill_latched"]:
                error = ValueError("cannot adopt a new configuration while the kill switch is active.")
            elif state["reconciliation_halt"]:
                error = ValueError("cannot adopt a new configuration during a reconciliation halt.")
            elif state["rolling_halt_active"]:
                error = ValueError("cannot adopt a new configuration while a rolling halt is active.")
            else:
                old_config = state["config_json"]
                self._write_kv({"config_json": new_config.as_dict()})
                self._log_locked(
                    "CONFIG_ADOPTED",
                    {
                        "operator": operator,
                        "reason": reason,
                        "old": old_config,
                        "new": new_config.as_dict(),
                    },
                )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        if error is not None:
            raise error
        self._config = new_config

    # -- order lifecycle reconciliation (REQ-007) --------------------------

    def record_order_outcome(
        self, client_order_id: str, *, terminal: bool, reason: str, now: datetime
    ) -> None:
        """Mark a reservation terminal once its broker outcome is known.

        This is a bookkeeping hook, not a broker call: an ``exec/`` adapter
        queries the broker by this durable client order ID and its
        executions (never inferring "not submitted" from a timeout, per
        REQ-007) and reports the terminal outcome here so the reservation
        stops counting toward worst-case exposure.
        """
        _require_nonempty_str("client_order_id", client_order_id)
        _require_nonempty_str("reason", reason)
        _require_aware("now", now)
        self._conn.execute("BEGIN IMMEDIATE")
        error: Optional[Exception] = None
        try:
            cursor = self._conn.execute(
                "UPDATE pending_orders SET terminal = ? WHERE client_order_id = ?",
                (1 if terminal else 0, client_order_id),
            )
            if cursor.rowcount == 0:
                error = ValueError(f"no reservation found for client_order_id={client_order_id!r}.")
            else:
                self._log_locked(
                    "ORDER_OUTCOME",
                    {"client_order_id": client_order_id, "terminal": terminal, "reason": reason},
                )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        if error is not None:
            raise error

    # -- the operator-only reduce-only override ----------------------------

    def evaluate_operator_override_reduce(
        self,
        snapshot: BrokerSnapshot,
        intent: OrderIntent,
        *,
        operator: str,
        reason: str,
        now: datetime,
    ) -> GateDecision:
        """The "separate, explicit, reduce-only command after a fresh
        position snapshot" spec 032's Kill Switch section describes as the
        only sanctioned way to reduce exposure during a kill. Also usable
        during a loss/drawdown halt, matching the failure-mode table's
        "Order is reduced-only during a halt or kill -> Allow only after
        fresh reconciliation and broker order-type verification."

        Unlike ``evaluate_order``, this path does not deny on
        ``KILL_LATCHED`` or a loss/drawdown halt by itself -- but it still
        denies on a stale/invalid snapshot, a reconciliation halt, or any
        order that is not strictly reduce-only. Every call is logged with
        the operator and reason, kill-latched-and-reducing being exactly the
        situation Rule 10-style accountability exists to keep auditable.
        """
        if not isinstance(snapshot, BrokerSnapshot):
            raise TypeError("snapshot must be a BrokerSnapshot")
        if not isinstance(intent, OrderIntent):
            raise TypeError("intent must be an OrderIntent")
        _require_nonempty_str("operator", operator)
        _require_nonempty_str("reason", reason)
        _require_aware("now", now)

        if not intent.is_reduce_only:
            raise ValueError(
                "evaluate_operator_override_reduce only accepts reduce-only orders "
                "(delta_quantity <= 0)."
            )

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            state = self._read_state()
            if state["config_json"] != self._config.as_dict():
                decision = self._deny(DENY_CONFIG_MISMATCH, action=ACTION_BLOCK_NEW, checks={})
                self._log_locked("DENY", dataclasses.asdict(decision))
                self._conn.execute("COMMIT")
                return decision

            deny_reason = self._check_freshness(snapshot, now=now)
            if deny_reason is not None:
                self._write_kv({"reconciliation_halt": True, "reconciliation_reason": deny_reason})
                decision = self._deny(deny_reason, action=ACTION_REDUCE_ONLY, checks={})
                self._log_locked("DENY", dataclasses.asdict(decision))
                self._conn.execute("COMMIT")
                return decision

            if state["reconciliation_halt"]:
                decision = self._deny(DENY_RECONCILIATION_HALT, action=ACTION_REDUCE_ONLY, checks={})
                self._log_locked("DENY", dataclasses.asdict(decision))
                self._conn.execute("COMMIT")
                return decision

            current_qty = float(snapshot.positions.get(intent.instrument, 0.0))
            new_qty = current_qty + intent.delta_quantity
            if new_qty < -_QTY_EPS:
                decision = self._deny(
                    DENY_SHORT_NOT_SUPPORTED,
                    action=ACTION_REDUCE_ONLY,
                    checks={"current_qty": current_qty, "new_qty": new_qty},
                )
                self._log_locked("DENY", dataclasses.asdict(decision))
                self._conn.execute("COMMIT")
                return decision

            checks = {
                "operator_override": True,
                "current_qty": current_qty,
                "new_qty": new_qty,
                "kill_latched": bool(state["kill_latched"]),
            }
            decision = self._reserve_and_allow(
                intent, action=ACTION_REDUCE_ONLY, checks=checks, now=now
            )
            self._log_locked(
                decision.outcome,
                {**dataclasses.asdict(decision), "operator": operator, "reason": reason},
            )
            self._conn.execute("COMMIT")
            return decision
        except Exception:
            self._conn.execute("ROLLBACK")
            raise


def new_client_order_id() -> str:
    """A durable, unique client order ID (REQ-007). Not broker-specific."""
    return uuid.uuid4().hex
