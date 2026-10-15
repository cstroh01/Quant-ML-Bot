"""057 Q138: build the approved input bundle (closes.csv + sources.json) for a Fidelity preview/LIVE session.

Fetches the eight spec 059 sleeves' raw Alpaca SIP daily closes through `paper_loop.fetch_sleeve_closes`
(spec 056 adapter, D-9) and writes exactly two files into `--out`:
- closes.csv: naive midnight NYSE session labels, one column per sleeve, ending at the session before `--session`;
- sources.json: {"csv_sha256": <SHA-256 of closes.csv bytes>, "sources": [8 SourceManifests]}.
Refuses (nothing written) on a fetch failure, a missing or non-finite close, or a last label that is not the
NYSE session before `--session`. Market data only: no broker call, no credential beyond the Alpaca data keys
read from the environment by the adapter, no arming, no order. Keys never reach the files.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "scripts", ROOT / "exec"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import numpy as np  # noqa: E402

from paper_loop import fetch_sleeve_closes, previous_session  # noqa: E402
from signals import ALLOCATION_SLEEVES  # noqa: E402


class InputsRefused(RuntimeError):
    """The bundle would not pass the session's own pre-login checks; nothing was written."""


def _jsonable(manifest: dict) -> dict:
    row = dict(manifest)
    if isinstance(row.get("fetched_at"), datetime):
        row["fetched_at"] = row["fetched_at"].isoformat()
    return row


def build_bundle(out: Path, *, now: datetime, session: date, fetcher=None,
                 key_env: str = "APCA_API_KEY_ID", secret_env: str = "APCA_API_SECRET_KEY") -> dict:
    """Write closes.csv and sources.json for `session`; return {'csv_sha256', 'last_session', 'rows'}."""
    if now.utcoffset() is None:
        raise InputsRefused("now must be timezone-aware")
    try:
        closes, manifests = fetch_sleeve_closes(now, key_env=key_env, secret_env=secret_env, fetcher=fetcher)
    except Exception as exc:  # RunAborted or adapter refusal: name the class only, never the payload
        raise InputsRefused(f"sleeve closes refused ({type(exc).__name__})") from None
    closes = closes.astype(float)
    closes.index.name = "session"
    if list(closes.columns) != list(ALLOCATION_SLEEVES) or len(manifests) != len(ALLOCATION_SLEEVES):
        raise InputsRefused("exactly the eight spec 059 sleeves are required")
    if closes.empty or not np.isfinite(closes.to_numpy()).all() or (closes <= 0).any().any():
        raise InputsRefused("every sleeve needs a finite positive close on every session")
    want = previous_session(session)
    if closes.index[-1].date() != want:
        raise InputsRefused(f"last completed session is {closes.index[-1].date()}, the run on {session} needs {want}")
    if any(m.get("source") != "alpaca_sip_daily" for m in manifests):
        raise InputsRefused("every source must be alpaca_sip_daily")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    raw = closes.to_csv(lineterminator="\n").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    (out / "closes.csv").write_bytes(raw)
    (out / "sources.json").write_text(json.dumps({"csv_sha256": digest, "sources": [_jsonable(m) for m in manifests]},
                                                 sort_keys=True, indent=1), encoding="utf-8")
    return {"csv_sha256": digest, "last_session": str(want), "rows": len(closes)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--session", type=date.fromisoformat, required=True, help="NYSE session the bundle is for")
    a = p.parse_args(argv)
    try:
        summary = build_bundle(a.out, now=datetime.now(timezone.utc), session=a.session)
    except InputsRefused as exc:
        print(f"Inputs refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
