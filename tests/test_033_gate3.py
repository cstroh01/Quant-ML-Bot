"""EXAMPLE — NOT A RESULT. Spec 033 T056/T057: Gate 3 artifact schema, reason codes, decision table.

Tests first; T062 implements `scripts/generate_gate3_evidence.py` to this contract:

- ``compose(evidence) -> artifact`` is pure apart from ``artifact_id``, which is fresh on
  every call, so identical evidence evaluated twice is two artifacts (FR-039). ``evidence`` carries the existing
  ``selection_bias`` outputs (``counts`` from ``lifetime_count``, ``matrix`` from
  ``build_matrix``, ``dsr`` from ``counted_dsr``, ``t_stat`` from ``hac_t_stat``,
  ``pbo`` from ``matrix_pbo``) plus selection, CV, cost and source metadata. It
  recomputes no statistic; it maps operands to a status and ordered reason codes.
- ``assess(artifact, current) -> {"status", "reason_codes"}`` re-checks currentness
  against the current ledger head, backfill, matrix and source identity (FR-043).
- ``write_artifact(artifact, root) -> str`` returns a repository-relative path and
  refuses a fixture-labelled artifact in the production directory (FR-048).

Family N (2026-10-09 amendment): the gating DSR is the family-N DSR while the family
is within its cap, else the lifetime-N DSR; the lifetime DSR is always published.
"""
import copy
import hashlib
import importlib
import json
import math
import re
from pathlib import PurePosixPath

import pytest

from spec033_support import CONFIG, GATE_FIELDS, LABEL, META, REASONS, SOURCE, api, ledger, rows, start

pytestmark = pytest.mark.xfail(strict=True, raises=AssertionError,
                               reason="spec 033 T062 not implemented: generate_gate3_evidence missing (remove in T062)")
PRODUCTION = "reports/artifacts/capital_gate/gate3/"
UNKNOWN = {"evidence_missing", "evidence_corrupt", "ledger_invalid", "backfill_incomplete", "candidate_ineligible",
           "matrix_undefined", "dsr_undefined", "t_stat_undefined", "pbo_undefined"}


def evidence(dsr=.97, t=3.4, pbo=.25, family_dsr=None, within_cap=True):
    counts = {"reason": None, "n_backfill": 40, "n_post_ledger": 6, "n_current": 46,
              "backfill_hash": "c" * 64, "ledger_head_hash": "e" * 64, "family": None}
    family = None
    if family_dsr is not None:
        counts["family"] = {"family": "example", "n_family": 3, "cap": 50, "within_cap": within_cap,
                            "n_dsr": 3 if within_cap else 46, "reverted_to_lifetime": not within_cap}
        family = {"value": family_dsr, "reason": None, "inputs": {"n_current": 3}, "matrix_hash": "f" * 64}
    sessions = [r["session"] for r in rows()]
    return {"selected_trial": "a", "family": "example", "generated_at_utc": "2026-10-11T00:00:00Z", "label": LABEL,
            "counts": counts,
            "matrix": {"matrix_hash": "f" * 64, "dates": sessions, "columns": ["a", "b"], "excluded_trials": [], "reason": None},
            "dsr": {"lifetime": {"value": dsr, "reason": None, "inputs": {"n_current": 46}, "matrix_hash": "f" * 64},
                    "family": family, "counts": counts},
            "t_stat": {"value": t, "reason": None, "hac_lags": 5},
            "pbo": {"value": pbo, "reason": None, "S": 16, "total_splits": 12870, "valid_splits": 12870, "rank_logit_summary": None,
                    "matrix_hash": "f" * 64},
            "cv": copy.deepcopy(CONFIG["cv"]), "costs": copy.deepcopy(META["costs"]), "source_identity": copy.deepcopy(SOURCE)}


def compose(value):
    return api("generate_gate3_evidence", "compose")(value)


