"""T029 / AC-8: the shared driver helper isolates copies and trips on real-ledger changes."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "mutation"))
from driver_support import ISOLATION, copy_into, guarded  # noqa: E402


def stand_in(tmp_path):
    root = tmp_path / "real"
    (root / "docs/trials").mkdir(parents=True)
    (root / "docs/trials/trials.jsonl").write_text("", encoding="utf-8")
    return root


def test_tripwire_silent_when_stand_in_ledger_unchanged(tmp_path):
    with guarded(stand_in(tmp_path)):
        pass


def test_tripwire_names_planted_change_to_stand_in_ledger(tmp_path):
    root = stand_in(tmp_path)
    with pytest.raises(AssertionError, match=r"returns/x\.jsonl"):
        with guarded(root):
            (root / "docs/trials/returns").mkdir()
            (root / "docs/trials/returns/x.jsonl").write_text("{}\n", encoding="utf-8")


def test_copies_always_carry_marker_conftest_and_helper(tmp_path):
    root = copy_into(tmp_path / "copy", ("tests/context.py",))
    for relative in (*ISOLATION, "tests/context.py"):
        assert (root / relative).is_file(), relative
