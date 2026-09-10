"""Tests for scripts/feature_set_comparison.py — spec 015's parallel path.

The load-bearing test in this file is `TestSerialParallelEquivalence`. Spec
015 is a pure performance change: it is allowed to make the comparison
faster and it is allowed to change nothing else. FR-005 states that as
bit-for-bit, and this file is where that is enforced — on the prediction
series, on every number in the four result dictionaries, and on the printed
report character for character.

"Close enough" is not the bar, and the reason is worth stating. The output of
this script is four p-values that decide whether spec 014's feature set
merges as an improvement or as a null result. A p-value that moves in the
fourth decimal because a sum was reduced in a different thread order is not a
rounding footnote — it means the number depends on the machine's core count,
and a result that depends on the machine is not a result. The tests below
would fail on a single differing bit.

The fixture is synthetic and generated in-process. No test here downloads
anything (CLAUDE.md, *Conventions → Tests*), and none reads `data/cache/`.

**Runtime.** This file is slower than its neighbours — it runs the full eight
unit comparison four times, once per execution mode, and spawns worker
processes. That is the cost of testing the thing the spec is actually about;
the fixture is sized down to roughly 250 bars and five outer folds to keep it
to tens of seconds rather than minutes.
"""

import concurrent.futures
import dataclasses
import math
import multiprocessing
import os
import pickle
import unittest

import numpy as np
import pandas as pd

# First, for the sys.path effect: every project import below depends on it.
from context import SCRIPTS_DIR

import feature_set_comparison as fsc
from estimators import ESTIMATOR_REGISTRY
from feature_set_comparison import (
    FEATURE_SET_A,
    FEATURE_SET_B,
    THREAD_LIMIT_VARS,
    ComparisonTask,
    _evaluate_feature_set_task,
    _pinned_thread_environment,
    _worker_init,
    build_tasks,
    compare_all_entries,
    compare_all_entries_parallel,
    format_report,
    pair_results,
)

# Sized so the whole eight-unit comparison runs in single-digit seconds while
# still producing several outer folds, real inner tuning, and a non-trivial
# number of paired bars. Too short and `nested_walk_forward` supports no outer
# folds at all; too long and this file dominates the suite.
FIXTURE_BARS = 250


