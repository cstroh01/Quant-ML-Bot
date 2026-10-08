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


# --- U3: champion/challenger registry, promotion and rollback (FR-005/006/007) ---

from dataclasses import dataclass
from datetime import date
import re

_HEX64 = re.compile(r"[0-9a-f]{64}")
MIN_SHADOW_SESSIONS = 20


class PromotionError(ValueError):
    """A registry transition that must not happen."""


@dataclass(frozen=True)
class Evidence:
    gate3_pass: bool
    gate3_digest: str
    gate3_session: date
    oos_beats_baselines: bool
    shadow_sessions: int
    breaches: int


class Registry:
    """Append-only event log; the champion is derived, never edited in place."""

    def __init__(self, path):
        self.path = Path(path)

    def history(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _append(self, event: dict) -> None:
        events = self.history() + [event]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(events, indent=1, default=str), encoding="utf-8")

    def champion(self) -> str | None:
        stack: list[str] = []
        for event in self.history():
            if event["event"] in ("promote",) or (event["event"] == "register" and event["stage"] == "champion"):
                stack.append(event["model"])
            elif event["event"] == "rollback" and len(stack) > 1:
                stack.pop()
        return stack[-1] if stack else None

    def register(self, model: str, *, stage: str, approver: str | None = None, session: date | None = None) -> None:
        if stage not in ("challenger", "champion"):
            raise PromotionError(f"unknown stage {stage!r}")
        if stage == "champion" and approver != "Camden":
            raise PromotionError("only Camden may install a champion; retraining registers a challenger")
        self._append({"event": "register", "model": model, "stage": stage, "approver": approver, "session": session})

    def promote(self, model: str, evidence: Evidence, *, approver: str, session: date,
                max_evidence_age_sessions: int) -> None:
        """Champion := model, only on Camden's approval with complete, fresh, immutable evidence."""
        if approver != "Camden":
            raise PromotionError("only Camden promotes")
        if not evidence.gate3_pass:
            raise PromotionError("Gate 3 did not pass")
        if not _HEX64.fullmatch(evidence.gate3_digest):
            raise PromotionError("Gate 3 evidence digest missing")
        from data import trading_days
        if len(trading_days(evidence.gate3_session, session)) - 1 > max_evidence_age_sessions:
            raise PromotionError("Gate 3 evidence is stale")
        if not evidence.oos_beats_baselines:
            raise PromotionError("OOS net expectancy does not beat both baselines")
        if evidence.shadow_sessions < MIN_SHADOW_SESSIONS:
            raise PromotionError(f"shadow evaluation shorter than {MIN_SHADOW_SESSIONS} sessions")
        if evidence.breaches:
            raise PromotionError("risk or reconciliation breach during shadow evaluation")
        self._append({"event": "promote", "model": model, "approver": approver, "session": session,
                      "evidence": evidence.__dict__})

    def rollback(self, *, reason: str, session: date) -> None:
        if self.champion() is None:
            raise PromotionError("no champion to roll back")
        self._append({"event": "rollback", "reason": reason, "session": session})
