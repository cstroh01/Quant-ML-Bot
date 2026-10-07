# Feature Specification: Ledger write guard (no accidental production trial records)

**Feature Branch**: `043-ledger-write-guard` (name only; Camden owns Git)
**Spec number**: 043. 042 is reserved for harness brittleness. 035, 038 and 039
are planned in `docs/HANDOFF-2026-09-25.md` but not yet written.
**Created**: 2026-09-28
**Status**: Draft. **Decisions D-1 to D-5 are DECIDED (Camden, 2026-09-28; see
§4).** Implementation still waits on the preconditions above (T002
measurement, and spec 041 landing first). No code was written and no test or
script was run to produce this document.
**Input**: Camden, 2026-09-28. Evidence: the 2026-09-28 incident (§1), a
read-only inventory of ledger write paths taken the same day (§2), and
[NOTE-for-ledger-write-guard-spec.md](NOTE-for-ledger-write-guard-spec.md),
moved here from spec 040.

## Hard preconditions

1. **043 implements before 040.** 040 moves `scripts/` to `src/qmb/`. 043 puts
   marker-based root resolution in place first, so 040 moves a proven resolver
   instead of creating one (§6).
2. **The production ledger is at its known state** when 043 starts, measured
   read-only at T002:
   - `docs/trials/trials.jsonl` has **174 lines**, SHA-256
     `1bb5dbfe90c9df370c65910650ade15dd9d0e0366d011e09baf303975275f30f`.
   - `docs/trials/trials.head.json` reads `{"head":"99a494e8…a679","records":174}`,
     file SHA-256 `f83b1b9be5a608d444d61496899d25139eb56184fd924acd030e61347d22d764`.
   - `docs/trials/returns/` is absent.
   - `docs/trials/backfill/*.json` are hashed at T002.

   If any value differs, 043 stops.
3. **No acceptance run touches the real ledger.** Every run that could reach a
   write path executes in a full copy of the repository outside `C:\GitHub`,
   with a tripwire that hashes the real `docs/trials/` before and after.

---

## T025 pin authorization (Camden, 2026-10-07)

Camden explicitly replaced the human implementation choice with a T025-only
agent pin exception for `scripts/feature_set_comparison.py`,
`scripts/logistic_baseline.py` and `scripts/multi_ticker_comparison.py`.
It covers only D-1 B flag/preflight and explicit spawned-worker enablement.
All other pin protections and human acceptance gates remain.

## 1. The incident, and why it was possible

**2026-09-28.** Verification scripts, run as standalone `python -` processes
outside pytest, called `multi_ticker_comparison._baseline_rows` directly. Each
call opened `research_attempt`, which called `current_ledger()`. With
`SPEC033_SYNTHETIC_ROOT` unset, that returned the production `TrialLedger()`.
The damage:

- **42 records** appended to `trials.jsonl`: **21 trials**, each a start and a
  terminal event. The roles were `buy_and_hold_baseline` and
  `random_signal_baseline`.
- `trials.head.json` was rewritten to `records: 216`.
- **21 return sidecars** were written under `docs/trials/returns/`. The first
  post-incident check missed these because it hashed only `trials.jsonl`.
- **`N_current` was unchanged only by luck.** `n_post_ledger` counts only
  `candidate` starts (`trial_registry.py:223`), and none of the 21 trials was a
  candidate. The same mistake made through `run_one_ticker` would have
  inflated the DSR gate's trial count.

Camden restored the files by hand. A Codex pytest run that overlapped with the
scripts ended with exit code 1 from `tests/conftest.py:40`: "spec033: tests
changed the production lifetime ledger". A clean, isolated re-run on
2026-09-28 was green, with 903 passed and all ledger artifacts byte-identical.

**Root cause.** `scripts/trial_runner.py:17-31` `current_ledger()`:

```python
    fixture_root = os.environ.get("SPEC033_SYNTHETIC_ROOT")
    if fixture_root:
        ...
        return TrialLedger(root / "attempts" / uuid.uuid4().hex, synthetic=True)
    return TrialLedger()          # production, by default, for every caller
```

Production is the **default**. Isolation exists only inside pytest, because only
`tests/conftest.py` sets the variable. Its shutdown guard (`:37-40`) has three
limits:
- It compares **only `trials.jsonl`**, not the head file, sidecars, lock or
  backfill.
