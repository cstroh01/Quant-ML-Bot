# Tasks: Ledger write guard

**Input**: [spec.md](spec.md), [plan.md](plan.md), [NOTE-for-ledger-write-guard-spec.md](NOTE-for-ledger-write-guard-spec.md)
**Organization**: single-threaded. Template phases do not authorize Git
operations or parallel agents. **T001 recorded Camden's choices for D-1 to D-5 on
2026-09-28; implementation still waits on the spec's hard preconditions.** Tasks marked *(per D-n)* take the chosen
option's shape.

Line numbers are as of 2026-09-28. **Every site is anchored by its exact text**,
and T004 re-locates them.

**Standing rule for every task:** no process that imports research or backtest
code runs against the real repository outside pytest's conftest isolation. Any
run that could reach a write path runs in a copy (T010), with the tripwire on.

---

## Phase 0: Decisions, preconditions and measurement

- [x] T001 **Camden decides D-1 to D-5** (spec §4). Decided 2026-09-28 and
  recorded in spec §4: D-1 B, D-2 A1, D-3 (a) 1 and (b) iii, D-4 a + c in one
  shared helper, D-5 a.
- [x] T002 **Measure the real ledger, read-only** (hashing and `verify()` only;
  nothing that can call `start` or `finish`):
  - the line count and SHA-256 of `trials.jsonl`;
  - the content and SHA-256 of `trials.head.json`;
  - that `returns/` is absent;
  - the SHA-256 of every `backfill/*.json`;
  - `verify()` head and `n_post_ledger`.

  Save the results to `artifacts/ledger-pre.json`. Stop if they differ from
  spec hard precondition 2.
- [x] T003 Baseline: run `python -m pytest tests` and record the exit code and
  the passed, failed and error counts. It must be 0 failed and 0 errors.
  Re-check the T002 hashes afterwards.
- [x] T004 **Re-inventory** with the spec §2 search patterns. Update §2's
  tables if anything moved or appeared. Treat any new writer or entry point as
  in scope.

## Phase 1: Harness and gates, red-proven on today's code

- [x] T010 `tests/ledger_copy_support.py` (helper name, not a test module name):
  - `make_copy(dst)` copies the repository except `data/cache/`, `venv/`,
    `node_modules/`, `.git/` and `__pycache__`, and asserts that `dst` is not
    inside the real repository.
  - `manifest(root)` maps each path under `docs/trials/` (recursively) to its
    SHA-256, with absence recorded explicitly.
  - `child_env()` is `os.environ` minus `SPEC033_SYNTHETIC_ROOT` and minus
    every D-1 enablement.
  - `tripwire()` is a context manager that hashes the real `docs/trials/`
    before and after and raises, naming each changed path.
- [x] T011 `tests/ledger_guard_child.py` (helper name) plus
  `tests/test_043_entry_points.py`:
  - The child patches data access to labelled synthetic frames:
    `download_market_data` for E2–E4, and a synthetic unadjusted bundle for
    E1 (via `tests/unadjusted_fixtures.py`).
  - It then runs E1–E4's `main`, and E5 through `TestClient` `GET /tearsheet`.
  - The test asserts AC-1 per entry point.
  - **Observe it red on today's code for the right reason**: each entry
    point's copy manifest changes. Record which files changed for each entry
    point, and the per-request E5 counts (expected 44 records and up to 22
    sidecars).
- [x] T012 `tests/test_043_incident.py`: AC-2, a direct
  `multi_ticker_comparison._baseline_rows` call in a child in the copy.
  **Observe it red**: 6 records and 3 sidecars for `seed_count=2`.
- [x] T013 `tests/test_043_enabled_control.py`: AC-3, the enabled path in a
  copy. It is green today only for the D-1 A shape, and red until T025 for B
  and C. Record which.
- [x] T014 `tests/test_043_project_root.py`: AC-5's cases plus the planted
  depth-based `ROOT`. It stays red until T020–T022.
- [x] T015 Tripwire proof: `tripwire()`, fed a stand-in "real" directory with
  one planted appended record, raises and names the path (the AC-4 and AC-8
  red half).

## Phase 2: Implementation, in review-unit order

### U1: Root (FR-006, D-5)

- [x] T020 `pyproject.toml` *(per D-5)*. For D-5a exactly:
  ```toml
  [project]
  name = "quant-ml-bot"
  version = "0.0.0.dev0"
  ```
- [x] T021 `scripts/_project.py`: `project_root()` and `ProjectRootNotFound`,
  exactly as spec FR-006 describes (stdlib `tomllib`, no caching, cwd never
  read). Keep the contract identical to spec 040 §1.5 R1, so that 040 T016
  becomes a move.
- [x] T022 `scripts/trial_registry.py:19` (`ROOT = Path(__file__).resolve().parents[1]`)
  → `ROOT = project_root()`. `TrialLedger.__init__`'s production and
  synthetic root checks (`:171-172`) are otherwise unchanged. T014 turns
  green.

### U2: Write guard (FR-001 to FR-005)

