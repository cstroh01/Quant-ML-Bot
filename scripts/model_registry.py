"""Spec 053: model artifact manifests, champion/challenger records, promotion.

U1 guarantees: an artifact directory is written once (model bytes + manifest)
and never overwritten; the manifest names every identity field needed to
reproduce training; ``load_verified`` refuses unless the artifact bytes hash to
the manifest and every expected context field matches exactly. No order code,
no statistics computation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pickle

REQUIRED = ("algorithm", "algorithm_version", "seed", "training_cutoff", "feature_schema", "label",
            "dataset_sha256", "membership_sha256", "source_tree_hash", "dependencies")


class ManifestError(ValueError):
    """An artifact that must not be loaded or written."""


def write_artifact(directory, model, **context) -> dict:
    """Persist ``model`` and its manifest once; refuse missing context or overwrite."""
    directory = Path(directory)
    missing = [field for field in REQUIRED if field not in context]
    if missing:
        raise ManifestError(f"manifest context missing: {', '.join(missing)}")
    if (directory / "manifest.json").exists() or (directory / "model.pkl").exists():
        raise ManifestError(f"artifact already exists in {directory}; artifacts are immutable")
    directory.mkdir(parents=True, exist_ok=True)
    blob = pickle.dumps(model, protocol=5)
    (directory / "model.pkl").write_bytes(blob)
    manifest = {field: context[field] for field in REQUIRED}
    manifest["artifact_sha256"] = hashlib.sha256(blob).hexdigest()
    manifest["written_at_utc"] = datetime.now(timezone.utc).isoformat()
    (directory / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=1), encoding="utf-8")
    return manifest


def load_verified(directory, *, expected: dict):
    """Load a model only if its bytes and every expected context field match its manifest."""
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    blob = (directory / "model.pkl").read_bytes()
    if hashlib.sha256(blob).hexdigest() != manifest["artifact_sha256"]:
        raise ManifestError("artifact bytes do not match the manifest digest")
    for field in REQUIRED:
        if field in expected and expected[field] != manifest[field]:
            raise ManifestError(f"{field} drift: manifest {manifest[field]!r} != expected {expected[field]!r}")
    return pickle.loads(blob), manifest
