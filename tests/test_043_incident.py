"""AC-2: the incident's direct library path must refuse without recording."""
from ledger_copy_support import assert_refused, run_child


def test_direct_baseline_call_changes_no_ledger_bytes():
    result = run_child("incident")
    assert_refused(result, "multi_ticker_comparison", "production_recording")
