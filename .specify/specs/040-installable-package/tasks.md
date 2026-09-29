# Tasks: Installable package (`scripts/` → `src/qmb/`)

**Input**: [spec.md](spec.md), [plan.md](plan.md), [MIGRATION-INVENTORY.md](../../../docs/implementation/spec-040/MIGRATION-INVENTORY.md)
**Organization**: single-threaded, and no other lane open. Phases 0–2 build and
red-prove the gates. **Phase 3 is ONE atomic unit.** Template phases do not
authorize Git operations or parallel agents.

Line numbers are as of 2026-09-27 and have already drifted from the inventory's
(for example, the multi_ticker message is at `:446-447`, not `:399-402`).
**Every site is anchored by its exact text.** T005 re-locates each one after 036
and 041 merge.

---

## Phase 0: Preconditions and measurement

- [ ] T001 Confirm that 036 and 041 have merged and that no other branch or lane is
  open (Camden).
- [ ] T002 Export `PRE` read-only to a scratch directory outside the repository.
  Use no Git process; follow the 037 approach (Dulwich object read) or ask
  Camden for an archive.
- [ ] T003 **Re-measure the baseline at `PRE`** (not copied from any document):
  `python -m pytest tests -q -p no:cacheprovider --junitxml=.specify/specs/040-installable-package/artifacts/pre.xml`.
  It must show 0 failed and 0 errors, or 040 stops. Record `PRE`'s SHA, passed
  count, subtests, Python version and OS here.
- [ ] T004 Measure the ledger at `PRE`: `verify()` head, record count and
  `n_post_ledger`; the SHA-256 of every file under `docs/trials/` (saved to
  `artifacts/trials-pre.sha256`); and `N_backfill`. These values fill
  `runner-renames.json`.
- [ ] T005 **Re-inventory.** Re-run INV's searches (`__file__`, `sys.path`,
  `"scripts`, `scripts/`, `SCRIPTS_DIR`, `import context`, `find_spec(`,
  `research_config("`, flat imports of the 29 names) over the `PRE` tree. Add
  every site that 036 or 041 introduced, such as
  `tests/test_unadjusted_caller_wiring.py:12-14` (`SCRIPTS = … / "scripts"` plus
  an insert), and 036's CLI subprocess test that invokes
  `python scripts/ma_crossover_backtest.py`.
- [ ] T006 **Close the allowlist.** Write `ac1-allowlist.json`: every non-import
  edit from T020–T047, plus T005's additions, as `{path, before, after}`. Also
  write the file manifest (spec §7). **Camden reviews this file.** It is the
  human-sized review surface of the whole migration. After T006, any need for an
  edit not on the list means stopping and amending the spec, not the list.

## Phase 1: Gate tooling, each red-proven before the migration

- [ ] T010 `tools/ac1_filter.py` (stdlib only): the `--stdin` Git-diff mode and
  the `--before/--after` tree mode, with the classifier from spec AC-1 (a)–(d).
- [ ] T011 `tests/test_040_ac1_filter.py`: the five AC-1 cases (control, logic
  edit, wrong target, history edit, stray file), with exact messages.
- [ ] T012 `tools/compare_junit.py`: compares node-ID sets and outcomes, and
  prints `pre-existing P/P passed; new K (enumerated); missing 0; unexpected 0`.
- [ ] T013 `tests/test_040_ledger_boundary.py`: AC-4b and AC-4c, plus the R-4a,
  R-4b, R-4c and control cases, all on copies under `tmp_path`, with the
  production file opened read-only. It is written now and will be red until
  Phase 3, because `qmb` and the mapping file do not exist yet. Observe it red,
  for the right reason.
