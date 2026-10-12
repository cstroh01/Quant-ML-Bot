"""Spec 033 T062: offline Gate 3 evidence — verify inputs, calculate once, write an immutable artifact.

`compose` maps already-computed `selection_bias` outputs to a status and ordered reason codes and
recomputes no statistic. `write_artifact` writes `<GATE3_DIR><artifact_id>.json` exactly once and
appends one `{"artifact_id", "path", "sha256"}` row to `<GATE3_DIR>index.jsonl`; prior bytes never
change (FR-039). `assess` re-checks currentness (FR-043). `main` is the offline command (T060); it
claims nothing about any gate but Gate 3.

`gather` is the only function that reads the ledger and computes: it needs the family's
preregistered matrix policy and HAC bandwidth (a `gate3` block in the family declaration) and
refuses without one. Matrix currentness has no stored emitted matrix to compare against yet
(FR-022 names no location), so `current_inputs` reports the matrix as unknown and an artifact can
never assess as current until that is decided.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from selection_bias import build_matrix, counted_dsr, hac_t_stat, matrix_pbo
from trial_registry import ROOT, TrialLedger, source_identity, trial_counts, verify_family

SCHEMA_VERSION = 1
GATE3_DIR = "reports/artifacts/capital_gate/gate3/"
DSR_THRESHOLD = 0.95
T_THRESHOLD = 3.0
PBO_S = 16
REASONS = ("evidence_missing", "evidence_corrupt", "ledger_invalid", "backfill_incomplete", "candidate_ineligible",
           "matrix_undefined", "dsr_undefined", "t_stat_undefined", "pbo_undefined", "ledger_changed",
           "backfill_changed", "matrix_changed", "source_changed", "dsr_below_threshold", "t_stat_below_threshold")
UNKNOWN = frozenset(REASONS[:9])
CURRENT = (("ledger_head_hash", "ledger_changed"), ("backfill_hash", "backfill_changed"),
           ("matrix_hash", "matrix_changed"), ("source_identity", "source_changed"))


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _ordered(codes: set[str]) -> list[str]:
    return [code for code in REASONS if code in codes]


def compose(evidence: dict) -> dict:
    """The Gate 3 artifact for `evidence`: every FR-040 field, a status and frozen-order reason codes.

    `unknown` when any input is missing, failed, undefined or from another matrix; else `failed` when
    DSR < 0.95 or HAC t < 3.0; else `passed`. PBO must be computed at S = 16 but has no cutoff. The
    gating DSR is the family-N DSR while the family is within its cap, else the lifetime-N DSR.
    `artifact_id` is fresh on every call, so a repeated evaluation is a new artifact.
    """
    e = copy.deepcopy(evidence)
    codes: set[str] = set()
    counts = e.get("counts") if isinstance(e.get("counts"), dict) else None
    matrix = e.get("matrix") if isinstance(e.get("matrix"), dict) else None
    dsr = e.get("dsr") if isinstance(e.get("dsr"), dict) else None
    t_stat = e.get("t_stat") if isinstance(e.get("t_stat"), dict) else None
    pbo = e.get("pbo") if isinstance(e.get("pbo"), dict) else None
    if None in (counts, matrix, dsr, t_stat, pbo):
        codes.add("evidence_missing")
    if counts is not None and counts.get("reason"):
        codes.add(counts["reason"] if counts["reason"] in UNKNOWN else "evidence_missing")
    if matrix is not None and (matrix.get("reason") or not matrix.get("columns") or not matrix.get("dates")):
        codes.add("matrix_undefined")
    if matrix is not None and e.get("selected_trial") not in (matrix.get("columns") or []):
        codes.add("candidate_ineligible")
    family = (counts or {}).get("family")
    lifetime = (dsr or {}).get("lifetime") if dsr and not dsr.get("reason") else None
    gating = lifetime
    if dsr is not None and dsr.get("reason"):
        codes.add(dsr["reason"] if dsr["reason"] in UNKNOWN else "dsr_undefined")
    if family is not None and family.get("within_cap"):
        gating = (dsr or {}).get("family")
        if not isinstance(gating, dict) or not _finite(gating.get("value")):
            codes.add("dsr_undefined")
    matrix_hash = (matrix or {}).get("matrix_hash")
    for stat in (lifetime, gating, pbo):
        if isinstance(stat, dict) and stat.get("matrix_hash") not in (None, matrix_hash):
            codes.add("evidence_corrupt")
    dsr_value = gating.get("value") if isinstance(gating, dict) else None
    if dsr is not None and not _finite(dsr_value):
        codes.add("dsr_undefined")
    t_value = (t_stat or {}).get("value")
    if t_stat is not None and not _finite(t_value):
        codes.add("t_stat_undefined")
    if pbo is not None and (not _finite(pbo.get("value")) or pbo.get("S") != PBO_S):
        codes.add("pbo_undefined")
    if _finite(dsr_value) and dsr_value < DSR_THRESHOLD:
        codes.add("dsr_below_threshold")
    if _finite(t_value) and t_value < T_THRESHOLD:
        codes.add("t_stat_below_threshold")
    status = "unknown" if codes & UNKNOWN else "failed" if codes else "passed"
    dates = (matrix or {}).get("dates") or []
    artifact = {
        "schema_version": SCHEMA_VERSION, "artifact_id": uuid.uuid4().hex,
        "generated_at_utc": e.get("generated_at_utc"), "selected_trial": e.get("selected_trial"),
        "status": status, "reason_codes": _ordered(codes),
        "ledger_head_hash": (counts or {}).get("ledger_head_hash"), "n_backfill": (counts or {}).get("n_backfill"),
        "n_post_ledger": (counts or {}).get("n_post_ledger"), "n_current": (counts or {}).get("n_current"),
        "backfill_hash": (counts or {}).get("backfill_hash"), "matrix_hash": matrix_hash,
        "matrix_rows": len(dates), "matrix_columns": len((matrix or {}).get("columns") or []),
        "date_range": [dates[0], dates[-1]] if dates else None,
        "excluded_trials": (matrix or {}).get("excluded_trials"),
        "dsr": {**(gating or {}), "value": dsr_value, "threshold": DSR_THRESHOLD},
        "dsr_lifetime": lifetime,
        "t_stat": {**(t_stat or {}), "value": t_value, "threshold": T_THRESHOLD},
        "pbo": pbo, "cv": e.get("cv"), "costs": e.get("costs"), "source_identity": e.get("source_identity"),
        "family": family,
    }
    if "label" in e:
        artifact["label"] = e["label"]
    return artifact


def assess(artifact: dict, current: dict) -> dict:
    """`stale` with every changed input when a passed/failed artifact no longer matches `current`.

    An unknown artifact stays unknown. A current input that cannot be determined (`None`) makes a
    known artifact unknown (`evidence_missing`), never current.
    """
    if artifact.get("status") not in ("passed", "failed"):
        return {"status": "unknown", "reason_codes": list(artifact.get("reason_codes") or ["evidence_missing"])}
    if any(current.get(key) is None for key, _ in CURRENT):
        return {"status": "unknown", "reason_codes": ["evidence_missing"]}
    changed = [code for key, code in CURRENT if artifact.get(key) != current.get(key)]
    if changed:
        return {"status": "stale", "reason_codes": changed}
    return {"status": artifact["status"], "reason_codes": list(artifact["reason_codes"])}


def write_artifact(artifact: dict, root: Path = ROOT) -> str:
    """Write `artifact` once under GATE3_DIR and append its index row; return the repository-relative path.

    A fixture-labelled artifact is refused (FR-048). An existing artifact file is never overwritten
    (`FileExistsError`) and then no index row is appended.
    """
    if "label" in artifact:
        raise ValueError("a fixture-labelled artifact is never written to the production evidence directory")
    if not isinstance(artifact.get("artifact_id"), str) or not artifact["artifact_id"].isalnum():
        raise ValueError("artifact_id must be alphanumeric")
    directory = Path(root) / GATE3_DIR
    directory.mkdir(parents=True, exist_ok=True)
    relative = f"{GATE3_DIR}{artifact['artifact_id']}.json"
    raw = json.dumps(artifact, sort_keys=True).encode("utf-8")
    with open(Path(root) / relative, "xb") as handle:
        handle.write(raw)
    row = {"artifact_id": artifact["artifact_id"], "path": relative, "sha256": hashlib.sha256(raw).hexdigest()}
    with open(directory / "index.jsonl", "ab") as index:
        index.write(json.dumps(row, sort_keys=True).encode("utf-8") + b"\n")
    return relative


def _ledger(root: Path) -> TrialLedger:
    return TrialLedger(root, synthetic=Path(root).resolve() != ROOT)


def _current_backfill(root: Path) -> dict | None:
    """The stored, self-hashed backfill artifact with the largest count: a superseding one wins."""
    folder = Path(root) / "docs/trials/backfill"
    stored = [json.loads(p.read_bytes()) for p in sorted(folder.glob("*.json")) if p.name != "manifest.json"]
    stored = [a for a in stored if isinstance(a, dict) and isinstance(a.get("n_backfill"), int)]
    return max(stored, key=lambda a: a["n_backfill"]) if stored else None


def current_inputs(artifact: dict, root: Path = ROOT) -> dict:
    """Today's ledger head, backfill hash and source identity under `root`; the matrix is unknown (None)."""
    backfill = _current_backfill(root)
    return {"ledger_head_hash": _ledger(root).verify()["head"],
            "backfill_hash": backfill.get("sha256") if backfill else None,
            "matrix_hash": None,  # FR-022 names no stored emitted matrix yet; see the module docstring
            "source_identity": source_identity(root)}


