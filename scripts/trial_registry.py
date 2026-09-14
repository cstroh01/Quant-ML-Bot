"""Append-only, tamper-evident experiment registry for trial metadata."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TRIALS_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "trials" / "trials.jsonl"
)
REQUIRED_FIELDS = {
    "trial_id",
    "timestamp_utc",
    "git_commit",
    "git_dirty",
    "spec",
    "family",
    "target",
    "universe",
    "features",
    "feature_hash",
    "model",
    "cv",
    "seed",
    "outcome",
    "metrics",
    "sampling_frequency",
    "return_convention",
    "risk_free_source",
    "cost_model",
    "oos_returns_path",
    "oos_returns_sha256",
    "comparable_oos_sharpe",
    "notes",
    "prev_hash",
    "record_hash",
}
ALLOWED_OUTCOMES = {"kept", "abandoned", "rejected", "exploratory"}
ALLOWED_SAMPLING_FREQUENCIES = {"daily", "weekly", "monthly"}
ALLOWED_RETURN_CONVENTIONS = {"funded_account", "trade_pnl", "unfunded"}
NULLABLE_REQUIRED_FIELDS = {
    "risk_free_source",
    "cost_model",
    "oos_returns_sha256",
    "comparable_oos_sharpe",
    "oos_returns_path",
}


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _record_hash_for_obj(obj: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def _resolve_path(path: str | Path | None = None) -> Path:
    if path is None:
        return DEFAULT_TRIALS_PATH
    return Path(path)


def _short_git_commit(repo_root: Path) -> str | None:
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return None

    head_path = git_dir / "HEAD"
    if not head_path.exists():
        return None

    head_text = head_path.read_text(encoding="utf-8").strip()
    if not head_text:
        return None

    if head_text.startswith("ref:"):
        ref_name = head_text.split(" ", 1)[1].strip()
        ref_path = git_dir / ref_name
        if ref_path.exists():
            value = ref_path.read_text(encoding="utf-8").strip()
            if value:
                return value[:7]

        packed_refs_path = git_dir / "packed-refs"
        if packed_refs_path.exists():
            for line in packed_refs_path.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                if line.startswith("#"):
                    continue
                if line.endswith(ref_name):
                    sha = line.split()[0]
                    if sha:
                        return sha[:7]
    elif len(head_text) >= 7:
        return head_text[:7]
    return None


def _read_git_dirty(repo_root: Path) -> bool:
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return False
    head_path = git_dir / "HEAD"
    if not head_path.exists():
        return False
    head_text = head_path.read_text(encoding="utf-8").strip()
    if not head_text:
        return False
    if head_text.startswith("ref:"):
        ref_name = head_text.split(" ", 1)[1].strip()
        ref_path = git_dir / ref_name
        if ref_path.exists():
            return False
    return False


def _ensure_required_fields(record: dict[str, Any]) -> None:
    for field in sorted(REQUIRED_FIELDS):
        if field not in record:
            raise ValueError(f"Missing required field: {field}")
        if record[field] is None and field not in NULLABLE_REQUIRED_FIELDS:
            raise ValueError(f"Missing required field: {field}")


def validate_for_gate(record: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in ("sampling_frequency", "return_convention"):
        value = record.get(field)
        if value in (None, ""):
            missing.append(field)

    has_return_series = bool(record.get("oos_returns_path")) and bool(
        record.get("oos_returns_sha256")
    )
    if has_return_series:
        return list(dict.fromkeys(missing))

    comparable = record.get("comparable_oos_sharpe")
    for field in ("oos_returns_path", "oos_returns_sha256"):
        if record.get(field) in (None, ""):
            missing.append(field)
    if comparable in (None, ""):
        missing.append("comparable_oos_sharpe")
    return list(dict.fromkeys(missing))


def _sorted_list(values: Any, *, field_name: str) -> list[str]:
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list")
    result = [str(value) for value in values]
    return sorted(result)


def _normalize_record(fields: dict[str, Any], *, path: Path) -> dict[str, Any]:
    record = dict(fields)
    if "path" in record:
        record.pop("path")

    if "trial_id" not in record or not record["trial_id"]:
        record["trial_id"] = str(uuid.uuid4())

    if "timestamp_utc" not in record or not record["timestamp_utc"]:
        record["timestamp_utc"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    if "git_commit" not in record or not record["git_commit"]:
        git_commit = _short_git_commit(path.resolve().parents[1])
        if git_commit is None:
            raise ValueError("Missing required field: git_commit")
        record["git_commit"] = git_commit

    if "git_dirty" not in record or record["git_dirty"] is None:
        record["git_dirty"] = _read_git_dirty(path.resolve().parents[1])

    if not isinstance(record["git_dirty"], bool):
        raise ValueError("git_dirty must be a bool")

    for name in ("spec", "family", "notes"):
        if name not in record:
            raise ValueError(f"Missing required field: {name}")
        if name in ("spec", "family") and not isinstance(record[name], str):
            raise ValueError(f"{name} must be a string")
        if name == "notes" and not isinstance(record[name], str):
            raise ValueError("notes must be a string")

    target = record.get("target")
    if not isinstance(target, dict):
        raise ValueError("target must be a dict")
    if "label" not in target or "horizon_days" not in target:
        raise ValueError("target must include label and horizon_days")
    if not isinstance(target["label"], str) or not isinstance(
        target["horizon_days"], int
    ):
        raise ValueError(
            "target.label must be a string and target.horizon_days must be an int"
        )
    record["target"] = target

    universe = _sorted_list(record.get("universe"), field_name="universe")
    record["universe"] = universe

    features = _sorted_list(record.get("features"), field_name="features")
    record["features"] = features
    record["feature_hash"] = hashlib.sha256(
        _canonical_json(features).encode("utf-8")
    ).hexdigest()

    model = record.get("model")
    if not isinstance(model, dict):
        raise ValueError("model must be a dict")
    if "name" not in model or "params" not in model:
        raise ValueError("model must include name and params")
    record["model"] = model

    cv = record.get("cv")
    if not isinstance(cv, dict):
        raise ValueError("cv must be a dict")
    for field_name in ("scheme", "folds", "purge_days", "embargo_days"):
        if field_name not in cv:
            raise ValueError(f"cv must include {field_name}")
    record["cv"] = cv

    if "seed" not in record or record["seed"] is None:
        record["seed"] = None
    elif not isinstance(record["seed"], int):
        raise ValueError("seed must be an int or null")

    outcome = record.get("outcome")
    if outcome not in ALLOWED_OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(ALLOWED_OUTCOMES)}")
    record["outcome"] = outcome

    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be a dict")
    for key in ("is_sharpe", "oos_sharpe", "n_obs"):
        if key not in metrics:
            raise ValueError(f"metrics must include {key}")
    record["metrics"] = metrics

    oos_returns_path = record.get("oos_returns_path")
    if oos_returns_path is not None and not isinstance(oos_returns_path, str):
        raise ValueError("oos_returns_path must be a string or null")
    record["oos_returns_path"] = oos_returns_path

    sampling_frequency = record.get("sampling_frequency")
    if sampling_frequency not in ALLOWED_SAMPLING_FREQUENCIES:
        raise ValueError(
            "sampling_frequency must be one of "
            f"{sorted(ALLOWED_SAMPLING_FREQUENCIES)}"
        )
    record["sampling_frequency"] = sampling_frequency

    return_convention = record.get("return_convention")
    if return_convention not in ALLOWED_RETURN_CONVENTIONS:
        raise ValueError(
            "return_convention must be one of " f"{sorted(ALLOWED_RETURN_CONVENTIONS)}"
        )
    record["return_convention"] = return_convention

    risk_free_source = record.get("risk_free_source")
    if risk_free_source is not None and not isinstance(risk_free_source, str):
        raise ValueError("risk_free_source must be a string or null")
    record["risk_free_source"] = risk_free_source

    cost_model = record.get("cost_model")
    if cost_model is not None:
        if not isinstance(cost_model, dict):
            raise ValueError("cost_model must be a dict or null")
        for key in ("commission", "slippage", "impact"):
            if key not in cost_model:
                raise ValueError(f"cost_model must include {key}")
    record["cost_model"] = cost_model

    if oos_returns_path is None:
        record["oos_returns_sha256"] = None
    else:
        oos_returns_sha256 = record.get("oos_returns_sha256")
        if oos_returns_sha256 is not None:
            if not isinstance(oos_returns_sha256, str):
                raise ValueError("oos_returns_sha256 must be a string or null")
            record["oos_returns_sha256"] = oos_returns_sha256
        else:
            oos_returns_path_obj = Path(oos_returns_path)
            if oos_returns_path_obj.exists():
                record["oos_returns_sha256"] = hashlib.sha256(
                    oos_returns_path_obj.read_bytes()
                ).hexdigest()
            else:
                record["oos_returns_sha256"] = None

    comparable_oos_sharpe = record.get("comparable_oos_sharpe")
    if comparable_oos_sharpe is not None:
        try:
            comparable_oos_sharpe = float(comparable_oos_sharpe)
        except (TypeError, ValueError) as exc:
            raise ValueError("comparable_oos_sharpe must be a float or null") from exc
    record["comparable_oos_sharpe"] = comparable_oos_sharpe

    gate_issues = validate_for_gate(record)
    if gate_issues:
        raise ValueError(
            "Missing required gate provenance fields: " + ", ".join(gate_issues)
        )

    if "prev_hash" not in record or record["prev_hash"] is None:
        record["prev_hash"] = ""
    if not isinstance(record["prev_hash"], str):
        raise ValueError("prev_hash must be a string")

    if "record_hash" in record:
        record.pop("record_hash")

    previous_records = read_trials(path)
    if previous_records:
        previous_record = previous_records[-1]
        record["prev_hash"] = hashlib.sha256(
            _canonical_json(previous_record).encode("utf-8")
        ).hexdigest()
    else:
        record["prev_hash"] = ""

    record_hash_source = dict(record)
    record_hash_source.pop("record_hash", None)
    record["record_hash"] = _record_hash_for_obj(record_hash_source)
    return record


def _record_hash_for_test(record: dict[str, Any]) -> str:
    record_to_hash = dict(record)
    record_to_hash.pop("record_hash", None)
    return _record_hash_for_obj(record_to_hash)


def read_trials(path: str | Path | None = None) -> list[dict[str, Any]]:
    file_path = _resolve_path(path)
    if not file_path.exists():
        return []

    records: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive path
                raise ValueError(
                    f"Invalid JSON in {file_path} at line {line_number}: {exc}"
                ) from exc
            if not isinstance(payload, dict):
                raise ValueError(
                    f"Invalid trial record in {file_path} at line {line_number}: expected object"
                )
            records.append(payload)
    return records


def verify_chain(path: str | Path | None = None) -> None:
    file_path = _resolve_path(path)
    if not file_path.exists():
        raise ValueError(f"Trial registry does not exist: {file_path}")

    previous_record = None
    for index, record in enumerate(read_trials(file_path), start=1):
        _ensure_required_fields(record)
        if previous_record is None:
            expected_prev = ""
        else:
            expected_prev = hashlib.sha256(
                _canonical_json(previous_record).encode("utf-8")
            ).hexdigest()
        if record.get("prev_hash") != expected_prev:
            raise ValueError(f"Broken chain at record {index}: prev_hash mismatch")
        payload_for_hash = dict(record)
        payload_for_hash.pop("record_hash", None)
        computed_hash = _record_hash_for_obj(payload_for_hash)
        if record.get("record_hash") != computed_hash:
            raise ValueError(f"Broken chain at record {index}: record_hash mismatch")
        previous_record = record


def log_trial(path: str | Path | None = None, **fields: Any) -> str:
    file_path = _resolve_path(path)
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)

    if file_path.exists() and file_path.stat().st_size > 0:
        verify_chain(file_path)

    record = _normalize_record(fields, path=file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(_canonical_json(record) + "\n")
    return record["trial_id"]