- [ ] T014 `tests/test_040_installability.py`: AC-5's import sweep
  (`control` / `planted_flat_import`, with a masking `PYTHONPATH` entry in the
  planted case). The copy includes `pyproject.toml`, so `project_root()` resolves
  to the copy. It also holds AC-6's spawn test. The `project_root()` cases (env override,
  the marker via `__file__`, `ProjectRootNotFound` with neither, cwd never
  consulted) **already exist from spec 043 (its AC-5 tests)**. 040 keeps them,
  retargeted from `scripts/_project.py` to `qmb._project`, and adds none.
  Red until Phase 3.

## Phase 2: New files (inert until Phase 3)

- [ ] T015 `pyproject.toml`: **edit** the minimal marker file that spec 043
  T020 created (`[project] name = "quant-ml-bot"`, `version = "0.0.0.dev0"`)
  into exactly spec §4's content. `[project] name` stays unchanged: it is the
  root marker.
- [ ] T016 `src/qmb/__init__.py` (docstring only) is new. `src/qmb/_project.py`
  is a **move** of `scripts/_project.py` (created by spec 043 T021) with the
  import rewrite only. The contract is unchanged (spec §1.5 R1; stdlib
  `tomllib`; no caching, so an env change in a test takes effect). The AC-1 (a)
  module set gains `_project`.
- [ ] T017 `tests/repo_paths.py`: `REPO_ROOT = Path(__file__).resolve().parents[1]`,
  `PACKAGE_DIR = REPO_ROOT / "src" / "qmb"`. No `sys.path` access; a test asserts
  this by AST.
- [ ] T018 `docs/trials/runner-renames.json` from T004's values (spec §1.6).

---

## Phase 3: THE MIGRATION — one atomic unit

Do all of T019–T047 in one working-tree change, then run Phase 4. No
intermediate state is committed or gated.

- [ ] T019 Move the 29 modules `scripts/<m>.py` → `src/qmb/<m>.py`. Move the two
  scratch modules → `scratch/`, byte-identical. Delete `tests/context.py`.
  Rewrite every intra-project import `M → qmb.M` (`import M as X` →
  `from qmb import M as X`; `import M` → `from qmb import M`), absolute only.

### `__file__`-relative paths (spec §5; the largest source of silent breakage)

- [ ] T020 `src/qmb/data.py:52` (cache root)
  ```python
  # before
  PROJECT_ROOT = Path(__file__).resolve().parents[1]
  # after
  PROJECT_ROOT = project_root()          # + import: from qmb._project import project_root
  ```
  `CACHE_DIR = PROJECT_ROOT / "data" / "cache"` (`:53`) is unchanged. Test:
  under AC-3a from a foreign cwd, `qmb.data.CACHE_DIR == REPO_ROOT / "data" / "cache"`.
- [ ] T021 `src/qmb/feature_set_comparison.py:866-868` (checkpoint)
  ```python
  # before
  CHECKPOINT_PATH = (
      Path(__file__).resolve().parents[1] / "data" / "cache" / "feature_set_comparison.json"
  )
  # after
  CHECKPOINT_PATH = (
      CACHE_DIR / "feature_set_comparison.json"
  )
  # import line (allowlisted, not a pure prefix rewrite):
  # from qmb.data import download_market_data  ->  from qmb.data import CACHE_DIR, download_market_data
  ```
  This reuses the single source of truth that `data.py:48-51` documents.
- [ ] T022 `src/qmb/trial_registry.py:19-20` (**L1: ledger root**).
  **After spec 043, `ROOT = project_root()` is already in place.** This task
  reduces to the import rewrite (`project_root` now imported from
  `qmb._project`). The before/after below shows the state before 043.
  ```python
  # before
  ROOT = Path(__file__).resolve().parents[1]
  # after
  ROOT = project_root()                  # + import: from qmb._project import project_root
  ```
  `DEFAULT_TRIALS_PATH = ROOT / "docs/trials/trials.jsonl"` (`:20`) is unchanged.
  Test: AC-4b's `TrialLedger().path` assertion and the R-4c red.
