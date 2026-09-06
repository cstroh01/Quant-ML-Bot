"""Nested, leakage-safe hyperparameter tuning over walk-forward folds.

An outer fold hands a tuner its training positions. Those positions are
sorted but **not** contiguous: after spec 006, every earlier fold's embargo
gap leaves a hole inside them. The obvious inner split — slice the frame up
to the outer test window — silently re-admits exactly those embargoed rows,
and reports a slightly better score for whichever hyperparameter got away
with it most. That is a Rule 2 violation introduced by the tuner, on top of a
splitter that was just fixed.

So the inner splitter never slices the original frame. It builds a sub-frame
from the outer fold's own `train_indices`, runs the real
`walk_forward_splits` on it, and maps every yielded position back through
that array. A row that is not in `outer_train_indices` is not in the
sub-frame at all, so it cannot be selected on.

**Why holes do not weaken the purge**, which is a reviewer's first objection:
inside the sub-frame, adjacent rows can be more than one real bar apart
wherever a hole was removed. `walk_forward_splits` measures purge and embargo
in rows of the frame it is given, so `E` sub-frame rows span *at least* `E`
real bars — never fewer. Both err conservative across a hole: they over-purge
and over-cover, never under. That direction is the safe one, and it is why
reuse is sound rather than merely convenient.

Signal layer (Rule 8): imports `walk_forward_cv`, `estimators`, and
scikit-learn metrics only. No signal, no fill, no notion of what a prediction
means for a position. It is handed a frame and column names, not a target
kind to interpret.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, mean_squared_error

from estimators import (
    CLASSIFICATION,
    REGRESSION,
    TASKS,
    build_estimator,
    get_spec,
    param_grid_points,
)
from walk_forward_cv import (
    DEFAULT_INITIAL_TRAIN_MONTHS,
    DEFAULT_TEST_MONTHS,
    walk_forward_splits,
)

# Columns of the frame `tune_on_fold` returns as its third element. Named
# once so an empty result (zero inner folds) has the same shape as a
# populated one, and a caller can concatenate the two without a special case.
INNER_SCORE_COLUMNS = [
    "Grid_Point",
    "Params",
    "Inner_Fold",
    "Train_Rows",
    "Val_Rows",
    "Score",
]

# Columns of `nested_walk_forward`'s per-fold results frame.
FOLD_RESULT_COLUMNS = [
    "Fold",
    "Train_Rows",
    "Test_Rows",
    "Train_End",
    "Test_Start",
    "Params",
    "Tuned",
    "Inner_Folds",
    "Grid_Points",
    "Inner_Best_Score",
]


# --------------------------------------------------------------------------
# Phase 1 — the inner splitter.
#
# Everything from here down to `score_fold` is self-contained: it depends on
# `walk_forward_cv` only, and is the half of this spec that lands as `011a`
# if the diff needs splitting for reviewability (tasks.md, CLAUDE.md).
# --------------------------------------------------------------------------


def _check_strictly_increasing(outer_train_indices: np.ndarray) -> None:
    """Raise unless the position array is strictly increasing.

    The positional back-map (`outer_train_indices[inner_train]`) is only
    meaningful if sub-frame position `i` corresponds to real position
    `outer_train_indices[i]` *in the same chronological order*. An unsorted
    or duplicated array would still index without error and still return
    positions — just the wrong ones, silently — and the calendar-ordering
    assertion inside a fold loop would then be checking an order the data
    does not have.
    """
    if outer_train_indices.ndim != 1:
        raise ValueError(
            "outer_train_indices must be one-dimensional; got shape "
            f"{outer_train_indices.shape}"
        )
    if outer_train_indices.size > 1 and not np.all(np.diff(outer_train_indices) > 0):
        raise ValueError(
            "outer_train_indices must be strictly increasing (sorted, no "
            "duplicates); the positional back-map is unsound otherwise"
        )


def inner_splits_over(
    features: pd.DataFrame,
    outer_train_indices: np.ndarray,
    *,
    initial_train_months: int = DEFAULT_INITIAL_TRAIN_MONTHS,
    test_months: int = DEFAULT_TEST_MONTHS,
    label_horizon: int,
    embargo_bars: int,
    date_column: str = "Date",
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield inner train/validation positions drawn only from `outer_train_indices`.

    Every yielded position is a member of `outer_train_indices`. The purge
    and embargo are `walk_forward_splits`'s own — this function does not
    restate them, it re-runs them on a sub-frame built from the outer fold's
    legal training rows.

    Positions are positional row indices into `features`, matching what
    `walk_forward_splits` yields. `outer_train_indices` may contain internal
    gaps (it normally does, after the first couple of outer folds); this
    function does not reason about *why* a position is absent, only that it
    is.

    Validation is eager — the strictly-increasing check raises on the call,
    not on the first `next()` — so a caller that builds the array wrongly
    finds out at the call site rather than inside a loop body.

    Raises:
        ValueError: if `outer_train_indices` is not one-dimensional and
            strictly increasing, or for anything `walk_forward_splits`
            itself rejects.
    """
    positions = np.asarray(outer_train_indices)
    _check_strictly_increasing(positions)
    return _inner_splits(
        features,
        positions,
        initial_train_months=initial_train_months,
        test_months=test_months,
        label_horizon=label_horizon,
        embargo_bars=embargo_bars,
        date_column=date_column,
    )