- It sees only writes made **during** a pytest run.
- It cannot tell a test's write from another process's.

**The same default applies to the terminal.** Run outside pytest, `GET
/api/backtest/tearsheet` writes the production ledger on every successful
view (§4, D-2).

## 2. Write surface (re-inventoried 2026-09-30 at T004)

Search patterns: `current_ledger|TrialLedger\(|run_trial\(|research_attempt\(|immutable_write\(|injected_ledger|trial_runner|trial_registry|\.start\(|\.finish\(`,
`api\("trial_`, `SPEC033_SYNTHETIC_ROOT|environ|subprocess|env=|multiprocessing|spawn`,
`__main__`, plus an AST pass mapping each `research_attempt` call to its enclosing
function. **Counts are a floor**: string-based `getattr` dispatch is not
searched, and call chains below `main()` were not traced line by line.

### 2.1 Bytes that count as "ledger bytes"

Everything under `<project root>/docs/trials/`:

| File | Written by |
|---|---|
| `trials.jsonl` | `TrialLedger._append` (`trial_registry.py:225`) |
| `trials.head.json`, `trials.head.tmp` | `_append` (`:231-233`) |
| `trials.lock` and the `docs/trials/` directory itself | `serialized()` (`:135-165`), **before** `verify()` runs |
| `returns/<trial_id>.jsonl` plus its temporary file | `finish` → `immutable_write` (`:253-257`, `:121`) |
| `backfill/<id>.json` | `trial_backfill.write_backfill` (`:57`, `:73`) |

A refusal placed after `serialized()` is too late: the lock file and the
directory already exist. **Refusal precedes the first call into `serialized()`,
`mkdir`, `immutable_write` or `_append`.**

### 2.2 Entry points (reach the ledger with the variable unset)

| # | Entry point | Reaches |
|---|---|---|
| E1 | `scripts/ma_crossover_backtest.py:332` `__main__` → `main` (`:253`) | `:268` (candidate); `baseline_results` `:123`, `:135` |
| E2 | `scripts/logistic_baseline.py:367` → `main` (`:313`) | `:318`, `:332` (candidates); imports `baseline_results` |
| E3 | `scripts/multi_ticker_comparison.py:466` → `main` (`:431`) | `run_one_ticker` `:282`, `:320`; `_baseline_rows` `:137`, `:155`; `model_cv.nested_walk_forward` `:461`, `tune_on_fold` `:330` |
| E4 | `scripts/feature_set_comparison.py:1008` → `main` (`:979`) | `_predictions_by_date` `:167`, in **spawned workers** that inherit the parent's environment; `model_cv` |
| E5 | `reports/api/main.py:79` (uvicorn) → `GET /api/backtest/tearsheet` (`reports/api/routes/backtest.py:39`) | `:60` (candidate); `baseline_results` via `:88`, with `seed_count=20` |

**Library callers are the path the incident used.** Any process that imports
the functions above and calls them directly reaches the ledger without passing
through an entry point. A guard placed only at E1–E5 would not have stopped
2026-09-28.

**Other writers.**
- `trial_runner.run_trial` (`:43-51`) has no production callers.
- `trial_backfill.write_backfill` writes to the root its caller passes. Its
  only caller is `tests/test_033_backfill.py:46`, with `tmp_path`.

### 2.3 Tests and drivers that do not rely on the conftest variable

None writes production today. The edge cases:
- `tests/test_033_trial_ledger.py:180` constructs the production
  `TrialLedger()`, but only reads `.path`. `__init__` writes nothing.
- `tests/test_unadjusted_caller_wiring.py:118` runs the real CLI in a subprocess
  with the working directory set to the real repository. It is protected by
  the inherited variable, and, as a second layer, by the load failing before
  `research_attempt`.
- `tests/mutation/run_spec_018_mutants.py:22-26` and `run_mutation_check.py:51`
  do not copy `tests/conftest.py`. Their children write to the **copy's**
  `docs/trials/`, only because `ROOT` is depth-based today (D-4).

---

## 3. Requirements

