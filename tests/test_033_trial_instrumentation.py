"""EXAMPLE — NOT A RESULT. Inventory and planted production bypass guards."""
import ast
import json
from pathlib import Path
from context import SCRIPTS_DIR

ROOT = SCRIPTS_DIR.parent
INTERNAL = {"scripts/trial_runner.py", "scripts/trial_registry.py"}
PRIMITIVES = {"run_backtest", "nested_walk_forward", "fit_predict_walk_forward", "evaluate_walk_forward", "tune_on_fold", "score_fold"}

def callee(node, aliases):
    """Primitive a callee expression names: a name, an attribute, or getattr(x, "name")."""
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return node.attr
    if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "getattr" and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
        return node.args[1].value
    return ""

def classified(root):
    """T014: read T003's inventory as {(path, call): classifications}; absent inventory is empty."""
    path = root / "tests/fixtures/spec_033/runner_inventory.json"
    calls = json.loads(path.read_text(encoding="utf-8"))["calls"] if path.exists() else []
    found = {}
    for c in calls:
        found.setdefault((c["path"], c["call"]), set()).add(c["classification"])
    return found


def bypasses(root):
    """Find unwrapped research calls. Only an inventory entry classified `test-only`, and no other
    class for the same (path, call), exempts a call; every other inventoried path is scanned too."""
    inventory = classified(root)
    exempt = {key for key, kinds in inventory.items() if kinds == {"test-only"}}
    runners = sorted({p for (p, _), kinds in inventory.items() if kinds != {"test-only"}})
    failures = [f"{p} missing ({', '.join(sorted(k for (q, _), ks in inventory.items() if q == p for k in ks))})"
                for p in runners if not (root / p).is_file()]
    paths = {path for folder in ("scripts", "reports/api") for path in (root / folder).rglob("*.py")}
    paths |= {root / p for p in runners if (root / p).is_file()}
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix()
        if relative in INTERNAL:  # the ledger's own modules, by exact canonical path only
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        aliases = {alias.asname or alias.name: alias.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for alias in n.names}
        assignments = [(n.targets[0].id, n.value) for n in ast.walk(tree) if isinstance(n, ast.Assign)
                       and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)]
        for _ in assignments:  # resolve `Name = <primitive>` chains to a fixpoint
            for target, value in assignments:
                if (resolved := callee(value, aliases)) in PRIMITIVES:
                    aliases[target] = resolved
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call): continue
            name = callee(node.func, aliases)
            if name not in PRIMITIVES or (relative, name) in exempt: continue
            parent = node
            guarded = False
            while parent in parents:
                parent = parents[parent]
                if isinstance(parent, ast.With):
                    guarded |= any(isinstance(x.context_expr, ast.Call) and getattr(x.context_expr.func, "id", "") == "research_attempt" for x in parent.items)
            if not guarded:
                failures.append(f"{relative}:{node.lineno} {name}")
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


def test_recording_cli_strategy_is_candidate_not_required_random_baseline():
    tree = ast.parse((ROOT / "scripts/ma_crossover_backtest.py").read_text(encoding="utf-8"))
    wrappers = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "research_attempt"]
    wrappers = [n for n in wrappers if any(k.arg == "role" and isinstance(k.value, ast.Constant) and k.value.value == "candidate" for k in n.keywords)]
    assert len(wrappers) == 1
    assert next(k.value.value for k in wrappers[0].keywords if k.arg == "role") == "candidate"


def test_guard_catches_assignment_and_getattr_aliases(tmp_path):
    """AC-9: planted `rb = run_backtest; rb(x)` and `getattr(bt, "run_backtest")(x)`."""
    (tmp_path / "scripts").mkdir()
    path = tmp_path / "scripts/new_runner.py"
    path.write_text("from backtest_harness import run_backtest\nrb = run_backtest\nrb2 = rb\nrb(x)\nrb2(x)\n")
    assert bypasses(tmp_path) == ["scripts/new_runner.py:4 run_backtest", "scripts/new_runner.py:5 run_backtest"]
    path.write_text('import backtest_harness as bt\ngetattr(bt, "run_backtest")(x)\nf = getattr(bt, "run_backtest")\nf(x)\n')
    assert bypasses(tmp_path) == ["scripts/new_runner.py:2 run_backtest", "scripts/new_runner.py:4 run_backtest"]
    path.write_text('import backtest_harness as bt\nwith research_attempt(config):\n    getattr(bt, "run_backtest")(x)\n')
    assert bypasses(tmp_path) == []


