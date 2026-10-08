"""Spec 052 U4: causal membership and fold-local cross-sectional statistics. EXAMPLE — NOT A RESULT."""
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

import context  # noqa: F401
from asset_registry import Fact, Registry, causal_membership, fold_local_cross_section

UTC = timezone.utc


def test_membership_per_session_uses_that_sessions_snapshot():
    reg = Registry([
        Fact("A", "listed", "NYSE", date(2020, 1, 2), datetime(2020, 1, 2, 21, tzinfo=UTC), "s"),
        Fact("B", "listed", "NYSE", date(2020, 1, 6), datetime(2020, 1, 6, 21, tzinfo=UTC), "s"),
        Fact("A", "delisted", "merged", date(2020, 1, 7), datetime(2020, 1, 7, 21, tzinfo=UTC), "s"),
    ])
    out = causal_membership(reg, [date(2020, 1, 3), date(2020, 1, 6), date(2020, 1, 7)])
    assert out == {date(2020, 1, 3): {"A"}, date(2020, 1, 6): {"A", "B"}, date(2020, 1, 7): {"B"}}


def test_cross_sectional_stats_come_from_training_rows_only():
    frame = pd.DataFrame({"f": np.arange(10.0)}, index=pd.RangeIndex(10))
    train = list(range(6))
    shocked = frame.copy()
    shocked.loc[6:, "f"] = 1e6
    a, params_a = fold_local_cross_section(frame, "f", train)
    b, params_b = fold_local_cross_section(shocked, "f", train)
    assert params_a == params_b
    pd.testing.assert_series_equal(a.loc[train], b.loc[train])
    assert abs(params_a["mean"] - 2.5) < 1e-12
