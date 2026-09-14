import json
import os
import tempfile
import unittest

from context import SCRIPTS_DIR  # noqa: F401

import trial_registry


def make_record(**overrides):
    record = {
        "trial_id": "11111111-1111-4111-8111-111111111111",
        "timestamp_utc": "2026-09-14T12:00:00Z",
        "git_commit": "abc1234",
        "git_dirty": False,
        "spec": "013",
        "family": "momentum-price-only",
        "target": {"label": "AAPL", "horizon_days": 5},
        "universe": ["AAPL", "MSFT"],
        "features": ["close_5d_ret", "rsi_14"],
        "feature_hash": "a" * 64,
        "model": {"name": "logit", "params": {"C": 1.0, "solver": "lbfgs"}},
        "cv": {"scheme": "walkforward", "folds": 5, "purge_days": 5, "embargo_days": 5},
        "seed": 123,
        "outcome": "kept",
        "metrics": {"is_sharpe": None, "oos_sharpe": 1.23, "n_obs": 420},
        "sampling_frequency": "daily",
        "return_convention": "trade_pnl",
        "risk_free_source": "Fed funds proxy",
        "cost_model": {"commission": 0.0005, "slippage": 0.0002, "impact": 0.0},
        "oos_returns_path": "data/cache/out_returns.csv",
        "oos_returns_sha256": "b" * 64,
        "comparable_oos_sharpe": None,
        "notes": "Initial baseline trial.",
        "prev_hash": "",
    }
    record.update(overrides)
    if "record_hash" not in record:
        record["record_hash"] = trial_registry._record_hash_for_test(record)
    return record


class TrialRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.path = os.path.join(self.tmpdir.name, "trials.jsonl")

    def _log_three(self):
        first = trial_registry.log_trial(
            path=self.path,
            spec="013",
            family="momentum-price-only",
            target={"label": "AAPL", "horizon_days": 5},
            universe=["AAPL", "MSFT"],
            features=["close_5d_ret", "rsi_14"],
            model={"name": "logit", "params": {"C": 1.0, "solver": "lbfgs"}},
            cv={
                "scheme": "walkforward",
                "folds": 5,
                "purge_days": 5,
                "embargo_days": 5,
            },
            seed=123,
            outcome="kept",
            metrics={"is_sharpe": None, "oos_sharpe": 1.23, "n_obs": 420},
            sampling_frequency="daily",
            return_convention="trade_pnl",
            risk_free_source="Fed funds proxy",
            cost_model={"commission": 0.0005, "slippage": 0.0002, "impact": 0.0},
            oos_returns_path="data/cache/out_returns.csv",
            oos_returns_sha256="a" * 64,
            comparable_oos_sharpe=None,
            notes="first",
            git_commit="abc1234",
            git_dirty=False,
        )
        second = trial_registry.log_trial(
            path=self.path,
            spec="013",
            family="momentum-price-only",
            target={"label": "AAPL", "horizon_days": 5},
            universe=["AAPL", "MSFT"],
            features=["close_5d_ret", "rsi_14"],
            model={"name": "logit", "params": {"C": 1.0, "solver": "lbfgs"}},
            cv={
                "scheme": "walkforward",
                "folds": 5,
                "purge_days": 5,
                "embargo_days": 5,
            },
            seed=456,
            outcome="abandoned",
            metrics={"is_sharpe": None, "oos_sharpe": 0.87, "n_obs": 410},
            sampling_frequency="daily",
            return_convention="trade_pnl",
            risk_free_source="Fed funds proxy",
            cost_model={"commission": 0.0005, "slippage": 0.0002, "impact": 0.0},
            oos_returns_path="data/cache/out_returns_2.csv",
            oos_returns_sha256="b" * 64,
            comparable_oos_sharpe=None,
            notes="second",
            git_commit="abc1235",
            git_dirty=False,
        )
        third = trial_registry.log_trial(
            path=self.path,
            spec="013",
            family="momentum-price-only",
            target={"label": "AAPL", "horizon_days": 5},
            universe=["AAPL", "MSFT"],
            features=["close_5d_ret", "rsi_14"],
            model={"name": "logit", "params": {"C": 1.0, "solver": "lbfgs"}},
            cv={
                "scheme": "walkforward",
                "folds": 5,
                "purge_days": 5,
                "embargo_days": 5,
            },
            seed=789,
            outcome="rejected",
            metrics={"is_sharpe": None, "oos_sharpe": -0.54, "n_obs": 440},
            sampling_frequency="daily",
            return_convention="trade_pnl",
            risk_free_source="Fed funds proxy",
            cost_model={"commission": 0.0005, "slippage": 0.0002, "impact": 0.0},
            oos_returns_path="data/cache/out_returns_3.csv",
            oos_returns_sha256="c" * 64,
            comparable_oos_sharpe=None,
            notes="third",
            git_commit="abc1236",
            git_dirty=True,
        )
        return first, second, third

    def test_round_trip_log_three_trials(self):
        first, second, third = self._log_three()
        records = trial_registry.read_trials(self.path)
        self.assertEqual(len(records), 3)
        self.assertEqual([rec["trial_id"] for rec in records], [first, second, third])
        self.assertEqual(records[0]["notes"], "first")
        self.assertEqual(records[1]["notes"], "second")
        self.assertEqual(records[2]["notes"], "third")

    def test_verify_chain_passes_on_clean_file(self):
        self._log_three()
        trial_registry.verify_chain(self.path)

    def test_verify_chain_raises_if_any_middle_record_is_edited(self):
        self._log_three()
        with open(self.path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        payload = json.loads(lines[1])
        payload["notes"] = "tampered note"
        lines[1] = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.writelines(lines)
        with self.assertRaises(ValueError):
            trial_registry.verify_chain(self.path)

    def test_verify_chain_raises_if_a_record_is_deleted(self):
        self._log_three()
        with open(self.path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        del lines[1]
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.writelines(lines)
        with self.assertRaises(ValueError):
            trial_registry.verify_chain(self.path)

    def test_concurrentish_append_keeps_all_records(self):
        first = trial_registry.log_trial(
            path=self.path,
            spec="013",
            family="momentum-price-only",
            target={"label": "AAPL", "horizon_days": 5},
            universe=["AAPL", "MSFT"],
            features=["close_5d_ret", "rsi_14"],
            model={"name": "logit", "params": {"C": 1.0}},
            cv={
                "scheme": "walkforward",
                "folds": 5,
                "purge_days": 5,
                "embargo_days": 5,
            },
            seed=123,
            outcome="kept",
            metrics={"is_sharpe": None, "oos_sharpe": 1.23, "n_obs": 420},
            sampling_frequency="daily",
            return_convention="trade_pnl",
            risk_free_source="Fed funds proxy",
            cost_model={"commission": 0.0005, "slippage": 0.0002, "impact": 0.0},
            oos_returns_path="data/cache/out_returns.csv",
            oos_returns_sha256="x" * 64,
            comparable_oos_sharpe=None,
            notes="first",
            git_commit="abc1234",
            git_dirty=False,
        )
        second = trial_registry.log_trial(
            path=self.path,
            spec="013",
            family="momentum-price-only",
            target={"label": "AAPL", "horizon_days": 5},
            universe=["AAPL", "MSFT"],
            features=["close_5d_ret", "rsi_14"],
            model={"name": "logit", "params": {"C": 1.0}},
            cv={
                "scheme": "walkforward",
                "folds": 5,
                "purge_days": 5,
                "embargo_days": 5,
            },
            seed=456,
            outcome="abandoned",
            metrics={"is_sharpe": None, "oos_sharpe": 0.87, "n_obs": 410},
            sampling_frequency="daily",
            return_convention="trade_pnl",
            risk_free_source="Fed funds proxy",
            cost_model={"commission": 0.0005, "slippage": 0.0002, "impact": 0.0},
            oos_returns_path="data/cache/out_returns_2.csv",
            oos_returns_sha256="y" * 64,
            comparable_oos_sharpe=None,
            notes="second",
            git_commit="abc1235",
            git_dirty=False,
        )
        records = trial_registry.read_trials(self.path)
        self.assertEqual(len(records), 2)
        self.assertEqual([r["trial_id"] for r in records], [first, second])

    def test_missing_required_field_raises_at_log_time(self):
        with self.assertRaises(ValueError):
            trial_registry.log_trial(
                path=self.path,
                spec="013",
                family="momentum-price-only",
                target={"label": "AAPL", "horizon_days": 5},
                universe=["AAPL", "MSFT"],
                features=["close_5d_ret", "rsi_14"],
                model={"name": "logit", "params": {"C": 1.0}},
                cv={
                    "scheme": "walkforward",
                    "folds": 5,
                    "purge_days": 5,
                    "embargo_days": 5,
                },
                seed=123,
                outcome="kept",
                metrics={"is_sharpe": None, "oos_sharpe": 1.23, "n_obs": 420},
                return_convention="trade_pnl",
                risk_free_source="Fed funds proxy",
                cost_model={"commission": 0.0005, "slippage": 0.0002, "impact": 0.0},
                oos_returns_path="data/cache/out_returns.csv",
                oos_returns_sha256="z" * 64,
                comparable_oos_sharpe=None,
                notes="missing sampling",
                git_commit="abc1234",
                git_dirty=False,
            )
        self.assertEqual(
            os.path.getsize(self.path) if os.path.exists(self.path) else 0, 0
        )

    def test_return_convention_outside_enum_raises_at_log_time(self):
        with self.assertRaises(ValueError):
            trial_registry.log_trial(
                path=self.path,
                spec="013",
                family="momentum-price-only",
                target={"label": "AAPL", "horizon_days": 5},
                universe=["AAPL", "MSFT"],
                features=["close_5d_ret", "rsi_14"],
                model={"name": "logit", "params": {"C": 1.0}},
                cv={
                    "scheme": "walkforward",
                    "folds": 5,
                    "purge_days": 5,
                    "embargo_days": 5,
                },
                seed=123,
                outcome="kept",
                metrics={"is_sharpe": None, "oos_sharpe": 1.23, "n_obs": 420},
                sampling_frequency="daily",
                return_convention="bad_enum",
                risk_free_source="Fed funds proxy",
                cost_model={"commission": 0.0005, "slippage": 0.0002, "impact": 0.0},
                oos_returns_path="data/cache/out_returns.csv",
                oos_returns_sha256="q" * 64,
                comparable_oos_sharpe=None,
                notes="bad return convention",
                git_commit="abc1234",
                git_dirty=False,
            )

    def test_validate_for_gate_names_missing_fields(self):
        record = {
            "sampling_frequency": None,
            "return_convention": None,
            "oos_returns_path": None,
            "oos_returns_sha256": None,
            "comparable_oos_sharpe": None,
        }
        self.assertEqual(
            trial_registry.validate_for_gate(record),
            [
                "sampling_frequency",
                "return_convention",
                "oos_returns_path",
                "oos_returns_sha256",
                "comparable_oos_sharpe",
            ],
        )

    def test_validate_for_gate_returns_empty_for_fully_provisioned_record(self):
        record = {
            "sampling_frequency": "daily",
            "return_convention": "trade_pnl",
            "oos_returns_path": "data/cache/out_returns.csv",
            "oos_returns_sha256": "abc123",
            "comparable_oos_sharpe": None,
        }
        self.assertEqual(trial_registry.validate_for_gate(record), [])

    def test_hash_chain_verifies_across_added_fields(self):
        self._log_three()
        trial_registry.verify_chain(self.path)


if __name__ == "__main__":
    unittest.main()
