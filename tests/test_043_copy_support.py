"""AC-4 / AC-8 tripwire proof and isolation-helper controls."""
import hashlib
from pathlib import Path
import pytest
import ledger_copy_support as support


def stand_in(tmp_path):
    root = tmp_path / "stand-in-real"
    base = root / "docs/trials"
    base.mkdir(parents=True)
    (base / "trials.jsonl").write_bytes(b'{"existing":true}\n')
    (base / "trials.head.json").write_bytes(b'{"records":1}\n')
    return root, base


def test_tripwire_unchanged_control(tmp_path):
    root, _ = stand_in(tmp_path)
    with support.tripwire(root):
        assert support.manifest(root)["returns"] == "absent"


@pytest.mark.parametrize("change", ["append", "sidecar", "remove_head"])
def test_tripwire_detects_and_names_each_planted_change(tmp_path, change):
    root, base = stand_in(tmp_path)
    name = {"append": "trials.jsonl", "sidecar": "returns/x.jsonl",
            "remove_head": "trials.head.json"}[change]
    with pytest.raises(AssertionError, match="ledger tripwire") as caught:
        with support.tripwire(root):
            path = base / name
            if change == "append":
                with path.open("ab") as stream:
                    stream.write(b'{"planted":true}\n')
            elif change == "sidecar":
                path.parent.mkdir()
                path.write_bytes(b'{"planted":true}\n')
            else:
                path.unlink()
    assert name in str(caught.value)


def test_tripwire_runs_finally_on_child_failure(tmp_path):
    root, base = stand_in(tmp_path)
    with pytest.raises(AssertionError, match="trials.jsonl"):
        with support.tripwire(root):
            with (base / "trials.jsonl").open("ab") as stream:
                stream.write(b'{"planted":true}\n')
            raise RuntimeError("child failed after writing")


def test_manifest_hashes_nested_paths_and_absence(tmp_path):
    root, base = stand_in(tmp_path)
    (base / "backfill").mkdir()
    (base / "backfill/x.json").write_bytes(b"fixture")
    result = support.manifest(root)
    assert result["backfill"] == "directory"
    assert result["backfill/x.json"] == hashlib.sha256(b"fixture").hexdigest()
    assert result["returns"] == "absent"
    assert support.manifest(tmp_path / "absent")["."] == "absent"


def test_child_env_removes_inherited_enabling_state(monkeypatch):
    for key in ("SPEC033_SYNTHETIC_ROOT", "QMB_LEDGER_WRITE", "QMB_PROJECT_ROOT"):
        monkeypatch.setenv(key, "planted")
    monkeypatch.setenv("SPEC043_UNRELATED", "kept")
    env = support.child_env()
    assert not {"SPEC033_SYNTHETIC_ROOT", "QMB_LEDGER_WRITE", "QMB_PROJECT_ROOT"} & env.keys()
    assert env["SPEC043_UNRELATED"] == "kept"
    assert support.os.environ["SPEC033_SYNTHETIC_ROOT"] == "planted"


def test_copy_exclusions_and_destination_guard(tmp_path, monkeypatch):
    source = tmp_path / "source"
    for name in ("venv/x", "node_modules/x", ".git/x", "__pycache__/x",
                 "data/cache/x", "docs/trials/keep", "scripts/keep", "tests/keep"):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"copy fixture")
    monkeypatch.setattr(support, "REPO", source)
    with pytest.raises(AssertionError):
        support.make_copy(source / "nested")
    with pytest.raises(AssertionError):
        support.make_copy(support.REAL_ROOT.parent / "forbidden-copy")
    destination = support.make_copy(tmp_path / "copy")
    files = {path.relative_to(destination).as_posix()
             for path in destination.rglob("*") if path.is_file()}
    assert files == {"docs/trials/keep", "scripts/keep", "tests/keep"}