- [ ] T023 `src/qmb/trial_runner.py:66-72` (`relative_path(ROOT, value)`).
  **No edit.** `ROOT` is imported from `trial_registry` and is correct after T022.
  Test: `_snapshot(REPO_ROOT / "data/cache/x.csv")` returns `"data/cache/x.csv"` when
  run from a foreign cwd. Before T022, it would raise "path outside repository".
- [ ] T024 `src/qmb/autocorrelation_check.py:14`
  ```python
  # before
  PLOTS_DIRECTORY = Path(__file__).resolve().parent.parent / "plots"
  # after
  PLOTS_DIRECTORY = project_root() / "plots"     # + import
  ```
- [ ] T025 `src/qmb/stationarity_check.py:17`: the same before/after as T024.

### Ledger identity (spec §1.4)

- [ ] T026 `src/qmb/trial_registry.py:96` (**L2**)
  ```python
  # before
      for folder in ("scripts", "reports/api"):
  # after
      for folder in ("src/qmb", "reports/api"):
  ```
  Paired test edit: `tests/test_033_trial_ledger.py:125`
  `(tmp_path / "scripts").mkdir(); src = tmp_path / "scripts/source.py"` →
  `(tmp_path / "src/qmb").mkdir(parents=True); src = tmp_path / "src/qmb/source.py"`.
- [ ] T027 **L3**: the 12 runner literals. Each changes `"scripts/` → `"src/qmb/`
  and nothing else on the line:
  - `feature_set_comparison.py:167`
  - `logistic_baseline.py:318` and `:332`
  - `ma_crossover_backtest.py:101`, `:113` and `:227`
  - `model_cv.py:330` and `:461`
  - `multi_ticker_comparison.py:137`, `:148`, `:258` and `:286`

  Example: `research_config("scripts/model_cv.py:tune_on_fold", locals())` →
  `research_config("src/qmb/model_cv.py:tune_on_fold", locals())`.
  **`docs/trials/trials.jsonl` is not touched.**

### AST / introspection tests

- [ ] T030 `tests/test_targets.py:605-622` (`_imported_module_names`)
  ```python
  # before
              if isinstance(node, ast.Import):
                  names.update(alias.name.split(".")[0] for alias in node.names)
              elif isinstance(node, ast.ImportFrom) and node.module:
                  names.add(node.module.split(".")[0])
  # after
              if isinstance(node, ast.Import):
                  names.update(_project_local(alias.name) for alias in node.names)
              elif isinstance(node, ast.ImportFrom) and node.module == "qmb":
                  names.update(alias.name for alias in node.names)
              elif isinstance(node, ast.ImportFrom) and node.module:
                  names.add(_project_local(node.module))
  # with, in the same class:
  #   def _project_local(name): return name.split(".")[1] if name.startswith("qmb.") else name.split(".")[0]
  ```
  The expected sets (`{"numpy","pandas"}` and `{"numpy","pandas","signals","targets"}`)
  are unchanged. Red check: a planted `from qmb.backtest_harness import x` in a
  copied `features.py` makes the features assertion fail.
- [ ] T031 `tests/test_order_gateway.py:42` and `:136`
  ```python
  # before
              if node.module in {"live_safety_gate", "scripts.live_safety_gate"}:
  # after
              if node.module in {"live_safety_gate", "qmb.live_safety_gate"}:
  # before
          roots = [REPO_ROOT / "scripts", REPO_ROOT / "reports"]
  # after
          roots = [REPO_ROOT / "src" / "qmb", REPO_ROOT / "reports"]
  ```
  Add a non-vacuity check: the scan visits at least 29 files under `src/qmb`.
