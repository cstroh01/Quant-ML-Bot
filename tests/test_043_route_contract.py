"""T027: GET cannot compute or record research, even with permission present."""
import ast
from pathlib import Path
import pytest

FORBIDDEN = {"run_backtest", "research_attempt", "baseline_results",
             "research_close_signal", "recorded_tearsheet_payload"}


def recording_calls(source):
    tree = ast.parse(source)
    route = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                 and n.name == "get_backtest_tearsheet")
    return sorted(n.func.id for n in ast.walk(route) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name) and n.func.id in FORBIDDEN)


def test_get_has_no_research_or_recording_calls():
    source = (Path(__file__).resolve().parents[1] / "reports/api/routes/backtest.py").read_text(encoding="utf-8")
    assert recording_calls(source) == []


@pytest.mark.parametrize("call", sorted(FORBIDDEN))
def test_read_only_guard_rejects_planted_computation(call):
    assert recording_calls("def get_backtest_tearsheet():\n    return 1\n") == []
    assert recording_calls(f"def get_backtest_tearsheet():\n    {call}()\n") == [call]
