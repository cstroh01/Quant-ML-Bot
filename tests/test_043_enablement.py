"""T025: scoped permission, pre-data refusal, and actual spawn transport."""
import importlib
import sys
from pathlib import Path
import pytest
from ledger_copy_support import run_child


def test_permission_is_nested_and_resets_on_exception():
    import trial_registry as registry
    path = Path("stand-in-ledger")
    with pytest.raises(registry.LedgerWriteRefused):
        registry._require_production_enabled("control", path)
    with registry.production_recording(reason="outer"):
        with pytest.raises(RuntimeError):
            with registry.production_recording(reason="inner"):
                assert registry.production_recording_reason() == "inner"
                raise RuntimeError("planted exception")
        assert registry.production_recording_reason() == "outer"
    with pytest.raises(registry.LedgerWriteRefused):
        registry._require_production_enabled("after", path)
    for reason in (None, "", " "):
        with pytest.raises(ValueError):
            with registry.production_recording(reason=reason):
                pytest.fail("invalid permission entered")


@pytest.mark.parametrize("module,loader,args", [
    ("ma_crossover_backtest", "load_unadjusted_for_ticker", []),
    ("logistic_baseline", "download_market_data", []),
    ("multi_ticker_comparison", "cache_path", ["--starting-capital", "10000", "--liquidate"]),
    ("feature_set_comparison", "load_prices", []),
])
def test_default_main_refuses_before_data(module, loader, args, monkeypatch):
    from trial_registry import LedgerWriteRefused
    monkeypatch.delenv("SPEC033_SYNTHETIC_ROOT", raising=False)
    monkeypatch.setenv("QMB_LEDGER_WRITE", "production")
    monkeypatch.setattr(sys, "argv", [module, *args])
    entry = importlib.import_module(module)
    def forbidden(*a, **kw):
        pytest.fail("data reached before permission preflight")
    monkeypatch.setattr(entry, loader, forbidden)
    with pytest.raises(LedgerWriteRefused, match=module):
        entry.main()


def test_enabled_e4_records_in_actual_spawned_workers():
    result = run_child("E4", enabled=True)
    assert result["returncode"] == 0, result["stderr"]
    assert result["outcome"]["completed"] and result["outcome"]["verified"]
    assert result["outcome"]["roles"] == {"candidate": 8}
    assert result["outcome"]["n_post_ledger"] == 95
    assert result["records"] == 16
    assert result["outcome"]["worker_pids"]
    assert result["outcome"]["parent_pid"] not in result["outcome"]["worker_pids"]


def test_spawn_token_is_load_bearing():
    def remove_transport(root):
        path = root / "scripts/feature_set_comparison.py"
        source = path.read_text(encoding="utf-8")
        token = ", task_spec, production_recording_reason()"
        assert source.count(token) == 1
        path.write_text(source.replace(token, ", task_spec"), encoding="utf-8")
    result = run_child("E4", enabled=True, mutate=remove_transport)
    assert result["returncode"] != 0
    assert "LedgerWriteRefused" in result["stderr"]
    assert result["records"] == 0 and result["changed"] == []
