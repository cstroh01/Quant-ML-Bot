"""Disclosure text and provenance stamps (spec 038 D-1, FR-001, FR-002).

Owns the SCOPE-V1 §6 limitations register, the Rule 15 Sharpe status string and
the Rule 11 provenance stamp. Knows nothing about signals, fills, sizing or P&L.
Runs no Git and opens no socket; the commit comes from
`trial_registry.source_identity`, which reads `.git` metadata as files.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
import hashlib
from pathlib import Path

from trial_registry import relative_path, source_identity

# One entry per `docs/SCOPE-V1.md` §6 bullet, wording kept, Markdown emphasis
# and line wrapping removed. tests/test_038_register.py parses §6 and fails if
# the two disagree in either direction.
LIMITATIONS: tuple[str, ...] = (
    "Survivorship bias. Research uses a fixed 25-ETF universe chosen as of 2026 (spec 058). "
    "ETFs that have closed are absent. The 5-ticker mega-cap panel (AAPL/MSFT/GOOGL/NVDA/AMZN) "
    "remains a machinery smoke test, not evidence of generalizable alpha. No delisted names in either.",
    "Corporate-action data is free-tier and only partially reconciled. yfinance has documented "
    "split/dividend/100× pricing defects, and the only free second source covers one year of "
    "history, so older actions are unreconciled by construction and labelled as such.",
    "Dividend payment dates are a declared conservative bound, not observed data. No free source "
    "provides them historically. Dividend cash is credited no earlier than it could have arrived, "
    "so the ledger is never optimistic.",
    "No point-in-time fundamentals. Nothing knowable-on-date beyond price and volume.",
    "Daily bars only. No intraday, no microstructure, no order-book data.",
    "Costs are modeled, not calibrated. Rule 13's half-spread plus square-root impact is an "
    "estimate from daily OHLC, never validated against real fills.",
    "No real capital has ever been deployed, and none will be before §5 passes.",
)

# Rule 15: carried on the same line as every Sharpe until 033's DSR gate passes.
SHARPE_STATUS = "provisional, undeflated (Rule 15)"

# Trial line for a descriptive run that recorded no research attempt.
DESCRIPTIVE_TRIAL = "none (descriptive, not a trial)"


def _session_label(value: date) -> str:
    """A naive session label as YYYY-MM-DD; refuses aware or intraday values."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            raise ValueError("data_end is a session label and must be timezone-naive")
        if value.time() != datetime.min.time() or getattr(value, "nanosecond", 0):
            raise ValueError("data_end must be midnight-normalized")
        value = value.date()
    if not isinstance(value, date):
        raise TypeError("data_end must be a date")
    return value.isoformat()


def provenance_stamp(
    source: str | Path,
    *,
    root: str | Path,
    clock: Callable[[], datetime],
    trial_id: str | None = None,
    data_end: date | None = None,
    workspace_state: str = "unknown",
) -> list[str]:
    """Return the Rule 11 stamp as plain lines.

    Guarantees: the source is a file inside `root`, named by its repository-relative
    path and SHA-256; the commit is read fresh from `source_identity(root)` on every
    call, or `unknown` when none is readable; the trial line is the given id or
    `DESCRIPTIVE_TRIAL`; the run time is the injected clock's instant converted to
    UTC, and the data's last session is a separate line that may not postdate the
    run's UTC date. A naive clock is refused.
    """
    root = Path(root)
    path = Path(source) if Path(source).is_absolute() else root / source
    name = relative_path(root, path)
    if not path.is_file():
        raise FileNotFoundError(f"source artifact not found: {name}")
    if trial_id is not None and (not isinstance(trial_id, str) or not trial_id.strip()):
        raise ValueError("trial_id must be a non-empty string or None")
    run = clock()
    if not isinstance(run, datetime) or run.tzinfo is None or run.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    run = run.astimezone(timezone.utc)
    identity = source_identity(root, workspace_state=workspace_state)
    lines = [
        f"source: {name} sha256={hashlib.sha256(path.read_bytes()).hexdigest()}",
        f"commit: {identity['git_sha'] or 'unknown'}",
        f"workspace: {identity['workspace_state']}",
        f"trial: {trial_id if trial_id is not None else DESCRIPTIVE_TRIAL}",
        f"run (UTC): {run.date().isoformat()} {run.strftime('%H:%M:%S')}Z",
    ]
    if data_end is not None:
        label = _session_label(data_end)
        if label > run.date().isoformat():
            raise ValueError("data_end is after the run's UTC date")
        lines.append(f"data through (last session): {label}")
    return lines