- **FR-001 Fail closed.** With `SPEC033_SYNTHETIC_ROOT` unset, and without
  production recording deliberately enabled (mechanism: **D-1**), every path
  that would write a ledger byte (§2.1) raises `LedgerWriteRefused`. The
  default never writes production.
- **FR-002 Nothing written before the refusal.** The refusal is enforced at two
  layers:
  - **(a) Write layer**, which stops the incident's path. `TrialLedger.start`,
    `TrialLedger.finish` and `trial_backfill.write_backfill`, when their root
    is the production root, check enablement **first**, before `serialized()`,
    `mkdir`, `immutable_write` or `_append`.
  - **(b) Early layer**, so no research runs unrecorded and no compute is
    wasted. `research_attempt` and the E1–E4 `main` functions check before
    loading data or fitting. E5 behaves per D-2.
- **FR-003 Named refusal.** The error names:
  - the runner string or entry point;
  - the resolved ledger path;
  - the statement that no ledger byte was written;
  - the exact deliberate action that enables recording (per D-1).

  CLIs exit nonzero with that message on stderr and print nothing to stdout.
- **FR-004 Synthetic path unchanged.** `SPEC033_SYNTHETIC_ROOT` plus the
  labelled context still selects a synthetic ledger, as it does today.
  `injected_ledger` is unchanged. The conftest fixtures keep isolating tests.
- **FR-005 Enablement is deliberate and scoped.** Enabling production recording
  requires an explicit act tied to the run that needs it (D-1). It is never a
  side effect of importing a module, of the working directory, or of a
  synthetic-root misconfiguration. An invalid synthetic context still raises,
  as `trial_runner.py:24-25` does today, and never falls through to production.
- **FR-006 Project root by marker, never by depth** (coordinated with 040 §1.5
  R1, identical contract):
  - `project_root()` returns `QMB_PROJECT_ROOT` if it is set. That directory
    must contain the marker, or `ProjectRootNotFound` is raised.
  - Otherwise it returns the nearest ancestor of the resolver module's
    resolved `__file__` that contains the marker.
  - Otherwise it raises `ProjectRootNotFound`, naming the places it searched.
  - **Marker**: a file named `pyproject.toml` whose `[project] name` is
    `quant-ml-bot`, read with stdlib `tomllib`.
  - The working directory is never consulted, and no `parents[n]` expression
    determines the root.
  - `trial_registry.ROOT` becomes `project_root()`. Pre-040 location:
    `scripts/_project.py` (D-5).
- **FR-007 History untouched.**
  - Every byte of `trials.jsonl` (174 lines, `1bb5dbfe…5275f30f`),
    `trials.head.json` and `backfill/*.json` is identical after 043.
  - `verify()`, the chain rules, `ROLES`, `TERMINALS`, `schema_version` (1)
    and the definition of `n_post_ledger` are unchanged.
  - No new field is written into ledger events.
- **FR-008 The conftest shutdown guard covers the whole ledger tree.**
  `tests/conftest.py:24-25` and `:37-40` snapshot a manifest of every path and
  SHA-256 under `docs/trials/` (including absence), not only `trials.jsonl`.
  The error names each changed, added or removed path. This closes the
  2026-09-28 blind spot for returns sidecars.
- **FR-009 E5 (read-only route) behaviour**: per **D-2**.
- **FR-010 Mutation drivers**: per **D-4**.
- **FR-011 Synthetic-label marker hardening**: per **D-3(b)**.
- **FR-012 Alias-assignment bypass in the instrumentation guard**: per
  **D-3(a)**. If D-3(a) excludes it, it stays recorded in the moved note file.

## 4. Decisions (all DECIDED 2026-09-28)

Each decision lists options, tradeoffs and a recommendation. The
recommendation is not a decision; each section ends with a **Decision** line
that records Camden's choice. The identifiers `LedgerWriteRefused`,
`production_recording`, `--record-trial` and version `0.0.0.dev0` are
placeholder names, open to renaming at review.

### D-1. The default when `SPEC033_SYNTHETIC_ROOT` is unset

Every option below fails closed for the accident case: a library call or an
entry point run with nothing set writes nothing. They differ in **where the
deliberate act lives**.

