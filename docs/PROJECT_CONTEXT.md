# Quant-ML-Bot — Project Context

_Last updated: 2026-09-06_

## Spec 014 - Scale-free features and fold-fit standardization: DONE

The fix for the Phase 3 negative result. Zero models beat baseline and ridge
was ill-conditioned; the cause was the design matrix, not the model.

- `scripts/features.py` now declares two named feature sets.
  `SCALE_FREE_FEATURE_COLUMNS` is the **default**: `Log_Return`,
  `Rolling_Volatility`, `SMA_Spread` (`Short_SMA/Long_SMA - 1`),
  `Close_To_Short` (`Close/Short_SMA - 1`), `Rel_Volume` (`Volume` over its
  trailing mean). `LEVEL_FEATURE_COLUMNS` is the old five, kept as the
  control the committed AAPL result was computed on.
- `features.FEATURE_COLUMNS` is **gone**, not repointed. The name meant the
  level set; letting it mean the scale-free one would change what existing
  code computes without changing what it says. Callers use
  `feature_columns(feature_set)`.
- `EstimatorSpec` gained `scale`. `build_estimator` returns a
  `StandardScaler` then estimator `Pipeline` for `logistic` and `ridge`, and
  a bare estimator for both `hgb` entries (a tree cannot see a monotone
  rescaling - asserted, not assumed). Because all three fit sites already fit
  per fold, the scaler does too: no call site changed.
- **Two defects, not one.** Non-stationarity (a fold trained on $50 bars
  extrapolating to $200 bars) and collinearity. Standardization fixes
  *neither* - it is a diagonal transform and cannot change a correlation.
  It was still worth adding, for the six-order-of-magnitude spread between
  `Log_Return` and `Volume` that made a single `alpha` meaningless. That is a
  third, smaller defect, and conflating it with the reported one is why
  "add a scaler" looked sufficient.

**Measured on cached 10y AAPL** (`scripts/feature_diagnostics.py`):

| | levels | scale_free |
|---|---|---|
| standardized condition number | 36.17 | 2.15 |
| max VIF | 268.31 | 1.60 |
| largest absolute correlation | 0.998 (`Short_SMA`/`Long_SMA`) | 0.527 (`Log_Return`/`Close_To_Short`) |

36.17 is above the conventional ill-conditioning line of 30 - independent
confirmation of the reported defect, on real data.

**A near-miss worth recording.** The first implementation defined the second
ratio as `Close/Long_SMA - 1` ("price against the long trend"), which sounds
right and is not: `Close/Long == (Close/Short) * (Short/Long)`, so it
re-measures the crossover spread. It correlated **0.865** with `SMA_Spread`
while passing every scale-invariance test and improving the condition number
9x. Only the pairwise VIF/correlation assertions caught it. Using the two
*legs* of that identity instead - fast (`Close/Short`) and slow
(`Short/Long`) - loses nothing, since their product recovers the long-trend
quantity exactly, and drops the correlation to 0.325. This is why the spec
states FR-005 pairwise rather than as a condition-number threshold.

- Two new diagnostic entry points: `feature_diagnostics.py` (conditioning)
  and `feature_set_comparison.py` (paired significance - McNemar for the
  classification entries, Wilcoxon signed-rank for the regression ones).
  Running the second is a **merge requirement**, because better conditioning
  is a property of the matrix and not evidence that any prediction improved.
  Its screening bar is p < 0.10 one-sided on at least one of four entries -
  explicitly *not* a capital-readiness bar, which is the deflated Sharpe step
  and comes later.
- The `logistic_baseline` equivalence tests still pass element for element,
  and now pin `feature_set="levels"` and `scale=False` explicitly rather than
  relying on defaults that this spec changed.
- No new dependency (Rule 6): `sklearn.pipeline`/`sklearn.preprocessing` are
  new imports of a package already in use; `scipy` and `statsmodels` were
  already in `requirements.txt`.
- New `tests/test_feature_scaling.py`. Full suite: **301 passed**.

## Spec 011 - Nested, leakage-safe hyperparameter tuning: DONE

`scripts/model_cv.py` selects hyperparameters using only an outer fold's own
training positions, which after spec 006's embargo fix are sorted but *not*
contiguous. The inner splitter never slices the original frame: it builds a
sub-frame from `train_indices`, runs the real `walk_forward_splits` on it,
and maps positions back. A row outside `outer_train_indices` is not in the
sub-frame at all, so it cannot be selected on.

This was code-complete on disk before spec 014 and was still listed as
pending here; recorded now.

