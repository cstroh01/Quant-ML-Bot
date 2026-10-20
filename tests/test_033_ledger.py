"""EXAMPLE — NOT A RESULT. Q124: current matrix identity and explicit holdout-spend verification.

All declarations, events, sidecars and planted defects live under tmp_path.
"""
import copy
import json
import uuid

import pytest

import generate_gate3_evidence as gate3
import selection_bias
import trial_registry as registry
from spec033_support import CONFIG, META, SOURCE, config, ledger, rows, start


def declared(tmp_path, monkeypatch):
    monkeypatch.setitem(registry.DECLARED_FAMILIES, "example", "example-declaration.json")
    policy = dict(alignment="exact_intersection", min_coverage=.95, objective="daily_sharpe",
                  risk_free=CONFIG["risk_free"], hac_lags=5, horizon=1)
    (tmp_path / "example-declaration.json").write_text(json.dumps(
        dict(family="example", n_family_cap=50, gate3=policy)))
    registry.declare_family("example", root=tmp_path, synthetic=True)
    log = ledger(tmp_path)
    for variant in range(2):
        trial = start(log, model=dict(name="example", params=dict(window=variant)))
        series = rows()
        for row in series:
            row["log_return"] += variant * .001
        log.finish(trial, "completed", returns=series, metadata=META)
    art = {"selected_trial": log.verify()["events"][0]["trial_id"], "family": {"family": "example"}}
    return log, art


def oracle(log):
    state = log.verify()
    trials = [{**e, "returns": [json.loads(line) for line in (log.root / e["sidecar"]["path"]).read_bytes().splitlines()]}
              for e in state["events"] if e["event_type"] == "completed"]
    policy = registry.verify_family("example", root=log.root)["declaration"]["gate3"]
    return selection_bias.build_matrix(trials, family={"id": "example", **{k: policy[k] for k in
                                       ("alignment", "min_coverage", "objective", "risk_free")}})


def test_current_matrix_is_rebuilt_from_verified_head_without_statistics(tmp_path, monkeypatch):
    log, art = declared(tmp_path, monkeypatch)
    expected = oracle(log)
    def forbidden(*args, **kwargs):
        pytest.fail("currentness computed a statistic")
    for name in ("counted_dsr", "hac_t_stat", "matrix_pbo"):
        monkeypatch.setattr(gate3, name, forbidden)
    before = gate3.current_inputs(art | {"matrix_hash": "invented"}, tmp_path)
    assert before["matrix_hash"] == expected["matrix_hash"], f"Q124 MATRIX HEAD: {before}"
    assert before["ledger_head_hash"] == log.verify()["head"]
    assert gate3.current_inputs(art | {"family": None}, tmp_path)["matrix_hash"] == before["matrix_hash"]
    third = start(log, model=dict(name="example", params=dict(window=3)))
    started = gate3.current_inputs(art, tmp_path)
    assert started["ledger_head_hash"] != before["ledger_head_hash"]
    assert started["matrix_hash"] == before["matrix_hash"]  # an unterminated start is counted, not imputed
    log.finish(third, "completed", returns=rows(), metadata=META)
    after = gate3.current_inputs(art, tmp_path)
    assert after["matrix_hash"] == oracle(log)["matrix_hash"] != before["matrix_hash"]


@pytest.mark.parametrize("case", ["missing declaration", "drift", "wrong family", "missing selected", "ineligible"])
def test_current_matrix_is_unknown_without_verified_policy_or_eligible_candidate(tmp_path, monkeypatch, case):
    log, art = declared(tmp_path, monkeypatch)
    assert gate3.current_inputs(art, tmp_path)["matrix_hash"] == oracle(log)["matrix_hash"]
    if case == "missing declaration":
        (tmp_path / registry.FAMILY_DIR / "example.json").unlink()
    elif case == "drift":
        source = tmp_path / "example-declaration.json"
        source.write_text(source.read_text().replace('"min_coverage": 0.95', '"min_coverage": 0.5'))
    elif case == "wrong family":
        art["family"] = {"family": "another"}
    elif case == "missing selected":
        art["selected_trial"] = str(uuid.uuid4())
    else:
        art["selected_trial"] = start(log)  # no completed returns for this candidate
    assert gate3.current_inputs(art, tmp_path)["matrix_hash"] is None


