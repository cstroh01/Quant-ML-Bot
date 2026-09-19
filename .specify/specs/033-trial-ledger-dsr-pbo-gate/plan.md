# Implementation Plan: Lifetime Trial Ledger, DSR, PBO, and Capital Gate 3

**Spec**: `.specify/specs/033-trial-ledger-dsr-pbo-gate/spec.md`  
**Status**: Planning only  
**Input**: The controlling source and thresholds are recorded in `spec.md`.

## Summary

Replace the unused metadata-only trial registry with one append-only,
hash-chained lifetime ledger; instrument every human-facing backtest path before
results are known; build a conservative pre-ledger count; calculate hand-rolled
DSR and deterministic `S = 16` CSCV/PBO from one provenance-checked daily OOS
trial matrix; generate immutable Gate 3 artifacts; and make the existing API
route validate and display those artifacts.

The low-level backtest harness remains an accounting primitive. A new lifecycle
wrapper owns research metadata and recording so the harness does not learn how
signals or models were produced.

## Technical Context

**Language**: Python under the versions already supported by the repository.  
**Existing dependencies used**: standard library, NumPy, pandas, SciPy.  
**New dependency**: none.  
**Canonical verification**: `python -m pytest tests`.  
**Storage**: repository-resident canonical JSON/JSONL outside `data/cache/`;
all lifetime records and evidence are human-reviewable and content-addressed.  
**Network**: forbidden in tests and evidence generation.  
**Time convention**: daily session labels are timezone-naive and
midnight-normalized; event timestamps are UTC-aware instants.  
**Scale**: initially tens to low thousands of trials, daily series of roughly
hundreds to a few thousand rows, and exactly 12,870 CSCV splits per PBO run.

## Proposed Project Structure

```text
scripts/
├── trial_ledger.py              # schema, canonicalization, append, verification
├── trial_runner.py              # start/terminal lifecycle around research runs
├── selection_bias.py            # pure DSR, matrix, CSCV/PBO, HAC gate inputs
└── generate_gate3_evidence.py   # offline artifact command

docs/trials/
├── ledger.jsonl                 # append-only events
├── returns/
│   └── <trial-id>.jsonl         # write-once full daily OOS series
└── backfill/
    ├── manifest.json            # campaign-level upper-bound inputs
    └── <backfill-id>.json        # immutable approved result

reports/artifacts/capital_gate/gate3/
├── index.jsonl                  # append-only artifact index
└── <artifact-id>.json           # immutable evidence package

reports/api/routes/capital_gate.py

tests/
├── fixtures/spec_033/           # paper inputs and labelled test-only matrices
├── test_033_trial_ledger.py
├── test_033_trial_instrumentation.py
├── test_033_backfill.py
├── test_033_dsr.py
├── test_033_pbo.py
├── test_033_gate3.py
└── mutation/
    └── run_spec_033_gate_mutants.py
```

`scripts/trial_registry.py`, `tests/test_trial_registry.py`, and the empty
`docs/trials/trials.jsonl` are migration inputs, not a second system. The
implementation PR must pick one migration path and complete it atomically:

1. rename/replace them with the structure above and update all tests; or
2. retain the old module name but fully upgrade it and use it as the sole
   authority.

The first path is preferred because “registry” currently suggests optional
metadata rather than a mandatory lifetime ledger. A compatibility shim is not
needed: repository inspection found no production caller.

## Architecture and Data Flow

```text
human/API/batch research runner
        |
        v
trial_runner.start(config, role) ----append+fsync----> ledger `started`
        |
        v
existing signal/CV/backtest code
        |
        +-- error/interruption ----append-----------> terminal error if possible
        |
        v
funded daily OOS equity -> net log returns
        |
        +--write-once sidecar + digest--------------> terminal completed event
                                                        |
                                                        v
backfill + verified ledger -> exact aligned T x M matrix
                                                        |
                              +-------------------------+------------------+
                              v                                            v
                         DSR + HAC t                                  CSCV/PBO S=16
                              +-------------------------+------------------+
                                                        v
                                             immutable Gate 3 artifact
                                                        |
                                                        v
                                          API validates and renders only
```

### Module boundaries

| Module | Owns | Must not know about |
|---|---|---|
| `trial_ledger.py` | Event schema, canonical hashes, locking, append, sidecar verification, count | DSR, model behavior, HTTP |
| `trial_runner.py` | Research lifecycle and opaque canonical config assembly | Statistical gate thresholds, API |
| `selection_bias.py` | Pure matrix, DSR, HAC t-stat, CSCV/PBO functions | Filesystem default paths, HTTP, model fitting |
| `generate_gate3_evidence.py` | Load/verify/compose evidence and write artifact | Request lifecycle, broker execution |
| API route | Locate latest indexed artifact, validate currentness, map to schema | Recomputing returns or statistics |

