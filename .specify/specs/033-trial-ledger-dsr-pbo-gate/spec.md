# Feature Specification: Lifetime Trial Ledger, DSR, PBO, and Capital Gate 3

**Feature**: `033-trial-ledger-dsr-pbo-gate`  
**Created**: 2026-09-18  
**Status**: Draft specification only; no implementation is authorized by this
spec-writing task.  
**Priority**: P0 — Gate 3 cannot grant capital-readiness permission without
this evidence path.

## Input / Context

The controlling project input is
`claude/research-solo-quant-edge-and-survival.md`, available to this session as
Camden's local project-doc copy at
`C:\Users\Owner\OneDrive\Building Skills\Quant Project Claude\Solo quant edge and survival.md`
(read 2026-09-18). Its first plan item directly requires:

- a lifetime append-only trial ledger keyed by configuration hash and git SHA,
  with the full daily out-of-sample return series for every inspected trial;
- a deliberately conservative pre-ledger trial-count backfill;
- a hand-rolled Deflated Sharpe Ratio (DSR), checked against Bailey and Lopez
  de Prado's worked example (`DSR ~= 0.905` at `N = 88`, rejected; `N = 46`
  passes);
- CSCV Probability of Backtest Overfitting (PBO) over the same trial matrix;
  and
- a candidate threshold of `DSR >= 0.95` at the ledger's current `N`, plus a
  `t-statistic >= 3` floor.