@pytest.mark.parametrize("cut", [0, -1, 7])
def test_matrix_currentness_preserves_boundaries_and_interior_gap(tmp_path, monkeypatch, cut):
    log, art = declared(tmp_path, monkeypatch)
    before = gate3.current_inputs(art, tmp_path)["matrix_hash"]
    third = start(log, model=dict(name="example", params=dict(window=4)))
    series = rows()
    removed = series.pop(cut)["session"]
    log.finish(third, "completed", returns=series, metadata=META)
    expected = oracle(log)
    assert len(expected["dates"]) == 31 and removed not in expected["dates"]
    assert gate3.current_inputs(art, tmp_path)["matrix_hash"] == expected["matrix_hash"] != before


def spend(log, selected, *, selected_hash=None, family="example", role="holdout"):
    """Append an explicit audit event only to a synthetic ledger; there is no production writer."""
    assert log.synthetic
    state = log.verify()
    chosen = next(e for e in state["events"] if e["trial_id"] == selected and e["event_type"] == "started")
    cfg = config(holdout=dict(family=family, selected_trial_id=selected,
                             selected_config_hash=selected_hash or chosen["config_hash"]))
    cfg, hashed = registry.canonical_config(cfg, root=log.root)
    return log._append(dict(trial_id=str(uuid.uuid4()), event_type="holdout_spend", role=role, family=family,
                            runner="fixture", config=cfg, config_hash=hashed, source=SOURCE), state["head"], len(state["events"]))


def completed(log):
    trial = start(log)
    log.finish(trial, "completed", returns=rows(), metadata=META)
    return trial


def test_verify_accepts_bound_explicit_spend_without_incrementing_candidate_count(tmp_path):
    log = ledger(tmp_path)
    selected = completed(log)
    event = spend(log, selected)
    state = log.verify()
    assert state["head"] == event["record_hash"] and state["n_post_ledger"] == 1
    with pytest.raises(ValueError, match="already spent"):
        start(log, role="holdout")


@pytest.mark.parametrize("case", ["hash", "family", "role", "unfinished selection", "second spend", "legacy first"])
def test_verify_rejects_invalid_or_second_spend_across_both_event_forms(tmp_path, case):
    log = ledger(tmp_path)
    selected = start(log) if case == "unfinished selection" else completed(log)
    kwargs = {}
    if case == "hash": kwargs["selected_hash"] = "0" * 64
    if case == "family": kwargs["family"] = "another"
    if case == "role": kwargs["role"] = "candidate"
    if case == "second spend":
        spend(log, selected)
        assert log.verify()["n_post_ledger"] == 1
    if case == "legacy first": start(log, role="holdout")
    spend(log, selected, **kwargs)
    rejected = False
    try:
        log.verify()
    except ValueError as error:
        rejected = "holdout" in str(error) or "selection" in str(error)
    assert rejected, f"Q124 SPEND REJECT: {case}"


def test_current_backfill_hash_requires_intact_complete_artifact(tmp_path):
    folder = tmp_path / "docs/trials/backfill"
    folder.mkdir(parents=True)
    body = dict(schema_version=1, status="complete", n_backfill=40)
    artifact = body | {"sha256": registry.digest(body)}
    path = folder / "example.json"
    path.write_text(json.dumps(artifact))
    assert gate3.current_inputs({}, tmp_path)["backfill_hash"] == artifact["sha256"]
    path.write_text(json.dumps(artifact | {"n_backfill": 41}))  # do not update the digest
    assert gate3.current_inputs({}, tmp_path)["backfill_hash"] is None
