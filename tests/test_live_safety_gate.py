"""Tests for the live-trading safety layer (spec 032).

Every gate here gets Rule 12 treatment somewhere in this file: a control
scenario proving the gate passes clean traffic, a scenario proving it denies
the traffic it exists to deny, and -- for the five defects a tired reviewer
could plausibly ship -- a planted mutant proving the *test* would actually
catch the bug, not just that the code currently behaves. The mutation tests
at the bottom use ``mutation_support_032.killed``, which mutates the loaded
module's source in memory, runs the same oracle against the mutant, and
restores the file untouched.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from context import SCRIPTS_DIR
import mutation_support_032
import live_safety_gate as lsg
from live_safety_gate import (
    ACTION_BLOCK_NEW,
    ACTION_CANCEL_RISK_ADDING,
    ACTION_KILL_LATCHED,
    ACTION_REDUCE_ONLY,
    ALLOW,
    BrokerKillQuery,
    BrokerSnapshot,
    ConfigMismatchError,
    DENY,
    DENY_BROKER_STATUS,
    DENY_CLOCK_SKEW,
    DENY_DUPLICATE_ORDER,
    DENY_KILL_LATCHED,
    DENY_LOSS_HALT,
    DENY_MAX_GROSS_PCT,
    DENY_MAX_POSITION_PCT,
    DENY_NON_POSITIVE_EQUITY,
    DENY_PRICE_UNAVAILABLE,
    DENY_RECONCILIATION_HALT,
    DENY_SHORT_NOT_SUPPORTED,
    DENY_STALE_SNAPSHOT,
    KILL_BROKER_CANCEL_PENDING,
    KILL_BROKER_DISABLE_UNVERIFIED,
    KILL_CONFIRMED,
    KILL_LOCAL_BLOCKED,
    KILL_RECONCILING,
    OrderIntent,
    SafetyConfig,
    SafetyGate,
    new_client_order_id,
)

UTC = timezone.utc


def at(hour=15, minute=0, day=10, month=6, year=2026):
    """A UTC instant that lands mid-day in America/New_York (no DST edges)."""
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def make_config(**overrides):
    values = dict(
        version="test-v1",
        max_position_pct=0.25,
        max_gross_pct=1.0,
        daily_loss_pct=0.02,
        rolling_drawdown_pct=0.05,
        rolling_window_sessions=5,
        max_snapshot_age_seconds=30.0,
        max_clock_skew_seconds=5.0,
    )
    values.update(overrides)
    return SafetyConfig(**values)


def make_snapshot(
    as_of, equity, *, positions=None, prices=None, cash_flow=0.0, status="OK"
):
    return BrokerSnapshot(
        as_of=as_of,
        status=status,
        equity=equity,
        external_cash_flow=cash_flow,
        positions=positions or {},
        prices=prices or {},
    )


def make_intent(instrument, delta, order_id=None):
    return OrderIntent(
        client_order_id=order_id or new_client_order_id(),
        instrument=instrument,
        delta_quantity=delta,
    )


class GateTestCase(unittest.TestCase):
    """Every test gets its own throwaway SQLite file -- no state leaks.

    SQLite on Windows will not let a temp directory delete a ``.db`` file
    while any connection to it is still open, so every gate this helper
    creates is tracked and closed in ``tearDown`` before the directory is
    cleaned up -- including gates a test deliberately reopens to simulate a
    restart.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "gate.db"
        self._gates = []
        self.addCleanup(self._close_gates)

    def _close_gates(self):
        for gate in self._gates:
            gate.close()

    def gate(self, config=None):
        instance = SafetyGate(self.db_path, config or make_config())
        self._gates.append(instance)
        return instance


# ---------------------------------------------------------------------------
# Configuration: no defaults, no dollar fallback, no silent mid-session change
# ---------------------------------------------------------------------------


class ConfigValidationTests(unittest.TestCase):
    def test_every_field_is_mandatory(self):
        with self.assertRaises(TypeError):
            SafetyConfig(version="v1")  # missing every limit

    def test_no_dollar_field_can_be_configured(self):
        # REQ-001's acceptance evidence: a fixed-dollar cap must not be
        # configurable or silently substituted. There is no such field to
        # pass, and the dataclass rejects an unknown one outright.
        with self.assertRaises(TypeError):
            make_config(max_position_dollars=10_000)

    def test_max_position_over_max_gross_raises(self):
        with self.assertRaises(ValueError):
            make_config(max_position_pct=0.9, max_gross_pct=0.5)

    def test_max_gross_over_one_raises_no_leverage(self):
        with self.assertRaises(ValueError):
            make_config(max_gross_pct=1.5)

    def test_loss_limit_must_be_strictly_below_one(self):
        with self.assertRaises(ValueError):
            make_config(daily_loss_pct=1.0)

    def test_negative_snapshot_age_raises(self):
        with self.assertRaises(ValueError):
            make_config(max_snapshot_age_seconds=-1.0)

    def test_unloadable_timezone_raises(self):
        with self.assertRaises(ValueError):
            make_config(timezone="Not/A_Zone")


