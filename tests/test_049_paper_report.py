"""049 T011: report recorded facts, retaining their source and disclosure."""

import copy
import json

import pytest

from scripts import paper_report
from mutation_support_019 import killed


DISCLOSURE = "Paper mechanics prototype. Not a performance result (SCOPE §6; spec 049)."


def example():
    return {
        "run_at_utc": "2026-10-06T12:45:04+00:00",
        "session": "2026-10-05", "mode": "submit",
        "safety_config_version": "2026-09-29-v1",
        "decision": {"AAPL": {"Confidence": 1.0, "Volatility": None, "Target": 0.08}},
        "actions": [{"ticker": "AAPL", "delta_quantity": 23,
                     "target_weight": 0.08, "outcome": "SUBMITTED", "client_order_id": "paper-id"}],
        "reconciliation": [{"client_order_id": "monday-id", "broker_status": "expired"}],
        "disclosure": DISCLOSURE,
    }


def test_recorded_fields_and_provenance():
    record = example()
    before = copy.deepcopy(record)
    report = paper_report.render_run(record, source="synthetic.jsonl:7")
    for text in ("synthetic.jsonl:7", record["run_at_utc"], "2026-10-05", "submit",
                 "2026-09-29-v1", "Confidence", "Volatility", "Target", "AAPL",
                 "1.0", "0.08", "23", "SUBMITTED", "paper-id", "monday-id", "expired", DISCLOSURE):
        assert text in report
    assert "not recorded" in report  # JSON null is never fabricated as zero.
    assert record == before


def test_rejections_unknowns_and_unusual_text():
    record = example()
    record["actions"] = [{"ticker": "A|B", "outcome": "DENIED", "reason": "gap\nlimit"},
                         {"ticker": "C", "outcome": "UNKNOWN", "reason": "timeout"}]
    report = paper_report.render_run(record, source="fixture")
    for text in ("A\\|B", "DENIED", "gap<br>limit", "UNKNOWN", "timeout"):
        assert text in report
    assert "| AAPL | 1.0 | not recorded | 0.08 |" in report


def test_aborted_record_never_becomes_a_success():
    report = paper_report.render_run(
        {"run_at_utc": "2026-10-06T12:45:04+00:00", "aborted": "data is stale"}, source="fixture")
    assert "data is stale" in report
    assert "Aborted" in report
    assert "Disclosure: not recorded" in report
    assert "SUBMITTED" not in report


@pytest.mark.parametrize("mode", ["dry_run", "offline_example"])
def test_modes_retained_without_relabelling(mode):
    record = example()
    record["mode"] = mode
    record["actions"] = []
    record["reconciliation"] = []
    assert mode in paper_report.render_run(record, source="fixture")


def test_missing_normal_disclosure_is_rejected():
    record = example()
    del record["disclosure"]
    with pytest.raises(ValueError, match="disclosure"):
        paper_report.render_run(record, source="fixture")


def test_jsonl_cli_preserves_order_and_changes_no_input(tmp_path, capsys):
    path = tmp_path / "synthetic.jsonl"
    aborted = {"run_at_utc": "2026-10-07T12:45:04+00:00", "aborted": "missing ticker"}
    path.write_text(json.dumps(example()) + "\n\n" + json.dumps(aborted) + "\n", encoding="utf-8")
    before = path.read_bytes()
    assert paper_report.main([str(path)]) == 0
    report = capsys.readouterr().out
    assert f"{path.resolve()}:1" in report
    assert f"{path.resolve()}:3" in report
    assert report.index("2026-10-06") < report.index("2026-10-07")
    assert path.read_bytes() == before


def test_malformed_lines_are_reported_not_skipped(tmp_path, capsys):
    path = tmp_path / "bad.jsonl"
    naive = {**example(), "run_at_utc": "2026-10-06T12:45:04"}
    path.write_text("\n".join([json.dumps(example()), "{invalid}", "[]", json.dumps({"mode": "submit"}),
                               json.dumps(naive)]) + "\n", encoding="utf-8")
    assert paper_report.main([str(path)]) == 1  # a scheduler sees the failure
    report = capsys.readouterr().out
    assert "## Malformed lines" in report and "SUBMITTED" in report
    for number in (2, 3, 4, 5):
        assert f"{path.resolve()}:{number}" in report.split("## 2026")[0]


def test_disclosure_drop_mutant_is_killed():
    def oracle():
        assert DISCLOSURE in paper_report.render_run(example(), source="fixture")

    killed(paper_report, "lines.append(disclosure)", "lines.append('')", oracle)