def current(art):
    return {k: copy.deepcopy(art[k]) for k in ("ledger_head_hash", "backfill_hash", "matrix_hash", "source_identity")}


def failed_count(e, reason):
    """Real error shapes: lifetime_count and counted_dsr return undefined(), not a partial dict."""
    e["counts"] = e["dsr"] = {"value": None, "reason": reason}


def undefined_family(e):
    """A within-cap family whose DSR is undefined must not quietly fall back to lifetime N."""
    e.update(evidence(family_dsr=.97))
    e["dsr"]["family"] = {"value": None, "reason": "matrix_family_mismatch"}


# T056 — artifact schema, ordered reason codes, evidence path and fixture labelling.

def test_artifact_carries_every_fr040_field_and_threshold_operand():
    art = compose(evidence())
    assert GATE_FIELDS <= art.keys()
    assert art["selected_trial"] == "a" and art["generated_at_utc"].endswith("Z") and art["artifact_id"]
    assert (art["dsr"]["value"], art["dsr"]["threshold"]) == (.97, .95)
    assert (art["t_stat"]["value"], art["t_stat"]["threshold"], art["t_stat"]["hac_lags"]) == (3.4, 3.0, 5)
    assert (art["pbo"]["value"], art["pbo"]["S"], art["pbo"]["valid_splits"]) == (.25, 16, 12870)
    assert (art["n_backfill"], art["n_post_ledger"], art["n_current"]) == (40, 6, 46)
    assert (art["ledger_head_hash"], art["backfill_hash"], art["matrix_hash"]) == ("e" * 64, "c" * 64, "f" * 64)
    assert (art["matrix_rows"], art["matrix_columns"]) == (32, 2)
    assert art["date_range"] == [rows()[0]["session"], rows()[-1]["session"]]
    assert (art["cv"], art["costs"], art["source_identity"]) == (CONFIG["cv"], META["costs"], SOURCE)
    assert art["dsr_lifetime"]["value"] == .97 and art["family"] is None


def test_reason_codes_are_known_and_in_frozen_order():
    value = evidence(dsr=.50)
    value["t_stat"] = {"value": None, "reason": "nonpositive_hac_se", "hac_lags": 5}
    value["pbo"].update(value=None, reason="rejected_cscv_splits")
    art = compose(value)  # frozen order differs from alphabetical on purpose
    assert art["reason_codes"] == ["t_stat_undefined", "pbo_undefined", "dsr_below_threshold"]
    assert set(art["reason_codes"]) <= set(REASONS) and art["status"] == "unknown"
    assert compose(evidence())["reason_codes"] == []


@pytest.mark.parametrize("plant, reason", [
    (lambda e: failed_count(e, "backfill_incomplete"), "backfill_incomplete"),
    (lambda e: failed_count(e, "ledger_invalid"), "ledger_invalid"),
    (lambda e: failed_count(e, "evidence_corrupt"), "evidence_corrupt"),
    (undefined_family, "dsr_undefined"),
    (lambda e: e["matrix"].update(reason="insufficient_matrix"), "matrix_undefined"),
    (lambda e: e.update(selected_trial="z"), "candidate_ineligible"),
    (lambda e: e.pop("pbo"), "evidence_missing"),
    (lambda e: e.pop("dsr"), "evidence_missing"),
])
def test_incomplete_or_unverifiable_inputs_are_unknown(plant, reason):
    value = evidence()
    plant(value)
    art = compose(value)
    assert art["status"] == "unknown" and reason in art["reason_codes"]
    assert GATE_FIELDS <= art.keys()


@pytest.mark.parametrize("stat", ["dsr", "pbo"])
def test_statistics_from_another_matrix_are_not_evidence(stat):
    value = evidence()
    (value["dsr"]["lifetime"] if stat == "dsr" else value["pbo"])["matrix_hash"] = "0" * 64
    art = compose(value)
    assert art["status"] == "unknown" and set(art["reason_codes"]) & UNKNOWN


