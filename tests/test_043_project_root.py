"""AC-5: marker roots, hostile cwd/overrides, and the planted depth defect."""
import importlib.util
from pathlib import Path
import sys
import pytest
from ledger_copy_support import REPO


def marker(root, name="quant-ml-bot"):
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n', encoding="utf-8")


def load(path, monkeypatch, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("case", ["override", "invalid_override", "file_marker",
                                  "neither", "wrong_nearer", "foreign_cwd"])
@pytest.mark.xfail(strict=True, reason="043 Phase 1 red; guard lands in T020+")
def test_project_root_contract(case, tmp_path, monkeypatch):
    source = REPO / "scripts/_project.py"
    assert source.exists(), f"T021 missing resolver: {source}"
    root = tmp_path / "marked"
    nested = root / "extra/scripts"
    nested.mkdir(parents=True)
    resolver = nested / "_project.py"
    resolver.write_bytes(source.read_bytes())
    monkeypatch.delenv("QMB_PROJECT_ROOT", raising=False)
    foreign = tmp_path / "foreign"
    marker(foreign)
    monkeypatch.chdir(foreign)  # Cwd always offers a tempting but wrong marker.
    if case != "neither":
        marker(root)
    expected = root.resolve()
    if case in {"override", "invalid_override"}:
        override = tmp_path / "override"
        override.mkdir()
        if case == "override":
            marker(override)
        monkeypatch.setenv("QMB_PROJECT_ROOT", str(override))
        expected = override.resolve()
    if case == "wrong_nearer":
        marker(nested.parent, "some-other-project")
    module = load(resolver, monkeypatch, "spec043_resolver")
    if case in {"neither", "invalid_override"}:
        with pytest.raises(module.ProjectRootNotFound) as caught:
            module.project_root()
        assert str(expected) in str(caught.value)
    else:
        assert module.project_root() == expected
        assert module.project_root() != foreign.resolve()


def relocated_registry(tmp_path, monkeypatch, *, planted=False):
    root = tmp_path / "marked"
    marker(root)
    nested = root / "extra/scripts"
    nested.mkdir(parents=True)
    source = (REPO / "scripts/trial_registry.py").read_text(encoding="utf-8")
    resolver = REPO / "scripts/_project.py"
    if resolver.exists():
        (nested / "_project.py").write_bytes(resolver.read_bytes())
        monkeypatch.delenv("QMB_PROJECT_ROOT", raising=False)
        load(nested / "_project.py", monkeypatch, "_project")
    if planted:
        old = "ROOT = project_root()"
        if old in source:
            assert source.count(old) == 1
            source = source.replace(old, "ROOT = Path(__file__).resolve().parents[1]")
        else:
            assert "ROOT = Path(__file__).resolve().parents[1]" in source
    path = nested / "trial_registry.py"
    path.write_text(source, encoding="utf-8")
    module = load(path, monkeypatch, "spec043_relocated_registry")
    return root.resolve(), module.ROOT.resolve()


def require_root(expected, actual):
    assert actual == expected, f"wrong ROOT: {actual}; expected: {expected}"


@pytest.mark.xfail(strict=True, reason="043 Phase 1 red; guard lands in T020+")
def test_registry_root_survives_extra_depth(tmp_path, monkeypatch):
    require_root(*relocated_registry(tmp_path, monkeypatch))


def test_planted_depth_root_names_wrong_directory(tmp_path, monkeypatch):
    expected, actual = relocated_registry(tmp_path, monkeypatch, planted=True)
    with pytest.raises(AssertionError, match="wrong ROOT") as caught:
        require_root(expected, actual)
    assert str(expected / "extra") in str(caught.value)