- [x] T023 Write layer: `TrialLedger.start` (`:236`) and `finish` (`:245`),
  for a non-synthetic ledger at `ROOT`, call `_require_production_enabled()`
  as their **first statement**, before `canonical_config`, `serialized()` or
  anything else. `trial_backfill.write_backfill` (`:57`) makes the same check
  first when `root` resolves to `ROOT`. Put the refusal type
  `LedgerWriteRefused` and the check in `trial_registry.py`, so the write
  layer has no dependency on `trial_runner`.
- [x] T024 Early layer: `trial_runner.current_ledger()` (`:17-31`) returns
  the production ledger only when enablement holds, and otherwise raises
  `LedgerWriteRefused`. `research_attempt` (`:114`) therefore refuses before
  its body runs. The invalid-synthetic-context `ValueError` (`:24-25`) is
  kept, and never falls through to production (FR-005).
- [x] T025 Enablement *(per D-1)*. For D-1 B:
  - `production_recording(reason: str)` is a context manager backed by a
    context variable.
  - E1–E4 CLIs take `--record-trial`. Without it, `main` refuses **before**
    loading data (the preflight), with FR-003's message.
  - E4 passes an explicit enable token to its spawned workers
    (`feature_set_comparison.py`'s pool initializer or task arguments). The
    workers enter `production_recording` only with that token.
  - No environment variable enables production.
- [x] T026 Re-run T011 to T013. AC-1, AC-2 and AC-3 are green. Then plant the
  removal of T023's check in a copy and show that AC-2 goes red: the write
  layer is load-bearing on its own.

### U3: Route (FR-009, D-2)

- [x] T027 `reports/api/routes/backtest.py` *(per D-2)*. For D-2 A1:
  - GET computes nothing that records.
  - It looks up a recorded trial by the configuration's `config_hash` and
    returns 200 from its sidecar, or 409 naming the recording command.
  - The recording command is the E1-style CLI under D-1.
  - AC-10 green. Red on pre-043 code, observed at T011.

### U4: Drivers and conftest (FR-008, FR-010, D-4)

- [x] T028 `tests/conftest.py:24-25` and `:37-40`: snapshot and compare a
  whole-tree manifest of `docs/trials/` (`ledger_copy_support.manifest`), and
  name each changed path. Red proof on a copy: a test run that writes
  `docs/trials/returns/x.jsonl` makes shutdown raise and name it (AC-6).
- [x] T029 Drivers *(per D-4)*. For D-4 a + c, a shared helper in
  `tests/mutation/`:
  - copy `tests/conftest.py` and `pyproject.toml`;
  - build the child environment with `child_env()`;
  - wrap the whole run in `tripwire()`.

  Apply the helper to `run_spec_018_mutants.py:22-26`,
  `run_mutation_check.py:51` and `run_unadjusted_wiring_mutants.py`. Run each
  driver: green control, killed mutants, tripwire silent (AC-8).

### U5: Marker (FR-011, D-3(b))

- [ ] T030 *(per D-3(b))*. For iii:
  - `trial_runner.py`:
    `SYNTHETIC_LABEL = "EXAMPLE — NOT A RESULT"`, ASCII-escaped in the
    source, compared exactly at `:24`.
  - `tests/conftest.py:20` and `:58`, and `tests/spec033_support.py:7`,
    import it.
  - A test pins that `trial_runner.py`'s bytes are ASCII on the defining line.
  - AC-7's red cases: U+FFFD, and cp1252 `0x97`.

### U6: Alias bypass (FR-012, D-3(a)), only if D-3(a) is 1

- [ ] T031 `tests/test_033_trial_instrumentation.py:18-23`: resolve
  `Name = <primitive>` assignments and
  `getattr(<module>, "<primitive>")` calls to their primitive. AC-9's planted
  cases are red before the change and flagged after; the clean tree is the
  green control.

## Phase 3: Gates, all required, in this order

- [ ] T032 **AC-6**: run `python -m pytest tests`. Record the exit code and the
  passed, failed and error counts. The target is 0 failed and 0 errors, with
  passed equal to T003 plus the new tests.
- [ ] T033 D-5 side effect: in T032's output, the pytest header's `rootdir:`
  and `configfile:` lines match T003's, or any difference is explained and
  shown harmless: same node IDs, same counts. The **collected test count** is
  unchanged by the presence of `pyproject.toml` (903 when D-5 was decided;
  compare against T003's recorded baseline).
- [ ] T034 **AC-4**: re-measure T002 read-only and compare it to
  `artifacts/ledger-pre.json`. Every value is identical.
- [ ] T035 AC-1, AC-2, AC-3, AC-5, AC-7 to AC-10 are green in T032. Each
  red-proof artifact from Phase 1 and from T026 is saved under `artifacts/`.
- [ ] T036 Hand off: the decisions taken; per review unit, the files and line
  counts; the artifact paths; and **the spec 040 amendments in spec §6**,
  listed for Camden to apply to 040 before 040's T001.

## Dependencies & Execution Order

T001 → T002 → T003 → T004 → T010–T015 (harness red-proven) → U1 (T020–T022) →
U2 (T023–T026) → U3 (T027) → U4 (T028–T029) → U5 (T030) → U6 (T031, if in
scope) → T032 → T033 → T034 → T035 → T036 → **then spec 040 may start** (its
T001, with the §6 amendments applied). No step replaces a failed or unexecuted
gate with a focused green claim.