class ConfigDurabilityTests(GateTestCase):
    def test_reopening_with_the_same_config_is_fine(self):
        self.gate().close()
        self.gate().close()  # no raise

    def test_reopening_with_a_different_value_under_the_same_version_raises(self):
        self.gate().close()
        with self.assertRaises(ConfigMismatchError):
            self.gate(make_config(max_position_pct=0.10))

    def test_adopt_new_config_records_a_deliberate_change(self):
        gate = self.gate()
        new_config = make_config(version="test-v2", max_position_pct=0.10)
        gate.adopt_new_config(new_config, operator="camden", reason="tighten cap", now=at())
        gate.close()
        reopened = self.gate(new_config)  # no ConfigMismatchError
        reopened.close()

    def test_adopt_new_config_blocked_while_killed(self):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="test", now=at())
        with self.assertRaises(ValueError):
            gate.adopt_new_config(
                make_config(version="v2"), operator="camden", reason="x", now=at()
            )


# ---------------------------------------------------------------------------
# Snapshot / intent validation
# ---------------------------------------------------------------------------


class DataContractTests(unittest.TestCase):
    def test_naive_as_of_is_rejected(self):
        with self.assertRaises(ValueError):
            BrokerSnapshot(
                as_of=datetime(2026, 6, 10, 15, 0),
                status="OK",
                equity=1000.0,
                external_cash_flow=0.0,
                positions={},
                prices={},
            )

    def test_zero_delta_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            make_intent("AAPL", 0.0)

    def test_reduce_only_property(self):
        self.assertTrue(make_intent("AAPL", -1.0).is_reduce_only)
        self.assertFalse(make_intent("AAPL", 1.0).is_reduce_only)


# ---------------------------------------------------------------------------
# Freshness / reconciliation
# ---------------------------------------------------------------------------


