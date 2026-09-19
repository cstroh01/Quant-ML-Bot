# Research: Trial Ledger, Deflated Sharpe, PBO, and Gate 3

**Spec**: `033-trial-ledger-dsr-pbo-gate`  
**Purpose**: Record the source basis, decisions, rejected alternatives, and
unresolved flags. This document defines no implementation status.

## Source Hierarchy

1. `.specify/memory/constitution.md` — non-negotiable repository rules.
2. `CLAUDE.md` — repository workflow and module boundaries.
3. `claude/research-solo-quant-edge-and-survival.md` — controlling project
   research input, read from Camden's local copy at
   `C:\Users\Owner\OneDrive\Building Skills\Quant Project Claude\Solo quant edge and survival.md`.
4. The user's spec-033 task — fixes `S = 16`, `DSR >= 0.95`, t-statistic
   `>= 3`, and the Rule 12 planted-defect/control obligation.
5. Primary papers linked by the project document:
   - [Bailey and Lopez de Prado, *The Deflated Sharpe
     Ratio*](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
   - [Bailey et al., *The Probability of Backtest
     Overfitting*](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)

The numeric thresholds in spec 033 are copied from levels 3 and 4. They are
not estimated from this repository's current results.

## R1 — The existing “trial registry” is not the requested ledger

**Decision.** Migrate or replace `scripts/trial_registry.py`; do not layer a
new ledger beside it.

**Inspection result.** The repository contains:

- `scripts/trial_registry.py`;
- `tests/test_trial_registry.py` (10 focused tests currently pass); and
- an empty `docs/trials/trials.jsonl`.

No production file calls `log_trial`. The module records optional metadata and
a path/digest for returns, but not a canonical complete configuration or full
series. It accepts `funded_account`, `trade_pnl`, and `unfunded` return
conventions. Its default return paths in tests point into `data/cache/`, which
CLAUDE.md defines as regenerable. It reads only a seven-character commit ID and
its dirtiness helper returns false for ordinary ref-based worktrees rather than
determining state. It has no DSR, PBO, backfill, or Gate 3 integration.

Calling this complete would preserve exactly the selection-history gap the new
gate exists to close. Calling it nonexistent would also be inaccurate. The
spec treats it as an unused prototype and makes one-authority migration an
acceptance requirement.

**Rejected alternative.** Keep `trial_registry.py` for old results and add
`trial_ledger.py` for new ones. Rejected because two sources can disagree on
`N`, and the permissive one would eventually be used by mistake.

## R2 — Record attempts before results, and count starts

**Decision.** A candidate's durable `started` event increases `N`; completion
is not required.

**Rationale.** Selection bias is created when a researcher chooses to inspect
a configuration. If errored, interrupted, abandoned, duplicated, and disliked
runs disappear, the record becomes a winners-only sample. Writing after
metrics are known gives every caller a window in which an inconvenient trial
can be omitted.

The terminal event is separate and immutable. It adds outcome and return
provenance but never edits the start. Repeating the same config counts twice
because the result was exposed twice and could influence later research.

**Rejected alternatives.** Count only completed trials; deduplicate by config
hash; log only kept candidates. All three undercount the search and reward
losing evidence.

## R3 — A production wrapper, not model knowledge inside the harness

**Decision.** Put lifecycle recording around human-facing research runners.
Keep `run_backtest` an accounting primitive.

**Rationale.** A configuration hash needs feature, target, model, CV, seed,
data, cost, and account choices. Passing those semantics into
`backtest_harness.py` would make accounting know how a signal was produced,
contrary to Rule 8. The wrapper can own opaque research configuration, call
existing code, and record the funded output.

The obvious weakness is bypass: an old script can call the harness directly.
The remedy is a static inventory test over production/human-facing call sites,
not coupling the harness to research. Unit tests legitimately call the harness
directly; they inject synthetic context and never affect lifetime `N`.

**Rejected alternatives.** Auto-log every low-level `run_backtest` call.
Rejected because current tests and required baselines call it many times, and
the harness lacks the research context needed to classify those calls. It
would pollute `N` with mechanical accounting fixtures while crossing Rule 8.

## R4 — Repository-resident event log plus write-once return sidecars

**Decision.** Use canonical JSONL events and one canonical JSONL daily-return
sidecar per completed trial, all outside `data/cache/`.

**Rationale.** The ledger is irrecoverable research evidence, not a cache.
Sidecars keep append operations small, make each series independently
content-addressable, and avoid rewriting a monolithic file. The terminal event
binds the sidecar by path and SHA-256, so a missing or changed sidecar breaks
verification.

JSON/JSONL uses the standard library, is diffable, and makes Rule 9 review
possible. Compression or binary columnar storage can be reconsidered only if
measured size becomes material; it is premature at the expected scale and
would add determinism/dependency questions.

**Rejected alternatives.** Paths into `data/cache/` (regenerable and may
vanish); mutable SQLite rows (updates make append-only semantics harder to
audit); a single huge JSON record per trial (expensive partial-write recovery);
Parquet (new serialization/dependency surface with no initial need).

## R5 — Configuration identity is broader than model parameters

**Decision.** Hash canonical resolved configuration, not raw CLI arguments.

**Rationale.** Two runs with the same estimator hyperparameters can differ in
data vintage, universe, feature transform, target horizon, folds, costs,
starting capital, or a default selected in code. Those are different trials.
A hash that omits them creates false duplicates and cannot reproduce the
result.

The stored event keeps both the canonical object and SHA-256. A hash alone is
not explainable. List ordering is preserved when behavior depends on it;
set-like fields are sorted. Data files carry digests. Non-finite numeric config
values are rejected before canonicalization.

Full git SHA is also mandatory, but SHA alone does not identify a dirty tree.
Dirty or unknown state therefore needs a source-tree content digest to become
Gate-eligible. This strengthens, rather than changes, the user's SHA
requirement.

## R6 — Conservative historical backfill method

**Decision.** Count full historical search surfaces, add without deduplication,
use uncertainty upper bounds, round up to the next power of two, then double.

**Method.** Build one reviewed row per historical campaign:

1. Identify scripts, result tables, audit artifacts, reports, configs, or a
   Camden-approved recollection that proves the campaign existed.
2. Enumerate every exposed selection dimension: model family, hyperparameter,
   feature set, target, horizon, ticker/universe, seed, refold, cost setting,
   and rerun.
3. Use the full Cartesian product even if surviving artifacts show only a
   subset. This treats “could have been run in that campaign” as run.
4. Add separate campaigns and artifact counts without config deduplication.
5. For a remembered range, use the upper endpoint.
6. Sum campaign upper bounds, round upward to a power of two, and double the
   result as a reserve for unrecorded ad hoc/AI/manual repeats.

This method is conservative by construction: it includes unproven members of
historical grids, double-counts possible repeats, always chooses the high end,
rounds upward, and then adds 100% reserve. Over-counting makes DSR harder to
pass; under-counting would make it easier.

It is not magic. If Camden identifies a campaign whose possible trial count
has no defensible finite upper bound, no multiplier proves completeness. That
case remains `unknown` until a human-approved bound exists.

**Rejected alternatives.** Count existing specs, saved result rows, unique
config hashes, or current grid sizes only. Each is a lower bound and silently
forgets abandoned or overwritten research. Use an “effective number of trials”
from correlations. Rejected because the task explicitly gates at current
ledger `N`, and raw `N` is the conservative choice.

## R7 — Separate lifetime N from actual matrix columns

**Decision.** DSR uses lifetime `N_current`; matrix analyses use actual
eligible columns `M`; `N_current >= M` is expected.

**Rationale.** Pre-ledger trials generally have no recoverable daily series.
Fabricating them as zero columns would distort both Sharpe dispersion and PBO.
Dropping them from `N` would erase selection history. The honest split is:

- `N_current` penalizes DSR for every known/estimated selection attempt; and
- the `T x M` matrix contains only verified real series and drives the observed
  trial-Sharpe distribution plus CSCV/PBO.

The artifact reports both counts and every excluded trial/reason. A smaller
`M` never authorizes substituting `M` for `N_current`.

## R8 — Matrix alignment uses exact shared dates and no imputation

**Decision.** Validate series independently, then use the exact intersection
of eligible daily session labels under a preregistered family definition.

**Rationale.** CSCV requires strategies evaluated over comparable observations.
Zero-filling a missing day says “the strategy earned zero,” which is a return
claim without evidence. Forward/back filling returns is mathematically invalid
and violates Rule 1. Union alignment would therefore manufacture data.

The exact intersection is allowed only when coverage/exclusion policy was
declared before seeing statistics and the resulting dates are committed in the
matrix hash. If intersection would erase a material part of history, the gate
should be unknown or use a narrower preregistered family; it must not choose
dates that improve the candidate.

**Rejected alternatives.** Union plus zeros; pairwise correlations with
different dates; per-column PBO windows. None produces one common matrix.

## R9 — Hand-rolled DSR with a paper fixture

**Decision.** Implement the published structure directly and use SciPy only
for normal distribution primitives.

The probabilistic Sharpe component is of the form:

```text
PSR(SR*) = Phi(
    (SR_hat - SR*) * sqrt(T - 1)
    / sqrt(1 - skew * SR_hat + ((kurtosis - 1) / 4) * SR_hat^2)
)
```

where kurtosis is Pearson kurtosis and all Sharpe inputs use the same sampling
frequency. DSR sets `SR*` to the expected maximum null Sharpe under `N` trials,
using the paper's extreme-value approximation, Euler's constant, normal
quantiles, and the observed dispersion of trial Sharpe estimates.

The implementation must transcribe the paper's worked-example inputs into a
labelled test fixture rather than reverse-engineer inputs to hit a desired
answer. The required observable checks are supplied by the project document:
approximately `0.905` at `N = 88` and a pass at the `0.95` threshold when
`N = 46`.

For repository returns, use the non-annualized daily Sharpe inside the PSR/DSR
formula with daily `T`; an annualized descriptive Sharpe may be emitted
separately. Mixing annualized Sharpe with a daily observation count changes the
small-sample adjustment and is forbidden. The paper fixture is the final
convention oracle.

**Rejected alternative.** Import a DSR value from a finance package. Rejected
by the direct “hand-rolled” requirement and because hidden skew/kurtosis and
annualization conventions defeat Rule 9.

## R10 — The t-statistic is HAC-adjusted OOS mean evidence

**Decision.** Define the gate statistic as mean daily OOS excess log return
divided by its Newey-West/Bartlett standard error, with lag at least
`horizon - 1`.

**Rationale.** The requested “t-statistic floor” is otherwise ambiguous.
Financial returns and overlapping holding/label horizons can be serially
dependent; the naive `s / sqrt(T)` denominator can inflate evidence. The repo
already has `metrics.mean_log_return_se` and tests tying HAC bandwidth to the
horizon. Reusing that convention avoids a second uncertainty formula.

The source project document says “t > 3.0,” while the user's direct task says
“floor >= 3.” The direct task controls, so exact equality passes. This is not a
constitutional conflict, but the artifact must state the inclusive boundary.

**Rejected alternatives.** Use raw annualized Sharpe as a t-stat; use fold
count as sample size; use a fixed lag smaller than `horizon - 1`; report a
classical iid t-stat without stating the assumption.

## R11 — CSCV/PBO uses S=16 and all complements

**Decision.** One deterministic chronological matrix, 16 contiguous blocks,
all `C(16, 8) = 12,870` half-block combinations.

**Rationale.** Sampling a subset adds unnecessary Monte Carlo variation and a
seed to a tractable calculation. Contiguous blocks preserve local time
structure. Every split selects the best IS trial under a preregistered
objective, carries that same trial OOS, ranks it among the OOS alternatives,
and computes the paper's rank logit. PBO is the fraction of valid logits at or
below zero.

Tie handling must be explicit and column-order invariant. A deterministic
average-rank convention is preferred; the implementation research step must
confirm it against the paper's convention before coding and the hand oracle
must pin the sign.

**Rejected alternatives.** Random 16-fold assignments; random split sampling;
choosing a new winner OOS; using separate matrices for DSR and PBO; silently
discarding invalid splits.

## R12 — PBO is required evidence, not a threshold invented here

**Decision.** Calculate and report PBO, but do not gate on a numeric PBO level.

**Rationale.** The source project document says to add CSCV/PBO; the direct
task fixes `S = 16`; neither supplies a PBO pass threshold. Inventing one in an
implementation spec would pretend a policy decision came from research when it
did not. A missing/invalid PBO still makes the evidence incomplete and the
status `unknown`.

This distinction must be obvious in the UI: DSR and t-statistic are threshold
operands; PBO is a mandatory diagnostic. Camden can add a threshold later by
amending a spec with a cited basis.

## R13 — Gate artifact is immutable and API computation-free

**Decision.** Compute offline, write a new content-addressed artifact, and let
the API validate/read it.

**Rationale.** Statistical computation during an HTTP request is slow,
non-reproducible under changing files, and difficult to cite. An immutable
artifact records exactly which ledger head, backfill, matrix, candidate, code,
and conventions generated each value. Rule 11 then has a concrete source.

Any new candidate start changes the ledger head and `N`; the prior artifact is
immediately stale. It remains historically valid but no longer supports a
current pass.

**Rejected alternatives.** Hard-code a status; calculate on each GET; overwrite
`latest.json`; treat a past pass as current after new research.

## R14 — Rule 12 proof uses a realistic selection-history defect

**Decision.** Use the source paper's `N = 88` deflation failure as the planted
bad strategy condition, the `N = 46` case as the clean control, and mutate the
real comparator plus the real `N` source in isolated copies.

**Rationale.** A plausible failure is not “all returns are NaN.” It is a
strategy whose unadjusted result and t-statistic look attractive after many
attempts but whose DSR is only about `0.905`. Weakening the threshold to
`DSR > 0` recreates the existing route text's nearly vacuous standard. Replacing
lifetime `N` with surviving matrix columns recreates survivorship. Those are
the exact defects this gate exists to catch.

The clean control is essential: a test that only gets red may be exercising a
gate stuck on failure. Both cases pass through the real evaluator and API.
Failure assertions name the reason code and artifact.

## R15 — Numbering and roadmap mismatch

**Decision.** Use `033` as directed and record that the audit remediation plan
previously mapped this work to `035`.

**Rationale.** The directory inventory's highest existing number is 032 and no
033 directory existed before this task. The old remediation mapping is a plan,
not a constitutional authority. Future implementation should update those
cross-references so work is not scheduled twice.

## R16 — Constitution conflict audit

No direct conflict was found.

- The ledger strengthens Rules 1-5 rather than bypassing them.
- Existing SciPy avoids a Rule 6 dependency addition.
- The research wrapper preserves Rule 8; injecting semantic config into the
  harness would create a conflict and must be flagged if proposed.
- No `git` command is needed or authorized under Rule 10.
- Immutable hashes and artifacts implement Rule 11.
- The planted bad variant, control, and isolated mutations implement Rule 12.

Two incomplete-evidence cases deliberately remain non-permissive: an
unreproducible dirty tree and an unbounded historical campaign. The spec does
not “resolve” either with an optimistic assumption; it returns `unknown`.

## Open Implementation Questions That Do Not Change the Contract

1. Which human-facing scripts are still intended research entry points versus
   diagnostics? The implementation must inventory them and record the list in
   the instrumentation test; uncertainty defaults to instrumented.
2. Whether to rename `trial_registry.py` or upgrade it in place. Exactly one
   authority is the contract either way.
3. The precise deterministic CSCV tie convention after matching the paper.
   It must be documented and column-order invariant.
4. Whether split-level PBO evidence is stored inline or in a digested sidecar.
   It must remain independently reproducible.
5. The campaign rows and upper bounds in the real backfill manifest. Camden's
   review is required because the repository cannot prove forgotten off-repo
   work. Until approved, Gate 3 remains `unknown`.