| Option | Mechanism | For | Against |
|---|---|---|---|
| **A. Fail closed; process-level opt-in** | An environment variable, such as `QMB_LEDGER_WRITE=production`, enables production writes for the whole process | One switch; spawned workers (E4) inherit it with no plumbing; smallest diff | Environment variables persist in shells, profiles, `.env` files, CI and agent lanes. A stale export recreates the incident exactly (overlapping lanes, 2026-09-28). Every test and driver must scrub it |
| **B. Fail closed; per-invocation flag** | CLIs take `--record-trial`. The API follows D-2. Library code enables only inside `with production_recording(reason=…)`, carried by a context variable. There is no environment switch | The deliberate act is typed per run and visible in shell history. The incident's path (a direct library call) has no flag and is refused. Nothing is inherited by accident | A context variable does not cross `spawn`, so E4's workers need an explicit enable token passed as an argument. More plumbing: four CLIs plus the workers |
| **C. Both required** | The flag **and** the variable | Two independent deliberate acts | The most friction. The variable's persistence risk remains, and it adds nothing B lacks against accidents |

**Recommendation: B.** Inherited process state was the 2026-09-28 accident
vector. A per-invocation flag makes enabling a visible act for each run, and
the explicit spawn token is a small, testable cost.

**Decision (Camden, 2026-09-28): B.** Production writes are refused by default
and allowed only by a per-run flag (`--record-trial` on the CLIs) or by
`production_recording()` in library code. There is no environment-variable
switch. E4's spawned workers receive an explicit enable token as an argument.

### D-2. Should a read-only route (`GET /tearsheet`) ever append a trial?

**What the current code does with repeat identical requests** (read
2026-09-28):
- Each successful `GET /api/backtest/tearsheet` opens one `candidate` attempt
  (`backtest.py:60`) and 21 baseline attempts: 1 buy-and-hold plus
  `seed_count=20` random (`:88`, via `ma_crossover_backtest.py:123`, `:135`).
- That is 44 ledger records and up to 22 return sidecars **per page view**,
  written to production whenever the API runs outside pytest.
- `n_post_ledger` counts every `candidate` start (`trial_registry.py:223`), and
  **nothing deduplicates by `config_hash`**.
- Spec 033 FR-026 defines
  `N_current = N_backfill + post_ledger_candidate_starts`. **N therefore rises
  by exactly 1 per identical request.**
- The DSR benchmark rises with page views, so the gate becomes stricter. At
  that point N measures terminal traffic, not research search.

| Option | Behaviour | For | Against |
|---|---|---|---|
| **A. GET never writes; recording is a separate, explicit action** | GET shows the tearsheet only for a configuration already recorded, looked up by `config_hash`. Otherwise it returns 409 with the command that records it. Recording is a deliberate action under D-1: a CLI (A1), or a `POST` route (A2) | GET becomes truly read-only, matching spec 018's read-only API on loopback. N counts deliberate evaluations. A1 keeps the API free of mutating routes | The terminal needs one recording step before the first view. A2 adds the API's first mutating route. The route's `runner` string (`reports/api/routes/backtest.py:run_backtest`) differs from E1's, so it is a separate configuration |
| **B. GET writes, deduplicated by `config_hash`** | Append only if no prior `started` event with the same `config_hash` and role exists | The terminal works unchanged after the first view; repeat views do not grow N | **Conflicts with spec 033 FR-026**, which forbids replacing `N_current` with unique hashes. Write-time deduplication is that replacement, applied to this runner. GET keeps side effects, takes the ledger lock on page loads, and returns 5xx on lock contention. It still needs production enablement under D-1 |
| **C. GET writes every time, only when enabled** | Status quo behind D-1 | Smallest change | Unusable by default (503), and when enabled N still counts page views |
| **D. GET computes without recording** | A labelled, unrecorded evaluation | Terminal unchanged | A Sharpe on screen that is not in N. Contradicts 033's "record before evaluation" and Rule 15 |

**Recommendation: A1.** It keeps GET read-only and the API free of mutating
routes, and it makes N count deliberate evaluations without touching FR-026.
If Camden prefers B, the FR-026 conflict must be resolved in 033 first, not
inside 043.

**Decision (Camden, 2026-09-28): A1.** `GET /tearsheet` never writes. It shows
an already-recorded configuration (looked up by `config_hash`) and otherwise
returns 409 with the recording command. Recording is a CLI step under D-1.
Option B (write-time deduplication) is rejected: it conflicts with spec 033
FR-026.

