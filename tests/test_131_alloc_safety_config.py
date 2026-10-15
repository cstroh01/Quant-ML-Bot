"""Queue Q131: the spec 059 allocation's PAPER SafetyConfig (Camden, 2026-10-14 23:32 CT, "alloc config yes").

EXAMPLE — NOT A RESULT. Offline; fakes; synthetic prices; temporary state.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from test_110_paper_allocation import ALL_FRACTIONAL, NOW, Client, sleeve_closes  # noqa: E402 - puts exec/ on path
import paper_loop  # noqa: E402
import replay_runner  # noqa: E402
from live_safety_gate import LiveSafetyGate  # noqa: E402


def test_values_are_the_ones_camden_accepted():
    c = paper_loop.ALLOCATION_SAFETY_CONFIG
    got = (c.version, c.max_position_pct, c.max_gross_pct, c.daily_loss_pct, c.rolling_drawdown_pct,
           c.rolling_window_sessions, c.max_snapshot_age_seconds, c.max_clock_skew_seconds)
    assert got == ("2026-10-14-alloc-v1", 0.40, 1.00, 0.03, 0.15, 63, 60, 5), f"Q131 VALUES {got}"
    assert paper_loop.PAPER_SAFETY_CONFIG.version == "2026-09-29-v1", "Q131 VALUES the 2026-09-29 config changed"


def test_the_allocation_deploys_through_the_gate_under_these_limits(tmp_path):
    gate = LiveSafetyGate(tmp_path / "gate.sqlite", paper_loop.ALLOCATION_SAFETY_CONFIG)
    planner = paper_loop.AllocationPlanner(tmp_path / paper_loop.ALLOCATION_STATE, ALL_FRACTIONAL)
    try:
        record = paper_loop.run_once(client=Client(), gate=gate, closes=sleeve_closes(), submit=True, now_fn=NOW,
                                     planner=planner)
    finally:
        gate.close()
    outcomes = {a["outcome"] for a in record["actions"]}
    assert outcomes == {"SUBMITTED"} and record["decision_executed"] == "2026-10-01", f"Q131 ALLOWS {outcomes}"
    assert record["safety_config_version"] == "2026-10-14-alloc-v1", "Q131 ALLOWS run log names the wrong config"


def test_main_trades_under_the_allocation_config(tmp_path, monkeypatch):
    seen = []
    real = paper_loop.LiveSafetyGate

    def spy(path, config):
        seen.append(config.version)
        return real(path, config)

    monkeypatch.setattr(paper_loop, "LiveSafetyGate", spy)
    monkeypatch.setattr(paper_loop, "GATE_DB", tmp_path / "paper-gate.sqlite")
    monkeypatch.setattr(paper_loop, "RUN_LOG_DIR", tmp_path / "paper-runs")
    monkeypatch.setattr(paper_loop, "fetch_sleeve_closes", lambda now, **_: (sleeve_closes(), []))
    paper_loop.main(["--offline"])
    assert seen == ["2026-10-14-alloc-v1"], f"Q131 WIRED main used {seen}"


def test_the_replay_defaults_to_the_allocation_config():
    from test_111_replay import panels
    opens, closes = panels()
    report = replay_runner.replay_window(opens, closes, date(2020, 2, 3), date(2020, 3, 13),
                                         profile=replay_runner.replay_profile(5000.0, 1.0))
    assert report["safety_config_version"] == "2026-10-14-alloc-v1", "Q131 REPLAY default config"
    assert not report["denied"] and not report["errors"], f"Q131 REPLAY {report['denied'][:3]} {report['errors']}"
    assert pd.Timestamp(report["window"][0]) == pd.Timestamp("2020-02-03"), "Q131 REPLAY window"
