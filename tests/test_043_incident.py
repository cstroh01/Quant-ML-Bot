"""AC-2: the incident's direct library path must refuse without recording."""
import pytest

from ledger_copy_support import assert_refused, run_child

pytestmark = pytest.mark.xfail(
    strict=True, reason="043 Phase 1 red; guard lands in T020+"
)


def test_direct_baseline_call_changes_no_ledger_bytes():
    result = run_child("incident")
    assert_refused(result, "multi_ticker_comparison", "production_recording")