def test_fixture_label_travels_and_production_path_is_repository_relative(tmp_path):
    labelled = compose(evidence())
    assert labelled["label"] == LABEL
    with pytest.raises(ValueError):
        api("generate_gate3_evidence", "write_artifact")(labelled, root=tmp_path)
    assert not (tmp_path / PRODUCTION).exists() or not any((tmp_path / PRODUCTION).iterdir())
    value = evidence()
    del value["label"]
    real = compose(value)
    assert "label" not in real
    path = api("generate_gate3_evidence", "write_artifact")(real, root=tmp_path)
    assert isinstance(path, str) and path.startswith(PRODUCTION) and "\\" not in path
    assert not PurePosixPath(path).is_absolute() and (tmp_path / path).is_file()


def test_family_dsr_gates_within_cap_and_lifetime_dsr_is_always_published():
    within = compose(evidence(dsr=.40, family_dsr=.97))
    assert (within["status"], within["dsr"]["value"], within["dsr_lifetime"]["value"]) == ("passed", .97, .40)
    assert within["family"]["n_dsr"] == 3 and within["n_current"] == 46
    reverted = compose(evidence(dsr=.40, family_dsr=.97, within_cap=False))
    assert (reverted["status"], reverted["reason_codes"]) == ("failed", ["dsr_below_threshold"])
    assert reverted["dsr"]["value"] == reverted["dsr_lifetime"]["value"] == .40
    assert reverted["family"]["reverted_to_lifetime"] is True


# T057 — decision table (spec "Gate Decision Table", FR-041..FR-043).

@pytest.mark.parametrize("dsr, t, pbo, status, reasons", [
    (.95, 3.0, .25, "passed", []),
    (.97, 3.4, .90, "passed", []),
    (math.nextafter(.95, 0), 3.4, .25, "failed", ["dsr_below_threshold"]),
    (.97, math.nextafter(3.0, 0), .25, "failed", ["t_stat_below_threshold"]),
    (.50, 1.0, .25, "failed", ["dsr_below_threshold", "t_stat_below_threshold"]),
    (float("nan"), 3.4, .25, "unknown", ["dsr_undefined"]),
    (.97, float("inf"), .25, "unknown", ["t_stat_undefined"]),
    (.97, 3.4, float("nan"), "unknown", ["pbo_undefined"]),
])
def test_decision_table(dsr, t, pbo, status, reasons):
    art = compose(evidence(dsr=dsr, t=t, pbo=pbo))
    assert (art["status"], art["reason_codes"]) == (status, reasons)


def test_pbo_must_be_s16_and_has_no_invented_cutoff():
    value = evidence(pbo=.99)
    assert compose(value)["status"] == "passed"
    value["pbo"]["S"] = 8
    assert (compose(value)["status"], compose(value)["reason_codes"]) == ("unknown", ["pbo_undefined"])


@pytest.mark.parametrize("field, reason", [
    ("ledger_head_hash", "ledger_changed"), ("backfill_hash", "backfill_changed"), ("matrix_hash", "matrix_changed"),
    (("source_identity", "git_sha"), "source_changed"), (("source_identity", "source_tree_hash"), "source_changed"),
])
@pytest.mark.parametrize("dsr", [.97, .50])
def test_input_mismatch_is_stale_for_passed_and_failed_evidence(field, reason, dsr):
    assess = api("generate_gate3_evidence", "assess")
    art = compose(evidence(dsr=dsr))
    assert assess(art, current(art))["status"] == art["status"] in {"passed", "failed"}
    now = current(art)
    if isinstance(field, tuple): now[field[0]][field[1]] = "9" * len(now[field[0]][field[1]])
    else: now[field] = "9" * 64
    assert assess(art, now) == {"status": "stale", "reason_codes": [reason]}