## Spec 010 — Estimator registry: DONE

Gave the project one place a model is declared, and one walk-forward
fit/predict loop that works for either task.

- New `scripts/estimators.py`: `EstimatorSpec` (factory + `param_grid` +
  `default_params`) and `ESTIMATOR_REGISTRY` keyed on `(name, task)`, with
  four entries — `logistic`/classification, `ridge`/regression, and
  **`hgb`/both**, using scikit-learn's `HistGradientBoosting*`. That is
  Phase 3's gradient-boosting feature, added as a registry entry with **no
  change to the fit/predict loop**, which was the whole argument for
  building a registry first.
- `fit_predict_walk_forward` fits one estimator per fold (never once on the
  whole frame) and returns `Int64`/`pd.NA` for classification or
  `float64`/`NaN` for regression. The regression path did not exist before
  this spec — `LogisticRegression` raises on a continuous label.
- Proven equivalent to `logistic_baseline.walk_forward_predictions` element
  for element on the classification path, so the Phase 2 control is pinned
  before spec 011 adds tuning as a second possible source of difference.
  `logistic_baseline.py` remains untouched.
- No new dependency (Rule 6): scikit-learn was already in use, and both
  `HistGradientBoosting*` and `Ridge` ship with it.
- New `tests/test_estimators.py`. Full suite: **210 passed**.

## Spec 009 — Selectable prediction target: DONE

Made the prediction target a real parameter instead of the hardcoded
`shift(-1)` direction label buried in `logistic_baseline.build_features`.

- New `scripts/targets.py`: `direction_label` (nullable `Int64`, matches
  the old label exactly) and `forward_log_return_label` (continuous,
  `NaN` where unobservable or non-positive), both behind `build_target(kind,
  horizon)`, which hands back `(label, task, label_horizon)` so a caller
  passes one number to both the label and `walk_forward_splits` instead of
  writing the horizon twice.
- New `scripts/features.py`: the general `build_features`, parameterized by
  window sizes, `target_kind`, and `label_horizon`. Proven equivalent to
  `logistic_baseline.build_features` by test, not by inspection.
  `logistic_baseline.py` itself is untouched — it stays the pinned Phase 2
  control result.
- Rejects `horizon <= 0` (a zero-horizon label is silently `False`/`0.0`
  everywhere) and an unrecognized target kind (no default, ever).
- New `tests/test_targets.py`: off-by-one both ways, boundaries, the
  positional-not-calendar gap case, mutation check, equivalence with the
  baseline. Full suite: **180 passed**.
- Sets up specs 010-013 directly: `task` (`"classification"`/`"regression"`)
  is what an estimator registry keys on next.

## Spec 008 — Metrics reporting layer: DONE

Added the risk-adjusted reporting a strategy comparison actually needs —
until now the harness produced a trade log and nothing downstream of it.

- New `scripts/metrics.py`: `equity_curve` (per-bar P&L reconciled to the
  harness's own trade-by-trade arithmetic to 1e-9), `sharpe_ratio`,
  `max_drawdown`, and `performance_summary` tying them together.
- New `scripts/constants.py`: `TRADING_DAYS_PER_YEAR` and
  `RISK_FREE_RATE_ANNUAL`, lifted out of `return_stats.py` so both modules
  share one number instead of two copies that could drift.
- An empty trade log is treated as an expected outcome, not an error — the
  path a cost-aware entry rule (spec 012) is expected to travel through
  often.
- New `tests/test_metrics.py`. Full suite: **152 passed, 70 subtests**.

## Spec 007 — OOS coverage index bug: FIXED

A latent index/position bug in `logistic_baseline.build_ml_signal`: the
first out-of-sample row was being located by pandas index *label*
(`first_valid_index()`) and then fed to `.iloc`, which expects a *position*.
The two only agree on a fresh 0-based `RangeIndex` — true of every caller
today, so nothing was wrong yet, but a per-ticker slice (Phase 3's
multi-ticker runner, spec 013) would have silently truncated the live
window or raised outright on a non-`RangeIndex` frame.

- Fixed to derive the position from a boolean mask (`np.flatnonzero`), never
  from the series' own index.
- New regression tests pin the fix against exactly this failure mode.

## Spec 006 — Embargo window semantics: FIXED

A measurement taken while scoping Phase 3 (gradient boosting, continuous
targets, nested tuning, multi-ticker generalization) found that
`walk_forward_cv.py`'s training set never grew: the embargo added in spec
003 permanently excluded each test window rather than only the gap after
it, and because test windows tile contiguously, their union swallowed the
whole expanding region. Every fold was training on the same first
`initial_train_months` of data.

- Fixed: the embargo is now a `embargo_bars`-row gap immediately after each
  fold's test window, added to a persistent ledger — a later fold's test
  data re-enters training, only the gap stays excluded.
- **All of spec 005's reported AAPL numbers are now known-stale** (produced
  under the old, non-expanding semantics) — flagged here as the reason,
  not silently corrected, since the honest replacement figures come from
  the Phase 3 multi-ticker run (spec 013), not a rerun of this fix alone.
