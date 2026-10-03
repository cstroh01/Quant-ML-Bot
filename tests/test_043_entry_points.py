"""AC-1 / AC-10: entry points must refuse before any ledger write."""
import pytest
from ledger_copy_support import (assert_e5_refused, assert_e5_served,
                                 assert_refused, run_child)

RUNNERS = {
    "E1": "ma_crossover_backtest", "E2": "logistic_baseline",
    "E3": "multi_ticker_comparison", "E4": "feature_set_comparison",
}

# Separate strict marks per review unit (043 review F4): each is removed by the
# task that turns its own case green, never wholesale.
RED_UNTIL_U2 = pytest.mark.xfail(
    strict=True, reason="043 Phase 1 red; CLI refusal lands in T023-T025 (U2)")
RED_UNTIL_U3 = pytest.mark.xfail(
    strict=True, reason="043 Phase 1 red; read-only route lands in T027 (U3)")


# E1, E2 and E4 turned green at T023-T024 (write and early layers). E3 stays
# red until T025's preflight: its per-ticker isolation boundary reports the
# refusal on stdout instead of exiting before any output.
@pytest.mark.parametrize("entry", [
    "E1", "E2", pytest.param("E3", marks=RED_UNTIL_U2), "E4",
    pytest.param("E5", marks=RED_UNTIL_U3)])
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
            assert_e5_refused(request)


@RED_UNTIL_U3
def test_e5_serves_recorded_configuration_read_only():
    """AC-10's green branch: an unconditional 409 cannot satisfy this (review F5)."""
    assert_e5_served(run_child("E5_recorded"))