def test_unknown_evidence_stays_unknown_when_inputs_also_moved():
    assess = api("generate_gate3_evidence", "assess")
    value = evidence()
    failed_count(value, "backfill_incomplete")
    art = compose(value)
    now = current(art) | {"ledger_head_hash": "9" * 64}
    assert assess(art, now)["status"] == "unknown"
    assert set(assess(art, now)["reason_codes"]) & UNKNOWN


# T058-T060 contract (queue Q99), beyond T056/T057's. Implemented by T062 unless marked T063/T064:
# - write_artifact writes `<PRODUCTION><artifact_id>.json` once, never overwriting, and appends one
#   {"artifact_id", "path", "sha256"} row (sha256 of the written bytes) to `<PRODUCTION>index.jsonl`.
# - current_inputs(artifact, root) returns today's ledger/backfill/matrix/source identity for `assess`.
# - main(argv) -> int is the offline command; gather(candidate=, family=, root=) builds its evidence.
# - T063: the route reads the latest index row under `capital_gate.ARTIFACT_ROOT`, verifies its digest,
#   and maps `assess(artifact, current_inputs(artifact, root))`; it never calls selection_bias.
GATE_ROUTE = "reports.api.routes.capital_gate"
STATISTICS = ("build_matrix", "lifetime_count", "counted_dsr", "matrix_dsr", "deflated_sharpe", "hac_t_stat", "matrix_pbo")
MOVED = {"ledger_head_hash": "9" * 64, "backfill_hash": "c" * 64, "matrix_hash": "f" * 64, "source_identity": SOURCE}


def real(**changes):
    value = evidence(**changes)
    del value["label"]
    return value


def write(art, root):
    return api("generate_gate3_evidence", "write_artifact")(art, root=root)


# T058 — immutable artifact and append-only index.

def test_each_evaluation_writes_a_new_file_and_an_append_only_index_row(tmp_path):
    first = compose(real())
    second = compose(real(dsr=.50) | {"generated_at_utc": "2026-10-12T00:00:00Z"})
    assert first["artifact_id"] != second["artifact_id"]
    index = tmp_path / PRODUCTION / "index.jsonl"
    path1 = write(first, tmp_path)
    bytes1, index1 = (tmp_path / path1).read_bytes(), index.read_bytes()
    path2 = write(second, tmp_path)
    assert path1 != path2 and (tmp_path / path1).read_bytes() == bytes1
    lines = index.read_bytes().splitlines()
    assert index.read_bytes().startswith(index1) and len(lines) == 2
    for path, art, line in zip((path1, path2), (first, second), lines):
        row, raw = json.loads(line), (tmp_path / path).read_bytes()
        assert (row["artifact_id"], row["path"], row["sha256"]) == (art["artifact_id"], path, hashlib.sha256(raw).hexdigest())
        assert json.loads(raw) == art
    with pytest.raises((FileExistsError, ValueError)):
        write(first, tmp_path)
    assert (tmp_path / path1).read_bytes() == bytes1 and len(index.read_bytes().splitlines()) == 2


def test_identical_evidence_evaluated_twice_is_two_artifacts_and_two_index_rows(tmp_path):
    first, second = compose(real()), compose(real())  # same evidence, same generated_at_utc
    assert first["artifact_id"] != second["artifact_id"], "FR-039: every evaluation is a new artifact"
    assert {k: v for k, v in first.items() if k != "artifact_id"} == {k: v for k, v in second.items() if k != "artifact_id"}
    paths = [write(first, tmp_path), write(second, tmp_path)]
    rows = [json.loads(line) for line in (tmp_path / PRODUCTION / "index.jsonl").read_text().splitlines()]
    assert paths[0] != paths[1] and [row["artifact_id"] for row in rows] == [first["artifact_id"], second["artifact_id"]]