def synthetic_prices(bars: int = FIXTURE_BARS, seed: int = 7) -> pd.DataFrame:
    """An OHLCV frame shaped like `data.download_market_data`'s output.

    A seeded geometric random walk, on business days, with the columns
    `features.build_features` reads: `Date`, `Close`, and `Volume`, plus the
    `Open`/`High`/`Low` a price frame carries. Explicitly seeded, so the whole
    file is reproducible (CLAUDE.md, *Conventions → Determinism*).

    There is deliberately no signal in it. These tests ask whether two
    execution paths agree, not whether a model predicts — a fixture with a
    planted edge would make the estimators agree for a reason that has nothing
    to do with the scheduler.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-04", periods=bars)
    close = 50.0 * np.exp(np.cumsum(rng.normal(loc=0.0004, scale=0.012, size=bars)))
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close * (1.0 + rng.normal(scale=0.001, size=bars)),
            "High": close * (1.0 + np.abs(rng.normal(scale=0.004, size=bars))),
            "Low": close * (1.0 - np.abs(rng.normal(scale=0.004, size=bars))),
            "Close": close,
            "Volume": rng.integers(1_000_000, 5_000_000, size=bars).astype(float),
        }
    )


def _report_child_thread_state(_ignored=None) -> dict:
    """Run in a worker: what the child actually ended up with.

    Module-level and picklable, because under `spawn` a nested function
    could not cross the boundary at all.

    Reports both the environment variable and the *effective* thread count,
    because spec 015's whole pinning bug was a case where the first said 1
    and the second said 16. Only the second one is the thing that costs
    wall-clock.
    """
    import os

    state = {"OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS")}
    try:
        from sklearn.utils._openmp_helpers import _openmp_effective_n_threads

        state["effective_threads"] = _openmp_effective_n_threads()
    except Exception:
        # A private scikit-learn helper. If it moves, the test that reads
        # this skips rather than failing for the wrong reason.
        state["effective_threads"] = None
    return state


def _run_units_in_pool(
    prices: pd.DataFrame, tasks: list[ComparisonTask], workers: int
) -> dict[tuple[str, str, str], tuple[pd.Series, pd.Series, int]]:
    """Run the given units through a real process pool, keyed by identity.

    Uses the same executor construction the production orchestrator uses —
    including `initializer=_worker_init` — because a pool without the
    initializer would not be testing the configuration that ships.
    """
    results = {}
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=workers, initializer=_worker_init
    ) as executor:
        futures = [
            executor.submit(_evaluate_feature_set_task, prices, task) for task in tasks
        ]
        for future in concurrent.futures.as_completed(futures):
            name, task, feature_set, predicted, labels, folds = future.result()
            results[(name, task, feature_set)] = (predicted, labels, folds)
    return results


class TestWorkerInitialization(unittest.TestCase):
    """T002 / FR-002 — the five thread limits, and only after a clean restore.

    These tests mutate `os.environ`, so each restores exactly what it found,
    including the distinction between "was set to something else" and "was not
    set at all". Leaking `OMP_NUM_THREADS=1` out of this file would silently
    single-thread every test that runs after it.
    """

    def setUp(self):
        self._saved = {name: os.environ.get(name) for name in THREAD_LIMIT_VARS}

    def tearDown(self):
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_all_five_variables_are_pinned_to_one(self):
        for name in THREAD_LIMIT_VARS:
            os.environ.pop(name, None)

        _worker_init()

        for name in THREAD_LIMIT_VARS:
            self.assertEqual(os.environ.get(name), "1", name)

    def test_an_existing_higher_setting_is_overwritten_not_respected(self):
        """A worker inheriting `OMP_NUM_THREADS=16` is the oversubscription
        bug. The initializer overwrites rather than defaults."""
        for name in THREAD_LIMIT_VARS:
            os.environ[name] = "16"

        _worker_init()

        for name in THREAD_LIMIT_VARS:
            self.assertEqual(os.environ.get(name), "1", name)

    def test_the_named_set_is_exactly_the_five_fr_002_lists(self):
        """Pins the list itself. Dropping one of these is a silent
        performance regression on whichever backend that variable governed —
        nothing raises, the run is just slower than it should be."""
        self.assertEqual(
            set(THREAD_LIMIT_VARS),
            {
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            },
        )


class TestParentSideThreadPinning(unittest.TestCase):
    """FR-002 / Design Constraint 2 — the pinning that actually takes effect.

    Spec 015 prescribes `initializer=_worker_init` alone. Measured, that does
    not pin anything: under `spawn` the child imports NumPy and sizes OpenMP's
    pool while unpickling, before the initializer body ever runs, and setting
    `OMP_NUM_THREADS` afterwards raised scikit-learn's effective count from 8
    to 16 rather than lowering it to 1.

    These tests are the regression guard for the fix. If someone deletes
    `_pinned_thread_environment` on the grounds that `_worker_init` looks
    sufficient, `test_a_pooled_worker_is_effectively_single_threaded` fails —
    which is the only reason that failure would ever be noticed, since an
    unpinned run produces identical numbers and merely takes longer.
    """

    def setUp(self):
        self._saved = {name: os.environ.get(name) for name in THREAD_LIMIT_VARS}

    def tearDown(self):
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_the_context_manager_sets_all_five_then_restores_them(self):
        os.environ.pop("OMP_NUM_THREADS", None)
        os.environ["MKL_NUM_THREADS"] = "12"

        with _pinned_thread_environment():
            for name in THREAD_LIMIT_VARS:
                self.assertEqual(os.environ.get(name), "1", name)

        # Restored to what it was, distinguishing "unset" from "set to 12".
        self.assertIsNone(os.environ.get("OMP_NUM_THREADS"))
        self.assertEqual(os.environ.get("MKL_NUM_THREADS"), "12")

    def test_the_environment_is_restored_even_if_the_body_raises(self):
        os.environ.pop("OMP_NUM_THREADS", None)
        with self.assertRaises(ZeroDivisionError):
            with _pinned_thread_environment():
                1 / 0
        self.assertIsNone(os.environ.get("OMP_NUM_THREADS"))

    def test_a_spawned_child_inherits_the_limit_without_any_initializer(self):
        """The mechanism, isolated. No `initializer` is passed, so the only
        way the child can see `OMP_NUM_THREADS=1` is by inheriting the
        parent's environment block at creation — which is the whole point,
        because inheritance happens before the child's first import and an
        initializer does not."""
        with _pinned_thread_environment():
            with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
                state = executor.submit(_report_child_thread_state).result()
        self.assertEqual(state["OMP_NUM_THREADS"], "1")

    def test_a_pooled_worker_is_effectively_single_threaded(self):
        """The assertion that would have caught the original bug.

        `OMP_NUM_THREADS` reading "1" is not evidence of anything — it read
        "1" in the broken version too. This checks the number the runtime
        will actually use."""
        with _pinned_thread_environment():
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=1, initializer=_worker_init
            ) as executor:
                state = executor.submit(_report_child_thread_state).result()

        if state["effective_threads"] is None:
            self.skipTest("sklearn's _openmp_effective_n_threads is unavailable")
        self.assertEqual(state["effective_threads"], 1)

    def test_the_orchestrator_leaves_this_process_unpinned(self):
        """A diagnostic script that single-threaded the caller's interpreter
        as a side effect would be a nasty thing to import."""
        os.environ.pop("OMP_NUM_THREADS", None)
        compare_all_entries_parallel(synthetic_prices(), max_workers=2)
        self.assertIsNone(os.environ.get("OMP_NUM_THREADS"))


class TestSpawnCompatibility(unittest.TestCase):
    """T003 / FR-003 / Design Constraint 4 — everything crossing the process
    boundary is picklable, and the worker target is module-level.

    On Linux's `fork` a closure or a lambda would work, and this whole class
    would pass vacuously. It is written for Windows and macOS `spawn`, where
    the child is a fresh interpreter and every argument travels as a pickle.
    """

    def test_worker_target_is_a_module_level_function(self):
        self.assertEqual(
            _evaluate_feature_set_task.__qualname__, "_evaluate_feature_set_task"
        )
        self.assertNotIn("<locals>", _evaluate_feature_set_task.__qualname__)
        self.assertEqual(_evaluate_feature_set_task.__module__, "feature_set_comparison")

    def test_initializer_is_a_module_level_function(self):
        self.assertEqual(_worker_init.__qualname__, "_worker_init")
        self.assertNotIn("<locals>", _worker_init.__qualname__)

    def test_worker_target_and_initializer_pickle(self):
        self.assertIs(pickle.loads(pickle.dumps(_evaluate_feature_set_task)),
                      _evaluate_feature_set_task)
        self.assertIs(pickle.loads(pickle.dumps(_worker_init)), _worker_init)

    def test_comparison_task_round_trips_through_pickle(self):
        task = ComparisonTask(
            name="logistic",
            task="classification",
            feature_set=FEATURE_SET_B,
            random_state=42,
        )
        self.assertEqual(pickle.loads(pickle.dumps(task)), task)

    def test_comparison_task_is_frozen_and_hashable(self):
        """It is used as half of a dictionary key's identity and as a payload.
        A mutable task could change its own address after submission."""
        task = build_tasks()[0]
        hash(task)
        with self.assertRaises(Exception):
            task.name = "something-else"

    def test_the_price_frame_survives_pickling_unchanged(self):
        """The one large argument crossing the boundary. A dtype that changed
        in transit would change the features and therefore the predictions."""
        prices = synthetic_prices()
        pd.testing.assert_frame_equal(pickle.loads(pickle.dumps(prices)), prices)


class TestWorkUnitConstruction(unittest.TestCase):
    """T001 / FR-004 — eight units, each carrying its own explicit seed."""

    def test_there_is_one_unit_per_entry_and_feature_set(self):
        tasks = build_tasks()
        self.assertEqual(len(tasks), len(ESTIMATOR_REGISTRY) * 2)
        self.assertEqual(len(set(tasks)), len(tasks))

    def test_every_unit_carries_the_requested_seed(self):
        for task in build_tasks(random_state=1234):
            self.assertEqual(task.random_state, 1234)

    def test_both_feature_sets_appear_for_every_entry(self):
        by_entry = {}
        for task in build_tasks():
            by_entry.setdefault((task.name, task.task), set()).add(task.feature_set)
        self.assertEqual(set(by_entry), set(ESTIMATOR_REGISTRY))
        for feature_sets in by_entry.values():
            self.assertEqual(feature_sets, {FEATURE_SET_A, FEATURE_SET_B})

    def test_the_unit_seed_reaches_the_walk_forward_not_the_module_constant(self):
        """FR-004 in the form that would actually catch a regression.

        A worker that ignored `task_spec.random_state` and read `RANDOM_STATE`
        instead cannot be caught by comparing outputs: under `spawn` the child
        re-imports this module, so the constant *is* there, and with the
        default seed the two readings agree. That is precisely what makes it a
        silent bug. So the assertion is on the argument actually forwarded to
        `nested_walk_forward`, with a seed deliberately unlike the constant.
        """
        prices = synthetic_prices()
        task = ComparisonTask(
            name="logistic",
            task="classification",
            feature_set=FEATURE_SET_B,
            random_state=20260908,
        )
        self.assertNotEqual(task.random_state, fsc.RANDOM_STATE)

        seen: list[int] = []
        original = fsc.nested_walk_forward

        def _spy(frame, **kwargs):
            seen.append(kwargs["random_state"])
            return original(frame, **kwargs)

        fsc.nested_walk_forward = _spy
        try:
            _evaluate_feature_set_task(prices, task)
        finally:
            fsc.nested_walk_forward = original

        self.assertEqual(seen, [20260908])

    def test_replacing_the_seed_leaves_the_rest_of_the_unit_intact(self):
        """`dataclasses.replace` on a frozen task — the shape a caller
        overriding one field would use."""
        task = build_tasks()[0]
        other = dataclasses.replace(task, random_state=7)
        self.assertEqual(other.random_state, 7)
        self.assertEqual(
            (other.name, other.task, other.feature_set),
            (task.name, task.task, task.feature_set),
        )


class TestMaxWorkersValidation(unittest.TestCase):
    """FR-007 — the worker count is validated before any work starts."""

    def test_zero_workers_raises(self):
        with self.assertRaises(ValueError):
            compare_all_entries_parallel(synthetic_prices(), max_workers=0)

    def test_negative_workers_raises(self):
        with self.assertRaises(ValueError):
            compare_all_entries_parallel(synthetic_prices(), max_workers=-4)


class TestSynchronousPathCreatesNoProcesses(unittest.TestCase):
    """T005 / FR-007 — `max_workers=1` bypasses process-pool creation.

    This is the debuggability requirement, not a configuration no-op. A pool
    of one still pickles arguments, still starts a child interpreter, and
    still re-raises the child's exception with a traceback that does not
    include the caller's frames. The point of `max_workers=1` is to get the
    real stack back, and that only happens if no pool is created at all.

    Tested by making pool creation fail: the module's
    `ProcessPoolExecutor` name is replaced with something that raises, and
    the run is asserted to succeed anyway. A `max_workers=1` that quietly
    created a one-worker pool would raise here.
    """

    def test_no_executor_is_constructed(self):
        prices = synthetic_prices()
        constructed = []

        class _Forbidden:
            def __init__(self, *args, **kwargs):
                constructed.append((args, kwargs))
                raise AssertionError(
                    "max_workers=1 must not construct a ProcessPoolExecutor"
                )

        original = concurrent.futures.ProcessPoolExecutor
        concurrent.futures.ProcessPoolExecutor = _Forbidden
        try:
            results = compare_all_entries_parallel(prices, max_workers=1)
        finally:
            concurrent.futures.ProcessPoolExecutor = original

        self.assertEqual(constructed, [])
        self.assertEqual(len(results), len(ESTIMATOR_REGISTRY))

    def test_the_synchronous_path_runs_in_the_calling_process(self):
        """Not merely "no pool" — the same process. Checked by counting the
        live children of this process across the call."""
        prices = synthetic_prices()
        before = len(multiprocessing.active_children())
        compare_all_entries_parallel(prices, max_workers=1)
        after = len(multiprocessing.active_children())
        self.assertEqual(before, after)


class TestSerialParallelEquivalence(unittest.TestCase):
    """T009 / FR-005 / SC-002 — the correctness gate for the whole spec.

    Four runs of the same comparison over one fixture:

    - the eight units executed in this process, one after another;
    - the eight units executed through a two-worker pool;
    - the orchestrator in its synchronous mode (`max_workers=1`);
    - the orchestrator in its parallel mode (`max_workers=2`).

    Every number every one of them produces must match every other exactly.
    Note that this also exercises the thread-limit difference, not just the
    process boundary: the in-process runs use whatever thread count this
    machine's OpenMP and BLAS defaults give, and the pooled runs are pinned to
    one thread by `_worker_init`. If any estimator's output depended on thread
    count, these tests are where it would surface.
    """

    @classmethod
    def setUpClass(cls):
        cls.prices = synthetic_prices()
        cls.tasks = build_tasks()

        cls.serial_units = {
            (task.name, task.task, task.feature_set): _evaluate_feature_set_task(
                cls.prices, task
            )[3:]
            for task in cls.tasks
        }
        cls.parallel_units = _run_units_in_pool(cls.prices, cls.tasks, workers=2)

        cls.serial_results = compare_all_entries_parallel(cls.prices, max_workers=1)
        cls.parallel_results = compare_all_entries_parallel(cls.prices, max_workers=2)

    def _assert_exactly_equal(self, actual, expected, label):
        """Exact equality, with NaN treated as equal to NaN.

        `assertEqual` on floats is `==`, which is bitwise for finite values —
        a difference of one ULP fails. NaN is special-cased because
        `nan != nan` and both comparison functions legitimately emit
        `float("nan")` as the statistic on their no-discordant-pairs branch;
        two NaNs there mean the same "no test was possible", not a
        difference.
        """
        if isinstance(expected, float) and math.isnan(expected):
            self.assertTrue(
                isinstance(actual, float) and math.isnan(actual),
                f"{label}: expected NaN, got {actual!r}",
            )
            return
        self.assertEqual(actual, expected, label)
        self.assertIs(type(actual), type(expected), f"{label}: type differs")

    def test_prediction_series_are_identical(self):
        """SC-002, stated in the spec's own terms: `assert_series_equal`."""
        self.assertEqual(set(self.parallel_units), set(self.serial_units))
        for key, (predicted, labels, folds) in self.serial_units.items():
            parallel_predicted, parallel_labels, parallel_folds = self.parallel_units[
                key
            ]
            pd.testing.assert_series_equal(parallel_predicted, predicted, obj=str(key))
            pd.testing.assert_series_equal(parallel_labels, labels, obj=str(key))
            self.assertEqual(parallel_folds, folds, key)

    def test_prediction_dtypes_and_index_survive_the_process_boundary(self):
        """`assert_series_equal` checks these, but they are called out because
        they are what a pickle round-trip is most likely to quietly change —
        and an `Int64` that came back as `object` would still compare equal
        under a looser check while breaking `astype(int)` downstream."""
        for key, (predicted, labels, _) in self.serial_units.items():
            parallel_predicted, parallel_labels, _ = self.parallel_units[key]
            self.assertEqual(parallel_predicted.dtype, predicted.dtype, key)
            self.assertEqual(parallel_labels.dtype, labels.dtype, key)
            self.assertEqual(parallel_predicted.index.name, "Date", key)

    def test_pairing_the_two_unit_sets_gives_identical_statistics(self):
        """The units agree; this checks the tests computed from them agree —
        McNemar's contingency counts and Wilcoxon's statistic included."""
        for name, task in sorted(ESTIMATOR_REGISTRY):
            from_serial = pair_results(
                name=name,
                task=task,
                result_a=self.serial_units[(name, task, FEATURE_SET_A)],
                result_b=self.serial_units[(name, task, FEATURE_SET_B)],
            )
            from_parallel = pair_results(
                name=name,
                task=task,
                result_a=self.parallel_units[(name, task, FEATURE_SET_A)],
                result_b=self.parallel_units[(name, task, FEATURE_SET_B)],
            )
            self.assertEqual(set(from_serial), set(from_parallel))
            for key in from_serial:
                self._assert_exactly_equal(
                    from_parallel[key], from_serial[key], f"{name}/{task}:{key}"
                )

    def test_orchestrator_results_match_key_for_key_and_bit_for_bit(self):
        """FR-005 at the level the script actually reports at."""
        self.assertEqual(len(self.parallel_results), len(self.serial_results))
        for parallel, serial in zip(self.parallel_results, self.serial_results):
            self.assertEqual(set(parallel), set(serial))
            for key in serial:
                self._assert_exactly_equal(
                    parallel[key], serial[key], f"{serial['name']}/{serial['task']}:{key}"
                )

    def test_discordant_counts_and_p_values_are_equal(self):
        """Called out separately from the dictionary sweep above because these
        four numbers are what the spec 014 merge decision turns on. A test
        that only checked the dictionaries would still catch it; this one says
        out loud what it is protecting."""
        for parallel, serial in zip(self.parallel_results, self.serial_results):
            self.assertEqual(parallel["discordant"], serial["discordant"])
            self.assertEqual(parallel["p_one_sided"], serial["p_one_sided"])
            self.assertEqual(parallel["p_two_sided"], serial["p_two_sided"])

    def test_formatted_reports_match_character_for_character(self):
        """User Story 2, acceptance 3. The report is the artifact a reader
        actually sees, so it is compared as text rather than trusted to
        follow from the numbers."""
        self.assertEqual(
            format_report(self.parallel_results), format_report(self.serial_results)
        )

    def test_result_order_is_the_registry_order_in_both_modes(self):
        """FR-006 — completion order does not reach the report. With two
        workers on eight units of unequal cost, the finishing order is not the
        submission order; the assertion is that it does not matter."""
        expected = sorted(ESTIMATOR_REGISTRY)
        for results in (self.serial_results, self.parallel_results):
            self.assertEqual([(r["name"], r["task"]) for r in results], expected)

    def test_the_fr_007_alias_produces_the_same_results(self):
        """`compare_all_entries` is a delegation, and this is what keeps it
        one. Runs synchronously, so it costs a serial pass and no spawn."""
        results = compare_all_entries(self.prices, max_workers=1)
        for actual, expected in zip(results, self.serial_results):
            for key in expected:
                self._assert_exactly_equal(
                    actual[key], expected[key], f"alias:{expected['name']}:{key}"
                )

    def test_on_pair_reports_completed_comparisons_in_report_order(self):
        """The checkpoint hook. Each call must be a prefix of the final
        report order — a checkpoint written mid-run has to be readable as
        the same file the serial run would have written."""
        seen: list[list[tuple[str, str]]] = []
        compare_all_entries_parallel(
            self.prices,
            max_workers=2,
            on_pair=lambda done: seen.append([(r["name"], r["task"]) for r in done]),
        )

        expected = sorted(ESTIMATOR_REGISTRY)
        self.assertEqual(len(seen), len(expected))
        for snapshot in seen:
            # Sorted, and never containing a half-finished pair.
            self.assertEqual(snapshot, sorted(snapshot))
            self.assertTrue(set(snapshot).issubset(set(expected)))
        self.assertEqual(seen[-1], expected)
        # Strictly growing by one completed pair per call.
        self.assertEqual([len(s) for s in seen], list(range(1, len(expected) + 1)))


