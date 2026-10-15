"""Spec 059 T008 / FR-007: the §11.3 checklist prints ARMABLE only with evidence for every item.

EXAMPLE — NOT A RESULT. Synthetic artifacts in a temporary root; nothing is armed.
"""
from __future__ import annotations

import hashlib
import json

import context  # noqa: F401
import gate_checklist  # noqa: E402


def evidenced(tmp_path, numbers=None):
    numbers = numbers or [n for n, _ in gate_checklist.ITEMS]
    items = {}
    for n in numbers:
        path = tmp_path / "evidence" / f"item{n}.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"evidence for item {n}\n", encoding="utf-8")
        items[n] = {"artifact": f"evidence/item{n}.md", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "commit": "c3eb34846a65", "date_utc": "2026-10-15T01:00:00Z"}
    return {"items": items}


def test_every_item_evidenced_is_armable(tmp_path):
    armable, lines = gate_checklist.checklist(evidenced(tmp_path), tmp_path)
    assert armable and lines[-1].startswith("ARMABLE"), f"T008 ARMABLE {lines}"
    assert len(lines) == 8 and all("EVIDENCED" in line for line in lines[:7]), "T008 ARMABLE lines"
    assert all("c3eb34846a65" in line and "2026-10-15" in line for line in lines[:7]), "T008 SOURCE commit/date"


def test_one_missing_item_is_not_armable(tmp_path):
    manifest = evidenced(tmp_path, ["1", "2", "3", "4", "5", "7"])
    armable, lines = gate_checklist.checklist(manifest, tmp_path)
    assert not armable and lines[-1].startswith("NOT ARMABLE"), "T008 MISSING armable with item 6 absent"
    assert "MISSING" in lines[5] and "§11.3.6" in lines[5], f"T008 MISSING wrong line {lines[5]}"


def test_altered_absent_or_escaping_artifacts_are_missing(tmp_path):
    manifest = evidenced(tmp_path)
    (tmp_path / "evidence" / "item4.md").write_text("edited after the digest\n", encoding="utf-8")
    (tmp_path / "evidence" / "item5.md").unlink()
    manifest["items"]["2"]["artifact"] = "../outside.md"
    (tmp_path.parent / "outside.md").write_text("x", encoding="utf-8")
    manifest["items"]["3"]["date_utc"] = "2026-10-15T01:00:00-05:00"
    manifest["items"]["1"]["commit"] = "not-a-sha"
    armable, lines = gate_checklist.checklist(manifest, tmp_path)
    reasons = {line.split("§11.3.")[1][0]: line for line in lines[:7]}
    assert not armable, "T008 INTEGRITY armable with bad evidence"
    assert "hash" in reasons["4"] and "does not exist" in reasons["5"], f"T008 INTEGRITY {reasons}"
    assert "outside the repository" in reasons["2"] and "UTC" in reasons["3"] and "commit" in reasons["1"], f"T008 INTEGRITY {reasons}"


def test_cli_exit_code_and_unreadable_manifest(tmp_path, capsys):
    bad = tmp_path / "m.json"
    bad.write_text("{not json", encoding="utf-8")
    assert gate_checklist.main([str(bad)]) == 1, "T008 CLI unreadable manifest passed"
    assert "NOT ARMABLE" in capsys.readouterr().out, "T008 CLI message"
    empty = tmp_path / "e.json"
    empty.write_text(json.dumps({"items": {}}), encoding="utf-8")
    assert gate_checklist.main([str(empty)]) == 1, "T008 CLI empty manifest passed"