def test_a_new_candidate_start_or_changed_config_makes_the_prior_artifact_stale(tmp_path):
    assess = api("generate_gate3_evidence", "assess")
    log = ledger(tmp_path)
    start(log)
    value = real()
    value["counts"]["ledger_head_hash"] = log.verify()["head"]
    art = compose(value)
    assert assess(art, current(art))["status"] == "passed"
    for changed in ({}, {"model": {"name": "example", "params": {"window": 2}}}):  # re-run, then a new config
        start(log, **changed)
        now = current(art) | {"ledger_head_hash": log.verify()["head"]}
        assert assess(art, now) == {"status": "stale", "reason_codes": ["ledger_changed"]}


# T059 — the route reads evidence, never computes it, and stays unknown without it.

def gate_route(monkeypatch, root, now=None, *, discover=False):
    """Gate items from the real route over `root`; any statistic computed during the GET fails the test.

    `discover=True` leaves the generator's `current_inputs` as the caller set it."""
    api("generate_gate3_evidence", "current_inputs")
    gates, generator = importlib.import_module(GATE_ROUTE), importlib.import_module("generate_gate3_evidence")
    for name in (*STATISTICS, "gather"):
        for module in (importlib.import_module("selection_bias"), gates, generator):
            monkeypatch.setattr(module, name, lambda *a, _n=name, **k: pytest.fail(f"GET computed {_n}"), raising=False)
    monkeypatch.setattr(gates, "ARTIFACT_ROOT", root, raising=False)
    if not discover:
        monkeypatch.setattr(generator, "current_inputs", lambda art, root: copy.deepcopy(now) if now else current(art))
    return {gate.gate_number: gate for gate in gates.get_capital_gate_status().gates}


@pytest.mark.parametrize("dsr, now, status", [(.97, None, "passed"), (.50, None, "failed"), (.97, MOVED, "stale")])
def test_route_serves_indexed_evidence_without_computing(tmp_path, monkeypatch, dsr, now, status):
    write(compose(real(dsr=.50 if dsr > .5 else .97) | {"generated_at_utc": "2026-10-10T00:00:00Z"}), tmp_path)
    path = write(compose(real(dsr=dsr)), tmp_path)  # the latest index row is the one served
    gates = gate_route(monkeypatch, tmp_path, now)
    assert (gates[3].status, gates[3].evidence) == (status, path)
    assert all((gates[n].status, gates[n].evidence) == ("unknown", None) for n in (1, 2, 4, 5))


def test_route_stays_unknown_without_a_valid_indexed_artifact(tmp_path, monkeypatch):
    empty = gate_route(monkeypatch, tmp_path)[3]
    assert (empty.status, empty.evidence, empty.details) == ("unknown", None, importlib.import_module(GATE_ROUTE).NO_EVIDENCE)
    path = write(compose(real(dsr=.50)), tmp_path)
    tampered = json.loads((tmp_path / path).read_bytes()) | {"status": "passed", "reason_codes": []}
    (tmp_path / path).write_text(json.dumps(tampered))  # well-formed, but no longer the indexed digest
    gate = gate_route(monkeypatch, tmp_path)[3]
    assert (gate.status, gate.evidence) == ("unknown", None)
    for planted, art in (("outside.json", compose(real())), (PRODUCTION + "fixture.json", compose(evidence()))):
        raw = json.dumps(art).encode()  # digest matches, but outside the gate3 directory or fixture-labelled
        (tmp_path / planted).write_bytes(raw)
        with (tmp_path / PRODUCTION / "index.jsonl").open("ab") as index:
            index.write(json.dumps({"artifact_id": art["artifact_id"], "path": planted,
                                    "sha256": hashlib.sha256(raw).hexdigest()}).encode() + b"\n")
        assert gate_route(monkeypatch, tmp_path)[3].evidence is None, planted