- [ ] T032 `tests/test_033_trial_instrumentation.py`:
  - `:5-7` `from context import SCRIPTS_DIR` / `ROOT = SCRIPTS_DIR.parent` →
    `from repo_paths import REPO_ROOT` / `ROOT = REPO_ROOT`.
  - `:13` `("scripts", "reports/api")` → `("src/qmb", "reports/api")`.
  - `:41`, `:43`, `:47`, `:51`, `:52` and `:53`: planted-tree `"scripts"` →
    `"src/qmb"`. At `:52`, the planted source string's
    `from backtest_harness import` → `from qmb.backtest_harness import`.
  - Non-vacuity: the real scan visits at least 29 files.
  - `tests/fixtures/spec_033/runner_inventory.json`: 19 `"scripts/<file>.py"` →
    `"src/qmb/<file>.py"` (a prefix-rule file).
- [ ] T033 `tests/test_collection_guards.py:35-48`: the walk itself is unchanged.
  Verify that no `test*.py` or `*_test.py` file exists under `src/qmb/`. The
  guard's real run over the new layout is its green control. Add non-vacuity to
  both real-tree guards (spec §5 rule):
  - `:35` `test_python_tests_live_under_tests`: assert that
    `python_test_files(REPO)` yielded at least one file under `TESTS` before
    checking `misplaced`.
  - `:41` `test_each_test_module_collects_cases`: assert that
    `python_test_files(TESTS)` yielded at least one file, and that
    `collected_test_paths` is non-empty.
  Red check: point either walk at an empty `tmp_path`. The assertion fails
  instead of passing with an empty `misplaced` or `missing` list.
- [ ] T046 **Import-boundary helpers: qualified and relative imports.** Five AST
  helpers reduce every import to its first dotted segment. After T019 they read
  `from qmb.walk_forward_cv import …` as `"qmb"`, and they skip `from . import x`
  (`node.module is None`). Every `… & forbidden == set()` test then passes
  vacuously, which is the Rule 12 failure spec §5 names. Sites, anchored by text
  (`elif isinstance(node, ast.ImportFrom) and node.module:`):
  - `tests/test_estimators.py:576` (`TestModuleBoundaries._imported_modules`)
  - `tests/test_ml_signal.py:693` (`_imported_modules`)
  - `tests/test_model_cv.py:1007` (`_imported_modules`)
  - `tests/test_portfolio_risk.py:274` (`_imported_modules`)
  - `tests/test_targets.py:620` (`_imported_module_names`). T030 already covers
    the qualified forms here. This task adds the relative forms and the count.

  Each helper resolves every form to the project-local module name:
  ```python
  # import qmb.x / import qmb.x as y  -> "x"      (T030's _project_local)
  # from qmb.x import y               -> "x"
  # from qmb import x                 -> "x"
  # from .x import y   (level >= 1)   -> "x"
  # from . import x    (level >= 1)   -> "x"      (currently skipped)
  # import numpy / from numpy.linalg import y -> "numpy"   (unchanged)
  ```
  **Non-vacuity**: each helper counts the files it parsed and the import nodes
  it visited, and each boundary test asserts that the file count is nonzero and
  that at least one import node was seen. A missing or renamed target must fail
  loudly, not produce an empty set. The declared expected sets are unchanged.
  Red checks, each in a copied module under `tmp_path`: a planted
  `from qmb.backtest_harness import x` and a planted `from . import backtest_harness`
  each make that file's forbidden-module test fail. The unmodified copy is the
  green control.
- [ ] T047 `tests/test_no_fabricated_values.py:157` and `:163`: add non-vacuity to
  both source scans (spec §5 rule). `reports/` does not move, so this protects
  against a renamed or emptied directory, not against T019 itself.
  - `:157` `ROUTES_DIR.glob("*.py")`: assert that the scan visited at least one
    route module.
  - `:163` `WEB_SRC.rglob("*.ts*")`: assert that the scan visited at least one
    component file.
  Red check: with `ROUTES_DIR` / `WEB_SRC` patched to an empty `tmp_path`, each
  test fails on the count, not on `found == []`.

### `SCRIPTS_DIR` users (not in the inventory)