- Named consequence, spec 011: after this fix a fold's legal training
  positions are no longer contiguous (an earlier fold's embargo gap can
  fall inside a later fold's training range), which is exactly what a
  nested hyperparameter search has to handle correctly.

## Spec 005 — ML signal wiring: DONE

Wired `logistic_baseline.py`'s walk-forward model into an actual tradeable
signal and ran it through `backtest_harness.py`, beside both Rule 4
baselines with identical costs — the first spec to actually trade on
spec 003's purge/embargo fix rather than just score it.

- `walk_forward_predictions`: collects one out-of-sample prediction per
  row, fold-by-fold (same `label_horizon=1, embargo_bars=1` as
  `evaluate_walk_forward`) — never fit-once-predict-all, which would leak.
- `build_ml_signal` / `_signal_from_predictions`: turns predictions into
  `Buy_Next_Open`/`Sell_Next_Open` via the same next-open-shifted
  transition-detector pattern `sma_crossover_signal` uses. Rows before the
  first fold have no prediction and trade flat.
- `main()` slices to the live (post-warm-up) window and reports the ML
  strategy beside buy-and-hold and the random baseline, same $1.00/5bps
  cost model as `ma_crossover_backtest.py`.
- New `tests/test_logistic_baseline.py`: fold-coverage, agreement with a
  manually replicated fold loop, transition/shift logic (tested directly,
  independent of any model fit), and an end-to-end smoke test. Full suite:
  117 passed.
- **Real AAPL run (2y, live window 2025-04-16 to 2026-09-02):** overall
  walk-forward accuracy 0.519 vs. a 0.542 majority-class baseline — the
  model is *not* beating "always guess up." Strategy P&L $47.25 vs.
  buy-and-hold $126.71 vs. random baseline mean $74.26 ± $19.00 (20 seeds,
  same cost model). The strategy underperforms both baselines. This is the
  expected, honest result for a 5-feature logistic model on daily
  single-stock direction (SC-004) — not a bug, and not grounds to tune the
  model within this spec's scope. It is real evidence the pipeline is
  correct: a reliably-better-than-random model on a dataset this weak
  would be the "too good" result CLAUDE.md says to distrust first.
- Reused (imported, not modified) `ma_crossover_backtest.baseline_results`
  and `.mean_holding_bars`; wrote a local `_format_ml_comparison` rather
  than reusing `.format_comparison`, which hardcodes the SMA strategy's
  own label.
- Out of scope, untouched: `scripts/data.py`, `scripts/signals.py`,
  `scripts/backtest_harness.py`, `scripts/plotting.py`,
  `scripts/walk_forward_cv.py`; no behavior change to
  `scripts/ma_crossover_backtest.py`.

**Where this leaves the ML track:** mechanics are proven end to end
(backtest -> costs -> baselines -> purge/embargo CV -> live signal). The
model itself is the weak link, not the pipeline. Next real ML step is
improving the model (better features, a stronger classifier, or both) —
not wiring, which is now done.


## Spec 003 — Purged & embargoed walk-forward CV: DONE

Closed the Rule 2 gap in `scripts/walk_forward_cv.py`: the expanding-window
splitter had no purge and no embargo, so the training row immediately
before each fold boundary carried a label (`Close[i+1]`) computed from
inside that fold's own test window.

- `walk_forward_splits` now takes required keyword-only `label_horizon`
  and `embargo_bars` (no defaults — the caller states its own label
  horizon, per the Rule 1/8 module boundary). Raises `ValueError` if
  `embargo_bars < label_horizon`.
- Purges training rows within `label_horizon` bars of each fold's test
  start; maintains a persistent embargo ledger applied in full to every
  later fold, so an earlier fold's embargo zone stays excluded permanently
  (not just from the immediately following fold).
- `logistic_baseline.py`'s call site now passes `label_horizon=1,
  embargo_bars=1`, matching its `Close[i+1]` label exactly.
- New `tests/test_walk_forward_cv.py` (module had zero tests — also
  closes a standalone Rule 5 gap): purge boundary + off-by-one-at-equality,
  embargo-immediate, embargo-persistence across 3+ folds, validation,
  `label_horizon=0`, empty-after-purge-is-skipped, and a
  `logistic_baseline.py` integration case. Full suite: 110 passed.
- **Expected, not a regression:** `logistic_baseline.py`'s reported fold
  accuracies will differ from any prior run — the old numbers were computed
  on leaked data and were never a real result to preserve.
- Out of scope, untouched: `scripts/data.py`, `scripts/signals.py`,
  `scripts/backtest_harness.py`, `scripts/plotting.py`,
  `scripts/ma_crossover_backtest.py`.


## Response Style (non-negotiable)

Keep every response short and skimmable — bullets, tables, short
sentences. Camden does not retain information from big paragraph
blocks; break everything up, always.

## Role of This Project's Chat

This chat handles sequencing, review, and teaching — never finished
code. Copilot, Claude Code, and Antigravity do implementation;
Camden runs and reviews locally. Any coding step gets handed off as
a natural-language prompt, not code pasted in chat.

## Mission

Build Camden into a genuine expert in quant math, ML/DL, and
software engineering through this project — not someone who
copy-pasted a trading bot into existence. Every session should
teach something real, in this priority order:

1. Quant math & statistics depth
2. ML/DL modeling
3. Software/systems engineering
4. Market/trading domain knowledge (intentionally last — but never
   skipped at the pre-live-capital risk gate)

## How to Teach

Plain language before jargon, and define terms the moment they
appear. Every concept needs something concrete under it — a small
worked example, a real chart, a short code trace, or an analogy —
never taught in the abstract. If an explanation doesn't land, come
back with a genuinely different angle rather than the same one
reworded. Stay in Mentor Mode throughout: flag risks and
inefficiencies without being asked, benchmark against real
industry/quant practice by name, and give a direct opinion when one
path is clearly better. "What's next" is always a short 2-3 option
menu, never an open-ended question.

## Standing Principles

- Prove the plumbing with a dumb baseline before any model touches
  it — a model layered on broken plumbing just disguises bugs as
  bad predictions.
- Sequence by dependency, not calendar — "next" is whatever the
  current step unlocks.
- Roadmap is fixed: backtest, then paper trading, then small live
  capital — no skipping a phase because a backtest looked good.
- Lookahead bias gets checked as a first-principles question on
  every signal and every model, every time.
- Prefer the existing local Jean_E/Ollama stack for local inference
  needs before introducing new tooling.

## Confirmed Understanding (do not re-teach from scratch)

- Signal, execution, and accounting are three separate layers,
  whether the signal is rule-based or ML-based.
- A backtest simulates, it doesn't prove.
- Log returns are additive across time; simple returns are not.
- Fat tails (excess kurtosis 3-12) are a documented real property
  of stock returns, not a data bug.
- Extreme moves come from two sources — company-specific (earnings)
  and market-wide (macro shocks) — and that distinction matters for
  risk later.
- Volatility clusters in time rather than resetting daily.
- Shared trough dates across tickers (e.g. AAPL/GOOGL both bottoming
  4/8/2025) signal a market-wide shock; a slow multi-month decline
  unique to one ticker (MSFT, 10/2025-6/2026) signals a
  company-specific pattern instead.

## Current State

- Phase 0 environment is complete and committed.
- Data pipeline (`scripts/data.py`) pulls split/dividend-adjusted
  prices (`auto_adjust=True`) and caches results to
  `data/cache/*.csv` (Yahoo Finance is unreachable from Claude's own
  execution environments, so the cache is the permanent workaround,
  not temporary).
- **Spec 001 (data ingestion) implemented.** `scripts/data.py` went
  from zero tests to 46, closing the Rule 5 gap on the one module
  every other module depends on. Three things worth keeping:

  - **A real bug surfaced.** `Date` came back as `datetime64[s]`
    from a fresh download and `datetime64[us]` from the CSV cache
    read. Same instants, different dtype — so a cache hit and a
    cache miss were not interchangeable, and a downstream join
    between them would have worked until it silently didn't. This
    is the Rule 5 failure mode exactly: no exception, just a
    mismatch waiting for the right query.
  - **A timestamp convention is now ruled on, project-wide.** `Date`
    is timezone-naive, midnight-normalized, and denotes a session
    rather than an instant. The rule now lives in CLAUDE.md
    (*Conventions → Timestamps*): instants are always tz-aware,
    session labels are always tz-naive, and a session label crossing
    into instant-space is localized to `America/New_York` explicitly
    by the code doing the crossing. `research.md` R3 has the
    reasoning; CLAUDE.md is where the next module reads the answer.
  - **FR-009 answered "inspectable only."** `find_missing_bars`
    reports NYSE sessions with no bar; it does not fill, reject, or
    modify anything. Auto-fill was rejected on Rule 1 grounds — a
    backward fill writes into row `t` a value not knowable at `t`.
    It is wired into `scripts/data_pipeline_sanity_check.py`, so
    gaps print on every run — a count per ticker plus the first ten
    dates. That answers a question the NaN check structurally cannot:
    `isna()` finds a row that exists with a missing field, this finds
    a row that is not there at all.

  The NYSE calendar is hand-rolled from the exchange's rules, no new
  dependency. It reproduces the published session counts for
  2018-2025 exactly. pandas' `USFederalHolidayCalendar` was
  available and was rejected as *wrong*, not merely heavy: it omits
  Good Friday and adds Columbus and Veterans Day, when the market is
  open.
- SMA crossover baseline (`scripts/ma_crossover_backtest.py`) is
  reviewed and verified lookahead-free. Last *uncosted* real result:
  8 trades, 50% win rate, about +$33 total per share. That figure is
  now superseded — see spec 002 below, which makes every reported
  number net of costs.
- **Spec 002 (backtest costs & baselines) implemented.** Rule 3 and
  Rule 4 are closed, and 36 tests were added (67 → 103). What is
  worth knowing:

  - **Costs live in the harness, not the signal.** `run_backtest`
    takes `commission_per_trade` and `slippage_bps`, both keyword-only
    and both defaulting to `0.0`. The defaults multiply by exactly
    `1.0` and subtract exactly `0.0`, so the old uncosted arithmetic
    is reproduced bit for bit rather than approximately — that is why
    no existing test's expected numbers moved.
  - **Commission is charged per fill, not per round trip.** A $1.00
    commission costs a completed trade $2.00. This is a real modeling
    choice, taken as the conservative one; it matches how a broker
    bills. Worth a second look before any live capital.
  - **Slippage is applied against the trade, always.** The buy fill is
    raised, the sell fill lowered, on both exit paths — the normal
    sell and the end-of-data close. A test proves a winner flips to a
    loser under 200 bps, because that is the outcome Rule 3 exists to
    make visible rather than the outcome to engineer around.
  - **`summarize_trades` carries its cost parameters back out.** A net
    P&L cannot be decomposed into the costs that produced it, so the
    summary carries them or the number stops being reportable the
    moment it leaves the function.
  - **Both baselines are signal generators**, `buy_and_hold_signal`
    and `random_signal` in `scripts/signals.py`. Neither knows what a
    fill is. Buy-and-hold adds no exit logic at all: it relies on the
    harness's existing "still open at end" mark.
  - **The random baseline's non-overlap is structural.** Entries are
    drawn without replacement from a range shortened by the room each
    trip needs, then spread apart by construction — so trips cannot
    overlap, rather than being checked for overlap afterwards. Seed is
    required, via `numpy.random.default_rng`. Too few bars to match
    the strategy's trade count raises; it never quietly returns fewer
    trades, because a baseline at a different activity level answers a
    different question.
  - **Still to run on real data.** The end-to-end AAPL numbers are not
    in this repo yet — Yahoo is unreachable from the agent lane, so
    the three-way comparison has only been exercised on synthetic
    prices. Run `scripts/ma_crossover_backtest.py` locally to fill in
    the real figures.
- Return statistics (`scripts/return_stats.py`) are built and run on
  two years of real AAPL/MSFT/GOOGL data:

  | Ticker | Ann. Vol | Skew | Excess Kurtosis |
  |---|---|---|---|
  | AAPL | 28.7% | 0.26 | 10.30 |
  | MSFT | 28.6% | 0.87 | 12.11 |
  | GOOGL | 31.7% | 0.26 | 3.19 |

- MSFT's largest single-day moves traced to real dates: mostly
  quarterly earnings, one market-wide macro day (4/9/2025 tariff-
  pause rally).
- 21-day rolling volatility on MSFT ranged 10% to 58% — volatility
  clustering confirmed on real data, tied to earnings dates.
  **Deferred as a standalone script** — already explored, no new
  insight left, lower value than drawdown was. Do not re-raise
  unless something changes.
- **Risk-free-rate fix: DONE.** `RISK_FREE_RATE_ANNUAL = 0.0378`
  (real 3-month T-bill rate) is live in `scripts/return_stats.py`,
  replacing the old 0% placeholder. Sharpe ratio output now trusted.
- **Max drawdown: DONE.** Added to `scripts/return_stats.py` as new
  summary columns (Max Drawdown, Peak Date, Trough Date), built from
  a cumulative price index reconstructed via `np.exp(returns.cumsum())`
  and a running max — descriptive stat, no lookahead risk. Verified
  against real 2yr data:

  | Ticker | Max DD | Peak → Trough |
  |---|---|---|
  | AAPL | -33.36% | 2024-12-26 → 2025-04-08 |
  | GOOGL | -29.81% | 2025-02-04 → 2025-04-08 |
  | MSFT | -34.50% | 2025-10-28 → 2026-06-25 |

  All three sanity-checked against a -20%/-35% rule of thumb for
  2yr tech-stock drawdowns — passed.

### Housekeeping — Confirm First

The drawdown change (and a few other working-tree edits to
`data.py`, `ma_crossover_backtest.py`, `data_pipeline_sanity_check.py`,
`requirements.txt`) is verified correct but **not yet committed** —
`git status` shows it still sitting as uncommitted working-tree
changes. Commit it before starting the harness, so the harness diff
doesn't get tangled up with unrelated uncommitted work.

## Phase 3 — In Progress

Specs 006-009 closed out the plumbing gaps Phase 3 scoping surfaced
(embargo semantics, an OOS index bug, metrics, a selectable target), and
spec 010 is now implemented. Specs 011-013 carry Phase 3 the rest of the
way, dependency-sequenced:

Specs 010-013 were first drafted in one pass and then corrected before
implementation; the corrections are recorded in each spec's own *Revision
note* rather than silently applied. The substantive ones: gradient boosting
had been deferred out of 010 and was owned by no spec; 011's requirements
were self-contradictory (reuse `walk_forward_splits`' rule, while importing
no project module); and 012's cost hurdle dropped the `1/(1-s)` factor and
compared a simple return against a log-return target.

- **Spec 010 — Estimator registry. DONE** (see above). Also carries the
  parameter grids and declared fallback params spec 011 searches over.
- **Spec 011 — Nested, leakage-safe hyperparameter tuning. DONE** (see
  above).
- **Spec 014 — Scale-free features and fold-fit standardization. DONE**
  (see above). Inserted ahead of 012 and 013, which are **held**, on the
  reasoning below.
- **Spec 012 — Cost-aware entry rule. HELD until 014's evidence is in.**
  Turns a continuous return prediction into a trade only when it clears the
  actual round-trip cost hurdle. The mechanics are worth building either
  way, but building an entry rule on predictions from a matrix with a
  condition number of 36 and a max VIF of 268 spends real work on a known
  bug. Held deliberately, with time available; not blocked.
- **Spec 013 — Multi-ticker comparison table. HELD until 014's evidence
  is in.** Runs the full pipeline per ticker and produces the risk-adjusted
  table that replaces this doc's stale AAPL figures. Run before 014, that
  table compares four flavours of "does not beat baseline", which is not the
  payoff artifact it is meant to be. 014's `feature_set_comparison.py` is
  also the natural precursor: it is the same levels-vs-scale_free comparison
  on one ticker.

**Outstanding, and Camden's rather than an agent's:**

- ~~The 10-year download for AAPL, MSFT, GOOGL, NVDA, AMZN.~~ **Done** —
  `data/cache/AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv` holds 2,514 bars per ticker
  through 2026-09-04. Spec 014's diagnostics ran against it offline, which is
  how the condition-number table above exists. Both 014 scripts request the
  full universe rather than `["AAPL"]` so they hit this cache key instead of
  triggering a download.
- Run `scripts/ma_crossover_backtest.py` locally to produce the real AAPL
  three-way costed comparison. This has been outstanding since Phase 2:
  the repo has a correct cost model and still no costed result to show for
  it. Whether the SMA rule survives its own costs is a finding either way.

**Still true from earlier phases:**

1. Rule 10 and the Actions lane carve-out (CLAUDE.md) is a documented
   exception, not a constitutional amendment, until Camden makes it one
   in `.specify/memory/constitution.md` directly.
2. The agent lane cannot reach Yahoo Finance. Every real multi-ticker run
   (spec 013) and any other real-data run happens on Camden's machine,
   not in an agent session or CI.