def test_real_current_inputs_see_an_advanced_ledger_and_the_route_turns_stale(tmp_path, monkeypatch):
    """Only the ledger head is discovered for real: a synthetic root has no backfill or emitted matrix."""
    discover, assess = (api("generate_gate3_evidence", name) for name in ("current_inputs", "assess"))
    log = ledger(tmp_path)
    start(log)
    value = real()
    value["counts"]["ledger_head_hash"] = log.verify()["head"]
    art = compose(value)
    assert discover(art, tmp_path)["ledger_head_hash"] == art["ledger_head_hash"]
    path = write(art, tmp_path)
    head_only = lambda a, root: current(a) | {"ledger_head_hash": discover(a, root)["ledger_head_hash"]}  # noqa: E731
    monkeypatch.setattr(importlib.import_module("generate_gate3_evidence"), "current_inputs", head_only)
    assert gate_route(monkeypatch, tmp_path, discover=True)[3].status == "passed"
    start(log)  # the ledger advances after the artifact was generated
    assert discover(art, tmp_path)["ledger_head_hash"] == log.verify()["head"] != art["ledger_head_hash"], \
        "current_inputs echoed the artifact"
    assert assess(art, head_only(art, tmp_path)) == {"status": "stale", "reason_codes": ["ledger_changed"]}
    gate = gate_route(monkeypatch, tmp_path, discover=True)[3]
    assert (gate.status, gate.evidence) == ("stale", path)


def plant_backfill(root, n_backfill):
    body = {"schema_version": 1, "campaign_id": f"example-{n_backfill}", "status": "complete", "n_backfill": n_backfill}
    stored = body | {"sha256": api("trial_registry", "digest")(body)}
    folder = root / "docs/trials/backfill"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"example-{n_backfill}.json").write_text(json.dumps(stored))
    return stored


@pytest.mark.parametrize("moved, field, reason", [("backfill", "backfill_hash", "backfill_changed"),
                                                  ("source", "source_identity", "source_changed")])
def test_real_current_inputs_see_a_superseding_backfill_or_changed_source(tmp_path, moved, field, reason):
    """Backfill (self-hashed files under docs/trials/backfill) and source (trial_registry.source_identity)
    are discovered for real; the emitted matrix has no specified storage yet (FR-022), so it is not."""
    discover, assess = (api("generate_gate3_evidence", name) for name in ("current_inputs", "assess"))
    log = ledger(tmp_path)
    start(log)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "strategy.py").write_text("WINDOW = 20\n")
    value = real()
    value["counts"].update(ledger_head_hash=log.verify()["head"], backfill_hash=plant_backfill(tmp_path, 40)["sha256"])
    value["source_identity"] = api("trial_registry", "source_identity")(tmp_path)
    art = compose(value)
    found = discover(art, tmp_path)
    assert (found["backfill_hash"], found["source_identity"]) == (art["backfill_hash"], art["source_identity"])
    if moved == "backfill":
        plant_backfill(tmp_path, 41)  # a superseding, larger count
    else:
        (tmp_path / "scripts" / "strategy.py").write_text("WINDOW = 21\n")
    now = discover(art, tmp_path)
    assert now[field] != art[field], "current_inputs echoed the artifact"
    assert assess(art, current(art) | {field: now[field]}) == {"status": "stale", "reason_codes": [reason]}


def plant_row(root, raw_row):
    with (root / PRODUCTION / "index.jsonl").open("ab") as index:
        index.write(raw_row + b"\n")


def plant_artifact(root, name, raw):
    (root / PRODUCTION / name).write_bytes(raw)
    return json.dumps({"artifact_id": name, "path": PRODUCTION + name, "sha256": hashlib.sha256(raw).hexdigest()}).encode()


@pytest.mark.parametrize("case", ["truncated row", "row not an object", "row without sha256", "artifact not json",
                                  "artifact wrong schema", "indexed file missing", "index not utf-8"])
