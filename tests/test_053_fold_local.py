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


class SpyModel(LogisticRegression):
    """LogisticRegression that records the rows each fit sees (via y's index, which the pipeline
    passes through unscaled)."""
    fits: list = []

    def fit(self, X, y, sample_weight=None):
        SpyModel.fits.append(list(y.index))
        return super().fit(X, y, sample_weight)


def test_model_is_fit_on_exactly_the_folds_training_rows():
    SpyModel.fits = []
    _, meta = fold_local_predictions(panel(), ["x1", "x2"], "y", SpyModel,
                                     label_horizon=1, embargo_bars=2, initial_train_months=12, test_months=6)
    assert len(SpyModel.fits) == meta["folds"]
    for fit_rows, train_rows, test_rows in zip(SpyModel.fits, meta["train_rows"], meta["test_rows"]):
        assert fit_rows == train_rows
        assert not set(fit_rows) & set(test_rows)
        assert max(fit_rows) < min(test_rows)


def test_each_embargo_gap_stays_out_of_every_later_folds_training():
    frame = panel()
    _, meta = run(frame)
    embargo = meta["embargo"]
    assert meta["folds"] >= 3, "need a fold that trains past an earlier gap"
    for k, test_rows in enumerate(meta["test_rows"]):
        gap = set(range(max(test_rows) + 1, max(test_rows) + 1 + embargo))
        after_gap = max(test_rows) + 1 + embargo
        for later in meta["train_rows"][k + 1:]:
            assert not gap & set(later)
            if max(later) > after_gap:
                assert after_gap in later  # gap is exactly `embargo` rows, not longer
