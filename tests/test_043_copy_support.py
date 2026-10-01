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


def e5_request(status=200, records=0, sidecars=0, n=(88, 88), body_sha="a" * 64, body=None):
    return dict(status=status, records=records, sidecars=sidecars, n_before=n[0],
                n_after=n[1], body_sha256=body_sha, body=body)


def e5_result(*requests, records=44, sidecars=22):
    return dict(returncode=0, stderr="", records=records, sidecars=sidecars,
                changed=["trials.jsonl"], outcome={"requests": list(requests)})


def test_e5_served_control_passes():
    support.assert_e5_served(e5_result(e5_request(), e5_request()))


REFUSAL = {"detail": "not recorded; run python scripts/ma_crossover_backtest.py --record-trial"}


@pytest.mark.parametrize("planted, message", [
    # The F5 vacuous implementation: GET returns 409 even after recording.
    (e5_result(e5_request(409, body=REFUSAL), e5_request(409, body=REFUSAL)),
     "recorded config not served"),
    # GET recomputes and records again on every view (the pre-043 route).
    (e5_result(e5_request(records=44, sidecars=22, n=(88, 89)), e5_request(),
               records=88, sidecars=44), r"\(88, 44\)"),
    # GET serves without writing bytes but still counts a trial in N.
    (e5_result(e5_request(n=(88, 89)), e5_request()), "n_before"),
    # Two identical GETs disagree: the response is not the one recorded trial.
    (e5_result(e5_request(), e5_request(body_sha="b" * 64)), "body_sha256"),
])
def test_e5_served_rejects_each_planted_defect(planted, message):
    with pytest.raises(AssertionError, match=message):
        support.assert_e5_served(planted)


def test_e5_refused_requires_the_recording_command():
    support.assert_e5_refused(e5_request(409, n=(87, 87), body=REFUSAL))
    vague = e5_request(409, n=(87, 87), body={"detail": "conflict; pass --record-trial"})
    with pytest.raises(AssertionError, match="ma_crossover_backtest"):
        support.assert_e5_refused(vague)


def fake_repo(tmp_path):
    """Minimal stand-in repository whose child only writes its outcome file."""
    repo = tmp_path / "stand-in-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "docs/trials").mkdir(parents=True)
    (repo / "docs/trials/trials.jsonl").write_bytes(b'{"existing":true}\n')
    (repo / ".specify/specs/043-ledger-write-guard/artifacts").mkdir(parents=True)
    (repo / "tests/ledger_guard_child.py").write_text(
        "from pathlib import Path\nPath('guard-outcome.json').write_text('{}')\n",
        encoding="utf-8")
    return repo


def test_run_child_leaves_the_checkout_untouched(tmp_path, monkeypatch):
    """Review F10: an ordinary test run never appends evidence into the repo."""
    repo = fake_repo(tmp_path)
    monkeypatch.setattr(support, "REPO", repo)
    monkeypatch.delenv(support.EVIDENCE_LOG_VAR, raising=False)
    before = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))
    result = support.run_child("stand-in")
    after = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))
    assert after == before, f"run_child wrote into the checkout: {set(after) - set(before)}"
    assert result["evidence"]["entry"] == "stand-in"
    assert result["evidence"]["label"] == "EXAMPLE — NOT A RESULT"


def test_run_child_harvests_evidence_only_when_named(tmp_path, monkeypatch):
    repo = fake_repo(tmp_path)
    monkeypatch.setattr(support, "REPO", repo)
    log = tmp_path / "harvest/events.jsonl"
    log.parent.mkdir()
    monkeypatch.setenv(support.EVIDENCE_LOG_VAR, str(log))
    support.run_child("stand-in")
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and '"entry": "stand-in"' in lines[0]