def test_route_fails_closed_on_malformed_index_or_artifact(tmp_path, monkeypatch, case):
    write(compose(real()), tmp_path)  # a valid passed artifact first: the route must not fall back to it
    assert gate_route(monkeypatch, tmp_path)[3].status == "passed", "control: the valid artifact is served"
    if case == "truncated row":
        plant_row(tmp_path, b'{"artifact_id": "x", "path": "' + PRODUCTION.encode())
    elif case == "row not an object":
        plant_row(tmp_path, b'["x", "y"]')
    elif case == "row without sha256":
        plant_row(tmp_path, json.dumps({"artifact_id": "x", "path": PRODUCTION + "x.json"}).encode())
    elif case == "artifact not json":
        plant_row(tmp_path, plant_artifact(tmp_path, "broken.json", b'{"status": "passed", "reason_co'))
    elif case == "artifact wrong schema":
        plant_row(tmp_path, plant_artifact(tmp_path, "thin.json", json.dumps({"status": "passed", "reason_codes": []}).encode()))
    elif case == "indexed file missing":
        plant_row(tmp_path, json.dumps({"artifact_id": "gone", "path": PRODUCTION + "gone.json", "sha256": "0" * 64}).encode())
    else:
        plant_row(tmp_path, b"\xff\xfe not utf-8")
    gate = gate_route(monkeypatch, tmp_path)[3]  # must return, never raise a server error
    assert (gate.status, gate.evidence) == ("unknown", None), case


def test_gate3_text_names_the_real_thresholds_and_diagnostic_pbo():
    text = {g.gate_number: g for g in importlib.import_module(GATE_ROUTE).get_capital_gate_status().gates}[3].description
    assert "remains positive" not in text, "T064: a positive probability is not the gate"
    assert re.search(r"DSR[^;,]{0,20}(≥|>=)\s*0\.95", text), "T064 DSR threshold"
    assert re.search(r"t[- ]stat\w*[^;,]{0,20}(≥|>=)\s*3(\.0)?\b", text), "T064 t-statistic threshold"
    assert "PBO" in text and "diagnostic" in text.lower(), "T064 PBO wording"


# T060 — the offline command.

def command(tmp_path, monkeypatch, value, *, now=None, argv=None):
    main = api("generate_gate3_evidence", "main")
    module, asked = importlib.import_module("generate_gate3_evidence"), []
    monkeypatch.setattr(module, "gather", lambda **kw: asked.append(kw) or copy.deepcopy(value))
    monkeypatch.setattr(module, "current_inputs", lambda art, root: copy.deepcopy(now) if now else current(art))
    explicit = ["--candidate", "b", "--family", "example", "--root", str(tmp_path)]
    return main(explicit if argv is None else argv), asked


@pytest.mark.parametrize("argv", [[], ["--candidate", "a"], ["--family", "example"]])
def test_command_requires_explicit_candidate_and_family(tmp_path, monkeypatch, argv):
    with pytest.raises(SystemExit) as stopped:
        command(tmp_path, monkeypatch, real(), argv=[*argv, "--root", str(tmp_path)])
    assert stopped.value.code not in (0, None) and not (tmp_path / PRODUCTION).exists()


@pytest.mark.parametrize("plant, now, ok", [
    (None, None, True),
    (lambda e: failed_count(e, "ledger_invalid"), None, False),
    (None, MOVED, False),
])
def test_command_prints_the_new_path_exits_nonzero_unless_current_and_claims_no_other_gate(
        tmp_path, monkeypatch, capsys, plant, now, ok):
    value = real() | {"selected_trial": "b"}
    if plant: plant(value)
    code, asked = command(tmp_path, monkeypatch, value, now=now)
    out = "".join(capsys.readouterr())
    rows = [json.loads(line) for line in (tmp_path / PRODUCTION / "index.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["path"] in out
    assert (code == 0) is ok and [(kw["candidate"], kw["family"]) for kw in asked] == [("b", "example")]
    claim = r"gates?\s*[1245][^\n]*\b(pass|ready|clear)|capital[- ]ready|cleared for|overall[^\n]*readi"
    assert not re.search(claim, out, re.I), "FR-050: no claim beyond Gate 3"