The backtest harness continues to own fills, trades, P&L, and funded equity.
It may expose the funded daily equity/return output needed by the wrapper, but
it receives no model, feature, or selection-family semantics. If implementation
cannot preserve that boundary, stop and flag Rule 8.

## Design Decisions

### D1 — Event-sourced ledger, write-once return sidecars

One giant record containing thousands of returns makes every append expensive
and makes partial-write recovery harder. Use small append-only lifecycle events
plus one immutable sidecar per completed trial. The terminal event commits the
sidecar digest and coverage. “Full series in the ledger” is satisfied by a
content-addressed sidecar that the ledger makes mandatory; a path without a
valid digest is not evidence.

The writer validates the existing chain before append, takes an inter-process
lock, writes to a temporary sidecar, flushes and atomically renames it, appends
one canonical JSON line, flushes, and calls `fsync`. The exact lock mechanism
may be platform-specific behind one interface, but Windows and Linux behavior
must share tests. A stale/partial lock needs an explicit recovery protocol; it
must never be ignored automatically.

### D2 — Record before result, count starts

The selection opportunity exists when the project decides to try a candidate,
not when the run succeeds. `N_post_ledger` therefore counts candidate
`started` events. Terminal state, eligibility, duplicated config hash, and
sidecar survival do not reduce it. This prevents a crashing or rejected trial
from vanishing.

Unit tests and mechanical accounting fixtures are not research selection. They
use an injected temporary path and `synthetic_test`. A production runner has no
optional “off” switch. An AST/static inventory test protects the known
human-facing callers and fails when a new one bypasses `trial_runner`.

### D3 — Full config hash plus full source identity

Canonical config JSON is constructed from explicit values after defaults are
resolved, not from a partial CLI argument dictionary. Lists whose order affects
behavior retain order; true sets are sorted. Floats use JSON numeric encoding
only after finite-value validation. Paths become repository-relative POSIX
paths and data inputs carry content digests.

Git SHA is the full 40-hex commit ID. It is insufficient for a dirty tree, so
workspace state is one of `clean`, `dirty`, or `unknown`; dirty/unknown runs
also need a deterministic content hash over the executed repository source.
Missing source identity never prevents the start event from being logged, but
it prevents a Gate 3 pass.

No implementation calls the `git` executable. SHA may be injected or read from
`.git/HEAD` plus refs/packed-refs. Worktree dirtiness must not reuse the current
prototype's always-false placeholder.

### D4 — Backfill is an upper-bound exercise

Backfill is campaign-based because individual pre-ledger attempts are not
recoverable. For each campaign:

1. cite surviving scripts, configs, reports, audit logs, or Camden's approved
   recollection;
2. enumerate the full reachable Cartesian product of every selection choice;
3. add evidenced repeats and separate campaigns without deduplication;
4. use the upper endpoint of any remembered range;
5. sum, round up to the next power of two, then double; and
6. preserve the worksheet and approval in an immutable artifact.

This deliberately counts configurations that may never have run and
double-counts uncertain repeats. Those are safe errors for DSR. If a known
campaign is genuinely unbounded, the correct result is incomplete/unknown,
not a guessed number.

### D5 — One matrix, two analyses, two counts

The verified shared daily matrix has `M` actual eligible columns. Both the
trial Sharpe distribution used by DSR and all CSCV splits use that exact matrix
and its hash. DSR's multiple-testing count is the larger lifetime
`N_current = N_backfill + candidate starts`; it MUST NOT be substituted with
`M`. Backfilled trials without return series are not PBO columns.

Matrix construction uses exact session-label intersection only after every
series independently passes schema, digest, cost, funded-return, OOS, CV, and
time validation. Exclusions are recorded. No fill method is permitted.

### D6 — DSR is transparent, not a library badge

Implement the Bailey-Lopez de Prado equations directly. SciPy supplies normal
distribution primitives; NumPy/pandas supply moments and arrays. Public pure
functions accept named statistical inputs so the paper fixture can test the
formula separately from file and matrix construction.

The integration path derives candidate Sharpe, skewness, Pearson kurtosis,
observation count, and matrix trial-Sharpe dispersion from verified returns.
Domain checks return structured undefined reasons, never NaN-as-pass.

### D7 — HAC t-statistic reuses repository conventions

Use the selected candidate's daily OOS excess log return mean divided by a
Newey-West/Bartlett standard error. Prefer the already-tested primitive in
`scripts/metrics.py` rather than copy the estimator. Record the actual lag and
enforce at least `horizon - 1`. If reuse would create a circular dependency,
extract one shared statistical primitive under a separate, narrowly scoped
task; do not duplicate formulas silently.

