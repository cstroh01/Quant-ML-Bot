"""Pure upper-biased historical-count arithmetic; inspection is a separate step."""
from __future__ import annotations
from datetime import datetime, timezone
import math
import json
from pathlib import Path
import uuid
from trial_registry import canonical_json, digest, immutable_write

FIELDS = set("campaign_id description evidence dimensions cartesian_upper_bound rerun_upper_bound remembered_range chosen_upper_bound unresolved_reason".split())
FORMULA = "max(previous_counts, 2 * next_power_of_two(sum(max(product(dimensions)*rerun_upper_bound, remembered_range.upper, chosen_upper_bound)))))"

def _count(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer bound")
    return value

def calculate_backfill(manifest: dict, *, previous_counts: list[int] = ()) -> dict:
    """Use full products, sum campaigns, round upward, double, never decrease."""
    bounds, unresolved, ids = [], [], set()
    campaigns = manifest.get("campaigns")
    if not isinstance(campaigns, list) or not campaigns: raise ValueError("campaigns required")
    for row in campaigns:
        for field in sorted(FIELDS):
            if field not in row: raise ValueError(f"missing {field}")
        if row["campaign_id"] in ids: raise ValueError("duplicate campaign_id")
        ids.add(row["campaign_id"])
        if not row["evidence"] or not row["description"]: raise ValueError("evidence and description required")
        dimensions = row["dimensions"]
        product = math.prod(_count(v, "dimension") for v in dimensions.values())
        if row["cartesian_upper_bound"] != product: raise ValueError("cartesian_upper_bound does not match full product")
        if row["unresolved_reason"] or row["rerun_upper_bound"] is None or row["chosen_upper_bound"] is None:
            unresolved.append(row["campaign_id"]); bounds.append(None); continue
        reruns = _count(row["rerun_upper_bound"], "rerun_upper_bound")
        remembered = row["remembered_range"]
        if remembered is not None:
            if len(remembered) != 2 or _count(remembered[0], "remembered_range") > _count(remembered[1], "remembered_range"): raise ValueError("remembered_range bounds")
        required = max(product * reruns, remembered[1] if remembered else 0)
        chosen = _count(row["chosen_upper_bound"], "chosen_upper_bound")
        if chosen < required: raise ValueError("chosen_upper_bound understates possible executions")
        bounds.append(chosen)
    approval = manifest.get("approval")
    approved = isinstance(approval, dict) and bool(approval.get("author")) and bool(approval.get("approved_at_utc"))
    if approved:
        when = datetime.fromisoformat(approval["approved_at_utc"])
        if when.tzinfo is None or when.utcoffset().total_seconds() != 0: raise ValueError("approval UTC required")
    subtotal = sum(b for b in bounds if b is not None)
    rounded = 1 << (subtotal - 1).bit_length() if subtotal else 0
    previous = [_count(n, "previous_count") for n in previous_counts]
    complete = not unresolved and approved
    return {"status": "complete" if complete else "incomplete", "formula": FORMULA, "campaign_bounds": bounds,
            "raw_upper_bound": subtotal if not unresolved else None, "bounded_subtotal": subtotal,
            "rounded_upper_bound": rounded if not unresolved else None,
            "n_backfill": max([2 * rounded, *previous]) if complete else None,
            "unresolved_campaigns": unresolved, "approval": approval, "manifest_hash": digest(manifest)}

def write_backfill(root: Path, manifest: dict, *, previous_counts: list[int] = ()) -> Path:
    """Publish approved evidence exclusively; callers cannot convert a draft into N."""
    prior = list(previous_counts)
    for path in (root / "docs/trials/backfill").glob("*.json"):
        if path.name == "manifest.json":
            continue
        artifact = json.loads(path.read_bytes())
        claimed = artifact.pop("sha256")
        if digest(artifact) != claimed or artifact.get("status") != "complete":
            raise ValueError(f"invalid previous backfill: {path.name}")
        prior.append(artifact["n_backfill"])
    result = calculate_backfill(manifest, previous_counts=prior)
    if result["status"] != "complete": raise ValueError("backfill incomplete; explicit human approval and finite bounds required")
    artifact = {**result, "manifest": manifest, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "backfill_id": str(uuid.uuid4())}
    artifact["sha256"] = digest(artifact)
    path = root / "docs/trials/backfill" / (artifact["backfill_id"] + ".json")
    immutable_write(path, canonical_json(artifact))
    return path
