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
    """Load a model only if its bytes and every required context field match its manifest.

    ``expected`` must name every field in ``REQUIRED``; nothing is unpickled until all match.
    """
    directory = Path(directory)
    missing = [field for field in REQUIRED if field not in expected]
    if missing:
        raise ManifestError(f"expected context missing: {', '.join(missing)}; every field is verified")
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
    """Immutable promotion evidence, bound to one artifact, one configuration and one mode."""
    gate3_pass: bool
    gate3_digest: str
    gate3_session: date
    oos_beats_baselines: bool
    shadow_sessions: int
    breaches: int
    artifact_sha256: str
    config_sha256: str
    mode: str


MODES = ("PAPER", "LIVE")


class Registry:
    """Append-only event log for one mode; the champion is derived, never edited in place.

    A champion exists only through ``promote`` with bound, fresh evidence and Camden's approval.
    """

    def __init__(self, path, *, mode: str):
        if mode not in MODES:
            raise PromotionError(f"unknown mode {mode!r}")
        self.path = Path(path)
        self.mode = mode

    def history(self) -> list[dict]:
        if not self.path.exists():
            return []
        events = json.loads(self.path.read_text(encoding="utf-8"))
        foreign = {e.get("mode") for e in events} - {self.mode}
        if foreign:
            raise PromotionError(f"registry file holds events for mode {sorted(map(str, foreign))}, not {self.mode}")
        return events

    def _append(self, event: dict) -> None:
        events = self.history() + [event | {"mode": self.mode}]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(events, indent=1, default=str), encoding="utf-8")

    def _stack(self) -> list[str]:
        stack: list[str] = []
        for event in self.history():
            if event["event"] == "promote":
                stack.append(event["model"])
            elif event["event"] == "rollback":
                stack.pop()
        return stack

    def champion(self) -> str | None:
        stack = self._stack()
        return stack[-1] if stack else None

    def register(self, model: str, *, stage: str, artifact_sha256: str, config_sha256: str,
                 approver: str | None = None, session: date | None = None) -> None:
        """Record a challenger bound to its artifact and configuration digests."""
        if stage != "challenger":
            raise PromotionError("register records challengers only; a champion is installed by promote() "
                                 "with bound evidence")
        for name, digest in (("artifact", artifact_sha256), ("config", config_sha256)):
            if not _HEX64.fullmatch(str(digest)):
                raise PromotionError(f"{name} digest missing")
        if any(e["event"] == "register" and e["model"] == model for e in self.history()):
            raise PromotionError(f"model {model!r} already registered")
        self._append({"event": "register", "model": model, "stage": stage, "approver": approver,
                      "session": session, "artifact_sha256": artifact_sha256, "config_sha256": config_sha256})

    def promote(self, model: str, evidence: Evidence, *, approver: str, session: date,
                max_evidence_age_sessions: int) -> None:
        """Champion := model, only on Camden's approval with complete, fresh evidence bound to it."""
        if approver != "Camden":
            raise PromotionError("only Camden promotes")
        record = next((e for e in self.history() if e["event"] == "register" and e["model"] == model), None)
        if record is None:
            raise PromotionError(f"model {model!r} is not a registered challenger")
        if evidence.mode != self.mode:
            raise PromotionError(f"evidence mode {evidence.mode!r} does not match registry mode {self.mode!r}")
        if evidence.artifact_sha256 != record["artifact_sha256"]:
            raise PromotionError("evidence artifact digest does not match the registered artifact")
        if evidence.config_sha256 != record["config_sha256"]:
            raise PromotionError("evidence config digest does not match the registered configuration")
        if not evidence.gate3_pass:
            raise PromotionError("Gate 3 did not pass")
        if not _HEX64.fullmatch(str(evidence.gate3_digest)):
            raise PromotionError("Gate 3 evidence digest missing")
        if evidence.gate3_session > session:
            raise PromotionError("Gate 3 evidence is dated in the future")
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
        """Restore the previous champion; refuses when there is none to restore."""
        stack = self._stack()
        if not stack:
            raise PromotionError("no champion to roll back")
        if len(stack) < 2:
            raise PromotionError("no previous champion to restore")
        self._append({"event": "rollback", "reason": reason, "session": session})


# --- U2: fold-local fitting over purged/embargoed walk-forward splits (FR-002) ---


def fold_local_predictions(data, feature_cols, label_col, make_model, *, label_horizon: int, embargo_bars: int,
                           initial_train_months: int, test_months: int):
    """Out-of-fold predicted probabilities; scaler and model are fit on each fold's training rows only.

    Returns (predictions indexed like ``data`` with NaN outside test windows, metadata with fold
    count, purge, embargo, per-fold train/test row labels and scaler means).
    """
    import pandas as pd
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from walk_forward_cv import walk_forward_splits

    preds = pd.Series(float("nan"), index=data.index, name="p_up")
    meta = {"folds": 0, "purge": label_horizon, "embargo": embargo_bars,
            "train_rows": [], "test_rows": [], "scaler_means": []}
    for train_idx, test_idx in walk_forward_splits(data, initial_train_months, test_months,
                                                   label_horizon=label_horizon, embargo_bars=embargo_bars):
        train, test = data.iloc[train_idx], data.iloc[test_idx]
        pipeline = make_pipeline(StandardScaler(), make_model())
        pipeline.fit(train[feature_cols], train[label_col])
        preds.loc[test.index] = pipeline.predict_proba(test[feature_cols])[:, 1]
        meta["folds"] += 1
        meta["train_rows"].append(list(train.index))
        meta["test_rows"].append(list(test.index))
        meta["scaler_means"].append(list(pipeline[0].mean_))
    return preds, meta
