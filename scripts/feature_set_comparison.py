"""Does the scale-free feature set actually predict better? A paired test.

`feature_diagnostics.py` shows the design matrix is better conditioned. That
is a property of the *matrix*. It is not evidence that any prediction
improved, and spec 014 does not get to claim one from the other — a
well-conditioned matrix of useless features is still useless.

So this script runs the real nested walk-forward for every registry entry
under both feature sets and tests the two prediction series against each
other. Spec 014 FR-012 makes running it a merge requirement, not an option.

**Why paired tests.** The two feature sets are evaluated on the same bars,
under the same splits, with the same seed. The only thing that differs is
the feature matrix. A paired test removes the period effect — which
dominates any comparison of two walk-forward runs, because both are mostly
measuring what the market did — and asks only about the within-bar
difference. An unpaired comparison of two accuracy numbers throws that away
and is why "0.519 vs 0.524" reads as noise.

- **Classification** (`logistic`, `hgb`) — McNemar's test on the paired
  correct/incorrect outcomes. The bars both sets get right and the bars both
  get wrong carry no information about which set is better; McNemar
  correctly conditions on the discordant pairs alone.
- **Regression** (`ridge`, `hgb`) — Wilcoxon signed-rank on the paired
  per-bar squared-error differences. Signed-rank rather than a paired
  t-test because squared-error differences on daily returns are heavily
  right-skewed, and a t-test on them is a test about a handful of large
  days.

**The bar, and what it is not.** `p < 0.10` one-sided on at least one of the
four entries is what spec 014 means by "shows real improvement, not just
better conditioning". That is a *screening* threshold: cheap evidence,
sized for four comparisons on a single ticker, chosen to catch a real effect
rather than to certify one. It is emphatically **not** the project's
capital-readiness bar, which is the deflated Sharpe ratio and comes later.
Nothing this script prints justifies allocating capital.

All four p-values are reported whatever they say. A null result merges: the
conditioning fix stands on its own, and "well-conditioned features did not
move the prediction" is a finding worth recording rather than burying.

**Spec 015 — why this runs in parallel now.** The eight runs above are four
registry entries times two feature sets, and serially they took two to three
hours on one ticker, which blocked spec 013's five. They are also completely
independent: each builds its own feature frame from a read-only price frame,
tunes and fits inside its own nested walk-forward with an explicit seed, and
never reads anything another run wrote. So they are farmed out to
`concurrent.futures.ProcessPoolExecutor` — standard library, no new
dependency (Rule 6).

The non-obvious half is that the parallelism does not work without pinning
each worker to a single compute thread. `HistGradientBoosting` parallelizes
over every core it can see, and a worker cannot see its siblings; eight
workers each claiming sixteen threads runs *slower* than the serial loop it
replaced.

Pinning them is harder than it looks, and the obvious way does not work. See
`_pinned_thread_environment` — the variables have to be set in *this* process
before a worker is spawned, because by the time an `initializer=` callback
runs in the child, the child has already imported NumPy and OpenMP has
already sized its pool.

None of this is allowed to change a number. `pair_results` and both
comparison functions are shared verbatim between the parallel and
synchronous paths, results are collated in `sorted(ESTIMATOR_REGISTRY)` order
rather than completion order, and `tests/test_feature_set_comparison.py`
asserts the two paths agree bit for bit — on the prediction series, on every
statistic, and on this module's printed report character for character.

Rule 8: a diagnostic entry point over the signal and model layers. It
imports `data`, `features`, `estimators` and `model_cv`, and knows nothing
of fills, positions, or P&L — no metric here is a return.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import dataclasses
import json
import math
import os
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from statsmodels.stats.contingency_tables import mcnemar

from data import download_market_data
from estimators import CLASSIFICATION, ESTIMATOR_REGISTRY, REGRESSION
from features import build_features, feature_columns
from model_cv import nested_walk_forward

TICKER = "AAPL"
PERIOD = "10y"

# The cached download is the five-ticker universe (spec 013's
# `TICKER_UNIVERSE`), so the whole list is requested and `TICKER` selected out
# of it. Asking for `[TICKER]` alone would miss that cache file — the key is
# the sorted ticker list — and trigger a network call this lane cannot make.
CACHE_TICKERS = ["AAPL", "AMZN", "GOOGL", "MSFT", "NVDA"]

LABEL_HORIZON = 1
EMBARGO_BARS = 1
RANDOM_STATE = 42

# The project's walk-forward defaults, restated here so the printed report
# carries them. A metric without its fold geometry is not reportable
# (CLAUDE.md, *Pull request requirements* item 3).
INITIAL_TRAIN_MONTHS = 6
TEST_MONTHS = 1
INNER_INITIAL_TRAIN_MONTHS = 6
INNER_TEST_MONTHS = 1

# The screening threshold. See the module docstring for what it is not.
ALPHA = 0.10

# Which target each task is compared on. `direction` is the up/down label the
# Phase 2 control used; `return` is the forward log return spec 009 added.
TARGET_KIND = {CLASSIFICATION: "direction", REGRESSION: "return"}

FEATURE_SET_A = "levels"
FEATURE_SET_B = "scale_free"


def _predictions_by_date(
    prices: pd.DataFrame,
    *,
    name: str,
    task: str,
    feature_set: str,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.Series, pd.Series, int]:
    """Run the nested walk-forward once and index its output by date.

    Returns `(predictions, labels, outer_folds)`, both series indexed by
    `Date` and restricted to the rows the walk-forward actually covered.

    `random_state` is an explicit parameter rather than a read of the module
    constant (spec 015 FR-004). Once this function runs inside a spawned
    worker process, "the seed the parent was using" is not a thing the child
    can inherit — the seed has to travel with the work unit or the run is
    not reproducible. It defaults to `RANDOM_STATE` so every existing caller
    keeps the seed it already had.

    Indexing by date rather than by position is what makes the two feature
    sets comparable at all: they have different warm-up lengths, so row 40 of
    one is not row 40 of the other. Aligning on the timestamp compares the
    same trading day to itself, which is the whole premise of a paired test.
    """
    frame, task_out, horizon = build_features(
        prices,
        target_kind=TARGET_KIND[task],
        label_horizon=LABEL_HORIZON,
        feature_set=feature_set,
    )
    assert task_out == task, f"expected task {task!r}, got {task_out!r}"

    predictions, covered, fold_results = nested_walk_forward(
        frame,
        feature_columns=feature_columns(feature_set),
        label_column="Label",
        task=task,
        name=name,
        label_horizon=horizon,
        embargo_bars=EMBARGO_BARS,
        random_state=random_state,
        initial_train_months=INITIAL_TRAIN_MONTHS,
        test_months=TEST_MONTHS,
        inner_initial_train_months=INNER_INITIAL_TRAIN_MONTHS,
        inner_test_months=INNER_TEST_MONTHS,
    )

    dates = pd.to_datetime(frame["Date"])
    covered_index = np.sort(np.asarray(covered))
    predicted = pd.Series(
        predictions.iloc[covered_index].to_numpy(),
        index=pd.Index(dates.iloc[covered_index], name="Date"),
    )
    labels = pd.Series(
        frame["Label"].iloc[covered_index].to_numpy(),
        index=pd.Index(dates.iloc[covered_index], name="Date"),
    )
    return predicted, labels, len(fold_results)


# --------------------------------------------------------------------------
# Spec 015 — the parallel work unit, and the process-level thread pinning it
# needs to be worth anything.
# --------------------------------------------------------------------------

# The five environment variables that bound a worker to one thread. Named once
# so `_worker_init` and the test that checks it cannot drift apart.
THREAD_LIMIT_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


@dataclasses.dataclass(frozen=True)
class ComparisonTask:
    """One unit of parallel work: one estimator entry under one feature set.

    Frozen because it is a key as well as a payload — the collation step
    indexes results by `(name, task, feature_set)` and a mutable task would
    let a worker change its own address.

    `random_state` rides along rather than being read from module scope in
    the child. Under `spawn` the child re-imports this module, so a module
    constant would in fact be *there* — but it would be there by coincidence
    of import, not because the caller asked for it, and a caller that wanted
    a different seed would silently get 42. Carrying the seed in the work
    unit is what makes the seed a fact about the job (FR-004).
    """

    name: str
    task: str
    feature_set: str
    random_state: int


@contextlib.contextmanager
def _pinned_thread_environment():
    """Set the thread limits in *this* process, restoring them on exit.

    This is the half of the pinning that actually works, and it is worth
    being precise about why the other half does not.

    Spec 015's Design Constraint 2 prescribes pinning via
    `ProcessPoolExecutor(initializer=_worker_init)`, on the reasoning that
    the initializer runs before any submitted work. It does. But that is not
    the deadline that matters. Under `spawn` the child is a fresh
    interpreter which, in the course of unpickling the callables it was
    handed, imports this module — and therefore NumPy, SciPy and
    scikit-learn — *before* the initializer body runs. OpenMP and OpenBLAS
    size their thread pools at that import. By the time `_worker_init`
    assigns `OMP_NUM_THREADS=1`, the pools exist and the variable is read by
    no one.

    Measured on this machine, 16 logical cores, inside a pooled worker:

        with initializer only:  OMP_NUM_THREADS=1, openmp reports 16 threads
        no initializer at all:  OMP_NUM_THREADS unset, sklearn uses 8

    So the prescribed mechanism did not merely fail to pin — it doubled the
    thread count. scikit-learn's `_openmp_effective_n_threads` applies a
    physical-core heuristic (8 of the 16) when `OMP_NUM_THREADS` is unset,
    and defers to `omp_get_max_threads()` (16) once it is set. Setting the
    variable too late reads to scikit-learn as "the user configured this
    deliberately", and it stops second-guessing a number OpenMP had already
    fixed.

    The deadline is therefore before the child's interpreter starts, not
    before its first task — which means the variables must be set here, in
    the parent, and inherited. A spawned child receives a copy of this
    process's environment block at creation, so a variable set before the
    pool is built is present in the child from its very first import.
    `ProcessPoolExecutor` creates workers lazily as work is submitted, so
    this stays in force for the whole lifetime of the pool rather than just
    its construction.

    Restoring on exit matters because this mutates process-global state that
    outlives the pool. Leaving `OMP_NUM_THREADS=1` set would silently
    single-thread everything the caller did afterwards — including, in the
    test suite, every test that happened to run next. The distinction
    between "was set to something else" and "was not set at all" is
    preserved, because those are different states to `_openmp_effective_n_threads`
    and, per the measurement above, produce different thread counts.

    Uses only `os` and `contextlib` — standard library, no new dependency
    (FR-008 / Rule 6).
    """
    saved = {name: os.environ.get(name) for name in THREAD_LIMIT_VARS}
    try:
        for name in THREAD_LIMIT_VARS:
            os.environ[name] = "1"
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _worker_init() -> None:
    """Pin this worker process to a single compute thread.

    Passed as `ProcessPoolExecutor(initializer=...)`, per FR-002 and the
    spec's Design Constraint 2, and retained because it is genuinely the
    belt to `_pinned_thread_environment`'s braces: it guarantees the
    variables are set in the child whatever the start method, including a
    `fork` child that inherited a parent whose environment had since been
    restored.

    It is *not*, on its own, sufficient to pin anything — read
    `_pinned_thread_environment` for the measurement and the reason. Do not
    delete that context manager on the grounds that this function looks like
    it already does the job. It looks like it and it does not, which is the
    entire trap.
    """
    import os

    for variable in THREAD_LIMIT_VARS:
        os.environ[variable] = "1"


def _evaluate_feature_set_task(
    prices: pd.DataFrame, task_spec: ComparisonTask
) -> tuple[str, str, str, pd.Series, pd.Series, int]:
    """Run one `ComparisonTask` and return its result tagged with its identity.

    A module-level function, taking only picklable arguments and returning
    only picklable values, because that is what `spawn` requires (FR-003).
    A closure over `prices`, or a lambda, or a bound method of a local
    object, pickles on Linux's `fork` and raises `PicklingError` on Windows
    — a portability failure that would not show up in a POSIX CI run.

    The identity is returned *with* the result rather than tracked by the
    caller against the future, so collation cannot mis-attribute a result to
    the wrong estimator if completion order is scrambled — which it always
    is. The tuple is self-describing; the caller does not have to remember
    what it asked for.
    """
    predicted, labels, outer_folds = _predictions_by_date(
        prices,
        name=task_spec.name,
        task=task_spec.task,
        feature_set=task_spec.feature_set,
        random_state=task_spec.random_state,
    )
    return (
        task_spec.name,
        task_spec.task,
        task_spec.feature_set,
        predicted,
        labels,
        outer_folds,
    )


def compare_classification(
    labels: pd.Series, predicted_a: pd.Series, predicted_b: pd.Series
) -> dict:
    """McNemar's test on paired correct/incorrect outcomes.

    `exact=True` uses the binomial test rather than the chi-square
    approximation. That is the right default here because the discordant
    count can be small, and the approximation is unreliable exactly there.

    statsmodels reports a two-sided p-value. Under the exact symmetric
    binomial the one-sided p is half of it in the favoured direction, so the
    one-sided figure is derived rather than re-implemented — and reported
    beside the two-sided one so a reader can see both.
    """
    truth = labels.astype(int).to_numpy()
    correct_a = predicted_a.astype(int).to_numpy() == truth
    correct_b = predicted_b.astype(int).to_numpy() == truth

    # b_wins: A wrong, B right. a_wins: A right, B wrong. These two cells are
    # the entire evidence; the concordant cells cancel.
    b_wins = int(np.sum(~correct_a & correct_b))
    a_wins = int(np.sum(correct_a & ~correct_b))
    table = [
        [int(np.sum(correct_a & correct_b)), a_wins],
        [b_wins, int(np.sum(~correct_a & ~correct_b))],
    ]

    if a_wins + b_wins == 0:
        # Identical predictions everywhere. No test is possible and none is
        # needed: the answer is "no difference", stated rather than computed.
        return {
            "test": "mcnemar (exact)",
            "n": len(truth),
            "discordant": 0,
            "statistic": float("nan"),
            "p_two_sided": 1.0,
            "p_one_sided": 1.0,
            "accuracy_a": float(np.mean(correct_a)),
            "accuracy_b": float(np.mean(correct_b)),
            "favours_b": False,
            "note": "identical predictions; no discordant pairs",
        }

    result = mcnemar(table, exact=True)
    two_sided = float(result.pvalue)
    favours_b = b_wins > a_wins
    one_sided = two_sided / 2.0 if favours_b else 1.0 - two_sided / 2.0

    return {
        "test": "mcnemar (exact)",
        "n": len(truth),
        "discordant": a_wins + b_wins,
        "statistic": float(result.statistic),
        "p_two_sided": two_sided,
        "p_one_sided": float(min(1.0, one_sided)),
        "accuracy_a": float(np.mean(correct_a)),
        "accuracy_b": float(np.mean(correct_b)),
        "favours_b": bool(favours_b),
        "note": "",
    }


def compare_regression(
    labels: pd.Series, predicted_a: pd.Series, predicted_b: pd.Series
) -> dict:
    """Wilcoxon signed-rank on paired per-bar squared-error differences.

    The paired quantity is `se_b - se_a`, so `alternative="less"` is the
    one-sided test that B has the smaller error — stated directly to scipy
    rather than derived from a two-sided p-value.

    `zero_method="wilcox"` discards exactly-tied pairs, which is the
    standard treatment and the conservative one: a bar where both feature
    sets erred identically is evidence for neither.
    """
    truth = labels.to_numpy(dtype=float)
    error_a = (predicted_a.to_numpy(dtype=float) - truth) ** 2
    error_b = (predicted_b.to_numpy(dtype=float) - truth) ** 2
    difference = error_b - error_a

    if not np.any(difference != 0.0):
        return {
            "test": "wilcoxon signed-rank",
            "n": len(truth),
            "discordant": 0,
            "statistic": float("nan"),
            "p_two_sided": 1.0,
            "p_one_sided": 1.0,
            "mse_a": float(np.mean(error_a)),
            "mse_b": float(np.mean(error_b)),
            "favours_b": False,
            "note": "identical squared errors; nothing to rank",
        }

    one_sided = wilcoxon(difference, alternative="less", zero_method="wilcox")
    two_sided = wilcoxon(difference, alternative="two-sided", zero_method="wilcox")

    return {
        "test": "wilcoxon signed-rank",
        "n": len(truth),
        "discordant": int(np.sum(difference != 0.0)),
        "statistic": float(one_sided.statistic),
        "p_two_sided": float(two_sided.pvalue),
        "p_one_sided": float(one_sided.pvalue),
        "mse_a": float(np.mean(error_a)),
        "mse_b": float(np.mean(error_b)),
        "favours_b": bool(np.mean(error_b) < np.mean(error_a)),
        "note": "",
    }


def pair_results(
    *,
    name: str,
    task: str,
    result_a: tuple[pd.Series, pd.Series, int],
    result_b: tuple[pd.Series, pd.Series, int],
) -> dict:
    """Pair one entry's two feature-set runs and test them against each other.

    Takes the two `_predictions_by_date` outputs rather than computing them,
    which is what lets the serial and parallel paths share this code
    verbatim. That sharing is not tidiness — it is the mechanism behind
    FR-005. If the pairing, intersection, and test selection were written
    twice, "bit-for-bit identical" would be a claim about two
    implementations agreeing, and the equivalence test would be checking
    that claim forever. Written once, the only thing parallelism can change
    is *where* the two prediction series were computed, and predictions are
    a pure function of `(prices, name, task, feature_set, random_state)`.
    """
    predicted_a, labels_a, folds_a = result_a
    predicted_b, labels_b, folds_b = result_b

    # Restrict to the dates both runs covered. The warm-up lengths differ, so
    # the two coverage sets are not identical and pairing requires the
    # intersection — taking either run's own index would silently compare a
    # bar to nothing.
    shared = predicted_a.index.intersection(predicted_b.index)
    shared = shared.sort_values()

    labels = labels_a.loc[shared]
    pd.testing.assert_series_equal(
        labels, labels_b.loc[shared], check_names=False, check_dtype=False
    )

    if task == CLASSIFICATION:
        result = compare_classification(
            labels, predicted_a.loc[shared], predicted_b.loc[shared]
        )
    else:
        result = compare_regression(
            labels, predicted_a.loc[shared], predicted_b.loc[shared]
        )

    result.update(
        {
            "name": name,
            "task": task,
            "shared_bars": len(shared),
            "outer_folds_a": folds_a,
            "outer_folds_b": folds_b,
        }
    )
    return result


def compare_entry(
    prices: pd.DataFrame,
    *,
    name: str,
    task: str,
    random_state: int = RANDOM_STATE,
) -> dict:
    """Run one registry entry under both feature sets and test the pair.

    The single-entry, single-process path. `compare_all_entries_parallel`
    does not call it — it schedules the two halves independently — but it
    remains the reference definition of what one paired comparison *is*, and
    the tests use it to pin the parallel path against something that never
    spawns anything.
    """
    return pair_results(
        name=name,
        task=task,
        result_a=_predictions_by_date(
            prices,
            name=name,
            task=task,
            feature_set=FEATURE_SET_A,
            random_state=random_state,
        ),
        result_b=_predictions_by_date(
            prices,
            name=name,
            task=task,
            feature_set=FEATURE_SET_B,
            random_state=random_state,
        ),
    )


def build_tasks(random_state: int = RANDOM_STATE) -> list[ComparisonTask]:
    """Every work unit for one full comparison, in deterministic order.

    Four registry entries times two feature sets is eight units. The order is
    `sorted(ESTIMATOR_REGISTRY)` outermost so that the synchronous path walks
    the entries in the same order the old serial loop did, which keeps its
    progress output readable against the previous run's log.

    Order is a convenience here and nothing more: the collation step re-sorts,
    so a scheduler that returns these in any order at all produces the same
    report (FR-006).
    """
    return [
        ComparisonTask(
            name=name, task=task, feature_set=feature_set, random_state=random_state
        )
        for name, task in sorted(ESTIMATOR_REGISTRY)
        for feature_set in (FEATURE_SET_A, FEATURE_SET_B)
    ]


def _default_worker_count(task_count: int) -> int | None:
    """How many workers `max_workers=None` should mean.

    `None` means "all available logical cores" (FR-007), but never more
    workers than there is work: eight units on a sixteen-core machine wants
    eight processes, not sixteen. The extra eight would each pay a full
    interpreter startup and a full copy of the price frame in order to sit
    idle. This caps rather than expands, so it cannot cause the
    oversubscription the thread pinning exists to prevent.

    Returns `None` when the core count is unavailable, handing the decision
    back to `ProcessPoolExecutor`'s own default.
    """
    cores = os.cpu_count()
    if not cores:
        return None
    return max(1, min(cores, task_count))


def compare_all_entries_parallel(
    prices: pd.DataFrame,
    *,
    max_workers: int | None = None,
    random_state: int = RANDOM_STATE,
    on_pair: Callable[[list[dict]], None] | None = None,
    verbose: bool = False,
) -> list[dict]:
    """Run all eight work units, pair them, and return the four comparisons.

    Returns the results ordered by `(name, task)` over
    `sorted(ESTIMATOR_REGISTRY)` — the order `format_report` prints and the
    order the serial loop produced — regardless of which process finished
    first (FR-006).

    `max_workers=None` uses one worker per available core, capped at the eight
    units of work. `max_workers=1` does not create a pool at all: it runs the
    units synchronously in this process, in this thread, so an exception
    arrives as its own traceback through the actual call stack instead of a
    pickled copy re-raised across a process boundary (FR-007, User Story 3).
    That is the path to debug a model failure on.

    `on_pair`, if given, is called each time an entry's *second* feature set
    lands, with the list of completed comparisons so far in report order. That
    is what lets `main` keep the spec 014 checkpointing behaviour: this run is
    long, and a crash in the eighth unit should not discard the first seven.
    Note the granularity — a pair, not a unit. Half a comparison is not a
    result, and writing one would put a record in the checkpoint that no
    reader could interpret.

    Why parallelism is safe here at all: the eight units share nothing. Each
    rebuilds its own feature frame from a read-only price frame, runs its own
    nested walk-forward with an explicit seed, and touches no global state —
    no RNG, no cache, no accumulator between them. Rule 1 is untouched for the
    same reason: a unit cannot see another unit's data, let alone another
    bar's future, and the purge and embargo are computed inside
    `nested_walk_forward` exactly as before. The only thing the schedule can
    change is completion order, and collation sorts that away.

    Raises:
        ValueError: for `max_workers` below 1.
        RuntimeError: if a worker fails, naming the work unit that failed and
            chaining the original exception.
    """
    if max_workers is not None and max_workers < 1:
        raise ValueError(f"max_workers must be >= 1 or None, got {max_workers!r}")

    tasks = build_tasks(random_state=random_state)
    units: dict[tuple[str, str, str], tuple[pd.Series, pd.Series, int]] = {}
    pairs: dict[tuple[str, str], dict] = {}

    def record(payload: tuple[str, str, str, pd.Series, pd.Series, int]) -> None:
        name, task, feature_set, predicted, labels, folds = payload
        units[(name, task, feature_set)] = (predicted, labels, folds)
        if verbose:
            print(f"  unit done: {name}/{task} [{feature_set}]", flush=True)

        key_a = (name, task, FEATURE_SET_A)
        key_b = (name, task, FEATURE_SET_B)
        if key_a not in units or key_b not in units:
            return

        pairs[(name, task)] = pair_results(
            name=name, task=task, result_a=units[key_a], result_b=units[key_b]
        )
        if verbose:
            print(
                f"  paired {name}/{task}: "
                f"p(one-sided)={pairs[(name, task)]['p_one_sided']:.4f}",
                flush=True,
            )
        if on_pair is not None:
            on_pair([pairs[key] for key in sorted(ESTIMATOR_REGISTRY) if key in pairs])

    if max_workers == 1:
        # The synchronous path. No pool, no pickling, no child interpreter —
        # the same calls the serial loop made, on this stack.
        for task_spec in tasks:
            if verbose:
                print(
                    f"running {task_spec.name}/{task_spec.task} "
                    f"[{task_spec.feature_set}] ...",
                    flush=True,
                )
            record(_evaluate_feature_set_task(prices, task_spec))
    else:
        workers = (
            _default_worker_count(len(tasks)) if max_workers is None else max_workers
        )
        # `_pinned_thread_environment` must wrap the *whole* pool lifetime,
        # not just its construction: workers are spawned lazily as work is
        # submitted, and each one inherits the environment as it exists at
        # the moment it is created.
        with _pinned_thread_environment(), concurrent.futures.ProcessPoolExecutor(
            max_workers=workers, initializer=_worker_init
        ) as executor:
            futures = {
                executor.submit(_evaluate_feature_set_task, prices, task_spec): task_spec
                for task_spec in tasks
            }
            for future in concurrent.futures.as_completed(futures):
                task_spec = futures[future]
                try:
                    payload = future.result()
                except Exception as error:
                    # `concurrent.futures` re-raises the child's exception
                    # carrying the child's traceback, which says which *line*
                    # failed and nothing about which of eight
                    # identical-looking jobs was on it. The identity is only
                    # known here, so it is attached here. `raise ... from
                    # error` keeps the original as `__cause__`; nothing is
                    # swallowed.
                    raise RuntimeError(
                        f"worker failed on {task_spec.name}/{task_spec.task} "
                        f"[{task_spec.feature_set}], seed "
                        f"{task_spec.random_state}: {error}"
                    ) from error
                record(payload)
        # Leaving the `with` block shuts the pool down and joins every child
        # before this function returns, so no worker outlives the call
        # (SC-004). It is also why the failure path above raises inside the
        # block rather than collecting errors and raising after it: the
        # context manager still tears the pool down on the way out.

    missing = [key for key in sorted(ESTIMATOR_REGISTRY) if key not in pairs]
    if missing:
        raise RuntimeError(f"no comparison produced for {missing}")

    return [pairs[key] for key in sorted(ESTIMATOR_REGISTRY)]


def compare_all_entries(
    prices: pd.DataFrame,
    *,
    max_workers: int | None = None,
    random_state: int = RANDOM_STATE,
    on_pair: Callable[[list[dict]], None] | None = None,
    verbose: bool = False,
) -> list[dict]:
    """The spec's FR-007 name for `compare_all_entries_parallel`.

    Spec 015 names this function two ways — FR-007 says `compare_all_entries`,
    task T004 says `compare_all_entries_parallel` — and both names are load
    bearing in the document, so both exist. This is a thin delegation, not a
    second implementation: there is one orchestrator, and the alias cannot
    drift from it.
    """
    return compare_all_entries_parallel(
        prices,
        max_workers=max_workers,
        random_state=random_state,
        on_pair=on_pair,
        verbose=verbose,
    )


def format_report(results: list[dict]) -> str:
    """A printable report: the fold geometry, the four rows, and the verdict."""
    lines: list[str] = []
    lines.append(f"{TICKER} feature-set comparison over {PERIOD}")
    lines.append(f"  {FEATURE_SET_A!r} (control) vs {FEATURE_SET_B!r} (spec 014)")
    lines.append("")
    lines.append("Fold geometry — required beside any reported metric:")
    lines.append(
        f"  outer: initial_train_months={INITIAL_TRAIN_MONTHS}, "
        f"test_months={TEST_MONTHS}"
    )
    lines.append(
        f"  inner: initial_train_months={INNER_INITIAL_TRAIN_MONTHS}, "
        f"test_months={INNER_TEST_MONTHS}"
    )
    lines.append(
        f"  purge = label_horizon = {LABEL_HORIZON} bar(s); "
        f"embargo = {EMBARGO_BARS} bar(s)"
    )
    lines.append(
        "  commission and slippage: not applicable — nothing here is a "
        "backtest; these are prediction-quality tests only."
    )
    lines.append(f"  seed: {RANDOM_STATE}")
    lines.append("")

    for result in results:
        lines.append(f"--- {result['name']} / {result['task']} ---")
        lines.append(
            f"  outer folds: {result['outer_folds_a']} ({FEATURE_SET_A}) / "
            f"{result['outer_folds_b']} ({FEATURE_SET_B}); "
            f"paired bars: {result['shared_bars']}"
        )
        if result["task"] == CLASSIFICATION:
            lines.append(
                f"  accuracy: {result['accuracy_a']:.4f} -> "
                f"{result['accuracy_b']:.4f}"
            )
            lines.append(f"  discordant pairs: {result['discordant']}")
        else:
            lines.append(
                f"  MSE: {result['mse_a']:.8f} -> {result['mse_b']:.8f}"
            )
            lines.append(f"  non-tied pairs: {result['discordant']}")
        lines.append(f"  test: {result['test']}")
        lines.append(
            f"  p (two-sided): {result['p_two_sided']:.4f}"
            f"   p (one-sided, {FEATURE_SET_B} better): "
            f"{result['p_one_sided']:.4f}"
        )
        if result["note"]:
            lines.append(f"  note: {result['note']}")
        lines.append("")

    passing = [r for r in results if r["p_one_sided"] < ALPHA]
    lines.append("=== verdict ===")
    lines.append(
        f"Screening bar: p < {ALPHA:.2f} one-sided on at least one entry."
    )
    if passing:
        which = ", ".join(f"{r['name']}/{r['task']}" for r in passing)
        lines.append(f"MET, on: {which}")
    else:
        lines.append(
            "NOT MET. The conditioning fix stands on its own and spec 014 "
            "still merges, but nothing here is evidence about the model."
        )
    lines.append("")
    lines.append(
        "This is a screening threshold on one ticker, not a capital-readiness "
        "bar. That is the deflated Sharpe step, and it is not this."
    )
    return "\n".join(lines)


CHECKPOINT_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "cache" / "feature_set_comparison.json"
)


def _json_safe(value):
    """Replace non-finite floats with `None` so the output is valid JSON.

    `json.dumps` emits a bare `NaN` token for `float("nan")`, which Python's
    own `json.load` accepts and every other JSON reader rejects. Both
    comparison functions put `float("nan")` in `statistic` on their
    no-discordant-pairs branch, so a perfectly ordinary run produces a file
    that only Python can read. `null` is the JSON spelling of "no value",
    which is what that statistic is.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _checkpoint(results: list[dict]) -> None:
    """Write completed entries to `data/cache/` after each one, atomically.

    Called through `compare_all_entries_parallel`'s `on_pair` hook, once per
    *completed pair*. Under parallel execution the pairs finish out of order,
    but the hook is handed them already sorted into report order, so a
    checkpoint written mid-run is a prefix of the final file rather than a
    scrambled subset of it — and never contains a half-finished comparison,
    which is not a result and could not be read as one.

    This run is long and prints only at the end. An exception in the
    fourth entry used to discard the first three, which is a bad trade for
    two lines of code. The file is regenerable output under `data/cache/`,
    so it is gitignored like everything else there.

    The write goes to a sibling temporary file and is moved into place with
    `os.replace`, which is atomic on both POSIX and Windows for a same
    directory rename. Writing in place would truncate the previous
    checkpoint first, so a process killed part-way through the write would
    destroy the completed entries the checkpoint exists to protect. A reader
    either sees the whole previous checkpoint or the whole new one, never a
    half-written file.

    This is a reboot-shaped failure, and one reached this script: the
    2026-09-06 run died to a restart rather than an exception. It happened
    to land inside the first entry, before any checkpoint was owed, so
    nothing was lost to a torn write that time. The window is real anyway —
    the run writes four times over several hours — and closing it costs a
    rename.
    """
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CHECKPOINT_PATH.with_suffix(".json.tmp")

    # Serialise before opening anything. A payload that cannot be encoded
    # must not have already truncated a good checkpoint.
    payload = json.dumps(_json_safe(results), indent=2)

    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, CHECKPOINT_PATH)
    except BaseException:
        # The half-written temporary is the casualty; the real checkpoint
        # was never opened and still holds the last complete set of entries.
        temporary.unlink(missing_ok=True)
        raise