### D8 — Deterministic CSCV/PBO

Partition chronological rows into 16 contiguous blocks with sizes differing by
at most one. Enumerate every combination of eight IS blocks using
`itertools.combinations`; use the complement OOS. The winner objective is fixed
before execution and uses the same return/Sharpe convention as the matrix.
Evaluate the IS winner OOS, convert its deterministic relative rank to the
paper's logit, and set PBO to the share of logits `<= 0`.

Persist split-level data or a content-addressed compressed summary sufficient
to independently recompute aggregate PBO. Do not hide rejected splits; report
their count and reason. The spec intentionally adds no PBO threshold.

### D9 — Offline evidence, read-only API

`generate_gate3_evidence.py` takes explicit candidate and family identifiers,
verifies all inputs, calculates the gate, writes a new immutable artifact, and
appends its digest/path to an index. It never edits an old artifact or declares
other capital gates passed.

The HTTP route performs schema and currentness validation only. It maps:

- complete current evidence meeting thresholds -> `passed`;
- complete current evidence missing either threshold -> `failed`;
- incomplete/undefined/corrupt evidence -> `unknown`; and
- internally valid evidence whose committed inputs no longer match -> `stale`.

Starting any new candidate changes the ledger head and immediately makes the
prior artifact stale. This is necessary: the relevant `N` changed.

## Data Contracts

### Ledger event minimum fields

| Group | Fields |
|---|---|
| Identity | schema version, event ID, trial ID, event type, UTC instant |
| Search | role, family, runner, outcome/reason |
| Configuration | canonical config object, SHA-256 config hash |
| Source | full git SHA, workspace state, optional source-tree hash |
| Chain | prior record hash, record hash |
| Terminal provenance | sidecar path/hash, rows, first/last session, convention, costs, CV metadata |

The canonical config object may be stored in the start event as well as hashed;
a hash without the config cannot be reviewed under Rule 9.

### Return sidecar rows

```text
{"session":"YYYY-MM-DD","log_return":<finite number>}
```

Header metadata belongs in the terminal ledger event so every data line has one
unambiguous shape. Sessions are strictly increasing, unique, and daily labels.

### Backfill campaign row

```text
campaign_id, description, evidence[], dimensions{}, cartesian_upper_bound,
rerun_upper_bound, remembered_range, chosen_upper_bound, unresolved_reason
```

### Gate artifact core

```text
artifact_id, generated_at_utc, status, reason_codes[], selected_trial,
ledger_head_hash, n_backfill, n_post_ledger, n_current, backfill_hash,
matrix_hash, matrix_rows, matrix_columns, date_range, excluded_trials[],
dsr{value, inputs, threshold}, t_stat{value, hac_lags, threshold},
pbo{value, S, total_splits, valid_splits, summary}, cv, costs,
source_identity, schema_version
```

## Test Strategy

Tests are written before the implementation they cover and confirmed red for
the intended missing behavior, not an import/setup accident.

### Ledger tests

- canonical config hashing, resolved defaults, order-sensitive vs set-like
  fields, non-finite rejection;
- full SHA and source-tree provenance;
- duplicate starts count twice;
- error/interruption/start-only counting;
- immutable sidecars and digest verification;
- edited/deleted/reordered/duplicated event mutation cases;
- partial final line, missing sidecar, corrupt sidecar, stale lock;
- multi-process contention with no lost event;
- lifetime production default vs injected synthetic-test path;
- static inventory of human-facing backtest entry points.

### Backfill tests

- Cartesian product arithmetic from a tiny manifest;
- separate-campaign addition without dedupe;
- remembered upper endpoint;
- next-power-of-two then doubling order;
- immutable supersession never lowers `N`;
- unresolved campaign -> incomplete/unknown.

### DSR and t-stat tests

- paper worked example at `N = 88` and `N = 46`;
- explicit skew/kurtosis convention and domain failures;
- `N_current` includes start-only and backfilled attempts;
- hand-calculated small return example for Sharpe inputs;
- HAC oracle and `lags >= horizon - 1`;
- exact threshold equality, one representable value below, non-finite and
  zero-standard-error cases.

### Matrix/time tests

- exact common-date alignment without filling;
- reordered, duplicate, timezone-aware, non-midnight, and gapped labels;
- unequal start/end dates and excluded-trial reasons;
- future perturbation does not change an earlier row or selection;
- one matrix hash reaches both DSR and PBO.

### PBO tests

- 16 contiguous blocks, near-equal sizing, deterministic boundaries;
- exactly 12,870 complementary splits;
- independent tiny oracle for winner, OOS rank, logit direction, and PBO;
- deterministic tie rule and column-order invariance;
- fewer than 16 rows and insufficient columns -> undefined;
- no random sampling and no zero-filled trial.