def _inner_splits(
    features: pd.DataFrame,
    positions: np.ndarray,
    *,
    initial_train_months: int,
    test_months: int,
    label_horizon: int,
    embargo_bars: int,
    date_column: str,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """The generator half of `inner_splits_over`, split out so validation is eager."""
    if positions.size == 0:
        return

    # reset_index(drop=True) because walk_forward_splits reads the frame
    # positionally; the sub-frame's own index is never consulted again, and
    # results come back through `positions`, not through it.
    sub = features.iloc[positions].reset_index(drop=True)

    for inner_train, inner_val in walk_forward_splits(
        sub,
        initial_train_months,
        test_months,
        date_column,
        label_horizon=label_horizon,
        embargo_bars=embargo_bars,
    ):
        yield positions[inner_train], positions[inner_val]


# --------------------------------------------------------------------------
# Phase 2 — scoring and the tuning loop (`011b`, if split).
# --------------------------------------------------------------------------


def score_fold(y_true, y_pred, *, task: str) -> float:
    """Score one inner fold. **Lower is better, for both tasks.**

    The convention is decided here rather than left to the caller because a
    sign error is invisible: it selects the *worst* candidate on every fold
    and still reports a plausible-looking number. `tune_on_fold` takes the
    minimum, and this function is the only place the direction is set.

    - Classification: `log_loss`, with `labels=[0, 1]` passed **explicitly**.
      Without it, a fold whose labels happen to be all one class makes
      scikit-learn infer a single-class problem and silently reshape its
      expectations, and the score stops being comparable across folds.
      `y_pred` is P(class 1) — a probability, not a hard label.
    - Regression: mean squared error. `y_pred` is the predicted value.

    Raises:
        ValueError: for an unknown task.
    """
    if task == CLASSIFICATION:
        return float(log_loss(np.asarray(y_true), np.asarray(y_pred), labels=[0, 1]))
    if task == REGRESSION:
        return float(mean_squared_error(np.asarray(y_true), np.asarray(y_pred)))
    raise ValueError(f"unknown task {task!r}; valid tasks are {list(TASKS)}")


def _predict_for_scoring(model, X: pd.DataFrame, *, task: str) -> np.ndarray:
    """Predictions in the form `score_fold` expects for this task.

    For classification that is P(class 1), read out of `predict_proba` by
    locating class 1 in `model.classes_` rather than by assuming column 1.
    `predict_proba`'s columns are ordered by `classes_`, so column 1 is
    P(class 1) only when both classes were seen, in that order.

    A training fold containing a single class is the case that breaks the
    assumption, and the two registered classification families behave
    differently on it: `LogisticRegression` refuses to fit at all ("this
    solver needs samples of at least 2 classes"), while
    `HistGradientBoostingClassifier` fits with `classes_ == [0]` and still
    returns two columns — neither of which is P(class 1). Reading the class
    list gives 0 there, which is the true probability, and `log_loss`'s own
    clipping keeps the score finite rather than infinite.
    """
    if task != CLASSIFICATION:
        return np.asarray(model.predict(X), dtype=float)

    proba = np.asarray(model.predict_proba(X), dtype=float)
    classes = list(model.classes_)
    if 1 in classes:
        return proba[:, classes.index(1)]
    return np.zeros(len(X), dtype=float)


def tune_on_fold(
    features: pd.DataFrame,
    outer_train_indices: np.ndarray,
    *,
    name: str,
    task: str,
    feature_columns: list[str],
    label_column: str,
    label_horizon: int,
    embargo_bars: int,
    random_state: int,
    inner_initial_train_months: int = DEFAULT_INITIAL_TRAIN_MONTHS,
    inner_test_months: int = DEFAULT_TEST_MONTHS,
    date_column: str = "Date",
) -> tuple[dict[str, Any], bool, pd.DataFrame]:
    """Select hyperparameters using this outer fold's training data only.

    Returns `(best_params, tuned, inner_scores)`.

    `best_params` is the grid point with the lowest mean `score_fold` across
    the inner folds; ties go to the earlier grid point, and
    `param_grid_points` orders deterministically, so the choice reproduces
    across machines.

    `tuned` is `False` — and `best_params` is the registry's declared
    `default_params` — when this outer fold's training data supports no inner
    fold at all. That is an expected condition on early folds, not a broken
    configuration, so it does not raise. It is emphatically **not**
    `grid[0]`: falling back on whichever point sorts first would land on a
    configuration nothing declared, on exactly the folds where the fallback
    fires most.

    `inner_scores` has one row per (grid point, inner fold), for the record —
    empty, with the same columns, when nothing was tuned.

    Every row the outer fold excluded is excluded here too, because
    `inner_splits_over` never sees it (see the module docstring). Nothing in
    this function reads `features` outside `outer_train_indices`.

    Raises:
        ValueError: for an unregistered `(name, task)`, a non-increasing
            `outer_train_indices`, or an unknown task.
    """
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}; valid tasks are {list(TASKS)}")
    spec = get_spec(name, task=task)
    grid = param_grid_points(name, task=task)

    inner_folds = list(
        inner_splits_over(
            features,
            outer_train_indices,
            initial_train_months=inner_initial_train_months,
            test_months=inner_test_months,
            label_horizon=label_horizon,
            embargo_bars=embargo_bars,
            date_column=date_column,
        )
    )
    if not inner_folds:
        return (
            dict(spec.default_params),
            False,
            pd.DataFrame(columns=INNER_SCORE_COLUMNS),
        )

    rows: list[dict[str, Any]] = []
    mean_scores: list[float] = []

    # No short-circuit on a single-candidate grid: the loop runs identically
    # for one point and for eight, so the no-leak guarantee does not depend
    # on grid size, and a one-point grid still produces a scored record.
    for point_index, params in enumerate(grid):
        scores: list[float] = []
        for fold_number, (inner_train, inner_val) in enumerate(inner_folds, start=1):
            model = build_estimator(
                name, task=task, params=params, random_state=random_state
            )
            train_labels = features.iloc[inner_train][label_column]
            val_labels = features.iloc[inner_val][label_column]
            if task == CLASSIFICATION:
                train_labels = train_labels.astype(int)
                val_labels = val_labels.astype(int)

            model.fit(features.iloc[inner_train][feature_columns], train_labels)
            predicted = _predict_for_scoring(
                model, features.iloc[inner_val][feature_columns], task=task
            )
            score = score_fold(val_labels.to_numpy(), predicted, task=task)
            scores.append(score)
            rows.append(
                {
                    "Grid_Point": point_index,
                    "Params": dict(params),
                    "Inner_Fold": fold_number,
                    "Train_Rows": len(inner_train),
                    "Val_Rows": len(inner_val),
                    "Score": score,
                }
            )
        mean_scores.append(float(np.mean(scores)))

    best_index = int(np.argmin(mean_scores))
    inner_scores = pd.DataFrame(rows, columns=INNER_SCORE_COLUMNS)
    return dict(grid[best_index]), True, inner_scores