def load_prices() -> pd.DataFrame:
    """The single ticker this comparison runs on, sorted and re-indexed.

    Split out of `main` so the parallel path can be measured against the real
    cached dataset (T011) without going through the report printer.
    """
    market_data = download_market_data(CACHE_TICKERS, period=PERIOD)
    prices = market_data[market_data["Ticker"] == TICKER].copy()
    return prices.sort_values("Date").reset_index(drop=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line. `--workers` defaults to `None` (all cores).

    Parsing lives here rather than inside `main` on purpose. `main` is
    importable, and a `main()` that reached for `sys.argv` itself would parse
    the *test runner's* arguments when a test called it — `python -m unittest
    discover -s tests` would hand it `discover` and `-s`. The entry point
    below passes the parsed value in; every other caller passes what it means.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Paired feature-set comparison over every estimator registry entry."
        )
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Worker processes. Default: one per core, capped at the eight "
            "units of work. Pass 1 to run synchronously in this process for "
            "clean tracebacks."
        ),
    )
    return parser.parse_args(argv)


def main(max_workers: int | None = None) -> None:
    """Print the paired comparison for every registry entry.

    Runs outside the agent lane: it reads `data/cache/` and downloads if the
    cache is cold. It is eight nested walk-forward runs, each tuning a grid on
    inner folds inside every outer fold — hours serially, which is what spec
    015 is about.

    `max_workers` is forwarded to `compare_all_entries_parallel`: `None` for
    all cores, `1` for the synchronous debugging path.
    """
    prices = load_prices()

    results = compare_all_entries_parallel(
        prices,
        max_workers=max_workers,
        random_state=RANDOM_STATE,
        # Checkpoint on every completed pair, exactly as the serial loop did.
        # `on_pair` hands over the completed comparisons already in report
        # order, so a checkpoint written mid-run is the same file the serial
        # run would have written at the same point.
        on_pair=_checkpoint,
        verbose=True,
    )

    print()
    print(format_report(results))


if __name__ == "__main__":
    main(max_workers=parse_args().workers)