class FreshnessTests(GateTestCase):
    def test_control_a_fresh_ok_snapshot_is_not_denied_on_freshness_grounds(self):
        gate = self.gate()
        snap = make_snapshot(at(), 100_000.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(snap, make_intent("AAPL", 1.0), now=at())
        self.assertEqual(decision.outcome, ALLOW)

    def test_stale_snapshot_denies_and_latches_reconciliation_halt(self):
        gate = self.gate()
        snap = make_snapshot(at(), 100_000.0, prices={"AAPL": 10.0})
        now = at() + timedelta(seconds=60)  # older than max_snapshot_age_seconds=30
        decision = gate.evaluate_order(snap, make_intent("AAPL", 1.0), now=now)
        self.assertEqual(decision.reason, DENY_STALE_SNAPSHOT)
        self.assertTrue(gate.status()["reconciliation_halt"])

    def test_no_automatic_expiry_a_later_fresh_snapshot_still_denies(self):
        gate = self.gate()
        stale = make_snapshot(at(), 100_000.0, prices={"AAPL": 10.0})
        gate.evaluate_order(stale, make_intent("AAPL", 1.0), now=at() + timedelta(seconds=60))
        fresh = make_snapshot(at(minute=1), 100_000.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(fresh, make_intent("AAPL", 1.0), now=at(minute=1))
        self.assertEqual(decision.reason, DENY_RECONCILIATION_HALT)

    def test_explicit_clear_restores_trading(self):
        gate = self.gate()
        stale = make_snapshot(at(), 100_000.0, prices={"AAPL": 10.0})
        gate.evaluate_order(stale, make_intent("AAPL", 1.0), now=at() + timedelta(seconds=60))
        fresh = make_snapshot(at(minute=1), 100_000.0, prices={"AAPL": 10.0})
        gate.clear_reconciliation_halt(fresh, operator="camden", reason="verified", now=at(minute=1))
        decision = gate.evaluate_order(fresh, make_intent("AAPL", 1.0), now=at(minute=1))
        self.assertEqual(decision.outcome, ALLOW)

    def test_clock_skew_from_the_future_denies(self):
        gate = self.gate()
        future_snap = make_snapshot(at(minute=5), 100_000.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(future_snap, make_intent("AAPL", 1.0), now=at())
        self.assertEqual(decision.reason, DENY_CLOCK_SKEW)

    def test_broker_status_not_ok_denies(self):
        gate = self.gate()
        snap = make_snapshot(at(), 100_000.0, prices={"AAPL": 10.0}, status="DEGRADED")
        decision = gate.evaluate_order(snap, make_intent("AAPL", 1.0), now=at())
        self.assertEqual(decision.reason, DENY_BROKER_STATUS)

    def test_zero_equity_denies_before_sizing_division(self):
        gate = self.gate()
        snap = make_snapshot(at(), 0.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(snap, make_intent("AAPL", 1.0), now=at())
        self.assertEqual(decision.reason, DENY_NON_POSITIVE_EQUITY)

    def test_negative_equity_denies_before_sizing_division(self):
        gate = self.gate()
        snap = make_snapshot(at(), -100.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(snap, make_intent("AAPL", 1.0), now=at())
        self.assertEqual(decision.reason, DENY_NON_POSITIVE_EQUITY)


# ---------------------------------------------------------------------------
# Max position / gross size (Design section 1)
# ---------------------------------------------------------------------------


class ExposureLimitTests(GateTestCase):
    def test_control_a_small_order_well_under_cap_is_allowed(self):
        gate = self.gate()
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(snap, make_intent("AAPL", 5.0), now=at())
        self.assertEqual(decision.outcome, ALLOW)

    def test_exact_boundary_is_denied_inclusive(self):
        gate = self.gate(make_config(max_position_pct=0.25))
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(snap, make_intent("AAPL", 25.0), now=at())  # 250/1000 == 0.25
        self.assertEqual(decision.reason, DENY_MAX_POSITION_PCT)

    def test_one_step_under_the_boundary_is_allowed(self):
        gate = self.gate(make_config(max_position_pct=0.25))
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(snap, make_intent("AAPL", 24.999), now=at())
        self.assertEqual(decision.outcome, ALLOW)

    def test_equity_scales_the_permissible_notional_proportionally(self):
        gate = self.gate(make_config(max_position_pct=0.25))
        small_equity = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(small_equity, make_intent("AAPL", 26.0), now=at())
        self.assertEqual(decision.reason, DENY_MAX_POSITION_PCT)

        gate2 = self.gate(make_config(max_position_pct=0.25))
        big_equity = make_snapshot(at(), 100_000.0, prices={"AAPL": 10.0})
        decision2 = gate2.evaluate_order(big_equity, make_intent("AAPL", 26.0), now=at())
        self.assertEqual(decision2.outcome, ALLOW)

    def test_existing_position_plus_working_order_plus_new_order_all_count(self):
        gate = self.gate(make_config(max_position_pct=0.25))
        snap = make_snapshot(
            at(), 1000.0, positions={"AAPL": 10.0}, prices={"AAPL": 10.0}
        )
        first = gate.evaluate_order(snap, make_intent("AAPL", 5.0, "order-1"), now=at())
        self.assertEqual(first.outcome, ALLOW)  # (10+5)*10 = 150 -> 0.15, fine
        second = gate.evaluate_order(snap, make_intent("AAPL", 10.0, "order-2"), now=at())
        # worst case: 10 (position) + 5 (reserved order-1) + 10 (candidate) = 25 -> 250/1000 == 0.25
        self.assertEqual(second.reason, DENY_MAX_POSITION_PCT)

    def test_unfilled_pending_sell_does_not_create_capacity_for_new_buy(self):
        gate = self.gate(make_config(max_position_pct=0.60, max_gross_pct=1.0))
        snap = make_snapshot(
            at(), 2000.0, positions={"AAPL": 100.0}, prices={"AAPL": 10.0}
        )
        pending_sell = gate.evaluate_order(
            snap, make_intent("AAPL", -50.0, "pending-sell"), now=at()
        )
        self.assertEqual(pending_sell.outcome, ALLOW)

        candidate = gate.evaluate_order(
            snap, make_intent("AAPL", 60.0, "new-buy"), now=at()
        )

        # The sell is still unfilled: worst case remains 100 + 60 shares,
        # not 100 - 50 + 60. 1600 / 2000 breaches the 60% position cap.
        self.assertEqual(candidate.reason, DENY_MAX_POSITION_PCT)

    def test_two_orders_that_each_pass_alone_cannot_jointly_exceed_gross(self):
        gate = self.gate(make_config(max_position_pct=0.5, max_gross_pct=0.5))
        snap = make_snapshot(
            at(), 1000.0, prices={"AAPL": 10.0, "MSFT": 10.0}
        )
        first = gate.evaluate_order(snap, make_intent("AAPL", 30.0, "order-1"), now=at())
        self.assertEqual(first.outcome, ALLOW)  # 300/1000 = 0.30 < 0.5
        second = gate.evaluate_order(snap, make_intent("MSFT", 30.0, "order-2"), now=at())
        # 300 + 300 = 600 -> 0.60 >= 0.5 gross cap
        self.assertEqual(second.reason, DENY_MAX_GROSS_PCT)

    def test_price_unavailable_denies_an_exposure_increasing_order(self):
        gate = self.gate()
        snap = make_snapshot(at(), 1000.0, prices={})
        decision = gate.evaluate_order(snap, make_intent("AAPL", 5.0), now=at())
        self.assertEqual(decision.reason, DENY_PRICE_UNAVAILABLE)

    def test_reduce_only_bypasses_the_exposure_cap(self):
        gate = self.gate(make_config(max_position_pct=0.05))
        # Position already far over any sane cap (market moved against us);
        # a reduce-only order must still be allowed through.
        snap = make_snapshot(
            at(), 1000.0, positions={"AAPL": 900.0}, prices={"AAPL": 10.0}
        )
        decision = gate.evaluate_order(snap, make_intent("AAPL", -5.0), now=at())
        self.assertEqual(decision.outcome, ALLOW)

    def test_short_not_supported(self):
        gate = self.gate()
        snap = make_snapshot(at(), 1000.0, positions={"AAPL": 5.0}, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(snap, make_intent("AAPL", -10.0), now=at())
        self.assertEqual(decision.reason, DENY_SHORT_NOT_SUPPORTED)

    def test_duplicate_client_order_id_denied(self):
        gate = self.gate()
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        gate.evaluate_order(snap, make_intent("AAPL", 1.0, "dup"), now=at())
        decision = gate.evaluate_order(snap, make_intent("AAPL", 1.0, "dup"), now=at())
        self.assertEqual(decision.reason, DENY_DUPLICATE_ORDER)

    def test_terminal_orders_stop_counting_toward_exposure(self):
        gate = self.gate(make_config(max_position_pct=0.25))
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        gate.evaluate_order(snap, make_intent("AAPL", 20.0, "order-1"), now=at())
        blocked = gate.evaluate_order(snap, make_intent("AAPL", 10.0, "order-2"), now=at())
        self.assertEqual(blocked.reason, DENY_MAX_POSITION_PCT)
        gate.record_order_outcome("order-1", terminal=True, reason="cancelled", now=at())
        allowed = gate.evaluate_order(snap, make_intent("AAPL", 10.0, "order-3"), now=at())
        self.assertEqual(allowed.outcome, ALLOW)


# ---------------------------------------------------------------------------
# Daily loss / rolling drawdown circuit breaker
# ---------------------------------------------------------------------------


class LossDrawdownBreakerTests(GateTestCase):
    def test_control_no_breach_no_halt(self):
        gate = self.gate()
        snap = make_snapshot(at(), 100_000.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(snap, make_intent("AAPL", 1.0), now=at())
        self.assertEqual(decision.outcome, ALLOW)

    def test_daily_loss_breach_blocks_adds_but_permits_reductions(self):
        gate = self.gate(make_config(daily_loss_pct=0.02))
        day1_open = make_snapshot(
            at(hour=14), 100_000.0, positions={"AAPL": 10.0}, prices={"AAPL": 10.0}
        )
        gate.evaluate_order(day1_open, make_intent("AAPL", 0.0001), now=at(hour=14))
        breached = make_snapshot(
            at(hour=16), 97_000.0, positions={"AAPL": 10.0}, prices={"AAPL": 10.0}
        )  # -3% vs day start
        add = gate.evaluate_order(breached, make_intent("AAPL", 1.0, "add"), now=at(hour=16))
        self.assertEqual(add.reason, DENY_LOSS_HALT)
        self.assertEqual(add.action, ACTION_CANCEL_RISK_ADDING)
        reduce = gate.evaluate_order(breached, make_intent("AAPL", -1.0, "reduce"), now=at(hour=16))
        self.assertEqual(reduce.outcome, ALLOW)
        self.assertEqual(reduce.action, ACTION_REDUCE_ONLY)

    def test_daily_halt_survives_intraday_recovery_same_day(self):
        gate = self.gate(make_config(daily_loss_pct=0.02))
        gate.evaluate_order(
            make_snapshot(at(hour=14), 100_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "seed"),
            now=at(hour=14),
        )
        gate.evaluate_order(
            make_snapshot(at(hour=15), 97_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "breach"),
            now=at(hour=15),
        )
        recovered = make_snapshot(at(hour=18), 99_900.0, prices={"AAPL": 10.0})  # still -0.1%, no new breach
        decision = gate.evaluate_order(recovered, make_intent("AAPL", 1.0, "after"), now=at(hour=18))
        self.assertEqual(decision.reason, DENY_LOSS_HALT)

    def test_daily_halt_clears_the_next_trading_day(self):
        gate = self.gate(make_config(daily_loss_pct=0.02))
        gate.evaluate_order(
            make_snapshot(at(hour=14), 100_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "seed"),
            now=at(hour=14),
        )
        gate.evaluate_order(
            make_snapshot(at(hour=15), 97_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "breach"),
            now=at(hour=15),
        )
        next_day = make_snapshot(at(day=11, hour=14), 97_500.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(next_day, make_intent("AAPL", 1.0, "next"), now=at(day=11, hour=14))
        self.assertEqual(decision.outcome, ALLOW)

    def test_cash_flow_is_excluded_from_daily_loss(self):
        gate = self.gate(make_config(daily_loss_pct=0.02))
        gate.evaluate_order(
            make_snapshot(at(hour=14), 100_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "seed"),
            now=at(hour=14),
        )
        # Equity drops 5% in raw terms, but all of it is a withdrawal, not a
        # trading loss -- must NOT halt.
        withdrawal = make_snapshot(
            at(hour=16), 95_000.0, prices={"AAPL": 10.0}, cash_flow=-5_000.0
        )
        decision = gate.evaluate_order(withdrawal, make_intent("AAPL", 1.0, "after"), now=at(hour=16))
        self.assertEqual(decision.outcome, ALLOW)

    def test_rolling_drawdown_latches_across_days_until_reset(self):
        gate = self.gate(make_config(rolling_drawdown_pct=0.10, rolling_window_sessions=5, daily_loss_pct=0.5))
        gate.evaluate_order(
            make_snapshot(at(day=8, hour=14), 100_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "d1"),
            now=at(day=8, hour=14),
        )
        gate.evaluate_order(
            make_snapshot(at(day=9, hour=14), 88_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "d2"),
            now=at(day=9, hour=14),
        )  # -12% drawdown from the day-1 high -> breach, latches
        recovered = make_snapshot(at(day=10, hour=14), 100_000.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(recovered, make_intent("AAPL", 1.0, "d3"), now=at(day=10, hour=14))
        self.assertEqual(decision.reason, DENY_LOSS_HALT)
        self.assertTrue(gate.status()["rolling_halt_active"])

    def test_rolling_reset_rejected_while_still_breaching(self):
        gate = self.gate(make_config(rolling_drawdown_pct=0.10, daily_loss_pct=0.5))
        gate.evaluate_order(
            make_snapshot(at(day=8, hour=14), 100_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "d1"),
            now=at(day=8, hour=14),
        )
        gate.evaluate_order(
            make_snapshot(at(day=9, hour=14), 88_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "d2"),
            now=at(day=9, hour=14),
        )
        still_down = make_snapshot(at(day=10, hour=14), 88_000.0, prices={"AAPL": 10.0})
        with self.assertRaises(ValueError):
            gate.reset_rolling_halt(still_down, operator="camden", reason="review", now=at(day=10, hour=14))

    def test_rolling_reset_succeeds_once_recovered_and_logged(self):
        gate = self.gate(make_config(rolling_drawdown_pct=0.10, daily_loss_pct=0.5))
        gate.evaluate_order(
            make_snapshot(at(day=8, hour=14), 100_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "d1"),
            now=at(day=8, hour=14),
        )
        gate.evaluate_order(
            make_snapshot(at(day=9, hour=14), 88_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "d2"),
            now=at(day=9, hour=14),
        )
        recovered = make_snapshot(at(day=10, hour=14), 100_000.0, prices={"AAPL": 10.0})
        gate.reset_rolling_halt(recovered, operator="camden", reason="reviewed", now=at(day=10, hour=14))
        decision = gate.evaluate_order(recovered, make_intent("AAPL", 1.0, "after"), now=at(day=10, hour=14))
        self.assertEqual(decision.outcome, ALLOW)
        events = [e["event_type"] for e in gate.evidence()]
        self.assertIn("ROLLING_HALT_RESET", events)


# ---------------------------------------------------------------------------
# Manual kill switch
# ---------------------------------------------------------------------------


class KillSwitchTests(GateTestCase):
    def test_control_no_kill_orders_flow_normally(self):
        gate = self.gate()
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(snap, make_intent("AAPL", 1.0), now=at())
        self.assertEqual(decision.outcome, ALLOW)

    def test_request_kill_returns_local_blocked_and_denies_everything(self):
        gate = self.gate()
        result = gate.request_kill(operator="camden", reason="unexpected behavior", now=at())
        self.assertEqual(result, KILL_LOCAL_BLOCKED)
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        add = gate.evaluate_order(snap, make_intent("AAPL", 1.0), now=at())
        self.assertEqual(add.reason, DENY_KILL_LATCHED)
        self.assertEqual(add.action, ACTION_KILL_LATCHED)

    def test_kill_denies_reduce_only_on_the_automated_path(self):
        # Deliberate, documented reading of spec 032's internal conflict --
        # see the module docstring. The automated strategy path follows the
        # stricter "all submissions denied" text.
        gate = self.gate()
        gate.request_kill(operator="camden", reason="halt everything", now=at())
        snap = make_snapshot(at(), 1000.0, positions={"AAPL": 5.0}, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(snap, make_intent("AAPL", -1.0), now=at())
        self.assertEqual(decision.reason, DENY_KILL_LATCHED)

    def test_operator_override_can_reduce_during_kill(self):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="halt everything", now=at())
        snap = make_snapshot(at(), 1000.0, positions={"AAPL": 5.0}, prices={"AAPL": 10.0})
        decision = gate.evaluate_operator_override_reduce(
            snap, make_intent("AAPL", -1.0), operator="camden", reason="manual flatten", now=at()
        )
        self.assertEqual(decision.outcome, ALLOW)

    def test_operator_override_rejects_an_order_that_is_not_reduce_only(self):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="halt everything", now=at())
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        with self.assertRaises(ValueError):
            gate.evaluate_operator_override_reduce(
                snap, make_intent("AAPL", 1.0), operator="camden", reason="x", now=at()
            )

    def test_confirm_kill_with_no_query_is_unverified(self):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="x", now=at())
        self.assertEqual(gate.confirm_kill(query=None, now=at()), KILL_BROKER_DISABLE_UNVERIFIED)

    def test_confirm_kill_with_working_orders_still_open_is_reconciling(self):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="x", now=at())
        query = BrokerKillQuery(working_orders_terminal=False, disable_status=None)
        self.assertEqual(gate.confirm_kill(query=query, now=at()), KILL_RECONCILING)

    def test_confirm_kill_broker_not_yet_disabled_is_cancel_pending(self):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="x", now=at())
        query = BrokerKillQuery(working_orders_terminal=True, disable_status=False)
        self.assertEqual(gate.confirm_kill(query=query, now=at()), KILL_BROKER_CANCEL_PENDING)

    def test_confirm_kill_fully_confirmed(self):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="x", now=at())
        query = BrokerKillQuery(working_orders_terminal=True, disable_status=True)
        self.assertEqual(gate.confirm_kill(query=query, now=at()), KILL_CONFIRMED)

    def test_reset_kill_without_confirmation_or_attestation_raises(self):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="x", now=at())
        with self.assertRaises(ValueError):
            gate.reset_kill(operator="camden", reason="resolved", now=at())

    def test_reset_kill_with_independent_attestation_succeeds(self):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="x", now=at())
        gate.reset_kill(
            operator="camden",
            reason="verified via broker UI",
            broker_disable_independently_verified=True,
            now=at(),
        )
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        decision = gate.evaluate_order(snap, make_intent("AAPL", 1.0), now=at())
        self.assertEqual(decision.outcome, ALLOW)

    def test_reset_kill_blocked_while_rolling_halt_active(self):
        gate = self.gate(make_config(rolling_drawdown_pct=0.10, daily_loss_pct=0.5))
        gate.evaluate_order(
            make_snapshot(at(day=8, hour=14), 100_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "d1"),
            now=at(day=8, hour=14),
        )
        gate.evaluate_order(
            make_snapshot(at(day=9, hour=14), 88_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "d2"),
            now=at(day=9, hour=14),
        )
        gate.request_kill(operator="camden", reason="x", now=at(day=9, hour=15))
        with self.assertRaises(ValueError):
            gate.reset_kill(
                operator="camden",
                reason="y",
                broker_disable_independently_verified=True,
                now=at(day=9, hour=15),
            )

    def test_both_latches_clear_inner_rolling_then_outer_kill(self):
        gate = self.gate(make_config(rolling_drawdown_pct=0.10, daily_loss_pct=0.5))
        gate.evaluate_order(
            make_snapshot(at(day=8, hour=14), 100_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "both-d1"),
            now=at(day=8, hour=14),
        )
        gate.evaluate_order(
            make_snapshot(at(day=9, hour=14), 88_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "both-d2"),
            now=at(day=9, hour=14),
        )
        gate.request_kill(operator="camden", reason="same incident", now=at(day=9, hour=15))

        with self.assertRaises(ValueError):
            gate.reset_kill(
                operator="camden",
                reason="wrong order",
                broker_disable_independently_verified=True,
                now=at(day=9, hour=15),
            )

        recovered = make_snapshot(
            at(day=10, hour=14), 100_000.0, prices={"AAPL": 10.0}
        )
        gate.reset_rolling_halt(
            recovered,
            operator="camden",
            reason="drawdown reviewed and recovered",
            now=at(day=10, hour=14),
        )
        inner_cleared = gate.status()
        self.assertFalse(inner_cleared["rolling_halt_active"])
        self.assertTrue(inner_cleared["kill_latched"])

        gate.reset_kill(
            operator="camden",
            reason="outer latch cleared last",
            broker_disable_independently_verified=True,
            now=at(day=10, hour=14),
        )
        self.assertFalse(gate.status()["kill_latched"])


# ---------------------------------------------------------------------------
# Durable state survives restart (REQ-006) -- the exact audit finding this
# module exists to close: spec 017's halt latch lived only in memory.
# ---------------------------------------------------------------------------


class RestartDurabilityTests(GateTestCase):
    def test_kill_latch_survives_a_simulated_restart(self):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="unexpected behavior", now=at())
        gate.close()

        restarted = self.gate()  # a brand-new process would do exactly this
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        decision = restarted.evaluate_order(snap, make_intent("AAPL", 1.0), now=at())
        self.assertEqual(decision.reason, DENY_KILL_LATCHED)

    def test_pending_reservations_survive_a_simulated_restart(self):
        gate = self.gate(make_config(max_position_pct=0.25))
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        gate.evaluate_order(snap, make_intent("AAPL", 20.0, "order-1"), now=at())
        gate.close()

        restarted = self.gate(make_config(max_position_pct=0.25))
        blocked = restarted.evaluate_order(snap, make_intent("AAPL", 10.0, "order-2"), now=at())
        self.assertEqual(blocked.reason, DENY_MAX_POSITION_PCT)

    def test_rolling_halt_survives_a_simulated_restart(self):
        gate = self.gate(make_config(rolling_drawdown_pct=0.10, daily_loss_pct=0.5))
        gate.evaluate_order(
            make_snapshot(at(day=8, hour=14), 100_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "d1"),
            now=at(day=8, hour=14),
        )
        gate.evaluate_order(
            make_snapshot(at(day=9, hour=14), 88_000.0, prices={"AAPL": 10.0}),
            make_intent("AAPL", 0.0001, "d2"),
            now=at(day=9, hour=14),
        )
        gate.close()

        restarted = self.gate(make_config(rolling_drawdown_pct=0.10, daily_loss_pct=0.5))
        recovered = make_snapshot(at(day=10, hour=14), 100_000.0, prices={"AAPL": 10.0})
        decision = restarted.evaluate_order(recovered, make_intent("AAPL", 1.0, "d3"), now=at(day=10, hour=14))
        self.assertEqual(decision.reason, DENY_LOSS_HALT)


# ---------------------------------------------------------------------------
# Evidence trail (REQ-010)
# ---------------------------------------------------------------------------


class EvidenceTrailTests(GateTestCase):
    def test_every_allow_and_deny_is_logged(self):
        gate = self.gate()
        snap = make_snapshot(at(), 1000.0, prices={"AAPL": 10.0})
        gate.evaluate_order(snap, make_intent("AAPL", 1.0, "ok"), now=at())
        gate.evaluate_order(snap, make_intent("AAPL", 1.0, "ok"), now=at())  # duplicate -> deny
        outcomes = [e["event_type"] for e in gate.evidence() if e["event_type"] in (ALLOW, DENY)]
        self.assertIn(ALLOW, outcomes)
        self.assertIn(DENY, outcomes)


# ---------------------------------------------------------------------------
# Rule 12 -- plant the defect, prove the gate fires, control passes clean.
# ---------------------------------------------------------------------------


class MutationTests(unittest.TestCase):
    """Each oracle below gets its own temp DB file so control and mutant runs
    never share state, and each targets exactly one plausible defect.

    ``mutation_support_032.killed`` re-executes the *entire* module source
    into ``live_safety_gate.__dict__`` to build the mutant, which means every
    class in the module -- not just the mutated method -- is a freshly built
    object while the mutant is live. An ``OrderIntent`` or ``SafetyConfig``
    built from this test file's own top-level imports (bound once, at import
    time, long before any mutation) is an instance of the *old* class, and
    would fail an ``isinstance`` check inside the mutant's freshly rebuilt
    ``SafetyGate``. Every object below is therefore built through ``module``
    itself (``module.SafetyConfig(...)`` etc.), so construction and
    consumption always agree on which class is currently live.
    """

    def _config(self, module, **overrides):
        values = dict(
            version="test-v1",
            max_position_pct=0.25,
            max_gross_pct=1.0,
            daily_loss_pct=0.02,
            rolling_drawdown_pct=0.05,
            rolling_window_sessions=5,
            max_snapshot_age_seconds=30.0,
            max_clock_skew_seconds=5.0,
        )
        values.update(overrides)
        return module.SafetyConfig(**values)

    def _snapshot(self, module, as_of, equity, *, positions=None, prices=None, cash_flow=0.0):
        return module.BrokerSnapshot(
            as_of=as_of,
            status="OK",
            equity=equity,
            external_cash_flow=cash_flow,
            positions=positions or {},
            prices=prices or {},
        )

    def _intent(self, module, instrument, delta, order_id=None):
        return module.OrderIntent(
            client_order_id=order_id or f"order-{delta}-{instrument}",
            instrument=instrument,
            delta_quantity=delta,
        )

    def test_inclusive_position_boundary_is_actually_enforced(self):
        def oracle():
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                gate = lsg.SafetyGate(
                    Path(tmp) / "gate.db", self._config(lsg, max_position_pct=0.25)
                )
                try:
                    snap = self._snapshot(lsg, at(), 1000.0, prices={"AAPL": 10.0})
                    decision = gate.evaluate_order(snap, self._intent(lsg, "AAPL", 25.0), now=at())
                    assert decision.outcome == lsg.DENY, "exact-boundary order must be denied"
                finally:
                    gate.close()

        mutation_support_032.killed(
            lsg,
            'exposure["instrument_notional"] / equity >= self._config.max_position_pct:',
            'exposure["instrument_notional"] / equity > self._config.max_position_pct:',
            oracle,
        )

    def test_nonpositive_equity_guard_is_actually_before_any_division(self):
        def oracle():
            for equity in (0.0, -100.0):
                with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                    gate = lsg.SafetyGate(Path(tmp) / "gate.db", self._config(lsg))
                    try:
                        snap = self._snapshot(lsg, at(), equity, prices={"AAPL": 10.0})
                        try:
                            decision = gate.evaluate_order(
                                snap, self._intent(lsg, "AAPL", 1.0), now=at()
                            )
                        except Exception as exc:
                            raise AssertionError(
                                f"equity {equity} must deny, not raise {type(exc).__name__}"
                            ) from exc
                        assert decision.reason == lsg.DENY_NON_POSITIVE_EQUITY, (
                            f"equity {equity} must fail closed before sizing"
                        )
                    finally:
                        gate.close()

        mutation_support_032.killed(
            lsg,
            "if not math.isfinite(snapshot.equity) or snapshot.equity <= 0.0:",
            "if not math.isfinite(snapshot.equity):",
            oracle,
        )

    def test_kill_latch_is_actually_checked(self):
        def oracle():
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                gate = lsg.SafetyGate(Path(tmp) / "gate.db", self._config(lsg))
                try:
                    gate.request_kill(operator="camden", reason="x", now=at())
                    snap = self._snapshot(
                        lsg, at(), 1000.0, positions={"AAPL": 5.0}, prices={"AAPL": 10.0}
                    )
                    decision = gate.evaluate_order(snap, self._intent(lsg, "AAPL", -1.0), now=at())
                    assert decision.outcome == lsg.DENY, "a kill latch must deny every order"
                finally:
                    gate.close()

        mutation_support_032.killed(
            lsg,
            'if state["kill_latched"]:\n            decision = self._deny(DENY_KILL_LATCHED',
            'if False and state["kill_latched"]:\n            decision = self._deny(DENY_KILL_LATCHED',
            oracle,
        )

    def test_pending_orders_are_actually_aggregated_into_exposure(self):
        def oracle():
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                gate = lsg.SafetyGate(
                    Path(tmp) / "gate.db",
                    self._config(lsg, max_position_pct=0.5, max_gross_pct=0.5),
                )
                try:
                    snap = self._snapshot(
                        lsg, at(), 1000.0, prices={"AAPL": 10.0, "MSFT": 10.0}
                    )
                    first = gate.evaluate_order(
                        snap, self._intent(lsg, "AAPL", 30.0, "order-1"), now=at()
                    )
                    assert first.outcome == lsg.ALLOW
                    second = gate.evaluate_order(
                        snap, self._intent(lsg, "MSFT", 30.0, "order-2"), now=at()
                    )
                    assert second.outcome == lsg.DENY, (
                        "a second order must not pass by ignoring the first's reservation"
                    )
                finally:
                    gate.close()

        mutation_support_032.killed(
            lsg,
            "return {instrument: float(total) for instrument, total in rows}",
            "return {}",
            oracle,
        )

    def test_reduce_only_is_actually_exempted_from_a_loss_halt(self):
        def oracle():
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                gate = lsg.SafetyGate(
                    Path(tmp) / "gate.db", self._config(lsg, daily_loss_pct=0.02)
                )
                try:
                    gate.evaluate_order(
                        self._snapshot(
                            lsg, at(hour=14), 100_000.0,
                            positions={"AAPL": 10.0}, prices={"AAPL": 10.0},
                        ),
                        self._intent(lsg, "AAPL", 0.0001, "seed"),
                        now=at(hour=14),
                    )
                    breached = self._snapshot(
                        lsg, at(hour=16), 97_000.0,
                        positions={"AAPL": 10.0}, prices={"AAPL": 10.0},
                    )
                    decision = gate.evaluate_order(
                        breached, self._intent(lsg, "AAPL", -1.0, "reduce"), now=at(hour=16)
                    )
                    assert decision.outcome == lsg.ALLOW, (
                        "a halt must still allow a reduce-only order through"
                    )
                finally:
                    gate.close()

        mutation_support_032.killed(
            lsg,
            "if halted and not is_reduce_only:",
            "if halted:",
            oracle,
        )

    def test_restart_actually_reloads_the_kill_latch_from_disk(self):
        def oracle():
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                path = Path(tmp) / "gate.db"
                gate = lsg.SafetyGate(path, self._config(lsg))
                gate.request_kill(operator="camden", reason="x", now=at())
                gate.close()
                restarted = lsg.SafetyGate(path, self._config(lsg))
                try:
                    snap = self._snapshot(lsg, at(), 1000.0, prices={"AAPL": 10.0})
                    decision = restarted.evaluate_order(
                        snap, self._intent(lsg, "AAPL", 1.0), now=at()
                    )
                    assert decision.outcome == lsg.DENY, (
                        "a restart must not forget a durable kill latch"
                    )
                finally:
                    restarted.close()

        mutation_support_032.killed(
            lsg,
            "return {key: json.loads(value) for key, value in rows}",
            'return {**{key: json.loads(value) for key, value in rows}, "kill_latched": False}',
            oracle,
        )


if __name__ == "__main__":
    unittest.main()
