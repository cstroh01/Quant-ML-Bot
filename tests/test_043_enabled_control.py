"""AC-3: a deliberate E1 recording must still produce a verified ledger."""
import pytest

from ledger_copy_support import run_child

pytestmark = pytest.mark.xfail(
    strict=True, reason="043 Phase 1 red; guard lands in T020+"
)


def test_record_trial_flag_records_complete_funded_trials():
    result = run_child("E1", enabled=True)
    assert result["returncode"] == 0, result["stderr"]
    assert result["records"] == 44
    assert result["sidecars"] == 22
    outcome = result["outcome"]
    assert outcome["completed"] and outcome["verified"]
    assert outcome["events"] == {"started": 22, "completed": 22}
    assert outcome["roles"] == {"candidate": 1, "buy_and_hold_baseline": 1,
                                "random_signal_baseline": 20}
    assert outcome["n_post_ledger"] == 88
    assert all(path in {"trials.jsonl", "trials.head.json", "returns"}
               or path.startswith("returns/") for path in result["changed"])