def nested_walk_forward(
    frame: pd.DataFrame,
    *,
    feature_columns: list[str],
    label_column: str,
    task: str,
    name: str,
    label_horizon: int,
    embargo_bars: int,
    random_state: int,
    initial_train_months: int | None = None,
    test_months: int | None = None,
    inner_initial_train_months: int = DEFAULT_INITIAL_TRAIN_MONTHS,
    inner_test_months: int = DEFAULT_TEST_MONTHS,
    date_column: str = "Date",
) -> tuple[pd.Series, np.ndarray, pd.DataFrame]:
    """Tune, fit, and predict one outer walk-forward fold at a time.

    Returns `(predictions, covered_positions, fold_results)`.

    For each outer fold: hyperparameters are selected on that fold's training
    positions only, a fresh estimator is fitted on those same positions with
    the selected parameters, and its test window is predicted. The outer test
    window is never seen by the tuner — that is the whole point of the nested
    structure, and it is what keeps the reported outer-fold score honest.

    `predictions` follows `task`'s dtype, matching
    `estimators.fit_predict_walk_forward`: `Int64` with `pd.NA` for
    classification, `float64` with `NaN` for regression. Rows before the
    first fold's test window are null — a real "no model yet" state, not a
    gap to fill.

    `covered_positions` is the concatenation of the outer folds' test
    indices, in fold order, with no position appearing twice.

    `fold_results` carries one row per outer fold: the fold number, the
    chosen parameters, the `tuned` flag, and the winning inner score. The
    flag is what makes the artifact honest — a reader can see which folds
    were actually tuned and which fell back to the declared default.

    Raises:
        ValueError: for an unknown task or an unregistered `(name, task)`.
        RuntimeError: if the frame supports no outer folds at all. An
            all-null series would read as "no signal yet" when the truth is
            "this configuration is broken" — the same distinction
            `fit_predict_walk_forward` draws.
    """
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}; valid tasks are {list(TASKS)}")
    get_spec(name, task=task)

    if task == CLASSIFICATION:
        predictions = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    else:
        predictions = pd.Series(np.nan, index=frame.index, dtype="float64")

    outer_kwargs: dict[str, Any] = {
        "label_horizon": label_horizon,
        "embargo_bars": embargo_bars,
        "date_column": date_column,
    }
    if initial_train_months is not None:
        outer_kwargs["initial_train_months"] = initial_train_months
    if test_months is not None:
        outer_kwargs["test_months"] = test_months

    grid_size = len(param_grid_points(name, task=task))
    covered: list[np.ndarray] = []
    fold_rows: list[dict[str, Any]] = []

    for fold, (train_indices, test_indices) in enumerate(
        walk_forward_splits(frame, **outer_kwargs), start=1
    ):
        train_dates = pd.to_datetime(frame.iloc[train_indices][date_column])
        test_dates = pd.to_datetime(frame.iloc[test_indices][date_column])
        assert (
            train_dates.max() < test_dates.min()
        ), f"Fold {fold} has test data at or before training data."

        params, tuned, inner_scores = tune_on_fold(
            frame,
            train_indices,
            name=name,
            task=task,
            feature_columns=feature_columns,
            label_column=label_column,
            label_horizon=label_horizon,
            embargo_bars=embargo_bars,
            random_state=random_state,
            inner_initial_train_months=inner_initial_train_months,
            inner_test_months=inner_test_months,
            date_column=date_column,
        )

        model = build_estimator(
            name, task=task, params=params, random_state=random_state
        )
        train_labels = frame.iloc[train_indices][label_column]
        if task == CLASSIFICATION:
            train_labels = train_labels.astype(int)
        model.fit(frame.iloc[train_indices][feature_columns], train_labels)
        predictions.iloc[test_indices] = model.predict(
            frame.iloc[test_indices][feature_columns]
        )

        covered.append(np.asarray(test_indices))
        if inner_scores.empty:
            inner_fold_count = 0
            best_score = float("nan")
        else:
            inner_fold_count = int(inner_scores["Inner_Fold"].max())
            best_score = float(
                inner_scores.groupby("Grid_Point")["Score"].mean().min()
            )
        fold_rows.append(
            {
                "Fold": fold,
                "Train_Rows": len(train_indices),
                "Test_Rows": len(test_indices),
                "Train_End": train_dates.max(),
                "Test_Start": test_dates.min(),
                "Params": params,
                "Tuned": tuned,
                "Inner_Folds": inner_fold_count,
                "Grid_Points": grid_size,
                "Inner_Best_Score": best_score,
            }
        )

    if not fold_rows:
        raise RuntimeError(
            "walk_forward_splits produced no folds; the frame is too short for "
            "the requested initial_train_months/test_months."
        )

    covered_positions = np.concatenate(covered)
    fold_results = pd.DataFrame(fold_rows, columns=FOLD_RESULT_COLUMNS)
    return predictions, covered_positions, fold_results