### D-3. Scope

**(a) The alias-assignment bypass** (`tests/test_033_trial_instrumentation.py:18-23`;
details in the note file).
- Options:
  1. include it as its own review unit;
  2. defer it to a separate spec;
  3. leave it recorded.
- Tradeoffs: it is an **under-recording** gap (research that escapes the
  ledger), the opposite direction from this spec's over-writing, but it guards
  the same count. It is latent: no production code uses it as of 2026-09-28.
  The fix is small and has a clear Rule 12 shape.
- **Recommendation: 1**, as a separate phase and review unit, so that the
  write-guard change stays reviewable on its own.

**(b) Hardening the synthetic-label marker** (`trial_runner.py:24`, an exact
comparison against `"EXAMPLE — NOT A RESULT"`).
- The risk is real in this repository. On 2026-09-26, a save converted
  `tests/test_multi_ticker_comparison.py:23`'s em-dash to byte `0x97`, and
  later to U+FFFD.
- The label is duplicated in `trial_runner.py:24`, `tests/conftest.py:20` and
  `:58`, and `tests/spec033_support.py:7`. Today a mangled copy fails closed
  (`ValueError`). Mangling all copies identically would still pass, with a
  label that is no longer Rule 11's.

| Option | For | Against |
|---|---|---|
| **i. Normalise before comparing** (NFKC plus dash folding) | Tolerates editor mangling | **Loosens a gate**: the accepted set grows. Normalisation must never map U+FFFD, and it still leaves the source literal fragile |
| **ii. ASCII marker** (such as `EXAMPLE - NOT A RESULT`, or a JSON sentinel) | Immune to re-encoding | A second spelling of Rule 11's label. Every copy and fixture changes |
| **iii. One constant with an ASCII-escaped literal, compared exactly** | `SYNTHETIC_LABEL = "EXAMPLE \u2014 NOT A RESULT"` is defined once in `trial_runner` and imported by `conftest.py` and `spec033_support.py`. The source bytes are ASCII, so no re-save can corrupt them; the comparison stays exact; Rule 11's text is unchanged | Touches three files. A test must pin that the literal stays escaped |

- **Recommendation: iii, folded into 043 from spec 038.** 043 already edits
  `current_ledger()`: line 24 is the marker, line 31 the production default.
  Two specs editing one seven-line function is how a merge silently drops a
  guard.
- **What removing the item from 038 changes**:
  - 038 (the Rule 11 and Rule 16 disclosure sweep, "S7 Late") is not yet
    written. The assignment exists only in planning, so no repository
    document changes.
  - 038 stays a pure disclosure sweep, with no ledger or test-harness code.
  - The label constant becomes a 043-owned contract. If 038 restyles Rule 11
    labels, it changes that one constant, and 043's gate (a planted
    mismatch) proves the change.
  - The hardening lands with 043, before 040, instead of late.

**Decision (Camden, 2026-09-28): (a) 1 and (b) iii.**
- (a) The alias-assignment bypass is included as its own review unit (U6).
- (b) The synthetic label is defined once as an ASCII-escaped `\u2014` literal
  and compared exactly. The marker hardening moves here from spec 038, which
  becomes a pure disclosure sweep.

### D-4. Isolation for mutation drivers that do not copy `conftest.py`

**Affected drivers**: `tests/mutation/run_spec_018_mutants.py` (its `COPIED`
list omits `tests/conftest.py` and has no `pyproject.toml`) and
`run_mutation_check.py` (copies `scripts/` and one test).

**What goes wrong without a decision**:
- **After 043**, their children find no marker (`ProjectRootNotFound`), or
  hit the fail-closed guard. The tearsheet control test turns red and the
  drivers stop working.
- **After 040**, a child that imports `qmb` from the editable install resolves
  `project_root()` to the **real** repository unless 040 T037/T038's
  `PYTHONPATH` treatment holds. Unguarded, that writes the real ledger.

