"""T026: same incident path, early layer disabled in both isolated controls."""
import pytest
from ledger_copy_support import assert_refused, run_child


@pytest.mark.parametrize("remove_write_guard", [False, True])
def test_incident_write_layer_is_independent(remove_write_guard):
    def mutate(root):
        early = root / "scripts/trial_runner.py"
        source = early.read_text(encoding="utf-8")
        check = "    _require_production_enabled(runner, TrialLedger().path)"
        assert source.count(check) == 1
        early.write_text(source.replace(check, "    # T026: early layer disabled in both controls"), encoding="utf-8")
        if remove_write_guard:
            writer = root / "scripts/trial_registry.py"
            lines = writer.read_text(encoding="utf-8").splitlines()
            checks = [line for line in lines if "if not self.synthetic: _require_production_enabled(" in line]
            assert len(checks) == 2
            writer.write_text("\n".join(line for line in lines if line not in checks) + "\n", encoding="utf-8")
    result = run_child("incident", mutate=mutate)
    if not remove_write_guard:
        assert_refused(result, "multi_ticker_comparison", "production_recording")
    else:
        assert result["returncode"] == 0, result["stderr"]
        assert result["outcome"]["completed"] and result["outcome"]["verified"]
        assert result["records"] == 6 and result["sidecars"] == 3
        with pytest.raises(AssertionError, match="changed 6 records, 3 sidecars"):
            assert_refused(result, "multi_ticker_comparison", "production_recording")
