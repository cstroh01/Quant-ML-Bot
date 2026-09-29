# Feature Specification: Installable package (`scripts/` → `src/qmb/`)

**Feature Branch**: `040-installable-package` (name only; Camden owns Git)
**Spec number**: 040, assigned by Camden.
**Created**: 2026-09-27
**Status**: Draft. Not implemented. No file was moved and no import rewritten by writing it.
**Input**: Camden, 2026-09-27. Evidence base: [MIGRATION-INVENTORY.md](../../../docs/implementation/spec-040/MIGRATION-INVENTORY.md)
(977 lines, written 2026-09-26; cited below as **INV §n**), plus the measurements
in [§ Measured facts](#measured-facts-2026-09-27) that this spec adds where the
inventory was incomplete.

## Hard preconditions

1. **Specs 036, 041 and 043 have merged.** 040 implements after all three. 043
   creates the minimal `pyproject.toml` marker and `scripts/_project.py`, and
   puts the ledger root on marker-based resolution before 040 moves anything
   (043 §6).
2. **Single-threaded, with no other lane open.** 040 touches an import line in
   nearly every Python file in the repository. Any concurrent branch conflicts
   with it everywhere, and a conflict resolved by hand is exactly how a flat
   import survives (see AC-5).
3. **The pre-migration suite is fully green** (0 failed, 0 errors) at the commit
   named `PRE` (T003). A red baseline gives AC-2 nothing to compare against, so
   040 does not start.

---

## 1. The hardest problem: the lifetime trial ledger

### 1.1 What is at stake

`docs/trials/trials.jsonl` is the append-only, hash-chained lifetime trial ledger.
The spec 033 DSR gate reads its effective trial count from it (Rule 15;
`SCOPE-V1.md` §5, where DSR is "against the full lifetime trial count"). INV §6.5
found that runner strings such as `"scripts/model_cv.py:tune_on_fold"` are
written into it. A module rename changes those strings.

### 1.2 How the chain actually works (read from `scripts/trial_registry.py`, 2026-09-27)

- `TrialLedger.verify()` recomputes each record's `record_hash` from the record
  itself and checks `prev_hash` against the previous record. It also recomputes
  `config_hash = digest(config)`, where `config` includes the `runner` string.
  Every historical record is **self-contained**. Its validity depends only on its
  own bytes and its predecessor's hash.
- The lifetime count, `n_post_ledger`, is the number of `started` events with
  `role == "candidate"`. **Nothing groups, deduplicates or joins by `runner` or by
  `config_hash`** (verified by grep over `scripts/`, `reports/` and `tests/`).

Consequence: new rows that carry new runner strings leave every historical hash
valid and every historical count unchanged. **Only editing history could break
the chain or the count.**

### 1.3 The rule (non-negotiable)

**THE LEDGER IS NEVER REWRITTEN.** An append-only hash-chained ledger loses its
entire purpose the moment its history is edited, and the DSR gate depends on it.
Therefore:

- **Historical rows keep their original `scripts/...` runner strings,
  byte-for-byte.** Every byte under `docs/trials/` at `PRE` is identical after the
  migration: `trials.jsonl`, `trials.head.json`, `backfill/*.json` (whose
  approvals are pinned by SHA-256 and also contain `scripts/` strings), and any
  return sidecars.
- **New rows written after the migration use the new strings** (§1.5).
- **A documented mapping records the rename**, so the two eras can be
  reconciled: `docs/trials/runner-renames.json`, the only new file under
  `docs/trials/` (§1.6).
- **Acceptance tests prove** that the chain validates end to end across the
  boundary and that the lifetime count is unchanged (AC-4).

### 1.4 The real danger: three silent ledger failures an "imports-only" migration would ship

These are worse than the runner strings, and the inventory lists only the first
one as a ledger issue:

| # | Site | What an imports-only migration does | Why it is silent |
|---|---|---|---|
| L1 | `trial_registry.py:19` `ROOT = Path(__file__).resolve().parents[1]` | In `src/qmb/`, `ROOT` becomes `src/`. The production ledger path becomes `src/docs/trials/trials.jsonl`, which does not exist | `verify()` on a missing file returns `{"events": [], "n_post_ledger": 0}`, with no error. **The DSR gate's post-ledger count drops from 87 to 0.** The next real trial writes a *new* chain from the zero hash in `src/docs/trials/`, forking the lifetime ledger |
| L2 | `trial_registry.py:96` `for folder in ("scripts", "reports/api")` in `source_identity` | `scripts/` no longer exists, so `rglob` yields nothing | Every new trial's `source_tree_hash` silently stops covering the research code. It then hashes only `reports/api` and the requirements files |
| L3 | 12 `research_config("scripts/…")` literals in 5 modules | Left alone, new rows name files that no longer exist | The rows still verify. Their provenance is simply false |

L3 is larger than INV §6.5 reports. INV lists 5 strings. The source contains
**12 call sites and 8 distinct strings**: `feature_set_comparison.py:167`,
`logistic_baseline.py:318` and `:332`, `ma_crossover_backtest.py:101`, `:113`
and `:227`, `model_cv.py:330` and `:461`, and `multi_ticker_comparison.py:137`,
`:148`, `:258` and `:286`.

### 1.5 Resolution

- **R1 (L1). Project root by marker, never by depth.** A new module,
  `src/qmb/_project.py`, provides `project_root() -> Path`:
  1. If `QMB_PROJECT_ROOT` is set, that directory. It must contain the marker, or
     `ProjectRootNotFound` is raised.
  2. Otherwise, the nearest ancestor of `Path(__file__).resolve()` that contains
     the marker. This covers the editable install and any run inside the checkout.
  3. Otherwise, raise `ProjectRootNotFound`, naming both places it searched.

  **Marker**: a `pyproject.toml` whose `[project] name` is `quant-ml-bot`, read
  with stdlib `tomllib`.

  **The current working directory is deliberately never consulted.** With two
  clones, a cwd lookup would silently pair one clone's code with the other
  clone's ledger and data. A non-editable install outside the checkout must set
  `QMB_PROJECT_ROOT`, or it fails loudly at import.
- **R2 (L2).** `source_identity` hashes `("src/qmb", "reports/api")`. Old rows keep
  the old hash scope. The mapping file records both scopes.
- **R3 (L3).** Each of the 12 literals becomes `"src/qmb/<module>.py:<callable>"`.
  The field keeps its existing format, a **repo-relative path plus the callable**.
  The mapping is therefore one prefix rule, and a reader can open the file the
  string names. See D-1 for the alternative spelling.

### 1.6 The mapping document: `docs/trials/runner-renames.json`

It is written once, in the migration, from values re-measured at T004. The
values below are EXAMPLE — NOT A RESULT: placeholders until T004.

```json
{
  "spec": "040-installable-package",
  "boundary_records": 174,
  "boundary_head": "<record_hash of record #boundary_records, from T004>",
  "boundary_n_post_ledger": 87,
  "runner_prefix_map": {"scripts/": "src/qmb/"},
  "source_identity_folders": {"before": ["scripts", "reports/api"], "after": ["src/qmb", "reports/api"]},
  "rule": "Records 1..boundary_records are pre-040 and are never rewritten. Later records use the after-values."
}
```

The file names the boundary by **record hash**, so an attempt to "tidy" history
cannot keep the boundary check green (AC-4 red proof R-4b).

### 1.7 Alternatives considered

- **Rewrite history with new strings and re-chain.** Rejected, and forbidden by
  §1.3. It also breaks the SHA-256-pinned backfill approvals.
- **Keep writing `scripts/...` strings forever.** Rejected. There is no mapping to
  maintain, but every new row would name a file that does not exist. That is a
  silent Rule 11 provenance defect.
- **Dotted form, `qmb.model_cv:tune_on_fold`** (D-1). It is valid, but the two eras
  would then differ in format as well as prefix, so reconciling them needs two
  rules instead of one.

---

## 2. Current state and target state

**Current (INV §1, §2, §5).** `scripts/` holds 31 flat modules and no
`__init__.py`. They import each other flat (`from data import …`): 176 statements
in 61 files. They are importable only through `sys.path.insert` in
`tests/context.py`, plus seven other insert sites (INV §2.1). There is no
`pyproject.toml`. The Python ≥ 3.12 floor (NumPy 2.5.2's `Requires-Python`) is
stated only in README prose. `LICENSE` exists and holds the MIT text (verified
2026-09-27), but nothing declares it as package metadata.

**Target.**

- `src/qmb/` holds the **29** non-scratch modules and an `__init__.py`. That file
  contains only a docstring, so importing the package has no side effects.
- The two scratch modules go to `scratch/` at the repo root (D-2). They import
  nothing from the project (verified 2026-09-27), and their
  `Path(__file__).parents[1]` still resolves to the repo root from there, so they
  move with **zero edits**.
- All intra-project imports are **absolute**: `from qmb.data import …`, or
  `from qmb import data` for `import data`. Relative imports are not used. That
  keeps AC-1's classifier to one rule, and it keeps the
  `exec(compile(source))` mutation engine (INV §6.4) independent of `__package__`.
- `pyproject.toml` (§4). `tests/context.py` is deleted. `tests/repo_paths.py` (a
  new non-test helper) exports `REPO_ROOT` and `PACKAGE_DIR` and **does not
  touch `sys.path`**.
- Every `sys.path.insert` for `scripts/` in `tests/` and `reports/` is deleted.
- `qmb` is resolvable only through the installed distribution.

## 3. Audit Finding 56 (`reports/api/routes/{data,diagnostics,ml_rundown}.py`, `parents[2]`)

**This spec fixes it, by deletion.** All six route and main preambles
(INV §2.1 item 4, and item 5 with its five routes) exist only to put `scripts/` on
`sys.path`. With `qmb` installed, each 4-line block is deleted. The wrong
`parents[2]` then no longer exists to be corrected.

`reports/api/main.py:13` keeps its `REPO_ROOT` line, because `DIST_DIR` (`:26`)
uses it. It lives in `reports/api/`, which does not move, so it stays correct.

---

## 4. `pyproject.toml` (created by 043 as a minimal marker; 040 edits it into this normative content)

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "quant-ml-bot"
version = "1.0.0"
description = "Quantitative research framework on free data: point-in-time features, purged walk-forward CV, deflated Sharpe, modeled costs."
readme = "README.md"
requires-python = ">=3.12"
license = "MIT"
license-files = ["LICENSE"]
authors = [{ name = "Camden Stroh" }]
dynamic = ["dependencies"]

[project.scripts]                                  # INV §3.2, minus the two scratch modules
qmb-sanity                 = "qmb.data_pipeline_sanity_check:main"
qmb-return-stats           = "qmb.return_stats:main"
qmb-ma-backtest            = "qmb.ma_crossover_backtest:main"
qmb-logistic-baseline      = "qmb.logistic_baseline:main"
qmb-multi-ticker           = "qmb.multi_ticker_comparison:main"
qmb-feature-set-comparison = "qmb.feature_set_comparison:main"
qmb-feature-diagnostics    = "qmb.feature_diagnostics:main"
qmb-stationarity           = "qmb.stationarity_check:main"
qmb-autocorrelation        = "qmb.autocorrelation_check:main"
qmb-walk-forward-cv        = "qmb.walk_forward_cv:main"

[tool.setuptools.dynamic]
dependencies = { file = ["requirements.txt"] }

[tool.setuptools.packages.find]
where = ["src"]
include = ["qmb", "qmb.*"]

[tool.pytest.ini_options]
# reports/ is a repo-local application, not part of the distribution. This makes
# `reports.api` importable in tests from any cwd. It is NOT how qmb is found:
# qmb lives under src/, which is not on this path.
pythonpath = ["."]
```

- **The first five script names are INV §3.1's.** The other five follow the same
  pattern. All ten `main` functions take no required arguments (verified
  2026-09-27; `feature_set_comparison.main(max_workers=None)`).
- **Why no build backend beyond setuptools is needed.** setuptools ≥ 77 alone
  provides every capability this spec uses: src-layout discovery, PEP 660
  editable installs, dependencies read dynamically from `requirements.txt`,
  console-script entry points, and PEP 639 `license = "MIT"`. Hatchling, flit or
  poetry would add a second tool and no capability this spec uses.
- **No runtime dependency is added.** setuptools is a build-time requirement,
  fetched into pip's isolated build environment. It is not installed into the
  runtime environment (it is absent from the local venv today, 2026-09-27).
- **Tradeoff of exact pins as install requirements.** Exact `==` pins in
  distribution metadata make the package hostile to co-installation. That is
  accepted: `quant-ml-bot` is a reproducible artifact, not a library, and
  reproducibility is the point.
- **`version = "1.0.0"`** must equal the tag Camden creates after AC-1 to AC-5
  pass.

---

## 5. Named breakage sites (each is a task with before/after in `tasks.md`)

These survive a pure import rewrite and break later. They are promoted from INV §6
and from this spec's own measurements.

| Group | Sites | Task |
|---|---|---|
| `__file__` depth | `data.py:52`, `feature_set_comparison.py:866-868`, `trial_registry.py:19-20`, `trial_runner.py:68` (inherits `ROOT`), `autocorrelation_check.py:14`, `stationarity_check.py:17` | T020–T025 |
| Ledger identity | `trial_registry.py:96` (L2); 12 runner literals (L3) | T026–T027 |
| AST/introspection tests | `test_targets.py:605-643`; `test_order_gateway.py:33-49`, `:135-147`; `test_033_trial_instrumentation.py:7-53` plus `tests/fixtures/spec_033/runner_inventory.json` (19 paths); `test_collection_guards.py:35-48` | T030–T033 |
| Import-boundary helpers (first-segment reduction, so `qmb.x` reads as `qmb` and `from . import x` is skipped) | `test_estimators.py:576`, `test_ml_signal.py:693`, `test_model_cv.py:1007`, `test_portfolio_risk.py:274`, `test_targets.py:620` | T046 (with T030) |
| Scanning guards without a count | `test_no_fabricated_values.py:157`, `:163`; `test_collection_guards.py:35`, `:41` | T047, T033 |
| `SCRIPTS_DIR` path users (not in INV) | `test_estimators.py:571`, `test_feature_set_comparison.py:670`, `test_ml_signal.py:688`, `test_model_cv.py:1002`, `test_portfolio_risk.py:269`, `:475` (package dir); `test_033_trial_instrumentation.py:7`, `test_033_dsr.py:71`, `test_033_trial_ledger.py:125`, `:160`, `:180`, `test_trial_registry.py:7`, `spec033_pbo_profile.py:31-32` (**`.parent` used as the repo root**) | T034 |
| Dynamic imports | `tests/spec033_support.py:18-22` (`find_spec` with a bare string) | T035 |
| Mutation engines | `mutation_support_019.py`, `mutation_support_032.py` (8 suites); `tests/mutation/run_mutation_check.py:51`, `:63`; `run_spec_018_mutants.py:22-26` | T036–T038 |
| Spawned workers | `feature_set_comparison.py:722-724` (`spawn`) | T039 |
| Bootstrap deletions | `tests/context.py`; `test_walk_forward_cv.py:10`, `:281-283`; `test_020_unadjusted_price_data.py:15-18`; `reports/api/main.py:14-16`; five route blocks; 34 `context` imports (INV §1.6) | T040–T042 |
| User-facing text | `multi_ticker_comparison.py:399-402` (sys.path one-liner in an error message); `README.md:104-108` plus the setup line; `CLAUDE.md` layout, module table and Tests section; `.github/workflows/test.yml`, `claude.yml` | T043–T045 |
| Added by 036/041 | `tests/test_unadjusted_caller_wiring.py:10` (036, in progress on 2026-09-27) and anything T005 finds | T005 |

**A rule for every scanning guard.** A guard that walks a directory (`rglob`) MUST
assert that it scanned at least the expected number of files. After the move, a
guard left pointing at `scripts/` walks an empty or missing directory and
**passes**. That is the exact failure Rule 12 names: a gate aimed at something
its target no longer contains.

**Deliberately unchanged, and enforced byte-identical by AC-1:**
- `.specify/specs/**` other than 040's own directory. These are historical
  records; CLAUDE.md says older specs "record the runner used at that time".
- `docs/audit-*/**`, including `probes.py`. It is a dated audit artifact, and it
  is no longer runnable as-is after 040.
- `docs/implementation/**`, and `docs/trials/**` except the one new mapping file.
- `tests/conftest.py`. `tests/` stays at the top level, so `parents[1]` stays
  correct.
- `.claude/hooks/run-tests.ps1`.
- Docstrings and comments that mention `scripts/` in prose.

---

## 6. Acceptance criteria

A migration touching about 60 files and 176 import statements cannot be reviewed
line by line, and CLAUDE.md treats reviewability as a hard constraint. These
criteria make the diff **mechanically checkable**. Camden reviews the
human-sized parts: the allowlist, `pyproject.toml`, `_project.py`, the new tests
and the mapping file. The filter reviews the rest.

### AC-1 — The diff contains nothing but the declared change

**Claim.** No changed line exists that is not one of the following:

- (a) an import line rewritten by exactly `M → qmb.M`, for M in the 29 package
  modules;
- (b) a deleted bootstrap line (a `context` import or a `sys.path` insert listed
  in §5);
- (c) an entry in the enumerated allowlist
  `.specify/specs/040-installable-package/ac1-allowlist.json` (exact path, exact
  before, exact after);
- (d) a `scripts/` → `src/qmb/` prefix substitution, and nothing else on that line,
  in the prefix files the allowlist names;
- or it lies in a file the manifest (§7) declares moved, new or deleted.

**Command (Camden, who owns Git; expected output is empty, exit 0):**

```powershell
git diff --find-renames=50% --unified=0 <PRE> <POST> -- . ':(exclude).specify/specs/040-installable-package' | python .specify/specs/040-installable-package/tools/ac1_filter.py --stdin
```

**Command (agent, no Git; compares a read-only export of `PRE` with the working
tree; expected output is empty, exit 0):**

```powershell
python .specify/specs/040-installable-package/tools/ac1_filter.py --before <PRE-export-dir> --after .
```

For every offending line, the filter prints `path:line: <why>`, and it exits 1 if
anything was printed. It prints every changed path not in the manifest (for
example `docs/trials/trials.jsonl: path not in 040 manifest`).

**Red proof** (`tests/test_040_ac1_filter.py`, isolated trees, no Git). Each case
asserts the exact message:

| Case | Planted | Expected |
|---|---|---|
| control | an exact migration of a 3-module mini tree | empty, exit 0 |
| logic edit | `TRADING_DAYS_PER_YEAR = 252` → `253` in a moved `constants.py` | `src/qmb/constants.py:<n>: non-import change` |
| wrong target | `from data import x` → `from qmb.metrics import x` | `…: import rewrite is not M → qmb.M` |
| history edit | one byte changed in `docs/trials/trials.jsonl` | `docs/trials/trials.jsonl: path not in 040 manifest` |
| stray file | a new `src/qmb/test_helper.py` | `…: path not in 040 manifest` |

### AC-2 — The same suite passes, at the same count

**Command:**

```powershell
python -m pytest tests -q -p no:cacheprovider --junitxml=.specify/specs/040-installable-package/artifacts/post.xml
python .specify/specs/040-installable-package/tools/compare_junit.py artifacts/pre.xml artifacts/post.xml
```

- **Pass**: every node ID in `pre.xml` is present in `post.xml` and passed.
  `post − pre` is exactly the node IDs of the new test modules listed in §7. There
  are 0 failures and 0 errors.
- **The baseline is re-measured at T003, immediately before migrating, at commit
  `PRE`.** It is never copied from a document. It must be fully green.
- *Observed on 2026-09-27, for context only, NOT the baseline:* Windows, Python
  3.13.14, a working tree with uncommitted changes, pre-036: **885 passed, 2
  failed, 1386 subtests passed, in 387.84 s**. The failures were
  `test_reports_api.py::TestReportsApi::test_backtest_tearsheet` and
  `test_clean_clone_037.py::test_changed_baseline_funding_mutant_is_killed`.
  That tree does not meet precondition 3. The raw log was kept outside the
  repository, in session scratch.

### AC-3 — Installed, and run from somewhere else. This is the reason the spec exists.

`tests/context.py` works only because it inserts a path computed from its own
location. Delete it, move out of the repository, and nothing makes `scripts/`
importable. The installed distribution must be what makes `qmb` importable.

**AC-3a (editable).** Run from a fresh venv:

```powershell
python -m venv $env:TEMP\qmb-ac3\venv
$py = "$env:TEMP\qmb-ac3\venv\Scripts\python.exe"
& $py -m pip install -r C:\GitHub\Quant-ML-Bot\requirements-dev.txt
& $py -m pip install -e C:\GitHub\Quant-ML-Bot
New-Item -ItemType Directory -Force $env:TEMP\qmb-ac3\elsewhere | Out-Null
Set-Location $env:TEMP\qmb-ac3\elsewhere
& $py -c "import qmb, importlib.metadata as m; print(qmb.__file__); print(m.version('quant-ml-bot'))"
& $py -c "import data"          # MUST fail: ModuleNotFoundError. No flat name leaks into site-packages (INV §4)
& $py -m pytest C:\GitHub\Quant-ML-Bot\tests -p no:cacheprovider
```

- **Pass**: `qmb.__file__` is under `…\Quant-ML-Bot\src\qmb\` and the version is
  `1.0.0`. `import data` raises `ModuleNotFoundError`. The suite result equals
  AC-2's.

**AC-3b (non-editable).** The same, with `pip install C:\GitHub\Quant-ML-Bot` (a
built wheel) and `$env:QMB_PROJECT_ROOT = "C:\GitHub\Quant-ML-Bot"`. An editable
install keeps `__file__` inside the checkout, so it cannot catch a depth-based
"fix" such as `parents[2]`. A wheel install can. **Pass**: the same suite result.
With `QMB_PROJECT_ROOT` unset, `python -c "import qmb.data"` raises
`ProjectRootNotFound`.

**AC-3c (entry points).** From `elsewhere`, every `[project.scripts]` entry loads:

```powershell
& $py -c "from importlib.metadata import entry_points as e; [x.load() for x in e(group='console_scripts') if x.value.startswith('qmb.')]; print('ok')"
```

**CI.** `.github/workflows/test.yml` gains `pip install -e .` and runs the suite
as `cd "$RUNNER_TEMP" && python -m pytest "$GITHUB_WORKSPACE/tests"`. That makes
AC-3a a permanent gate, not a one-time check.

### AC-4 — The ledger chain validates, and the lifetime count is unchanged

- **AC-4a (bytes).** Every file under `docs/trials/` at `PRE` has the same SHA-256
  after the migration. The only new path there is `runner-renames.json`. 043 adds no
  file under `docs/trials/`, so the `PRE` state already includes every 043 file
  state. This is enforced by AC-1, and by the T004 hash listing compared at T061.
- **AC-4b (production, read-only, in the suite).** `tests/test_040_ledger_boundary.py`:
  - `TrialLedger().verify()`, imported as `qmb.trial_registry`, succeeds.
    `TrialLedger().path` equals `REPO_ROOT / "docs/trials/trials.jsonl"`.
  - Record number `boundary_records` has `record_hash == boundary_head`.
  - `n_post_ledger`, counted over records 1 to `boundary_records`, equals
    `boundary_n_post_ledger`.
  - Every runner in records 1 to `boundary_records` starts with `scripts/`, and
    every later one starts with `src/qmb/`.
  - Every historical runner path, mapped through `runner_prefix_map`, names a file
    that exists in `src/qmb/`. The two eras reconcile.
  - The test stays valid as real trials are appended later, because it pins the
    prefix of the chain, not its length.
- **AC-4c (across the boundary, synthetic copy).** Copy `docs/trials/` to
  `tmp_path` and open it as `TrialLedger(tmp_path, synthetic=True)`. Append one
  `candidate` trial through the migrated `research_attempt(research_config("src/qmb/…"))`
  path, then `verify()` the whole chain:
  - records 1 to `boundary_records` are byte-identical;
  - the new record's `prev_hash == boundary_head`;
  - `n_post_ledger == boundary_n_post_ledger + 1`;
  - the new record's `source.source_tree_hash` covers `src/qmb/*.py`.
- **AC-4d (backfill).** The spec 033 backfill validation over `docs/trials/backfill/`
  returns the same approved `N_backfill` as at `PRE`.
- **Measured at `PRE`-equivalent, 2026-09-27** (to be re-measured at T004):
  174 records; head `99a494e810955da902fa890688aa8d0f12049c3c321cb4c6f2bef2977564a679`;
  `n_post_ledger` 87; historical runners are `scripts/model_cv.py:tune_on_fold`
  (88 events), `scripts/model_cv.py:grid_point` (84) and
  `scripts/ma_crossover_backtest.py:run_backtest` (2).

**Red proof (in `test_040_ledger_boundary.py`, on copies, never on the production
file):**

| Case | Planted | Expected |
|---|---|---|
| R-4a naive tidy | Replace `scripts/` → `src/qmb/` in the copied `trials.jsonl` | `verify()` raises `ValueError("record 1: config hash")` |
| R-4b consistent rewrite | The same, plus re-hash and re-chain every record and rewrite the anchor, so `verify()` passes | The boundary check fails with `boundary head mismatch`. AC-1 prints `docs/trials/trials.jsonl: path not in 040 manifest`. **This case shows the chain alone cannot detect a careful rewrite, which is why AC-1 and the pinned boundary hash exist** |
| R-4c L1 shipped | In a copied tree, `ROOT = Path(__file__).resolve().parents[1]` is left in `trial_registry.py` | The child process reports `TrialLedger().path` under `src/docs/trials/`, and the assertion `path == REPO_ROOT/"docs/trials/trials.jsonl"` fails |
| control | An unmodified copy | Every check passes |

### AC-5 (Rule 12) — A planted flat import that AC-3 must catch

**The defect.** In an isolated copy of the migrated tree, exactly one import is
reverted, in `src/qmb/metrics.py`:

```python
from qmb.constants import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR   # correct
from constants import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR       # planted
```

**Why it is plausible.** It is the line a rewrite tool skips (a second import
from a different project module in the same file), or the one a hand-resolved
merge conflict restores. It is also invisible in a diff of this size unless AC-1
runs. It survives in-repo whenever anything still puts `src/qmb` on `sys.path`: a
forgotten insert, or `pythonpath = ["src/qmb"]` in the pytest config. The
planted scenario includes that masking entry, so the in-repo run is shown
**green**, and only AC-3 goes red.

**Expected red, under AC-3a against the planted copy:**

```
ERROR collecting tests/test_metrics.py
  src/qmb/metrics.py:17: in <module>
    from constants import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR
E   ModuleNotFoundError: No module named 'constants'
…
Interrupted: <n> errors during collection
```

The pytest exit code is 2. Every test module that imports `qmb.metrics`, directly
or through another module, errors.

**In-suite proxy** (`tests/test_040_installability.py::test_import_sweep_from_foreign_cwd`,
parametrized `control` / `planted_flat_import`):

- It launches `python -P -c "<import every qmb module>"` with `cwd=tmp_path` and
  `PYTHONPATH=<copy>/src`, then asserts that the child's `qmb.__file__` is inside
  the copy (non-vacuity: it proves the copy was tested, not the installed tree).
- **planted**: return code 1, and stderr contains
  `No module named 'constants'` and `qmb` + `metrics.py`.
- **control**: return code 0.

Recorded one-time evidence: AC-3a run against the planted copy, saved to
`artifacts/ac5-red.txt`.

### AC-6 — Spawned workers import the package

`tests/test_040_installability.py::test_spawn_worker_from_foreign_cwd` starts a
fresh interpreter with `cwd=tmp_path` and no repo entry on `sys.path`. It runs
`compare_all_entries_parallel` with 2 workers on the smallest existing
equivalence fixture, under `spawn`. It asserts:

- the run completes;
- each worker's `_worker_init` ran;
- the pickled task callable's `__module__ == "qmb.feature_set_comparison"`;
- no worker has a top-level `feature_set_comparison` in `sys.modules`.

---

## 7. File manifest (closed at T006; AC-1 treats anything else as an error)

- **Moved, content changed only per AC-1 (a) to (d)**: `scripts/<m>.py` →
  `src/qmb/<m>.py` for the 29 modules in INV §5 rows 1-21 and 24-31, **and**
  `scripts/_project.py` → `src/qmb/_project.py` (created by 043, so it is a
  move and not a new file). The module set in AC-1 (a) therefore gains
  `_project`; T005/T006 re-derive the set.
- **Moved, byte-identical**: `scripts/scratch_aapl_correlations.py`,
  `scripts/scratch_multiticker_collinearity.py` → `scratch/`.
- **New**:
  - `src/qmb/__init__.py`
  - `docs/trials/runner-renames.json`
  - `tests/repo_paths.py`
  - `tests/test_040_installability.py`
  - `tests/test_040_ledger_boundary.py`
  - `tests/test_040_ac1_filter.py`
  - `.specify/specs/040-installable-package/{tools,artifacts}/**` and
    `ac1-allowlist.json`
- **Deleted**: `tests/context.py`, and the now-empty `scripts/`.
- **Edited**: exactly the files named in §5's table, each limited to the
  allowlist, **and** `pyproject.toml` (created by 043 T020; T015 edits it into
  §4's content and leaves `[project] name` unchanged, since that name is the
  marker).

## Decisions

- **D-1. Runner string format.** Recommended: `src/qmb/<module>.py:<callable>`,
  which is the same format as history with one prefix rule. The commissioning
  prompt said "qmb/…". If Camden prefers `qmb/<module>.py:…` or the dotted form,
  change only §1.5 R3 and the mapping's `runner_prefix_map`. Everything else
  stands.
- **D-2. Scratch modules** go to `scratch/` at the repo root. They are excluded
  from the distribution by `packages.find where = ["src"]`, moved byte-identical,
  and given no entry points. They are exploratory, and shipping them inside `qmb`
  would publish unreviewed code under the package name (INV §4 "ABERRANT").
- **D-3. Project-root resolution** is by marker and never by cwd (§1.5 R1).
- **D-4. Finding 56** is fixed by deleting the preambles (§3).

## Assumptions

- No strategy result is produced or reported, so Rules 2, 3, 4, 13 and 15 are not
  engaged. The ledger counts in AC-4 are registry metadata, not performance
  figures.
- Local verification runs on Windows. CI runs Ubuntu with Python 3.12. The AC-3
  commands are shown in PowerShell, and the CI step is their POSIX equivalent.

## Out of scope

- Renaming any module, splitting `data.py`, or any refactor beyond §5.
- Rewriting old specs, audit artifacts or the ledger.
- Guarding production-ledger writes, and the alias-assignment bypass note once
  kept here: see [spec 043](../043-ledger-write-guard/spec.md). 043 lands
  before 040, and its §6 lists the amendments 040 needs at that point.
- Publishing to PyPI.
- The repo split in ADR 0001 (v1.0 DoD item 6).
