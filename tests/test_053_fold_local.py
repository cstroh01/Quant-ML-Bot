"""Spec 053 U2: fold-local fitting through purged/embargoed walk-forward splits.

Synthetic data only. EXAMPLE — NOT A RESULT.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

import context  # noqa: F401
from model_registry import fold_local_predictions


def panel(seed=3, n=760):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n)
    x1, x2 = rng.normal(size=n), rng.normal(size=n)
    y = (x1 + 0.5 * rng.normal(size=n) > 0).astype(int)
    return pd.DataFrame({"Date": dates, "x1": x1, "x2": x2, "y": y})


def run(frame):
    return fold_local_predictions(frame, ["x1", "x2"], "y", lambda: LogisticRegression(C=1.0),
                                  label_horizon=1, embargo_bars=2, initial_train_months=12, test_months=6)


def test_predictions_cover_only_test_windows_and_report_cv_settings():
    preds, meta = run(panel())
    assert meta["folds"] >= 2 and meta["purge"] == 1 and meta["embargo"] == 2
    assert preds.notna().sum() > 0 and preds.isna().sum() > 0  # initial training window is never predicted


def test_future_rows_never_change_an_earlier_folds_predictions():
    base, meta = run(panel())
    first_fold_rows = meta["test_rows"][0]
    shocked = panel()
    later = shocked.index > max(first_fold_rows)
    shocked.loc[later, ["x1", "x2"]] = shocked.loc[later, ["x1", "x2"]] * 1000 + 50
    after, _ = run(shocked)
    pd.testing.assert_series_equal(base.loc[first_fold_rows], after.loc[first_fold_rows])


def test_scaler_is_fit_inside_each_fold():
    frame = panel()
    _, meta = run(frame)
    first_train = meta["train_rows"][0]
    expected_mean = frame.loc[first_train, "x1"].mean()
    assert abs(meta["scaler_means"][0][0] - expected_mean) < 1e-12


def test_training_rows_are_purged_before_each_test_window():
    frame = panel()
    _, meta = run(frame)
    for train_rows, test_rows in zip(meta["train_rows"], meta["test_rows"]):
        # label_horizon=1: the last row before the test window would see into it and must be purged
        assert max(r for r in train_rows if r < min(test_rows)) <= min(test_rows) - 2
