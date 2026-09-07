"""Which model families exist, how to build them, and one walk-forward loop.

This is the single place a model is declared. An entry carries its factory,
the grid a tuner may search (spec 011), and the parameters to fall back on
when tuning cannot run — all three together, because splitting them across
modules is how a "registry" stops being one on its first use.

`fit_predict_walk_forward` fits one estimator per fold and never once on the
whole frame (Rule 2). It is deliberately *untuned*: it always fits one fixed
parameter set. That makes it an equivalence checkpoint against
`logistic_baseline.walk_forward_predictions` before spec 011 adds tuning as a
second possible source of difference.

Signal layer (Rule 8): imports `walk_forward_cv` and scikit-learn only. No
signal, no fill, no notion of what a prediction means for a position.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from walk_forward_cv import walk_forward_splits

CLASSIFICATION = "classification"
REGRESSION = "regression"
TASKS = (CLASSIFICATION, REGRESSION)

# Deliberately coarse. One fit per grid point, per inner fold, per outer fold
# (spec 011) makes this multiplicative, and with this much selection noise a
# twelve-point grid is a lottery rather than a search. Revising these belongs
# with a real result, not with a guess.
MAX_GRID_POINTS = 8

# Step names for the pipeline a scaled entry is wrapped in. Named once so
# `final_estimator`, `fitted_scaler` and the tests all agree, and a reader
# grepping for "model" finds the definition rather than seven string
# literals.
SCALER_STEP = "scaler"
MODEL_STEP = "model"


@dataclass(frozen=True)
class EstimatorSpec:
    """One model family, for one task.

    `factory` takes `(params, random_state)` and returns an *unfitted*
    estimator — a fresh one is needed per fold, so the registry stores
    factories rather than instances.

    `default_params` is what spec 011 falls back to when an outer fold
    supports no inner folds. It is a member of this entry's own grid points
    (asserted by test), so the fallback lands on a configuration that is
    declared and exercised rather than on whichever point happens to sort
    first.

    `scale` declares whether this family needs its inputs standardized
    (spec 014). It is a property of the *family*, not of the caller: a
    penalized linear model shares one penalty across columns and so depends
    on their units, while a tree splits each column independently and cannot
    tell. Putting the flag here rather than at the call site is what keeps
    the three fit sites identical.
    """

    name: str
    task: str
    factory: Callable[[dict[str, Any], int], Any]
    param_grid: dict[str, list] = field(default_factory=dict)
    default_params: dict[str, Any] = field(default_factory=dict)
    scale: bool = False


def _logistic(params: dict[str, Any], random_state: int):
    # max_iter=1000 and the seed match logistic_baseline.py's construction
    # exactly. The equivalence test (spec 010 FR-006) depends on it, so this
    # line is pinned, not merely conventional.
    return LogisticRegression(max_iter=1000, random_state=random_state, **params)


def _ridge(params: dict[str, Any], random_state: int):
    return Ridge(random_state=random_state, **params)


def _hgb_classifier(params: dict[str, Any], random_state: int):
    return HistGradientBoostingClassifier(random_state=random_state, **params)


def _hgb_regressor(params: dict[str, Any], random_state: int):
    return HistGradientBoostingRegressor(random_state=random_state, **params)


ESTIMATOR_REGISTRY: dict[tuple[str, str], EstimatorSpec] = {
    ("logistic", CLASSIFICATION): EstimatorSpec(
        name="logistic",
        task=CLASSIFICATION,
        factory=_logistic,
        param_grid={"C": [0.01, 0.1, 1.0, 10.0]},
        # C=1.0 is scikit-learn's own default, which is what
        # logistic_baseline.py gets today by not passing C at all. Keeping it
        # as the fallback means an untuned fold reproduces the Phase 2 control
        # — with scale=False, which is what that control was measured under.
        default_params={"C": 1.0},
        scale=True,
    ),
    ("ridge", REGRESSION): EstimatorSpec(
        name="ridge",
        task=REGRESSION,
        factory=_ridge,
        param_grid={"alpha": [0.1, 1.0, 10.0, 100.0]},
        default_params={"alpha": 1.0},
        # The entry spec 014 was opened for. A single `alpha` penalizes every
        # coefficient equally, so without standardization the grid is really
        # searching "how much to penalize whichever column happens to be
        # largest".
        scale=True,
    ),
    ("hgb", CLASSIFICATION): EstimatorSpec(
        name="hgb",
        task=CLASSIFICATION,
        factory=_hgb_classifier,
        # Depth and leaf-count are the two knobs that matter most on a few
        # thousand daily bars; both are held small because the sample is
        # small. learning_rate is left at its default to keep the grid at 4.
        param_grid={"max_depth": [2, 3], "min_samples_leaf": [20, 50]},
        default_params={"max_depth": 3, "min_samples_leaf": 20},
        # No scaler on either tree entry. A split threshold is chosen per
        # column, so a monotone rescaling moves the threshold and nothing
        # else — the fitted tree is identical. Adding one would be a fit per
        # fold that provably cannot change a prediction.
        scale=False,
    ),
    ("hgb", REGRESSION): EstimatorSpec(
        name="hgb",
        task=REGRESSION,
        factory=_hgb_regressor,
        param_grid={"max_depth": [2, 3], "min_samples_leaf": [20, 50]},
        default_params={"max_depth": 3, "min_samples_leaf": 20},
        scale=False,
    ),
}


def _registered_pairs() -> list[tuple[str, str]]:
    return sorted(ESTIMATOR_REGISTRY)


def get_spec(name: str, *, task: str) -> EstimatorSpec:
    """Look up one registry entry, or raise naming what is registered.

    Raises:
        ValueError: if `(name, task)` is not registered. There is no default
            and never will be: silently substituting a model for the one a
            caller asked for produces a result attributed to the wrong thing.
    """
    try:
        return ESTIMATOR_REGISTRY[(name, task)]
    except KeyError:
        raise ValueError(
            f"no estimator registered for (name={name!r}, task={task!r}); "
            f"registered pairs are {_registered_pairs()}"
        ) from None


def param_grid_points(name: str, *, task: str) -> list[dict[str, Any]]:
    """Every complete parameter dict in this entry's grid.

    The Cartesian product, in a deterministic order (keys sorted, then
    `itertools.product`), so a tuner that reports "the third grid point won"
    means the same thing on every machine and every run.

    An entry with an empty grid yields exactly one point, `{}` — one
    configuration to try, not zero.
    """
    spec = get_spec(name, task=task)
    if not spec.param_grid:
        return [{}]

    keys = sorted(spec.param_grid)
    points = [
        dict(zip(keys, values))
        for values in itertools.product(*(spec.param_grid[key] for key in keys))
    ]
    if len(points) > MAX_GRID_POINTS:
        raise ValueError(
            f"grid for (name={name!r}, task={task!r}) has {len(points)} points, "
            f"above the cap of {MAX_GRID_POINTS}; see spec 010 FR-004"
        )
    return points


def build_estimator(
    name: str,
    *,
    task: str,
    params: dict[str, Any] | None,
    random_state: int,
    scale: bool | None = None,
):
    """Build one unfitted estimator, standardized if its entry says so.

    `params=None` means this entry's `default_params` — **not** an empty
    dict. The distinction matters: an empty dict silently accepts
    scikit-learn's defaults, which are not necessarily the ones this registry
    declares and tests.

    `random_state` is keyword-only with no default and is forwarded
    unconditionally, including to estimators for which it is inert
    (`LogisticRegression` with the default solver, `Ridge` with
    `solver="auto"`). Forwarding it always is what keeps a future registry
    entry from being stochastic by accident (Conventions → Determinism).

    `scale=None` means this entry's declared `scale`; `True` or `False`
    overrides it. The override exists for one purpose: the spec 010
    equivalence tests pin this loop against
    `logistic_baseline.walk_forward_predictions`, which standardizes nothing,
    and they now say `scale=False` rather than depending on the registry
    never changing. A caller who wants the registry's answer passes nothing.

    When scaling applies, the return is a `Pipeline` of `StandardScaler` then
    the estimator, under the step names `"scaler"` and `"model"`. Params are
    applied to the estimator *before* wrapping, so grids stay `{"alpha": ...}`
    rather than `{"model__alpha": ...}` — a registry entry describes its model,
    not the plumbing around it (Rule 2 is served by the wrapping, not by the
    naming). Because every fit site fits per fold, the scaler's mean and
    variance are computed on that fold's training rows alone.
    """
    spec = get_spec(name, task=task)
    effective = dict(spec.default_params if params is None else params)
    estimator = spec.factory(effective, random_state)

    if not (spec.scale if scale is None else scale):
        return estimator
    return Pipeline([(SCALER_STEP, StandardScaler()), (MODEL_STEP, estimator)])


def final_estimator(model):
    """The model itself, whether or not `build_estimator` wrapped it.

    `build_estimator` returns a bare estimator for an unscaled entry and a
    two-step `Pipeline` for a scaled one, so anything reading a fitted
    attribute — `coef_`, `alpha`, `classes_` — needs to know which it holds.
    Answering that here means callers do not each grow their own
    `named_steps["model"] if isinstance(...)` branch, and a later change to
    the pipeline's shape has one place to update.
    """
    if isinstance(model, Pipeline):
        return model.named_steps[MODEL_STEP]
    return model


def fitted_scaler(model):
    """The fitted `StandardScaler`, or `None` if this model has no scaler.

    `None` is the honest answer for an unscaled entry rather than an error:
    "this family does not standardize" is a normal configuration, not a
    caller mistake.
    """
    if isinstance(model, Pipeline):
        return model.named_steps.get(SCALER_STEP)
    return None


def fit_predict_walk_forward(
    frame: pd.DataFrame,
    *,
    feature_columns: list[str],
    label_column: str,
    task: str,
    name: str,
    label_horizon: int,
    embargo_bars: int,
    random_state: int,
    params: dict[str, Any] | None = None,
    initial_train_months: int | None = None,
    test_months: int | None = None,
    scale: bool | None = None,
) -> pd.Series:
    """One out-of-sample prediction per row, from purged, embargoed folds.

    Fits a fresh estimator per fold on that fold's training rows only and
    predicts its test window — never once on the whole frame, which is the
    lookahead Rule 2 exists to prevent. `scale` is forwarded to
    `build_estimator`; because the fit is per fold, so is the standardization,
    and a test window never contributes to the mean and variance used to
    transform it.

    The returned series' dtype follows `task`: `Int64` with `pd.NA` for
    classification, `float64` with `NaN` for regression. Rows before the
    first fold's test window are null in both cases. That is a real "no model
    yet" state, not a gap to fill — the same semantics spec 005 established.

    Raises:
        ValueError: for an unregistered `(name, task)`.
        RuntimeError: if the frame supports no folds at all. An all-null
            series would read as "no signal yet" when the truth is "this
            configuration is broken."
    """
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}; valid tasks are {list(TASKS)}")
    # Validate the pair up front, so a frame too short to produce folds
    # reports the unregistered name rather than the fold count.
    get_spec(name, task=task)

    if task == CLASSIFICATION:
        predictions = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    else:
        predictions = pd.Series(np.nan, index=frame.index, dtype="float64")

    split_kwargs: dict[str, Any] = {
        "label_horizon": label_horizon,
        "embargo_bars": embargo_bars,
    }
    if initial_train_months is not None:
        split_kwargs["initial_train_months"] = initial_train_months
    if test_months is not None:
        split_kwargs["test_months"] = test_months

    folds = 0
    for fold, (train_indices, test_indices) in enumerate(
        walk_forward_splits(frame, **split_kwargs), start=1
    ):
        folds += 1
        train_dates = pd.to_datetime(frame.iloc[train_indices]["Date"])
        test_dates = pd.to_datetime(frame.iloc[test_indices]["Date"])
        assert (
            train_dates.max() < test_dates.min()
        ), f"Fold {fold} has test data at or before training data."

        model = build_estimator(
            name, task=task, params=params, random_state=random_state, scale=scale
        )
        train_labels = frame.iloc[train_indices][label_column]
        if task == CLASSIFICATION:
            train_labels = train_labels.astype(int)
        model.fit(frame.iloc[train_indices][feature_columns], train_labels)
        predictions.iloc[test_indices] = model.predict(
            frame.iloc[test_indices][feature_columns]
        )

    if folds == 0:
        raise RuntimeError(
            "walk_forward_splits produced no folds; the frame is too short for "
            "the requested initial_train_months/test_months."
        )
    return predictions
