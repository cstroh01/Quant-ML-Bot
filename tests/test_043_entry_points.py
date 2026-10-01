"""AC-1 / AC-10: entry points must refuse before any ledger write."""
import pytest
from ledger_copy_support import assert_refused, run_child

RUNNERS = {
    "E1": "ma_crossover_backtest", "E2": "logistic_baseline",
    "E3": "multi_ticker_comparison", "E4": "feature_set_comparison",
}


@pytest.mark.parametrize("entry", ["E1", "E2", "E3", "E4", "E5"])
def test_default_entry_changes_no_ledger_bytes(entry):
    result = run_child(entry)
    if entry != "E5":
        assert_refused(result, RUNNERS[entry])
    else:
        assert not result["changed"], f'E5 wrote ledger bytes: {result["changed"]}'
        assert result["returncode"] == 0, result["stderr"]
        assert result["outcome"]["verified"]
        assert result["outcome"]["n_post_ledger"] == 87
        requests = result["outcome"]["requests"]
        assert len(requests) == 2
        for request in requests:
            assert request["status"] == 409
            assert request["records"] == request["sidecars"] == 0
            assert "--record-trial" in str(request["body"])