# --- T014: the guard consumes the runner inventory's per-call classifications. ---
INVENTORY = "tests/fixtures/spec_033/runner_inventory.json"
CLASSES = {"test-only", "candidate runner", "required baseline"}


def plant(root, files, calls):
    """Write `files` and a T003-shaped inventory naming `calls` (path, call, classification)."""
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    entries = [{"path": p, "line": 1, "call": c, "classification": k, "source": ""} for p, c, k in calls]
    (root / INVENTORY).parent.mkdir(parents=True, exist_ok=True)
    (root / INVENTORY).write_text(json.dumps({"label": "EXAMPLE — NOT A RESULT", "source": "", "calls": entries}), encoding="utf-8")


def test_t014_inventoried_candidate_outside_scanned_folders_is_flagged(tmp_path):
    plant(tmp_path, {"tests/manual_runner.py": "run_backtest(prices)\n"},
          [("tests/manual_runner.py", "run_backtest", "candidate runner")])
    found = bypasses(tmp_path)
    assert found == ["tests/manual_runner.py:1 run_backtest"], f"T014 CANDIDATE ignored: {found}"
    (tmp_path / "tests/manual_runner.py").write_text("with research_attempt(config):\n    run_backtest(prices)\n")
    assert bypasses(tmp_path) == [], "T014 CANDIDATE wrapped call flagged"


def test_t014_explicit_test_only_call_is_allowed_and_unlisted_twin_is_not(tmp_path):
    plant(tmp_path, {"scripts/mechanical.py": "run_backtest(prices)\n", "scripts/other.py": "run_backtest(prices)\n"},
          [("scripts/mechanical.py", "run_backtest", "test-only")])
    found = bypasses(tmp_path)
    assert found == ["scripts/other.py:1 run_backtest"], f"T014 TEST-ONLY: {found}"


def test_t014_test_only_exemption_is_scoped_to_its_named_call(tmp_path):
    plant(tmp_path, {"scripts/mechanical.py": "run_backtest(prices)\nnested_walk_forward(x)\n"},
          [("scripts/mechanical.py", "run_backtest", "test-only")])
    found = bypasses(tmp_path)
    assert found == ["scripts/mechanical.py:2 nested_walk_forward"], f"T014 SCOPE: {found}"


def test_t014_test_only_never_overrides_a_runner_classification(tmp_path):
    plant(tmp_path, {"scripts/mixed.py": "run_backtest(prices)\n"},
          [("scripts/mixed.py", "run_backtest", "test-only"), ("scripts/mixed.py", "run_backtest", "required baseline")])
    found = bypasses(tmp_path)
    assert found == ["scripts/mixed.py:1 run_backtest"], f"T014 CONFLICT: {found}"


def test_t014_unknown_classification_and_missing_runner_path_fail_closed(tmp_path):
    plant(tmp_path, {"scripts/odd.py": "run_backtest(prices)\n"},
          [("scripts/odd.py", "run_backtest", "probably fine"), ("scripts/gone.py", "run_backtest", "candidate runner")])
    found = bypasses(tmp_path)
    assert found == ["scripts/gone.py missing (candidate runner)", "scripts/odd.py:1 run_backtest"], f"T014 FAIL-CLOSED: {found}"


def test_t014_real_inventory_classes_and_test_only_locations():
    calls = json.loads((ROOT / INVENTORY).read_text(encoding="utf-8"))["calls"]
    assert {c["classification"] for c in calls} == CLASSES, "T014 CLASSES"
    assert all(c["path"].startswith("tests/") for c in calls if c["classification"] == "test-only"), "T014 TEST-ONLY LOCATION"


def test_t014_internal_module_exemption_is_exact_canonical_path_only(tmp_path):
    """Only scripts/trial_runner.py and scripts/trial_registry.py are internal; a same-named file elsewhere is not."""
    plant(tmp_path, {"tools/trial_runner.py": "run_backtest(prices)\n", "tools/trial_registry.py": "run_backtest(prices)\n",
                     "scripts/sub/trial_runner.py": "run_backtest(prices)\n",
                     "scripts/trial_runner.py": "run_backtest(prices)\n", "scripts/trial_registry.py": "run_backtest(prices)\n"},
          [("tools/trial_runner.py", "run_backtest", "candidate runner"), ("tools/trial_registry.py", "run_backtest", "candidate runner")])
    found = bypasses(tmp_path)
    assert found == ["scripts/sub/trial_runner.py:1 run_backtest", "tools/trial_registry.py:1 run_backtest",
                     "tools/trial_runner.py:1 run_backtest"], f"T014 BASENAME: {found}"