| Option | For | Against |
|---|---|---|
| **a. Copy `tests/conftest.py` and `pyproject.toml` into every driver copy** | Matches `run_unadjusted_wiring_mutants.py`, which already copies `conftest.py`. The copy then gets conftest's own shutdown guard | Protects the copy's ledger, not the real one |
| **b. Drivers set a labelled `SPEC033_SYNTHETIC_ROOT` in the child's environment and strip every enablement** | Explicit; does not depend on conftest | Duplicates conftest's logic in three drivers |
| **c. Real-repository tripwire** | Each driver hashes the real `docs/trials/` manifest before and after and fails on any change | Detects, does not prevent. Combine with a or b |

**Recommendation: a + c**, with the child's environment stripped of every
enablement. Put both in one shared driver helper so the three drivers cannot
drift.

**Decision (Camden, 2026-09-28): a + c.** The drivers copy `tests/conftest.py`
and `pyproject.toml` and run with the child's environment stripped of every
enablement. Each driver hashes the real `docs/trials/` manifest before and
after. All of it lives in ONE shared helper that reuses
`tests/mutation_support_019.py`. No third harness.

### D-5. Who creates `pyproject.toml` before 040 (added by this spec)

FR-006's marker needs `pyproject.toml` to exist, and today it does not. 040
T015 creates the full file.

| Option | For | Against |
|---|---|---|
| **a. 043 creates a minimal marker file** (`[project] name = "quant-ml-bot"`, `version = "0.0.0.dev0"`, no build section). 040 T015 then edits it into spec 040 §4's content | Smallest; 040's packaging decisions stay in 040 | 040's manifest entry changes from "New" to "Edited". A root `pyproject.toml` may change pytest's rootdir or configfile detection, which must be verified (T033) |
| **b. Move 040's full T015 into 043** | One edit to the file | Pulls packaging (setuptools, `src` discovery) into a guard spec, and `packages.find where = ["src"]` points at nothing before 040 |
| **c. A different marker file** | No packaging overlap | Contradicts the coordination rule (the root is found by `pyproject.toml`) and forks 040 R1 |

**Recommendation: a.**

**Decision (Camden, 2026-09-28): a.** 043 creates a minimal `pyproject.toml`
with no `[build-system]` and no packages, so nothing is half-installable.
040 T015 later expands it. T033 must show the collected test count is
unchanged by the file's presence (903 when D-5 was decided; T003 records the
baseline actually in force when 043 starts).

## 5. Acceptance criteria (each gate has a planted defect and a control, per Rule 12)

All runs that could reach a write path happen in a **copy** outside
`C:\GitHub`: the repository without `data/cache/`, `venv/` or `node_modules/`,
but with `pyproject.toml`. Each run:
- takes an explicit child environment with `SPEC033_SYNTHETIC_ROOT` and every
  enablement removed;
- compares a manifest (path to SHA-256, including absences) of the copy's
  `docs/trials/`;
- hashes the real `docs/trials/` before and after (the tripwire).

- **AC-1: each entry point, with the variable unset, changes zero ledger
  bytes.**
  - **Run**: E1 to E5 are each run in the copy with no enablement. A child
    harness (a non-test module name) replaces data access with labelled
    synthetic frames, so that **without the guard the write path is
    reachable**.
  - **Pass**: for every entry point, the manifest is identical (no `.lock`,
    `.tmp`, `returns/` or `backfill/` change); the refusal message matches
    FR-003; the CLI exit code is nonzero; E5 follows D-2.
  - **Red proof**: on the pre-043 code, each of E1–E5 changes the copy's
    manifest (observed red at T011, for the right reason). After 043, a copy
    with the FR-002(a) check removed changes the manifest for at least the
    library path (AC-2), which proves the write layer is load-bearing
    independently of the early layer.
- **AC-2: the incident reproduction changes zero ledger bytes.** In the copy
  with the variable unset, a direct library call to
  `multi_ticker_comparison._baseline_rows` on synthetic prices raises
  `LedgerWriteRefused`, and the manifest is identical. **Red**: pre-043 code
  appends 3 trials (6 records, 3 sidecars) for `seed_count=2`.
- **AC-3: the enabled path still records (the green control).** With
  enablement per D-1, E1 in the copy, on a synthetic bundle, appends exactly
  the expected start and terminal events and sidecars, and `verify()` passes
  on the copy. Without this, a guard stuck closed would pass AC-1.