class TestWorkerErrorPropagation(unittest.TestCase):
    """T010 — a worker failure surfaces with the identity of the work unit.

    The failure is induced with data rather than a monkeypatch, because a
    monkeypatch in this process does not reach a `spawn`ed child: the child
    re-imports the module from source and would never see it. A price frame
    too short to support a single outer fold makes every unit raise inside
    `model_cv.nested_walk_forward`, which is a real failure of the real code
    path.
    """

    def _too_short(self) -> pd.DataFrame:
        return synthetic_prices(bars=45)

    def test_the_fixture_really_does_fail(self):
        """Guards the test above it: if a 45-bar frame ever started working,
        the error-propagation tests would pass without testing anything."""
        with self.assertRaises(Exception):
            _evaluate_feature_set_task(self._too_short(), build_tasks()[0])

    def test_parallel_failure_names_the_work_unit(self):
        with self.assertRaises(RuntimeError) as caught:
            compare_all_entries_parallel(self._too_short(), max_workers=2)

        message = str(caught.exception)
        self.assertIn("worker failed on", message)
        # Names an entry, its task, its feature set, and its seed — enough to
        # re-run exactly the failing unit under `max_workers=1`.
        self.assertTrue(
            any(name in message for name, _ in ESTIMATOR_REGISTRY), message
        )
        self.assertTrue(
            FEATURE_SET_A in message or FEATURE_SET_B in message, message
        )
        self.assertIn(str(fsc.RANDOM_STATE), message)

    def test_the_original_exception_is_chained_not_swallowed(self):
        with self.assertRaises(RuntimeError) as caught:
            compare_all_entries_parallel(self._too_short(), max_workers=2)
        self.assertIsNotNone(caught.exception.__cause__)

    def test_the_pool_is_torn_down_after_a_failure(self):
        """SC-004 — a failing run leaves no children behind. The `with` block
        joins every worker on the way out, including the exceptional way."""
        before = set(p.pid for p in multiprocessing.active_children())
        with self.assertRaises(RuntimeError):
            compare_all_entries_parallel(self._too_short(), max_workers=2)
        after = set(p.pid for p in multiprocessing.active_children())
        self.assertEqual(after - before, set())

    def test_the_synchronous_path_raises_the_original_exception_directly(self):
        """The other half of User Story 3. `max_workers=1` deliberately does
        *not* wrap: the caller asked for a clean traceback, and wrapping would
        replace the failing frame with this module's."""
        with self.assertRaises(Exception) as caught:
            compare_all_entries_parallel(self._too_short(), max_workers=1)
        self.assertNotIn("worker failed on", str(caught.exception))


class TestNoNewDependency(unittest.TestCase):
    """FR-008 / Rule 6 — the parallelism is standard library only.

    Reads the source rather than the imports, so it catches a deferred import
    inside a function as well as a top-level one.
    """

    FORBIDDEN = ("joblib", "loky", "dask", "ray", "multiprocess", "pathos")

    def test_no_external_parallelism_library_is_imported(self):
        source = (SCRIPTS_DIR / "feature_set_comparison.py").read_text(
            encoding="utf-8"
        )
        for line in source.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            for banned in self.FORBIDDEN:
                self.assertNotIn(
                    banned, stripped, f"{banned} imported at: {stripped}"
                )

    def test_the_parallel_machinery_comes_from_concurrent_futures(self):
        self.assertIs(fsc.concurrent.futures, concurrent.futures)


if __name__ == "__main__":
    unittest.main()