def gather(*, candidate: str, family: str, root: Path = ROOT) -> dict:
    """Compute the evidence once, offline, from the verified ledger for `candidate` in `family`.

    Needs the family declaration's `gate3` block: `alignment`, `min_coverage`, `objective`,
    `risk_free` (for `build_matrix`) and `hac_lags`, `horizon` (for `hac_t_stat`); refuses without it.
    """
    policy = verify_family(family, root=root)["declaration"].get("gate3")
    needed = {"alignment", "min_coverage", "objective", "risk_free", "hac_lags", "horizon"}
    if not isinstance(policy, dict) or not needed <= policy.keys():
        raise ValueError(f"family {family!r} declares no complete gate3 policy {sorted(needed)}; "
                         "the matrix coverage rule and HAC bandwidth must be preregistered")
    log = _ledger(root)
    backfill = _current_backfill(root)
    counts = trial_counts(backfill or {}, log, family=family)
    trials = []
    for event in log.verify()["events"]:
        sidecar = event.get("sidecar")
        if event["event_type"] == "completed" and sidecar:
            lines = (Path(root) / sidecar["path"]).read_text(encoding="utf-8").splitlines()
            trials.append({**event, "returns": [json.loads(line) for line in lines]})
    matrix = build_matrix(trials, family={"id": family, **{k: policy[k] for k in
                                                           ("alignment", "min_coverage", "objective", "risk_free")}})
    column = matrix["columns"].index(candidate) if candidate in matrix.get("columns", []) else None
    returns = [row[column] for row in matrix.get("values", [])] if column is not None else []
    selected = next((t for t in trials if t["trial_id"] == candidate), {})
    return {"selected_trial": candidate, "family": family,
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "counts": counts, "matrix": matrix, "dsr": counted_dsr(matrix, selected_trial=candidate, counts=counts),
            "t_stat": hac_t_stat(returns, horizon=policy["horizon"], lags=policy["hac_lags"],
                                 annual_risk_free=policy["risk_free"]["annual_rate"]),
            "pbo": matrix_pbo(matrix), "cv": selected.get("config", {}).get("cv"),
            "costs": selected.get("sidecar", {}).get("metadata", {}).get("costs"),
            "source_identity": source_identity(root)}


def main(argv: list[str] | None = None) -> int:
    """Write one new Gate 3 artifact and print its path; exit 0 only when it is current and passed/failed."""
    parser = argparse.ArgumentParser(description="Spec 033 Gate 3 evidence (offline). Says nothing about other gates.")
    parser.add_argument("--candidate", required=True, help="the preselected trial id")
    parser.add_argument("--family", required=True, help="the declared family the candidate belongs to")
    parser.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        evidence = gather(candidate=args.candidate, family=args.family, root=root)
    except ValueError as error:
        print(f"Gate 3 evidence not generated: {error}", file=sys.stderr)
        return 2
    artifact = compose(evidence)
    path = write_artifact(artifact, root)
    verdict = assess(artifact, current_inputs(artifact, root))
    print(f"Gate 3 artifact: {path}")
    print(f"Gate 3 status: {verdict['status']}; reasons: {', '.join(verdict['reason_codes']) or 'none'}")
    return 0 if verdict["status"] in ("passed", "failed") else 1


if __name__ == "__main__":
    sys.exit(main())
