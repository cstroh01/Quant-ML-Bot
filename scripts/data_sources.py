"""Spec 056: free-source manifests, publication permissions and cross-source checks.

U1 guarantees: a manifest cannot be built without an aware fetch instant, a
completed-session label (YYYY-MM-DD), an explicit adjustment basis, a SHA-256
and a credential-free endpoint; a source's permission for one output class
never implies another, and an unverified permission (None) always refuses.
No network: fetchers live elsewhere and take injected clients.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from urllib.parse import parse_qsl, urlsplit

ADJUSTMENTS = frozenset({"raw", "adjusted"})
OUTPUT_CLASSES = ("private_research", "public_raw", "public_derived")
_SECRET_KEYS = re.compile(r"(key|token|secret|password|signature|auth)", re.I)
_DIGEST = re.compile(r"[0-9a-f]{64}")


class ManifestError(ValueError):
    """A manifest or permission request that must be refused."""


def _credential_free(url: str) -> bool:
    parts = urlsplit(url)
    if parts.username or parts.password:
        return False
    return not any(_SECRET_KEYS.search(k) for k, _ in parse_qsl(parts.query, keep_blank_values=True))


@dataclass(frozen=True)
class SourceManifest:
    source: str
    endpoint: str
    fetched_at: datetime
    completed_session: str
    adjustment: str
    row_count: int
    sha256: str
    contract_version: str

    def __post_init__(self) -> None:
        if not _credential_free(self.endpoint):
            raise ManifestError("endpoint carries a credential; strip it before recording")
        if self.fetched_at.tzinfo is None:
            raise ManifestError("fetched_at must be timezone-aware")
        try:
            date.fromisoformat(self.completed_session)
        except ValueError as error:
            raise ManifestError("completed_session must be a YYYY-MM-DD session label") from error
        if self.adjustment not in ADJUSTMENTS:
            raise ManifestError(f"adjustment must be one of {sorted(ADJUSTMENTS)}")
        if not (isinstance(self.row_count, int) and self.row_count >= 0):
            raise ManifestError("row_count must be a non-negative integer")
        if not _DIGEST.fullmatch(self.sha256):
            raise ManifestError("sha256 must be a hex digest")


@dataclass(frozen=True)
class SourceContract:
    source: str
    verified_on: str
    private_research: bool | None
    public_raw: bool | None
    public_derived: bool | None


def may_publish(contract: SourceContract, output_class: str) -> bool:
    """True only if this exact output class was verified as permitted."""
    if output_class not in OUTPUT_CLASSES:
        raise ManifestError(f"unknown output class {output_class!r}")
    return getattr(contract, output_class) is True


# --- U2: cross-source close checks (FR-004); U3: EDGAR facts as of their filed date (FR-005) ---

import pandas as pd


def close_mismatches(primary: pd.Series, check: pd.Series, *, tolerance_bps: float) -> pd.DataFrame:
    """Sessions where two independent closes disagree beyond tolerance or one is missing.

    Mismatches are reported for exclusion or disclosure; values are never averaged.
    """
    frame = pd.concat({"primary": primary, "check": check}, axis=1)
    missing = frame["primary"].isna() | frame["check"].isna()
    diff_bps = (frame["check"] / frame["primary"] - 1).abs() * 1e4
    return frame[missing | (diff_bps > tolerance_bps)]


def facts_as_of(facts: list[dict], as_of: date) -> list[dict]:
    """For each period end, the latest fact filed on or before ``as_of`` (original until restated)."""
    best: dict[str, dict] = {}
    for item in facts:
        if not item.get("filed"):
            raise ValueError("every EDGAR fact needs its filed date")
        if date.fromisoformat(item["filed"]) > as_of:
            continue
        current = best.get(item["end"])
        if current is None or item["filed"] > current["filed"]:
            best[item["end"]] = item
    return [best[end] for end in sorted(best)]