Those numbers are adopted from that project document, not re-derived here.
The project document cites [Bailey and Lopez de Prado, *The Deflated Sharpe
Ratio*](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) and
[Bailey et al., *The Probability of Backtest
Overfitting*](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

The repository constitution remains controlling. In particular, Rules 1-5
govern every return entering this gate, Rule 11 governs the evidence artifact,
and Rule 12 requires proof that this permission gate can go red.

## Verified Starting State

Verified without running `git`, as Rule 10 requires:

- `033` is the next number after the highest existing spec directory,
  `032-live-trading-safety-layer`. Directories `022` through `031` are absent,
  but `033` is the next sequential number after the current maximum and is not
  occupied.
- Outside `venv/`, `.venv/`, and `.specify/specs/`, `PBO` has no match.
  `DSR` and `deflated` occur only in narrative/audit material and Gate 3's
  hard-coded description; no DSR implementation or evidence artifact exists.
- `reports/api/routes/capital_gate.py` always returns Gate 3 as `unknown` and
  supplies no evidence reference.
- A metadata prototype does exist at `scripts/trial_registry.py`, with tests in
  `tests/test_trial_registry.py`, and an empty `docs/trials/trials.jsonl`.
  Nothing outside its test calls it. It is **not** the required ledger: it has
  no canonical configuration hash, records only a short commit identifier,
  permits `trade_pnl` and `unfunded` conventions, points return data into
  regenerable `data/cache/`, does not contain the full series, and is not wired
  to any backtest entry point. Spec 033 MUST migrate or replace it; a second
  independent registry is forbidden.
- The older audit remediation map tentatively assigned selection-bias work to
  spec `035`. That is a stale planning label, not an existing spec or a
  constitutional rule. This spec records the mismatch; implementation MUST
  update cross-references rather than leave two numbers claiming the same work.

## Problem

The project can inspect many variants and later display the best Sharpe as if
only one hypothesis existed. Today it cannot establish how many selection
opportunities occurred, reconstruct the daily OOS returns behind them, compute
DSR or PBO, or prove Gate 3 from a durable artifact. A permanently `unknown`
route is honest but incomplete; changing that string to `passed` without a
ledger would be dishonest.

The feature therefore has four inseparable parts:

1. record every real research backtest attempt before its result is known;
2. conservatively account for research conducted before recording began;
3. calculate DSR, the OOS mean-return t-statistic, and CSCV/PBO from one
   provenance-checked trial matrix; and
4. make Gate 3 read a write-once evidence artifact and fail closed.

## Scope Boundaries

### In scope

- Research backtests invoked by a human, agent, CLI, report API, notebook-like
  script, grid, sweep, or model/feature comparison in this repository.
- Kept, rejected, abandoned, errored, interrupted, repeated, and AI-generated
  candidate variants.
- Required buy-and-hold and random-signal baselines, recorded with a role that
  prevents them from silently becoming selected candidate trials.
- Daily, funded-account, net-of-cost, purged-and-embargoed walk-forward OOS
  returns used for Gate 3.
- Migration of the existing unused registry into one authoritative ledger.
- A machine-readable Gate 3 artifact and the API route that reads it.

### Out of scope

- Inventing new alpha, tuning a strategy, or changing a strategy's behavior.
- Making Gate 1, 2, 4, or 5 evidence-backed.
- Declaring a PBO pass/fail cutoff. The controlling input requires PBO to be
  calculated but supplies no threshold. Spec 033 reports PBO and requires it
  to be valid; it does not invent a second numeric gate.
- Reconstructing nonexistent historical daily return series. Backfilled trials
  increase `N`; they never receive fabricated returns or zero-filled columns.
- Treating DSR/PBO as leakage detection. The source document explicitly notes
  that a planted look-ahead oracle can survive deflation; structural leakage
  controls remain separate gates.
- Real-money execution or any file under `exec/`.

## Definitions

- **Research trial attempt**: one opportunity to inspect the performance of a
  candidate configuration. Re-running the same configuration is another
  attempt and another ledger event; identical config hashes are not deduped.
- **Synthetic test run**: a unit/integration fixture whose result is not
  inspected as research. It MUST use a dependency-injected temporary ledger
  and MUST NOT change lifetime `N`.
- **Trial role**: `candidate`, `buy_and_hold_baseline`,
  `random_signal_baseline`, or `synthetic_test`. Only `candidate` contributes
  to the selection-trial count, but every real backtest role is recorded.
- **Started trial**: a durable record written before result computation. A
  crash after start still represents a selection opportunity and counts in
  `N` when its role is `candidate`.
- **Terminal event**: an append-only `completed`, `rejected`, `errored`, or
  `abandoned` event referring to a started trial. No earlier event is edited.
- **Eligible return series**: a complete daily OOS funded-account return series
  produced by purged, embargoed walk-forward evaluation, net of declared
  commission and slippage, with valid provenance and no non-finite value.
- **Current ledger N**: conservative backfill `N_backfill` plus every
  post-ledger `candidate` start event through the ledger head used by the gate.
  `N` never decreases because a run failed, repeated a hash, lacked a return
  series, or was later disliked.
- **Trial matrix**: one date-indexed `T x M` matrix of eligible candidate OOS
  return columns aligned on their exact shared daily session labels. No missing
  observation is replaced by zero. This same matrix supplies trial Sharpe
  estimates to DSR and is partitioned by CSCV for PBO.
- **Selected candidate**: the preregistered trial whose Gate 3 status is being
  evaluated. Selection occurs outside the gate; the gate does not search for
  whichever column happens to pass.

## User Scenarios and Acceptance

### User Story 1 — Every research attempt becomes durable evidence (P1)

As Camden, I need a lifetime record written before a backtest reveals its
answer, so rejected and failed ideas cannot disappear from the selection count.

**Independent test**: run a successful candidate, a duplicate configuration,
an exception, and an interrupted process against a temporary ledger; verify
four distinct starts, immutable earlier bytes, terminal events where possible,
and `N = 4`.

**Acceptance scenarios**:

1. Given a candidate configuration, when execution begins, then a `started`
   event containing its config hash and full 40-hex git SHA is durable before
   any metric is calculated.
2. Given the same configuration is run twice, then both attempts have distinct
   trial IDs and both count in `N` even though their config hashes match.
3. Given computation raises or the process dies after `started`, then the
   attempt remains in the ledger and still counts.
4. Given a completed eligible trial, then every daily session and OOS return is
   stored in a write-once sidecar whose SHA-256 is committed by the terminal
   ledger event.
5. Given a real human-facing runner, then disabling the lifetime recorder is
   rejected; only an explicitly injected synthetic-test context may use a
   temporary ledger.

### User Story 2 — Pre-ledger research cannot vanish (P1)

As Camden, I need an auditable upper-biased estimate of all earlier selection
attempts, so a missing history makes the gate harder, not easier, to pass.

**Independent test**: build a fixture backfill manifest containing an explicit
grid, repeated artifacts, a remembered range, and an unresolved campaign;
verify full Cartesian products, no deduplication, upper endpoints, upward
rounding, and `unknown` status for the unresolved campaign.

**Acceptance scenarios**:

1. Every historical research campaign has a manifest row naming its evidence
   and its counting method.
2. A historical grid counts its full reachable Cartesian product across model,
   hyperparameter, feature, target, horizon, ticker/universe, seed, and rerun
   dimensions, even if only some outputs survived.
3. Repeated or identical configurations are never deduplicated across scripts,
   artifacts, commits, or remembered runs.
4. A remembered range uses its upper endpoint; the aggregate is rounded up to
   the next power of two and then doubled as an unknown-history reserve.
5. If any known campaign has no defensible finite upper bound, Gate 3 remains
   `unknown`; the implementation MUST NOT choose a convenient finite `N`.

### User Story 3 — DSR and PBO measure selection risk (P1)

As Camden, I need hand-rolled, source-checked DSR and deterministic CSCV/PBO,
so Gate 3 measures the search rather than reporting a raw best Sharpe.

**Independent test**: reproduce the source paper's DSR example and a small
hand-enumerated CSCV oracle, then run both from a single immutable matrix.

**Acceptance scenarios**:

1. The DSR fixture copied from the paper produces approximately `0.905` at
   `N = 88` (absolute tolerance `0.001`) and does not pass `0.95`.
2. The same paper fixture at `N = 46` passes `0.95`.
3. DSR uses `N_current`, not the number of surviving, eligible, unique, or
   matrix-resident trials.
4. CSCV uses `S = 16` contiguous chronological blocks and all
   `C(16, 8) = 12,870` half-block train/test combinations.
5. DSR's observed trial-Sharpe inputs and PBO both come from the same matrix
   hash, dates, columns, return convention, and costs.
6. Missing backfill returns increase DSR's `N` but never become synthetic PBO
   columns.

### User Story 4 — Gate 3 becomes evidence-backed and can go red (P1)

As Camden, I need the API to expose a reproducible Gate 3 verdict, so `passed`
means both numeric thresholds and every provenance requirement were satisfied.

**Independent test**: generate an immutable artifact from a clean fixture,
serve it through the real route, then plant a plausible overfit variant and
prove the same route reports `failed` with the DSR reason.

**Acceptance scenarios**:

1. Gate 3 passes only when `DSR >= 0.95` **and** the HAC OOS mean-return
   `t-statistic >= 3.0`, PBO was successfully computed with `S = 16`, and all
   mandatory evidence is valid.
2. A valid artifact below either numeric threshold reports `failed` and names
   each failed threshold.
3. Missing, malformed, incomplete, unverifiable, or insufficient evidence
   reports `unknown`; a ledger-head or source-hash mismatch reports `stale`.
4. The API never computes statistics on request. It reads and validates one
   immutable artifact, so repeated reads cannot change the verdict.
5. Every non-`unknown` response carries the evidence artifact reference
   required by `CapitalGateItem`.

## Functional Requirements

### A. Authoritative append-only ledger

- **FR-001**: There MUST be exactly one authoritative lifetime trial ledger.
  `scripts/trial_registry.py` and `docs/trials/trials.jsonl` MUST be migrated or
  retired; parallel authorities are forbidden.
- **FR-002**: A real research run MUST append and durably flush a `started`
  event before calculating or rendering a result. The event MUST contain a
  UUID trial ID, UTC instant, trial role, canonical config hash, full git SHA,
  workspace-state status, runner identity, and previous-record hash.
- **FR-003**: Canonical configuration MUST include every result-affecting
  choice available to the runner: data snapshot/hash and price basis, universe,
  date range, features and transforms, label/target and horizon, model and
  hyperparameters, CV folds/purge/embargo, seed, initial capital, commission,
  slippage, liquidation convention, risk-free convention, and code-selected
  defaults. It MUST serialize with one documented canonical JSON encoding and
  use SHA-256.
- **FR-004**: A terminal event MUST refer to its start ID and state
  `completed`, `rejected`, `errored`, or `abandoned`. It MUST NOT modify or
  replace the start event.
- **FR-005**: Every completed real backtest MUST store the full daily OOS
  return series as ordered `(session, return)` observations in a write-once
  repository artifact outside `data/cache/`. The terminal event MUST record
  its relative path, SHA-256, row count, first/last session, frequency, return
  convention, and costs.
- **FR-006**: Gate-eligible returns MUST be daily funded-account log returns
  derived from account equity, net of commission and slippage. In-sample
  returns, predictions, labels, fold-average Sharpes, unfunded trade P&L, and
  gross/costless returns MUST be ineligible.
- **FR-007**: The ledger MUST record rejected, abandoned, errored, interrupted,
  duplicate, manual, API, batch, sweep, and AI-generated candidate attempts.
  Outcome and duplicate hash MUST NOT reduce `N`.
- **FR-008**: Buy-and-hold and random-signal baselines MUST be recorded with
  their own role. They do not increase candidate-selection `N` unless a human
  or agent promoted them into the candidate search family.
- **FR-009**: Synthetic tests MUST inject a temporary ledger and use
  `synthetic_test`; production defaults MUST point to the lifetime ledger and
  MUST NOT expose a silent `record=False` escape hatch.
- **FR-010**: Append, return-sidecar creation, and hash-chain update MUST be
  serialized across processes and crash safe. A partial write MUST be detected
  and must make Gate 3 `unknown`, never silently truncate history.
- **FR-011**: Verification MUST detect edited, deleted, reordered, duplicated,
  and hash-disconnected records, missing/corrupt sidecars, and a sidecar whose
  contents do not match its recorded digest.
- **FR-012**: Dirty or unknown workspace state MUST still be logged. It is
  ineligible for a passing Gate 3 unless the event also records a deterministic
  source-tree content hash sufficient to reproduce the executed code.
- **FR-013**: Every human-facing production call path that can expose backtest
  performance MUST receive a recorder receipt. A static guard MUST enumerate
  those call sites and fail when a new uninstrumented path is added. Direct
  low-level harness calls in unit tests remain allowed only with synthetic
  context.
- **FR-014**: No ledger operation may invoke `git`. Full SHA provenance MUST
  come from an explicit launch value, CI environment, or direct `.git`
  metadata read; missing or ambiguous SHA is recorded and makes the trial
  ineligible rather than guessed.

### B. Conservative pre-ledger backfill

- **FR-015**: A versioned backfill manifest MUST enumerate every known
  pre-ledger campaign and cite repository scripts, reports, artifacts, audit
  evidence, or Camden's signed recollection as its source.
- **FR-016**: For code/config search surfaces, the count MUST be the full
  Cartesian product of every exposed choice, multiplied by tickers/universes,
  targets/horizons, seeds, folds/refolds when they were selection choices, and
  evidenced reruns. The backfill MUST count possible execution, not only saved
  winners.
- **FR-017**: Counts from separate campaigns, artifacts, and reruns MUST be
  added without cross-campaign config-hash deduplication. A trial that may have
  been observed twice is counted twice.
- **FR-018**: Human uncertainty MUST be captured as a closed range and use the
  upper endpoint. After summing all campaign upper bounds, the total MUST be
  rounded upward to the next power of two and doubled. This explicit reserve
  is intentionally biased toward over-counting because the source document
  states that under-counting is the dangerous error.
- **FR-019**: The backfill artifact MUST contain the formula, intermediate
  counts, evidence references, author/approval, date, and SHA-256. Its final
  `N_backfill` is immutable and never revised downward; corrections append a
  superseding record and `N` uses the maximum defensible value.
- **FR-020**: If a known campaign cannot be assigned a defensible finite upper
  bound, the backfill status is incomplete and Gate 3 MUST remain `unknown`.
  No statistical routine may silently omit that campaign.

### C. Trial matrix, DSR, and t-statistic

- **FR-021**: Matrix construction MUST select eligible candidate series by a
  preregistered family definition, verify each digest, and align only exact
  common daily session labels. It MUST NOT zero-fill, forward-fill, backfill,
  interpolate, or reinterpret a missing return as flat.
- **FR-022**: Matrix membership, excluded trial IDs with reasons, shared dates,
  column order, and canonical matrix SHA-256 MUST be emitted before statistics.
- **FR-023**: The selected candidate MUST be named before gate calculation and
  MUST be one verified matrix column. The gate MUST NOT choose the maximum DSR,
  Sharpe, or t-statistic after seeing results.
- **FR-024**: DSR MUST be hand implemented using SciPy only for mathematical
  primitives such as the normal CDF/quantile. No package DSR implementation or
  black-box portfolio-statistics wrapper may determine the result.
- **FR-025**: The implementation MUST expose and test the paper's inputs:
  observed Sharpe, number of observations, skewness, Pearson kurtosis,
  across-trial Sharpe dispersion, and `N_current`; it MUST validate their
  domains and return an explicit undefined result for an invalid denominator
  or insufficient sample.
- **FR-026**: DSR MUST use the selected candidate's verified daily OOS return
  series, the matrix-derived trial Sharpe distribution, and
  `N_current = N_backfill + post_ledger_candidate_starts`. It MUST NOT replace
  `N_current` with unique hashes, completed trials, eligible columns, or an
  effective/clustered trial count.
- **FR-027**: A test fixture transcribed from the DSR paper's worked example
  MUST reproduce `DSR ~= 0.905` at `N = 88` within absolute tolerance `0.001`
  and MUST show that the same fixture passes `0.95` at `N = 46`.
- **FR-028**: The gate t-statistic MUST be the selected candidate's mean daily
  OOS excess log return divided by its Newey-West/Bartlett HAC standard error.
  Bandwidth MUST be recorded and MUST be at least `horizon - 1`; an undefined
  or non-positive standard error cannot pass.
- **FR-029**: Sharpe and t-statistic calculations MUST use the repository's
  declared trading-days-per-year and risk-free log-return convention. Every
  convention and source MUST be included in the artifact.
- **FR-030**: No DSR, t-statistic, PBO, or threshold result may be rendered
  without the source ledger head hash, backfill hash, trial matrix hash,
  selected trial ID/config hash/git SHA, generation code SHA/content hash, and
  generation date.

### D. CSCV / PBO

- **FR-031**: PBO MUST use the exact matrix committed by FR-022 and fixed
  `S = 16`. Rows MUST be chronological and divided into 16 contiguous,
  deterministic, near-equal blocks; block sizes may differ by at most one.
- **FR-032**: The matrix MUST contain at least 16 observations, every block
  MUST be non-empty, and enough eligible strategy columns MUST exist to rank a
  selected strategy. Otherwise PBO is undefined and Gate 3 is `unknown`.
- **FR-033**: CSCV MUST enumerate all `C(16, 8) = 12,870` choices of eight
  in-sample blocks. The complementary eight blocks are OOS; no random subset
  or seed-dependent sampling is allowed.
- **FR-034**: For each split, the implementation MUST select the best
  in-sample column by one preregistered objective, evaluate that same column
  OOS, compute its relative OOS rank and rank logit, and retain the split-level
  record. Tie policy and non-finite handling MUST be deterministic and tested.
- **FR-035**: PBO MUST equal the fraction of valid split logits at or below
  zero under the paper's convention. The artifact MUST include PBO, valid and
  rejected split counts, rank-logit distribution summary, degradation summary,
  `S`, matrix dimensions, and matrix hash.
- **FR-036**: PBO is mandatory evidence but has no pass threshold in spec 033.
  The API MUST display it as a diagnostic and MUST NOT imply that a favorable
  PBO overrides DSR or the t-statistic.
- **FR-037**: A small deterministic matrix with a hand-enumerated or
  independently calculated oracle MUST test block construction, complement
  selection, winner carry-through, rank direction, logit sign, ties, and the
  final probability. A seeded simulation alone is not an oracle.
- **FR-038**: Backfilled trials without return series MUST NOT be added to the
  PBO matrix, imputed, cloned from surviving trials, or treated as zero-return
  strategies. Their penalty is exclusively the larger DSR `N` and the
  backfill-completeness requirement.

### E. Gate artifact and API

- **FR-039**: Gate calculation MUST write a new immutable JSON artifact for
  every evaluation. It MUST never overwrite prior evidence. An append-only
  index may identify the latest artifact.
- **FR-040**: The artifact MUST include schema version, artifact ID, UTC
  generation instant, selected candidate, status, all threshold operands,
  threshold values, PBO evidence, matrix/ledger/backfill provenance, CV and
  cost metadata, row/date coverage, software/source hashes, and ordered reason
  codes.
- **FR-041**: `passed` requires all of: verified complete ledger chain and
  sidecars; complete finite backfill; eligible selected candidate; valid shared
  matrix; successful `S = 16` PBO; `DSR >= 0.95`; and HAC t-statistic `>= 3.0`.
- **FR-042**: Valid evidence with `DSR < 0.95` or t-statistic `< 3.0` MUST be
  `failed`. Equality passes both thresholds.
- **FR-043**: Missing, malformed, corrupt, insufficient, non-finite, or
  incomplete evidence MUST be `unknown`, not `failed` or `passed`. An artifact
  whose recorded ledger head, sidecar, backfill, matrix, or selected config no
  longer matches current inputs MUST be `stale`.
- **FR-044**: `reports/api/routes/capital_gate.py` MUST validate and read the
  artifact; it MUST NOT calculate DSR/PBO during an HTTP request or hard-code a
  known status.
- **FR-045**: Gate 3's description MUST state the actual thresholds and that
  PBO is reported diagnostic evidence. The current phrase "remains positive"
  MUST be removed because a positive probability is not the specified gate.
- **FR-046**: Every `passed`, `failed`, or `stale` Gate 3 response MUST include
  a repository-relative evidence reference accepted by `CapitalGateItem`.
- **FR-047**: The route MUST remain `unknown` with the current no-evidence
  explanation until a valid artifact exists. Implementing code without
  generating real evidence does not grant a pass.
- **FR-048**: Test/example artifacts MUST be visibly labeled
  `EXAMPLE — NOT A RESULT` and MUST live under test fixtures, never in the
  production artifact index.
- **FR-049**: Artifact generation MUST be an explicit offline command that
  names the selected candidate and family. It MUST exit nonzero for unknown or
  stale evidence and MUST print the new artifact path for Camden to review.
- **FR-050**: No implementation task may claim the project is capital-ready.
  This spec only closes Gate 3's evidence mechanism; Gates 1, 2, 4, and 5 and
  human approval remain independent blockers.

### F. Rule 12 proof that the gate can go red

- **FR-051**: The real Gate 3 evaluator and real API route MUST be tested with
  a plausible selected strategy that has an attractive unadjusted result but
  the paper fixture's `DSR ~= 0.905` at `N = 88`. It MUST report `failed` with
  reason code `dsr_below_threshold`, even when its t-statistic is at least 3.
- **FR-052**: A clean control using the paper fixture's `N = 46` case, valid
  PBO evidence, and t-statistic at least 3 MUST report `passed` through the
  same evaluator and route.
- **FR-053**: The planted defect and control MUST differ only in the declared
  selection-history condition necessary to exercise deflation; costs, return
  dates, candidate series, and other gate inputs remain fixed.
- **FR-054**: An isolated mutation test MUST weaken `DSR >= 0.95` to
  `DSR > 0`. The planted `N = 88` case MUST catch it. An unmutated control MUST
  pass cleanly, and the repository module MUST remain byte-identical.
- **FR-055**: A second isolated mutation MUST replace `N_current` with the
  smaller eligible matrix-column count. A fixture with backfilled trials MUST
  catch it, proving the code reads the lifetime count rather than surviving
  artifacts only.
- **FR-056**: Failure assertions MUST name the specific reason code and
  evidence path, not merely assert `status != passed`.
- **FR-057**: Ledger guards MUST also plant realistic edited-record,
  deleted-record, missing-sidecar, uninstrumented-runner, and partial-write
  defects, each with a clean control, as required by Rule 12.
- **FR-058**: Time-series tests MUST cover off-by-one date alignment, first and
  last row, fold joins, a missing session, holiday gaps, unequal series starts,
  and future-row perturbation under Rules 1 and 5.
- **FR-059**: Tests MUST be network-free and run under the canonical command
  `python -m pytest tests`. Focused test commands are development aids, not the
  final verification gate.

## Gate Decision Table

| Evidence state | DSR | HAC t-stat | PBO S=16 | Gate 3 |
|---|---:|---:|---|---|
| Complete and current | `>= 0.95` | `>= 3.0` | valid | `passed` |
| Complete and current | `< 0.95` | any finite value | valid | `failed` |
| Complete and current | any finite value | `< 3.0` | valid | `failed` |
| Missing/corrupt/incomplete/undefined | any | any | any | `unknown` |
| Artifact no longer matches inputs | any | any | any | `stale` |

PBO has no numeric pass row because no threshold was supplied by the source
requirements. A missing or invalid PBO is incomplete evidence and therefore
`unknown`; a high PBO is reported without silently inventing a cutoff.

## Edge Cases

- A trial starts but the process is killed before any return: count it in `N`;
  retain `started`; no fake terminal event or return series.
- Same config, same SHA, same seed, run twice: two attempts, one config hash,
  both counted.
- Same config on a dirty tree: distinct source-tree hash; ineligible if the
  dirty content cannot be reproduced.
- No `.git` directory or detached/unresolved HEAD: log the attempt with unknown
  SHA and make it ineligible; do not drop it from `N`.
- Candidate has fewer than 16 shared observations: PBO undefined, Gate 3
  `unknown`.
- One series has an interior missing day: do not fill. Exclude with a reason or
  reduce to a preregistered exact intersection; record the choice and matrix
  hash.
- Zero-variance candidate, non-finite skew/kurtosis, invalid DSR denominator,
  or non-positive HAC standard error: `unknown`, not an exception-shaped pass.
- All strategies tie in a CSCV split: apply the documented deterministic tie
  rule and test it; do not depend on column insertion order accidentally.
- A backfilled campaign has no returns: increases `N`, excluded from matrix.
- Ledger is valid but empty: `unknown`.
- Artifact is valid but references a prior ledger head after a new trial
  starts: `stale` immediately; Gate 3 cannot remain passed while `N` changes.
- The selected trial is later abandoned: the historical artifact remains
  immutable, but a new evaluation cannot select it without an explicit new
  selection record.

## Constitution Review and Flags

| Rule | Bearing | Status |
|---|---|---|
| 1 — Point-in-time | Only chronological OOS return rows enter the gate; future-perturbation tests required. | Conforms |
| 2 — Purged/embargoed walk-forward | Eligibility requires recorded folds, purge, and embargo. CSCV is an additional selection-bias analysis, not a replacement for model CV. | Conforms |
| 3 — Costs/slippage | Eligible series are funded-account returns net of both. Existing registry's unfunded/trade-P&L options cannot pass. | Conforms |
| 4 — Baselines | This spec changes no strategy. Baselines are recorded but are not silently counted as selected candidates. Any later strategy PR still owes Rule 4. | Conforms |
| 5 — Time tests | Matrix alignment and return series receive off-by-one, boundary, and gap tests. | Conforms |
| 6 — Dependencies | SciPy is already pinned in `requirements.txt`; no new dependency is required. | Conforms |
| 7 — Execution | No broker or `exec/` work. | Conforms |
| 8 — Layer separation | Recording belongs around human-facing research runners, not inside signal logic. The low-level harness may return funded equity/returns but MUST NOT learn model/feature semantics. Any implementation that injects research config into the harness instead must be flagged before coding. | Conforms with stated boundary |
| 9 — Merge gate | Formula inputs, artifacts, reason codes, and data flow are explicit. Camden still must explain the implementation before merge. | Conforms |
| 10 — Version control | No agent runs `git`; provenance reads metadata or accepts an explicit SHA. Camden commits. | Conforms |
| 11 — Provenance | Every rendered number points to immutable ledger, matrix, backfill, source, and artifact hashes. | Conforms |
| 12 — Red proof | Paper-based failing variant, clean control, comparator mutation, lifetime-N mutation, and ledger defects are mandatory. | Conforms |

**Constitution conflict result**: no requested requirement inherently conflicts
with the constitution. Two tensions are resolved by failing closed rather than
weakening either source: (1) a dirty tree cannot be identified by git SHA alone,
so a reproducible source-tree hash is also required; and (2) unrecoverable
history cannot be given a convenient finite count, so Gate 3 stays `unknown`
until Camden approves a defensible upper bound. If implementation discovers
that complete instrumentation requires the harness to understand signal/model
configuration, that is a Rule 8 conflict and MUST be flagged rather than
implemented across the boundary.

## Success Criteria

- **SC-001**: Every production backtest entry point identified by the static
  guard produces a durable start receipt before exposing any result.
- **SC-002**: Duplicate, failed, interrupted, and abandoned candidate attempts
  all increase `N`; synthetic tests do not affect the lifetime ledger.
- **SC-003**: The backfill manifest is reviewable line by line, intentionally
  upper-biased, and either yields immutable `N_backfill` or blocks the gate as
  incomplete.
- **SC-004**: The paper fixture produces DSR within `0.001` of `0.905` for
  `N = 88`, fails `0.95`, and passes for `N = 46`.
- **SC-005**: CSCV enumerates exactly 12,870 splits at `S = 16` and matches an
  independent deterministic oracle.
- **SC-006**: One matrix hash is reported by DSR inputs and PBO outputs; no
  backfilled return is fabricated.
- **SC-007**: Gate 3 passes only at `DSR >= 0.95` and HAC t-statistic `>= 3`,
  with valid PBO and complete current provenance.
- **SC-008**: The Rule 12 planted overfit case and both required mutations go
  red with specific reason codes; the clean control goes green.
- **SC-009**: The API reports `unknown` without evidence, `stale` after a new
  trial changes the ledger head, and evidence-backed `failed`/`passed` only
  from immutable artifacts.
- **SC-010**: Focused spec tests pass and `python -m pytest tests` is run and
  reported honestly; no network and no new dependency are introduced.

