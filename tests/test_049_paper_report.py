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


@pytest.mark.parametrize("contents", ["{invalid}\n", "[]\n", json.dumps({"mode": "submit"}) + "\n"])
def test_invalid_record_names_file_and_line(tmp_path, capsys, contents):
    path = tmp_path / "bad.jsonl"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        paper_report.main([str(path)])
    assert error.value.code == 2
    output = capsys.readouterr()
    assert f"{path.resolve()}:1" in output.err
    assert not output.out


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