def offline_oracle():
    record = example()
    record.update(mode="offline_example", equity_source="placeholder, not an account")
    report = paper_report.render_run(record, source="synthetic.jsonl:1")
    numeric_rows = [line for line in report.splitlines() if "| AAPL |" in line]
    assert ("placeholder, not an account" in report and len(numeric_rows) == 2
            and all("EXAMPLE — NOT A RESULT" in line for line in numeric_rows)
            and DISCLOSURE in report), "offline figures must retain labels, placeholder provenance and disclosure"


def test_offline_numeric_rows_are_labelled_with_placeholder_provenance():
    offline_oracle()


def test_offline_label_drop_mutant_is_killed():
    killed(paper_report, r'example_label = "EXAMPLE \u2014 NOT A RESULT"',
           'example_label = ""', offline_oracle)


def test_offline_provenance_drop_mutant_is_killed():
    killed(paper_report, 'f"Equity source: {_cell(record.get(\'equity_source\'))}",',
           '"Equity source: not recorded",', offline_oracle)


# T011 daily report. Fixtures are synthetic: EXAMPLE — NOT A RESULT.
def day_log(tmp_path):
    first = example()
    first["equity"] = 100000.0
    first["actions"] = [
        {"ticker": "AAPL", "delta_quantity": 23, "outcome": "SUBMITTED", "client_order_id": "id-1"},
        {"ticker": "MSFT", "delta_quantity": 9, "outcome": "DENIED", "reason": "max_position_pct"},
        {"ticker": "NVDA", "delta_quantity": 4, "outcome": "REFUSED", "reason": "422 insufficient buying power"},
        {"ticker": "GOOGL", "delta_quantity": 2, "outcome": "UNKNOWN", "reason": "timeout"},
        {"ticker": "AMZN", "delta_quantity": 1}]
    aborted = {"run_at_utc": "2026-10-06T13:00:00+00:00", "aborted": "data is stale"}
    offline = {**example(), "run_at_utc": "2026-10-07T12:45:04+00:00", "mode": "offline_example",
               "equity": 100000.0, "equity_source": "placeholder, not an account",
               "actions": [{"ticker": "AAPL", "delta_quantity": 80, "outcome": "DRY_RUN"}]}
    path = tmp_path / "runs.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in (first, aborted, offline)), encoding="utf-8")
    return path


def test_daily_report_groups_outcomes_aborts_and_refusals(tmp_path):
    report, malformed = paper_report.render_daily(day_log(tmp_path))
    assert malformed == 0
    day1, day2 = report.split("## 2026-10-06")[1].split("## 2026-10-07")
    for text in ("#### SUBMITTED (1)", "#### DENIED (1)", "#### REFUSED (1)", "#### UNKNOWN (1)",
                 "#### not recorded (1)", "data is stale", "100000.0", "monday-id"):
        assert text in day1
    refusals = day1.split("### Refusals")[1]
    for text in ("max_position_pct", "422 insufficient buying power", "timeout", "AMZN"):
        assert text in refusals
    assert "id-1" not in refusals and "#### DRY_RUN (1)" in day2
    assert all("EXAMPLE — NOT A RESULT" in line for line in day2.splitlines() if "100000.0" in line)


def test_disclosure_and_limitations_at_top_and_bottom(tmp_path):
    report, _ = paper_report.render_daily(day_log(tmp_path))
    assert "Paper mechanics prototype. Not a performance result." in paper_report.LIMITATIONS
    for text in ("survivor", "corporate-action", "point-in-time fundamentals", "daily bars only", "modeled"):
        assert text in paper_report.LIMITATIONS
    head, tail = report.split("## 2026-10-06")[0], report.split("#### DRY_RUN")[1]
    for text in (paper_report.LIMITATIONS, DISCLOSURE, "Disclosure: not recorded in the aborted input"):
        assert text in head and text in tail


def test_daily_report_prints_no_performance_figure(tmp_path):
    report, _ = paper_report.render_daily(day_log(tmp_path))
    for word in ("sharpe", "return", "p&l", "pnl", "%", "profit"):
        assert word not in report.lower()


def test_profile_date_and_out(tmp_path, capsys):
    root = paper_report.project_root()
    assert paper_report.log_path(None) == root / "data/live_safety/paper-runs/runs.jsonl"
    assert paper_report.log_path("live") == root / "data/live_safety/live/paper-runs/runs.jsonl"
    for bad in ("", "..", "a/b", "a\\b"):
        with pytest.raises(ValueError, match="profile"):
            paper_report.log_path(bad)
    path, out = day_log(tmp_path), tmp_path / "report.md"
    before = path.read_bytes()
    assert paper_report.main([str(path), "--date", "2026-10-07", "--out", str(out)]) == 0
    assert not capsys.readouterr().out and "## 2026-10-07" in out.read_text(encoding="utf-8")
    assert "## 2026-10-06" not in out.read_text(encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        paper_report.main([str(path), "--out", str(path)])
    assert error.value.code == 2 and path.read_bytes() == before
