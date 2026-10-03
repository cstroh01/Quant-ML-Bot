"""EXAMPLE — NOT A RESULT. Spec 043 U2 (T023/T024): the write and early layers.

Every write-layer case points the production root at an isolated tmp tree, so a
broken guard writes there, never to the real docs/trials/. Each refusal case
passes inputs that would fail validation *after* the guard, which pins the
guard as the first statement: a guard moved below validation raises
ValueError instead of LedgerWriteRefused.
"""
import pytest

from context import SCRIPTS_DIR  # noqa: F401  (puts scripts/ on sys.path)
from spec033_support import CONFIG, SOURCE
import trial_backfill
import trial_registry
import trial_runner
from trial_registry import LedgerWriteRefused, TrialLedger


@pytest.fixture
def production_tmp(tmp_path, monkeypatch):
    """A non-synthetic ledger whose 'production' root is an isolated tmp tree."""
    root = tmp_path.resolve()
    monkeypatch.setattr(trial_registry, "ROOT", root)
    monkeypatch.setattr(trial_backfill, "ROOT", root)
    return root, TrialLedger(root)


def assert_named_refusal(error, runner, path):
    message = str(error.value)
    for token in (runner, str(path), "no ledger byte was written",
                  "--record-trial", "production_recording"):
        assert token in message, message


def test_default_is_disabled():
    assert trial_registry._production_enabled.get() is None


def test_start_refuses_first_and_writes_nothing(production_tmp):
    root, ledger = production_tmp
    assert not ledger.synthetic
    with pytest.raises(LedgerWriteRefused) as error:
        # {} would fail canonical_config; "bogus" would fail the role check.
        ledger.start({}, role="bogus", family="example", runner="fixture-runner")
    assert_named_refusal(error, "fixture-runner", ledger.path)
    assert not (root / "docs").exists(), "no lock, directory or record may exist"


def test_finish_refuses_first_and_writes_nothing(production_tmp):
    root, ledger = production_tmp
    with pytest.raises(LedgerWriteRefused) as error:
        ledger.finish("not-a-trial", "bogus-outcome", returns=[{"session": "x"}])
    assert_named_refusal(error, "TrialLedger.finish", ledger.path)
    assert not (root / "docs").exists()


def test_write_backfill_refuses_production_root_first(production_tmp):
    root, _ = production_tmp
    with pytest.raises(LedgerWriteRefused) as error:
        trial_backfill.write_backfill(root, {})  # {} fails "campaigns required"
    assert_named_refusal(error, "trial_backfill.write_backfill",
                         root / "docs/trials/backfill")
    assert not (root / "docs").exists()


def test_write_backfill_refuses_symlinked_production_target(production_tmp, tmp_path_factory):
    root, _ = production_tmp
    (root / "docs").mkdir()
    other = tmp_path_factory.mktemp("symlinked-root")
    try:
        (other / "docs").symlink_to(root / "docs", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not permitted on this platform/account")
    with pytest.raises(LedgerWriteRefused):
        trial_backfill.write_backfill(other, {})
    assert not (root / "docs/trials").exists()


def test_write_backfill_other_root_is_not_gated(production_tmp, tmp_path_factory):
    other = tmp_path_factory.mktemp("not-production")
    with pytest.raises(ValueError, match="campaigns required") as error:
        trial_backfill.write_backfill(other, {})
    assert not isinstance(error.value, LedgerWriteRefused)


def test_synthetic_ledger_is_unchanged(tmp_path):
    ledger = TrialLedger(tmp_path, synthetic=True)
    trial = ledger.start(CONFIG, role="synthetic_test", family="example",
                         runner="fixture", source=SOURCE)
    ledger.finish(trial, "rejected", reason="fixture")
    assert len(ledger.verify()["events"]) == 2


def test_enabled_control_writes_a_verified_record(production_tmp):
    """Green control: the gate is not stuck closed. T025 owns the public
    enabling API; this sets the underlying context variable directly."""
    root, ledger = production_tmp
    token = trial_registry._production_enabled.set("test_043_write_guard control")
    try:
        trial = ledger.start(CONFIG, role="candidate", family="example",
                             runner="fixture", source=SOURCE)
        ledger.finish(trial, "rejected", reason="fixture")
    finally:
        trial_registry._production_enabled.reset(token)
    assert ledger.verify()["n_post_ledger"] == 1
    with pytest.raises(LedgerWriteRefused):
        ledger.start(CONFIG, role="candidate", family="example",
                     runner="fixture", source=SOURCE)


def test_current_ledger_refuses_without_synthetic_root(monkeypatch):
    monkeypatch.delenv("SPEC033_SYNTHETIC_ROOT", raising=False)
    with pytest.raises(LedgerWriteRefused) as error:
        trial_runner.current_ledger("fixture-early")
    assert_named_refusal(error, "fixture-early", TrialLedger().path)


def test_research_attempt_refuses_before_body(monkeypatch):
    monkeypatch.delenv("SPEC033_SYNTHETIC_ROOT", raising=False)
    entered = []
    with pytest.raises(LedgerWriteRefused, match="fixture-attempt"):
        with trial_runner.research_attempt({"runner": "fixture-attempt"}):
            entered.append(True)
    assert not entered


def test_invalid_synthetic_context_never_falls_through(tmp_path, monkeypatch):
    (tmp_path / "synthetic-context.json").write_text("unlabelled", encoding="utf-8")
    monkeypatch.setenv("SPEC033_SYNTHETIC_ROOT", str(tmp_path))
    token = trial_registry._production_enabled.set("even when enabled")
    try:
        with pytest.raises(ValueError, match="unlabelled synthetic context") as error:
            trial_runner.current_ledger("fixture")
    finally:
        trial_registry._production_enabled.reset(token)
    assert not isinstance(error.value, LedgerWriteRefused)
