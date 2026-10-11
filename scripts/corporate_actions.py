"""Cross-source dividend reconciliation for the unadjusted cache (spec 035 U1).

Pure: no I/O, no network, no credentials, no file reads. It labels dividends
and never changes a price, date or amount (plan, Rules 1/5 table). Splits are
not re-matched here; their status comes from spec 044 FR-006 unchanged.
"""
from __future__ import annotations

import pandas as pd

# Spec 035 §8 D-2 (Camden, 2026-10-09): absolute $0.0001 per share at the
# declared per-share basis, because declarations are given to 4 decimals.
DIVIDEND_AMOUNT_TOLERANCE = 0.0001
DIVIDEND_AMOUNT_BASIS = "per_share"
# Float slack so a difference of exactly one tolerance step (one $0.0001 tick)
# is inside for every amount, not just those whose binary difference rounds down.
_FLOAT_SLACK = 1e-12

RECONCILED, UNRECONCILED, MISMATCH = "reconciled", "unreconciled", "mismatch"
OUTSIDE_COVERAGE = "outside second-source coverage"
RESULT_COLUMNS = [
    "Date", "Primary_Value", "Second_Value",
    "Reconciliation_Status", "Reconciliation_Reason",
]


def _dividends(actions: pd.DataFrame, source: str) -> dict:
    """Map each dividend ex-date (naive session label) to (amount, stated basis)."""
    rows = actions.loc[actions["Action_Type"].eq("dividend")]
    dates = pd.to_datetime(rows["Date"])
    if dates.dt.tz is not None:
        raise ValueError(f"{source} dividend dates must be naive session labels")
    dates = dates.dt.normalize()
    if dates.duplicated().any():
        raise ValueError(f"{source} has duplicate dividend ex-dates")
    bases = rows["Amount_Basis"] if "Amount_Basis" in rows else [None] * len(rows)
    return {
        date: (float("nan") if pd.isna(value) else float(value),
               None if pd.isna(basis) else basis)
        for date, value, basis in zip(dates, rows["Value"], bases)
    }


def _lookup(table: dict, date: pd.Timestamp):
    """Exact session-label match only: one session apart is a different date."""
    return table.get(date)


def _covered(date: pd.Timestamp, coverage) -> bool:
    return coverage is not None and coverage[0] <= date <= coverage[1]


def reconcile_dividends(
    primary: pd.DataFrame,
    second: pd.DataFrame,
    coverage: tuple | None,
    *,
    amount_tolerance: float,
    amount_basis: str,
) -> pd.DataFrame:
    """Return exactly one status row per dividend ex-date in either source.

    The sweep is over the union of both sources' ex-dates (M5). ``coverage``
    is an inclusive ``(start, end)`` pair of session labels, or ``None`` when
    the second source covers nothing. Outside it a dividend is
    ``unreconciled`` (M3). Inside it, ex-dates match exactly by session label
    (one session apart is ``mismatch``, M4), a one-sided dividend is
    ``mismatch``, a row whose amount basis is not stated as ``amount_basis``
    is ``unreconciled`` with that reason, and amounts further apart than
    ``amount_tolerance`` (inclusive) or missing are ``mismatch``. Inputs are never mutated.
    """
    if coverage is not None:
        coverage = tuple(pd.Timestamp(edge).normalize() for edge in coverage)
        if any(edge.tz is not None for edge in coverage):
            raise ValueError("coverage must be naive session labels")
    first = _dividends(primary, "primary")
    other = _dividends(second, "second source")
    rows = []
    for date in sorted(first.keys() | other.keys()):
        mine, theirs = _lookup(first, date), _lookup(other, date)
        status, reason = MISMATCH, None
        if not _covered(date, coverage):
            status, reason = UNRECONCILED, OUTSIDE_COVERAGE
        elif mine is None or theirs is None:
            reason = "second source only" if mine is None else "primary only"
        elif mine[1] != amount_basis or theirs[1] != amount_basis:
            status = UNRECONCILED
            reason = f"amount basis not stated as {amount_basis}"
        elif not abs(mine[0] - theirs[0]) <= amount_tolerance + _FLOAT_SLACK:  # NaN fails
            reason = "amount outside tolerance"
        else:
            status = RECONCILED
        rows.append({
            "Date": date,
            "Primary_Value": None if mine is None else mine[0],
            "Second_Value": None if theirs is None else theirs[0],
            "Reconciliation_Status": status,
            "Reconciliation_Reason": reason,
        })
    result = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    # Keep None (not NaN) as the reconciled rows' reason, even when all are reconciled.
    result["Reconciliation_Reason"] = pd.Series(
        [row["Reconciliation_Reason"] for row in rows], dtype=object)
    return result


def assert_no_mismatch(statuses: pd.DataFrame) -> None:
    """Raise ``ValueError`` naming every mismatched ex-date; return otherwise."""
    bad = statuses.loc[statuses["Reconciliation_Status"].eq(MISMATCH), "Date"]
    if len(bad):
        named = ", ".join(pd.Timestamp(d).strftime("%Y-%m-%d") for d in bad)
        raise ValueError(f"dividend reconciliation failed: mismatch on {named}")