- **AC-4: history is untouched.**
  - On the real repository, read-only: `trials.jsonl` is 174 lines with
    `1bb5dbfe…5275f30f`; the head file's SHA-256 is `f83b1b9b…d764`;
    `returns/` is absent; `backfill/*.json` match T002.
  - `TrialLedger().verify()` returns the T002 head and `n_post_ledger`.
  - **Red**: the tripwire comparison, fed a copy with one planted appended
    record, reports the path.
- **AC-5: root resolution.**
  - Cases: the `QMB_PROJECT_ROOT` override; the marker found via `__file__`;
    `ProjectRootNotFound` with neither; a `pyproject.toml` with a different
    `[project] name` in a nearer ancestor, which is skipped; the working
    directory never consulted (run from a foreign directory that contains its
    own marker).
  - **Red**: a planted depth-based `ROOT` (`parents[1]`), in a copy nested one
    directory deeper, resolves to the wrong directory, and the test names it.
- **AC-6: the full suite is green.** `python -m pytest tests` gives 0 failed
  and 0 errors. The passed count equals the T003 baseline plus the new tests.
  The widened FR-008 conftest guard is red-proven on a copy: a planted write
  to `returns/x.jsonl` during a test run makes shutdown raise and name that
  path.
- **AC-7 (if D-3(b) is iii)**:
  - The literal in `trial_runner.py` is ASCII-escaped, and a test pins that.
  - `conftest.py` and `spec033_support.py` import the one constant.
  - **Red**: a planted `synthetic-context.json` containing U+FFFD instead of
    U+2014 is refused, and so is one with a cp1252 `0x97` byte.
- **AC-8 (per D-4)**: each driver reports a green control and killed mutants.
  **Red**: its tripwire, fed a planted change to a stand-in "real"
  `docs/trials/`, fails and names the path.
- **AC-9 (if D-3(a) is 1)**: `bypasses()` flags a planted
  `rb = run_backtest; rb(x)` and a planted
  `getattr(bt, "run_backtest")(x)` outside `research_attempt`. The clean tree
  is the green control.
- **AC-10 (per D-2, option A)**: `GET /tearsheet` with no recorded
  configuration returns 409 with the recording command and changes zero
  ledger bytes. After recording, it returns 200 from the recorded trial. Two
  identical GETs change zero bytes and leave N unchanged. **Red**: the pre-043
  route appends 44 records per request (T011).

## 6. Coordination with spec 040 (043 lands first)

043 establishes FR-006 before the move. **040 needs these amendments when 043
merges.** They are listed here and not applied to 040; Camden amends 040.

1. 040's hard preconditions: add "043 has merged".
2. 040 T015 (`pyproject.toml`): the file exists (D-5a). The task becomes an
   edit to spec 040 §4's content, and §7 of 040 moves it from "New" to
   "Edited".
3. 040 T016 (`_project.py`): it becomes a **move** of `scripts/_project.py`
   to `src/qmb/_project.py` with the import rewrite, not a new file.
4. 040 T014's `project_root()` cases already exist from 043 (AC-5). 040 keeps
   them, retargeted to `qmb._project`.
5. 040 T022 (L1): `ROOT = project_root()` is already in place. The task
   reduces to the import rewrite.
6. 040 T037 and T038: the `PYTHONPATH` and non-vacuity treatment remains
   required. D-4's tripwire becomes the backstop if it regresses.
7. 040 AC-4a: `docs/trials/` hashes include every 043 file state (unchanged).
   043 adds no file under `docs/trials/`.

## 7. Out of scope

- Rewriting, trimming or "repairing" any ledger history. Recovery from an
  accidental write is a human action.
- Changing `N_current`'s definition, or any spec 033 FR (see the D-2 B
  conflict).
- Adding event fields or bumping `schema_version`.
- The 040 migration itself, and packaging beyond D-5's marker.
- Hardening against deliberate misuse: an operator who enables recording and
  runs junk is out of scope. This spec prevents accidents.

## Assumptions

- No strategy result is produced or reported, so Rules 2, 3, 4, 13 and 15 are
  not engaged. Synthetic prices in the acceptance harness are
  `EXAMPLE — NOT A RESULT`.
- The copy-based harness runs on Windows locally. Paths in the harness never
  hard-code `C:\GitHub`; they assert that the copy is not inside the real
  repository.
