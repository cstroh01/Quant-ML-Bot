"""EXAMPLE — NOT A RESULT. Inventory and planted production bypass guards."""
import ast
import json
from pathlib import Path
from context import SCRIPTS_DIR

ROOT = SCRIPTS_DIR.parent
PRIMITIVES = {"run_backtest", "nested_walk_forward", "fit_predict_walk_forward", "evaluate_walk_forward", "tune_on_fold", "score_fold"}

def bypasses(root):
    """Find direct research calls; mechanical tests and pure definitions are exempt."""
    failures = []
    for folder in ("scripts", "reports/api"):
        for path in (root / folder).rglob("*.py"):
            if path.name in {"trial_runner.py", "trial_registry.py"}:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            aliases = {alias.asname or alias.name: alias.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for alias in n.names}
            parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call): continue
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                name = aliases.get(name, name)
                if name not in PRIMITIVES: continue
                parent = node
                guarded = False
                while parent in parents:
                    parent = parents[parent]
                    if isinstance(parent, ast.With):
                        guarded |= any(isinstance(x.context_expr, ast.Call) and getattr(x.context_expr.func, "id", "") == "research_attempt" for x in parent.items)
                if not guarded:
                    failures.append(f"{path.relative_to(root).as_posix()}:{node.lineno} {name}")
    return failures

def test_inventory_and_production_guard():
    data = json.loads((ROOT / "tests/fixtures/spec_033/runner_inventory.json").read_text(encoding="utf-8"))
    assert data["calls"]
    assert not bypasses(ROOT), "uninstrumented research calls: " + "; ".join(bypasses(ROOT))

def test_guard_planted_bypass_and_clean_test_control(tmp_path):
    (tmp_path / "scripts").mkdir(); (tmp_path / "tests").mkdir()
    (tmp_path / "tests/mechanical.py").write_text("run_backtest(prices)")
    path = tmp_path / "scripts/new_runner.py"
    path.write_text("with research_attempt(config):\n    run_backtest(prices)\n")
    assert bypasses(tmp_path) == []
    path.write_text("run_backtest(prices)\n")
    assert bypasses(tmp_path) == ["scripts/new_runner.py:1 run_backtest"]


def test_guard_catches_aliased_bypass(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/new_runner.py").write_text("from backtest_harness import run_backtest as evaluate\nevaluate(prices)\n")
    assert bypasses(tmp_path) == ["scripts/new_runner.py:2 run_backtest"]


def test_api_strategy_is_candidate_not_required_random_baseline():
    tree = ast.parse((ROOT / "reports/api/routes/backtest.py").read_text(encoding="utf-8"))
    wrappers = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "research_attempt"]
    assert len(wrappers) == 1
    assert next(k.value.value for k in wrappers[0].keywords if k.arg == "role") == "candidate"