### Rule 12 gate proof

The integration fixture keeps candidate returns, costs, dates, PBO, and
t-statistic fixed. The `N = 88` selection history gives paper-example
`DSR ~= 0.905` and must fail specifically on DSR. The `N = 46` clean control
must pass. Then an isolated copied module is mutated twice:

1. `DSR >= 0.95` becomes `DSR > 0`; and
2. `N_current` becomes matrix column count.

Each mutant must be caught by a named test. The unmodified copied module must
pass, and pre/post SHA-256 of repository files must match. The driver lives
under `tests/mutation/`, not a pytest-discovered filename.

## Performance and Determinism

- Ledger append should be dominated by sidecar write size and complete in one
  local filesystem transaction; no network.
- Matrix construction is `O(T*M)` memory and time.
- CSCV performs exactly 12,870 split evaluations. Vectorize per-split column
  statistics where clear, but preserve a transparent reference oracle in
  tests. No multiprocessing is required at the initial scale.
- Every ordering is explicit: ledger order, trial columns, session rows, block
  boundaries, combinations, and tie resolution. No global random state.

## Constitution Check

| Rule | Plan response | Result |
|---|---|---|
| 1 | OOS-only eligibility, exact dates, future perturbation. | PASS |
| 2 | Purge/embargo metadata is mandatory; CSCV does not replace walk-forward CV. | PASS |
| 3 | Only costed funded-account returns are gate eligible. | PASS |
| 4 | No strategy change; baseline roles preserved separately. | N/A |
| 5 | Alignment boundaries and gaps have direct tests. | PASS |
| 6 | Uses existing SciPy/NumPy/pandas only. | PASS |
| 7 | No execution code or credentials. | PASS |
| 8 | Wrapper owns research metadata; harness remains accounting-only. | PASS, re-check during implementation |
| 9 | Formulas, data contracts, and reason codes are reviewable. | PASS subject to Camden explanation |
| 10 | No `git` command; Camden commits. | PASS |
| 11 | Immutable source, ledger, matrix, and artifact hashes accompany every figure. | PASS |
| 12 | Failing strategy/control plus two isolated mutations and ledger defects. | PASS |

## Risks and Failure Controls

1. **Partial instrumentation undercounts N.** Highest risk. Control: one
   mandatory wrapper, AST inventory guard, start-before-result semantics, no
   production opt-out.
2. **Existing prototype becomes a shadow authority.** Control: migrate/retire
   it in the same PR and test that only one default path exists.
3. **Backfill looks precise but is incomplete.** Control: campaign worksheet,
   upper endpoints, round-and-double reserve, human approval, unknown if
   unbounded.
4. **Survivorship enters the matrix.** Control: lifetime `N` is independent of
   matrix eligibility; every exclusion is emitted; missing series are never
   dropped from `N`.
5. **DSR formula convention drift.** Control: named inputs, paper fixture,
   direct equations, no black-box package.
6. **PBO rank direction is reversed.** Control: hand oracle that pins winner,
   relative rank, logit sign, and final fraction.
7. **API recomputes or trusts stale evidence.** Control: offline artifacts,
   digest/currentness validation, new trial -> stale.
8. **The gate passes while its comparator is broken.** Control: Rule 12
   `> 0` mutation plus the `N = 88` planted variant and clean control.

## Implementation Sequence

1. Freeze schemas and fixtures; capture current full-suite baseline honestly.
2. Write ledger/config/sidecar tests, then implement the sole authority.
3. Instrument production runners and add the static bypass guard.
4. Build and review the backfill manifest/tool; do not generate a passing gate
   until Camden approves its upper bounds.
5. Write paper/oracle tests, then implement matrix, DSR, HAC t-stat, and PBO.
6. Write Rule 12 gate tests and mutations, then implement offline artifact
   generation.
7. Change the API route last, while its no-artifact state remains `unknown`.
8. Run focused tests, mutation driver, and `python -m pytest tests`; record
   baseline-existing failures separately from regressions and do not call a red
   full suite complete.

## Complexity Tracking / Flags

This is too large for one unreviewable implementation PR if every historical
runner is migrated at once. The correct split is by dependency while keeping
Gate 3 non-permissive throughout:

1. ledger authority + sidecars + instrumentation guard;
2. approved backfill + matrix + DSR/PBO pure statistics;
3. immutable artifact + Rule 12 mutations + API reader.

Every intermediate state leaves the API at `unknown`. No split may introduce a
temporary hard-coded pass or a second ledger. This is a reviewability flag, not
authorization to omit any part of spec 033.