- [ ] T034 Package-directory users: the import line becomes
  `from repo_paths import PACKAGE_DIR as SCRIPTS_DIR`, and the use sites are
  unchanged:
  - `test_estimators.py:571`
  - `test_feature_set_comparison.py:670`
  - `test_ml_signal.py:688`
  - `test_model_cv.py:1002`
  - `test_portfolio_risk.py:269` and `:475`

  **Repo-root users**, where `SCRIPTS_DIR.parent` would silently become `src/`:
  - `test_033_dsr.py:71`: `SCRIPTS_DIR.parent` → `REPO_ROOT`.
  - `test_033_trial_ledger.py:160`: `assert cls.log.root != SCRIPTS_DIR.parent`
    → `!= REPO_ROOT`. Left unfixed, this passes vacuously.
  - `test_033_trial_ledger.py:180`: the same substitution.
  - `test_trial_registry.py:7`: the same substitution.
  - `spec033_pbo_profile.py:31-32`: `root = SCRIPTS_DIR.parent` → `root = REPO_ROOT`,
    and `root / "scripts/selection_bias.py"` → `root / "src/qmb/selection_bias.py"`.

### Dynamic imports and mutation engines

- [ ] T035 `tests/spec033_support.py:18-22`
  ```python
  # before
      assert importlib.util.find_spec(module), f"missing spec-033 behavior: {module}.{name}"
      obj = getattr(importlib.import_module(module), name, None)
  # after
      assert importlib.util.find_spec(f"qmb.{module}"), f"missing spec-033 behavior: {module}.{name}"
      obj = getattr(importlib.import_module(f"qmb.{module}"), name, None)
  ```
  The call sites (`api("trial_backfill", …)` and so on) are unchanged. Red check:
  `api("no_such_module", "x")` still fails with its message.
- [ ] T036 `tests/mutation_support_019.py` and `mutation_support_032.py`: **no
  edit.** Verify:
  1. under an editable install, `module.__file__` is the `src/qmb` source;
  2. no `killed(…, old, …)` target string in the 8 suites contains an import line
     (grep on 2026-09-27 found none; re-check in T005);
  3. each `source.count(old) == 1` still holds after the rewrite, which AC-2
     proves by running them.
- [ ] T037 `tests/mutation/run_mutation_check.py:51` and `:63`
  ```python
  # before
          shutil.copytree(REPO / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
          module = root / "scripts/data.py"
  # after
          shutil.copytree(REPO / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__"))
          shutil.copy2(REPO / "pyproject.toml", root / "pyproject.toml")
          module = root / "src/qmb/data.py"
  ```
  `run()` sets `PYTHONPATH=<root>/src`, and before the verdict it asserts the
  child imported `qmb` from `<root>`. Without that, the editable install shadows
  the copy, and the mutant is never loaded.
- [ ] T038 `tests/mutation/run_spec_018_mutants.py:22-26` `COPIED`: `"scripts"` →
  `"src"`, `"tests/context.py"` → `"tests/repo_paths.py"`, and add
  `"pyproject.toml"`. Apply the same `PYTHONPATH` and non-vacuity treatment as
  T037. Spec 043 D-4 already gives these drivers a shared isolation helper
  (conftest and `pyproject.toml` copy, stripped child environment, real-ledger
  tripwire). T037/T038 keep the `PYTHONPATH` and non-vacuity requirements and
  do not duplicate a copy the helper already performs; the tripwire is the
  backstop if this treatment regresses.

### Spawned workers

- [ ] T039 `src/qmb/feature_set_comparison.py:722-724`: **no edit**. The pickled
  callables become `qmb.feature_set_comparison.*` through the import rewrite.
  AC-6's test proves the spawned child resolves them from a foreign cwd.

### Bootstrap deletions

- [ ] T040 Remove the 34 `context` imports (INV §1.6), or replace them per T034.
  `tests/api_fixtures.py:22` is removed.
