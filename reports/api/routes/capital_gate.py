"""Capital Gate status and verification cockpit API endpoints.

Gate 3 reads immutable offline evidence (033 T063/T064). Other gates and the
test run remain unverified. This endpoint computes no selection statistics.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import generate_gate3_evidence as gate3
from fastapi import APIRouter
from reports.api.schemas import CapitalGateItem, CapitalGateStatusResponse, NotComputed

router = APIRouter(prefix="/api/capital_gate", tags=["capital_gate"])

NO_EVIDENCE = "No verification artifact is recorded for this gate, so its state is unknown."
ARTIFACT_ROOT = Path(__file__).resolve().parents[3]
_FIELDS = set("schema_version artifact_id generated_at_utc selected_trial status reason_codes ledger_head_hash "
              "n_backfill n_post_ledger n_current backfill_hash matrix_hash matrix_rows matrix_columns date_range "
              "excluded_trials dsr dsr_lifetime t_stat pbo cv costs source_identity family".split())


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError("invalid Gate 3 evidence")


def _json(raw: bytes) -> object:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("non-finite JSON")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def _finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _hash(value: object, length: int = 64) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


def _validate(artifact: object, artifact_id: str) -> dict:
    """Validate recorded operands/provenance, without recomputing DSR, HAC or PBO."""
    _require(isinstance(artifact, dict) and _FIELDS <= artifact.keys() and "label" not in artifact)
    a = artifact
    _require(type(a["schema_version"]) is int and a["schema_version"] == gate3.SCHEMA_VERSION)
    _require(a["artifact_id"] == artifact_id and isinstance(a["selected_trial"], str) and bool(a["selected_trial"]))
    instant = datetime.fromisoformat(a["generated_at_utc"])
    _require(instant.utcoffset() == timedelta(0))
    _require(a["status"] in ("passed", "failed", "unknown"))
    reasons = a["reason_codes"]
    _require(isinstance(reasons, list) and all(isinstance(code, str) for code in reasons))
    _require(reasons == [code for code in gate3.REASONS if code in reasons])
    if a["status"] == "unknown":
        _require(bool(set(reasons) & gate3.UNKNOWN))
        return a
    for key in ("ledger_head_hash", "backfill_hash", "matrix_hash"):
        _require(_hash(a[key]))
    for key in ("n_backfill", "n_post_ledger", "n_current", "matrix_rows", "matrix_columns"):
        _require(type(a[key]) is int and a[key] >= 0)
    _require(a["n_current"] == a["n_backfill"] + a["n_post_ledger"] and a["n_current"] >= 1)
    _require(a["matrix_rows"] >= gate3.PBO_S and a["matrix_columns"] >= 2)
    span = a["date_range"]
    _require(isinstance(span, list) and len(span) == 2 and date.fromisoformat(span[0]) <= date.fromisoformat(span[1]))
    _require(isinstance(a["excluded_trials"], list))
    for name in ("dsr", "dsr_lifetime", "t_stat", "pbo"):
        stat = a[name]
        _require(isinstance(stat, dict) and _finite(stat.get("value")) and not stat.get("reason"))
        if name != "t_stat":
            _require(0 <= stat["value"] <= 1 and stat.get("matrix_hash") == a["matrix_hash"])
    _require(a["dsr"].get("threshold") == gate3.DSR_THRESHOLD and a["t_stat"].get("threshold") == gate3.T_THRESHOLD)
    _require(type(a["t_stat"].get("hac_lags")) is int and a["t_stat"]["hac_lags"] >= 0)
    pbo = a["pbo"]
    _require(type(pbo.get("S")) is int and pbo["S"] == gate3.PBO_S)
    _require(type(pbo.get("valid_splits")) is int and type(pbo.get("total_splits")) is int)
    _require(pbo["valid_splits"] == pbo["total_splits"] == math.comb(gate3.PBO_S, gate3.PBO_S // 2))
    cv, costs, source = a["cv"], a["costs"], a["source_identity"]
    _require(isinstance(cv, dict) and cv.get("scheme") == "purged_embargoed_walk_forward")
    for key, minimum in (("folds", 1), ("purge", 1), ("embargo", 1)):
        _require(type(cv.get(key)) is int and cv[key] >= minimum)
    _require(isinstance(costs, dict) and _finite(costs.get("commission")) and costs["commission"] >= 0)
    _require(isinstance(costs.get("slippage"), dict) and costs["slippage"].get("model") == "spread_plus_sqrt_impact")
    _require(isinstance(source, dict) and _hash(source.get("git_sha"), 40) and _hash(source.get("source_tree_hash")))
    _require(source.get("workspace_state") in ("clean", "dirty", "unknown"))
    family = a["family"]
    n_dsr = a["n_current"]
    if family is not None:
        _require(isinstance(family, dict) and isinstance(family.get("family"), str))
        _require(type(family.get("within_cap")) is bool)
        _require(type(family.get("n_dsr")) is int and family["n_dsr"] >= 1)
        if family["within_cap"]:
            _require(type(family.get("cap")) is int and 1 <= family["cap"] <= 50)
            _require(type(family.get("n_family")) is int and 1 <= family["n_family"] <= family["cap"])
            n_dsr = family["n_family"]
        _require(family["n_dsr"] == n_dsr)
    for stat, count in ((a["dsr_lifetime"], a["n_current"]), (a["dsr"], n_dsr)):
        inputs = stat.get("inputs")
        _require(isinstance(inputs, dict) and type(inputs.get("n_current")) is int and inputs["n_current"] == count)
    # Check recorded decision consistency, never derive a statistic from returns.
    expected = [code for value, threshold, code in (
        (a["dsr"]["value"], gate3.DSR_THRESHOLD, "dsr_below_threshold"),
        (a["t_stat"]["value"], gate3.T_THRESHOLD, "t_stat_below_threshold")) if value < threshold]
    _require(reasons == expected and a["status"] == ("failed" if expected else "passed"))
    return a


def _gate3_status() -> dict:
    """Read only the newest index row; corruption must never resurrect an older pass."""
    missing = {"status": "unknown", "details": NO_EVIDENCE}
    try:
        root = Path(ARTIFACT_ROOT).resolve()
        directory = root / gate3.GATE3_DIR
        _require(directory.resolve() == directory)
        index = directory / "index.jsonl"
        _require(index.resolve() == index)
        row = _json(index.read_bytes().splitlines()[-1])
        _require(isinstance(row, dict))
        artifact_id = row.get("artifact_id")
        _require(isinstance(artifact_id, str) and re.fullmatch(r"[A-Za-z0-9]+", artifact_id) is not None)
        relative = f"{gate3.GATE3_DIR}{artifact_id}.json"
        _require(row.get("path") == relative and _hash(row.get("sha256")))
        path = root / relative
        _require(path.resolve() == path)
        raw = path.read_bytes()
        _require(hashlib.sha256(raw).hexdigest() == row["sha256"])
        artifact = _validate(_json(raw), artifact_id)
        verdict = gate3.assess(artifact, gate3.current_inputs(artifact, root))
        return {"status": verdict["status"], "evidence": relative,
                "details": ", ".join(verdict["reason_codes"]) or "Verified current Gate 3 evidence meets both inclusive thresholds; PBO is diagnostic."}
    except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError):
        return missing


@router.get("/status", response_model=CapitalGateStatusResponse)
def get_capital_gate_status() -> CapitalGateStatusResponse:
    """Return the evidence status of the 5 Capital Gates (Project Instructions v2.1 §12)."""
    gates = [
        CapitalGateItem(
            gate_number=1,
            title="Layer 3 Machine Gates",
            description="Automated CI verification: lookahead shift test, null pipeline test on shuffled labels (Sharpe <= 0.3), and 2x cost stress test.",
            status="unknown",
            details=NO_EVIDENCE,
        ),
        CapitalGateItem(
            gate_number=2,
            title="Out-of-Sample Positive Expectancy",
            description="Purged & embargoed walk-forward OOS backtest shows positive expectancy net of realistic transaction costs ($1.00/trade, 5 bps slippage).",
            status="unknown",
            details=NO_EVIDENCE,
        ),
        CapitalGateItem(
            gate_number=3,
            title="Deflated Sharpe Ratio (AFML)",
            description="DSR >= 0.95 and HAC t-statistic >= 3.0, including equality; valid S = 16 PBO is mandatory diagnostic evidence with no cutoff.",
            **_gate3_status(),
        ),
        CapitalGateItem(
            gate_number=4,
            title="Paper Trading Verification",
            description="Minimum 1-2 months paper trading (broker paper account or live-data simulation) matching backtest performance within tolerance.",
            status="unknown",
            details="Awaits Phase 4 order execution and broker paper account integration.",
        ),
        CapitalGateItem(
            gate_number=5,
            title="Capped Real Capital Allocation",
            description="Starts with small, explicitly-capped real capital with automated stop-loss circuit breakers and strict risk limits.",
            status="unknown",
            details="Subject to human approval and execution gate (Constitution Rule 7).",
        ),
    ]

    return CapitalGateStatusResponse(
        overall_readiness="Verification evidence only; this historical five-gate dashboard does not establish overall capital readiness. Consult SCOPE-V1 section 11.3 for the seven-item capital checklist.",
        test_run=NotComputed(
            reason="The API reads no CI result, so the terminal reports no test count or pass state."
        ),
        gates=gates,
    )
