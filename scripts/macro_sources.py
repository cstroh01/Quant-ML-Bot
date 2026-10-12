"""Spec 060 FR-003: point-in-time joins of macro and rates data onto session labels.

Pure: no I/O, no network, no credentials. Fetching stays in ``scripts/data_sources.py``
(``AlfredSeries`` for ALFRED; the Treasury adapter waits on spec 060 T001's verification).

Rule 1 for each join: the value placed on session ``d`` was public at ``d``'s decision time.
- ALFRED: ALFRED records availability by date, not moment, and some series post after the
  close (WALCL, Thursdays 16:30 ET). So session ``d`` sees the vintages current at the end of
  the previous calendar day: ``realtime_start <= d - 1 <= realtime_end``. This is stricter
  than spec 060 FR-003's "vintage start <= d"; Rule 1 governs the conflict.
- Rates with a publication instant: usable on ``d`` only if published at or before
  ``DECISION_TIME`` America/New_York on ``d``. Session labels stay naive; they are localized
  to New York explicitly here, at the boundary with the instant (CLAUDE.md, Timestamps).
"""
from __future__ import annotations

from datetime import time

import pandas as pd

NY = "America/New_York"
DECISION_TIME = time(16, 0)  # the NYSE close: signals are formed at the close, filled next open


def _sessions(sessions) -> list[pd.Timestamp]:
    labels = [pd.Timestamp(s) for s in sessions]
    if any(label.tz is not None for label in labels):
        raise ValueError("sessions must be naive session labels")
    return [label.normalize() for label in labels]


def alfred_asof(frame: pd.DataFrame, sessions) -> pd.Series:
    """Value of the newest observation known before each session, as then published.

    ``frame`` has the ``AlfredSeries.fetch`` columns ``date``, ``realtime_start``,
    ``realtime_end`` and ``value``. On session ``d`` the visible rows are those with
    ``date <= d - 1`` and ``realtime_start <= d - 1 <= realtime_end`` (calendar days) and a
    non-missing value; the newest observation date wins, and among its vintages the latest
    ``realtime_start``. A session with nothing visible gets NaN. The result is indexed by ``sessions`` in the
    given order; ``frame`` is not mutated.
    """
    starts = pd.to_datetime(frame["realtime_start"])
    ends = pd.to_datetime(frame["realtime_end"].map(
        lambda v: pd.Timestamp.max.normalize() if str(v) == "9999-12-31" else v))
    view = pd.DataFrame({"date": pd.to_datetime(frame["date"]), "realtime_start": starts,
                         "realtime_end": ends, "value": frame["value"]})
    out = {}
    for day in _sessions(sessions):
        known_by = day - pd.Timedelta(days=1)
        known = view.loc[(view["realtime_start"] <= known_by) & (view["realtime_end"] >= known_by)
                         & (view["date"] <= known_by) & view["value"].notna()]
        newest = known.sort_values(["date", "realtime_start"]).tail(1)
        out[day] = float(newest["value"].iloc[0]) if len(newest) else float("nan")
    return pd.Series(out, dtype=float)


def published_asof(frame: pd.DataFrame, sessions, columns: list[str]) -> pd.DataFrame:
    """``columns`` of the newest record public at each session's decision time.

    ``frame`` has ``date`` (the record's session label), ``published_at`` (a timezone-aware
    instant) and the value ``columns``. On session ``d`` the visible rows are those with
    ``date <= d`` and ``published_at`` at or before ``DECISION_TIME`` New York on ``d``; the
    newest record date wins, and among its versions the latest publication (a revision
    replaces a value only once published). A session with nothing visible gets NaN. Indexed
    by ``sessions`` in the given order; ``frame`` is not mutated.
    """
    published = pd.Series([pd.Timestamp(t) for t in frame["published_at"]], index=frame.index)
    if any(t.tz is None for t in published):
        raise ValueError("published_at must be timezone-aware instants")
    view = frame[["date", *columns]].assign(
        date=pd.to_datetime(frame["date"]), published_utc=[t.tz_convert("UTC") for t in published])
    rows = {}
    for day in _sessions(sessions):
        cutoff = pd.Timestamp.combine(day.date(), DECISION_TIME).tz_localize(NY).tz_convert("UTC")
        known = view.loc[(view["date"] <= day) & (view["published_utc"] <= cutoff)]
        newest = known.sort_values(["date", "published_utc"]).tail(1)
        rows[day] = (newest[columns].iloc[0] if len(newest)
                     else pd.Series(float("nan"), index=columns))
    return pd.DataFrame.from_dict(rows, orient="index", columns=columns).astype(float)