- [ ] T041 Delete the in-test inserts:
  - `test_walk_forward_cv.py:10` and `:281-283`;
  - `test_020_unadjusted_price_data.py:15-18`, the whole `REPO_ROOT` / `SCRIPTS` /
    insert block (after checking that `REPO_ROOT` has no other use);
  - T005's additions, such as `test_unadjusted_caller_wiring.py:12-14`.
- [ ] T042 `reports/api/main.py:14-16` (the `SCRIPTS_DIR` plus insert lines; keep
  `:13` `REPO_ROOT` for `DIST_DIR`). Also the 4-line blocks in
  `routes/backtest.py:14-17`, `data.py:14-17`, `diagnostics.py:11-14`,
  `ml_rundown.py:19-22` and `safety.py:10-13`, which closes Finding 56
  (spec §3). Remove `import sys` and `Path` where they become unused (import
  lines).

### User-facing text

- [ ] T043 `src/qmb/multi_ticker_comparison.py:446-447`
  ```python
  # before
              '  ./venv/Scripts/python.exe -c "import sys; '
              "sys.path.insert(0,'scripts'); from data import "
  # after
              '  ./venv/Scripts/python.exe -c "'
              "from qmb.data import "
  ```
- [ ] T044 README:
  - `README.md:104-108`: `python scripts/<x>.py` → `qmb-<name>`, using the spec §4
    names.
  - Setup: add `python -m pip install -e .` after the requirements install.

  CLAUDE.md:
  - The Layout block and the module table: `scripts/` → `src/qmb/` (a prefix-rule
    file).
  - The Tests section: add the editable install.
- [ ] T045 `.github/workflows/test.yml`: add `- run: pip install -e .`, and run
  pytest as `cd "$RUNNER_TEMP" && python -m pytest "$GITHUB_WORKSPACE/tests"` (the
  permanent AC-3a). `.github/workflows/claude.yml:39`: add `-e .` to its install.

---

## Phase 4: Gates, all required, in this order

- [ ] T050 **AC-1** (agent form): `python …/tools/ac1_filter.py --before <PRE export> --after .`
  must give empty output and exit 0. Camden runs the Git form.
- [ ] T051 **AC-2**: full suite to `artifacts/post.xml`; `compare_junit.py` must
  report 0 missing, 0 unexpected, and new equal to the three `test_040_*`
  modules.
- [ ] T052 **AC-3a / AC-3b / AC-3c**: the spec §6 commands, each output saved to
  `artifacts/ac3*.txt`.
- [ ] T053 **AC-4a**: `docs/trials/` hashes equal `artifacts/trials-pre.sha256`,
  plus the one new file. **AC-4b/c/d**: covered by T013's tests passing in T051.
- [ ] T054 **AC-5**: the in-suite proxy passes in T051 (planted case red, control
  green). Run AC-3a once against the planted copy, confirm the spec's expected
  red, and save it to `artifacts/ac5-red.txt`.
- [ ] T055 **AC-6**: passes in T051.
- [ ] T056 Run both mutation drivers (T037, T038). Each reports a green control
  and killed mutants. Save the outputs.
- [ ] T057 Hand off with `PRE`'s SHA, all artifact paths, and the one-line human
  review map (allowlist, `pyproject.toml`, `_project.py`, mapping file, new
  tests).

## Rollback and tagging

- **Rollback point: `PRE`** (T003). If any Phase 4 gate fails and cannot be fixed
  inside the same unit, the entire Phase 3 change is discarded back to `PRE` by
  Camden. The agent runs no Git. There is no partial landing.
- **Camden tags `v1.0` only after AC-1 through AC-5 have passed** (with AC-6
  recorded alongside), and after the remaining `SCOPE-V1.md` §3 items hold.

## Dependencies & Execution Order

T001 → T002 → T003 → T004 → T005 → T006 (Camden reviews) → T010–T014 (gates
red-proven) → T015–T018 → **[T019–T047 as one unit]** → T050 → T051 → T052 →
T053 → T054 → T055 → T056 → T057. No step replaces a failed or unexecuted gate
with a focused green claim.
