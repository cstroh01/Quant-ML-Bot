# Audit Remediation Plan

_Source: [AUDIT.md](AUDIT.md) (Codex, 2026-09-12). Written 2026-09-12._

Every finding in the audit (01–70), research directions A–D, the work order,
unknowns and "keep" list is assigned here to exactly one **primary** phase.
Work on one finding that belongs to a later phase is marked **↪**.

Spec numbers 018+ are **proposed** groupings, not assigned numbers. Camden
assigns the real numbers. Each spec follows the CLAUDE.md size rule: split any
spec that cannot be reviewed line by line.

## At a glance

| | Count |
|---|---|
| Findings | 70 |
| P0 | 14 (11 in Phase 3, 3 in Phase 4) |
| **Phase 3 — current, backtest/research** | **64** |
| Phase 4 — paper trading | 4 (06, 07, 08, 62) |
| Phase 5 — capped live capital | 2 (69, 70) |

Legend:
- **P0:** blocks relying on the result.
- **P1:** needed before treating research as evidence.
- **P2:** engineering improvement.
- **D:** defect. **G:** gap. **R:** reconsider.

Critical path:

```
Stage 0 → 3.1 honest terminal → 3.2 ledger + timing → 3.3 data + run store
        → spec 013 real run → 3.4 portfolio sim → 3.5 frozen experiment
        → Phase 4 paper → Phase 5 capped live
Stage 3.6 (engineering/workflow) runs in parallel throughout.
```

---

## Stage 0 — Decisions and housekeeping, before any new spec (Camden-owned)

| # | Item | Source |
|---|---|---|
| 0.1 | **Hold spec 013's real run** until Stages 3.1–3.3 land. Run now, it scores a close-to-close target the strategy cannot capture, on a non-funded ledger, with a cache mismatch that can trigger downloads — and would have to be rerun. | 01, 17, 22, 23 |
| 0.2 | **Decide on 017.** Either merge it as a pure decision component, split for size, with 40–44 and 06 recorded as known limits, or hold it. | 05, 017 flags |
| 0.3 | Put **spec 012** through the Merge Gate. It is still outstanding. | 67 |
| 0.4 | **Define the own-capital objective:** capital, maximum tolerable loss, benchmark, holding period, budget and time commitment. | 70 |
| 0.5 | **Fix the Spec Kit output path** (`specs/` → `.specify/specs/`) *before* creating the next spec, or a second numbering sequence starts. | 65 |
| 0.6 | **Clean up documentation drift** (listed below). | 67 |

Documentation drift to clean up in 0.6:
- 012's classification path is described as using the cost hurdle and hysteresis, which it does not.
- Test counts conflict: 301 / 311 / 366 / 541.
- `PROJECT_CONTEXT.md` still says Rule 10 is "not yet amended".
- The CLAUDE.md module table has no row for `portfolio_risk.py`.
- Spec 005 and `phase2_*` artifacts should be marked stale.
- `feature_set_comparison_PREVIOUS.json` and `_STALE_PARTIAL.json` should be deleted.
- Three pairs of plot PNGs are byte-identical: `plots/AAPL_acf.png` = `aapl_log_returns_acf.png`, and the same for MSFT and GOOGL.

---

## PHASE 3 (current) — Backtest/research: 64 findings

**Phase 3 exit:** the audit's work-order steps 1–5 all pass. The strategy must
beat an appropriate simple benchmark net of realistic costs, at acceptable
risk, on untouched data, with uncertainty and trial correction reported.
Failure is a valid outcome.

### Stage 3.1 — Honest terminal and adversarial regressions (work order 1): 15 findings

Pass condition:
- No fabricated forecast, p-value or pass badge.
- Malformed inputs cannot produce a successful result.
- API tests pass on a clean checkout with fixtures.

| ID | P | Type | Change | Where | Spec |
|---|---|---|---|---|---|
| 45 | P0 | D | Replace hardcoded p-values (0.084/0.215/0.042/0.310, identical for every ticker) with saved run artifacts. Tickers with no run show "unavailable". | `reports/api/routes/diagnostics.py:92` | 018 Terminal truthfulness |
| 46 | P0 | D | Remove the literal `P(Up)=54.2%` / `Logit=+0.17`. Label indicator commentary as rules, not ML drivers. | `reports/api/routes/ml_rundown.py:61`, `MLRundownPane.tsx` | 018 |
| 47 | P0 | D | Remove hardcoded gate badges and the "301 passed" / "311/311" text. Store unknown/failed/stale/passed states separately. ↪ Read versioned artifacts once 028 exists. | `reports/api/routes/capital_gate.py:13`, `Header.tsx:107` | 018 |
| 48 | P1 | D | Compute real holding bars (probe: 93/33/43/36/27, all reported as 1). Break friction into commission, spread and slippage. Export unrounded values. | `reports/api/routes/backtest.py:154`, `BacktestTearsheetView.tsx:92` | 018 |
| 49 | P1 | D | Make the gate decoder match the API's gates. Fix p-value explanations, "conditioning = proof" and volume-flow narratives. Remove Kelly teaching. Show unknown correlation as unknown, never zero. | `CapitalGateView.tsx:64`, `FeatureDiagnosticsView.tsx`, `MarketDataView.tsx` | 018 |
| 36 | P1 | R | State in UI and docs that good conditioning is a numerical property, not an alpha certificate. | `features.py`, spec 014, `FeatureDiagnosticsView.tsx` | 018 |
| 54 | P1 | G | Mark the 6-fold CV timeline as an illustration (the saved run has 113 folds). Label the tearsheet as SMA, not ML. ↪ Add run selectors after 028. | `CrossValidationView.tsx`, backtest and ML rundown routes | 018 |
| 03 | P0 | D | Reject NaN or non-positive fills, nonfinite costs and non-boolean signals before simulating. A NaN-skipping sum must never count as reconciliation. | `scripts/backtest_harness.py:13,108` | 019 Boundary validation |
| 04 | P0 | D | One cost-domain validator — finite commission ≥ 0, finite slippage in [0, 10000) — enforced in both library and HTTP. | `scripts/ml_signal.py:47`, `backtest_harness.py`, backtest route | 019 |
| 50 | P1 | D | Constrained request models with cross-field checks (short < long, window > 0, finite values, known ticker, bounded workload). Return a documented 4xx, never 500. | `reports/api/routes/backtest.py` | 019 |
| 51 | P1 | G | Now: remove `"*"` + `allow_credentials` from CORS and bind to loopback. ↪ Phase 4: TLS, auth, allowed hosts, rate limits, separate execution-API boundary. | `reports/api/main.py:33` | 019 |
| 29 | P1 | D | Exact one-sided McNemar via `binomtest` with the intended alternative (probe: 0.75 reported, 1.0 correct). Cover both directions and ties. | `scripts/feature_set_comparison.py:348` | 020 Diagnostics correctness |
| 35 | P1 | D | Singular or constant predictors → VIF infinite/undefined (probe: duplicates return 0.25; a constant column raises SVD error). Check against an independent oracle. | `scripts/feature_diagnostics.py:76`, `scratch_multiticker_collinearity.py:112` | 020 |
| 57 | P1 | D | CI reproduces a clean install: API test deps, small deterministic fixtures instead of ignored cache/dist, web build/lint in the job that needs them. Currently 7 of 11 API tests fail on a fresh checkout. | `.github/workflows/test.yml`, `tests/test_reports_api.py` | 021 Clean CI and oracles |
| 58 | P1 | G | Independent oracles: hand-calculated funded ledger, planted signal vs pure noise, overnight-only timing, all-NaN prices, exact singular VIF, whole-pipeline future perturbation. Mutation scripts live in the repo. Each later spec adds its own oracle. | `tests/` | 021 |

### Stage 3.2 — Funded ledger and execution-timing contract (work order 2): 9 findings

Pass condition:
- An independent cash/position oracle agrees at every event.
- Initial costs are counted.
- The actionable label and next-session alignment are verified.

| ID | P | Type | Change | Where | Spec |
|---|---|---|---|---|---|
| 22 | P0 | D+R | Predict the return the strategy can capture, e.g. `log(Open[t+h+1]/Open[t+1])` for next-open entry. Define `feature_available_at`, `decision_at`, `entry_at`, `exit_at`, `label_available_at` together, and resize the purge. Test: a synthetic overnight-only move yields no pre-entry profit. | `scripts/targets.py:88`, `ml_signal.py:75` | 022 Timing contract |
| 23 | P0 | D | Causal features on all sessions, plus a separate known-label training mask. Align out-of-sample predictions by ticker and session. Shift decisions on the real calendar — no row dropping or index resets (the API currently turns 09-04 data into a 09-03 rundown). | `scripts/features.py:106` | 022 |
| 24 | P1 | D | A NaN current price must not become class 0 (probe: `[NaN,101,102]` → 0). Mask both endpoints. Test NaN/inf at each. | `scripts/targets.py:65` | 022 |
| 13 | P0 | G | Store unadjusted prices plus split/dividend events for the ledger. Derive clearly labeled adjusted series for features. Archive vendor snapshots and adjustment conventions. | `scripts/data.py:315` | 025 Corporate actions |
| 01 | P0 | G+D | Funded ledger: starting cash, filled quantities, reservations, positions, fees, corporate actions, mark-to-market equity. Reject or resize unaffordable orders (probe: $100 account accepts a $201.10 entry). Acceptance: cash + marked positions reconciles at every event; a split and a dividend reconcile by hand. | `scripts/backtest_harness.py:13`, `metrics.py:63` | 023 Funded ledger |
| 11 | P1 | G | Ledger validation beyond one total: unique ordered sessions, allowed position transitions, trade/fill IDs, quantities, fee attribution, per-event balances, explicit zero/negative-equity handling. | `scripts/metrics.py:63` | 023 |
| 10 | P1 | D+R | Separate open-position valuation, optional benchmark liquidation and real exit orders. The streaming signal must not force flat because its batch ended. Record liquidation assumptions in metrics. | `backtest_harness.py:13`, `ml_signal.py:160` | 023 |
| 02 | P0 | D | Anchor returns and drawdown to pre-trade equity (probe: −5.26% reported, −10% correct). Acceptance: first-bar loss, first-bar profit, all-flat and terminal-loss cases match an independent ledger. | `scripts/metrics.py:176,226` | 024 Metrics conventions |
| 12 | P1 | R | State the Sharpe convention. Separate annualized mean log return from CAGR. Model cash interest separately from the hurdle, with historical or labeled rates. Report autocorrelation-aware uncertainty; don't assume `sqrt(252)`. | `metrics.py:195`, `return_stats.py:35`, `constants.py` | 024 |

Order: 022 and 025 in parallel → 023 → 024. Finding 02 is small enough to ship first.

### Stage 3.3 — Reproducible data and experiment store (work order 3): 17 findings

Pass condition:
- An offline run on the combined cache works.
- Run hash, config, folds, predictions and baselines are persisted.
- Failures are visible to machines.

| ID | P | Type | Change | Where | Spec |
|---|---|---|---|---|---|
| 14 | P1 | D | Validate downloads **and cache hits**: schema, finite positive prices, non-negative volume, OHLC bounds, unique ordered keys, minimum coverage. Canonicalize and deduplicate tickers. Quarantine bad data with reasons (probe: an all-NaN ticker is accepted). | `scripts/data.py:286,315` | 026 Data integrity |
| 15 | P1 | G | Record requested interval, expected last completed session, fetched-at time, provider and source version. A truncated tail counts as missing (cache ends 09-04). ↪ Phase 4: stale input → explicit "unavailable". | `data.py:209`, `reports/api/routes/data.py:27` | 026 |
| 16 | P1 | R | Maintained or versioned exchange calendar with fixtures. Reindex panels to expected sessions before daily returns, so a missing session never becomes a multi-day "one-day" return. | `scripts/data.py:143` | 026 |
| 19 | P1 | G | Unique temp file in the target directory, validate before publishing, atomic replace, clean up on failure, single-writer lock, run namespace. | `scripts/data.py:303` | 026 |
| 20 | P2 | D | Keep cache paths inside the cache root (probe: `../outside.csv` escapes). Ticker allowlist at HTTP. | `scripts/data.py:78` | 026 |
| 17 | P1 | D | Load the verified combined panel once and pass slices, or use a canonical ticker-partitioned store. Acceptance: network off, only combined cache present, all five runners get the same snapshot. **Must precede the 013 real run.** | `scripts/multi_ticker_comparison.py:212,357` | 027 Dataset manifest |
| 18 | P1 | D+G | Scripts and API resolve data through one typed manifest (ticker, interval, snapshot ID). Remove the API's arbitrary-CSV fallback. An empty cache must not advertise five tickers. | `reports/api/routes/data.py:27` | 027 |
| 59 | P1 | G | Immutable run directories with a manifest (code, dependencies, data hash, config, candidates, failures). Atomic result publishing. Resumable task IDs. Data snapshots stored separately from results. | `feature_set_comparison.py:844`, `data/cache` | 028 Run store and trial ledger |
| 38 | P2 | G | Persist fold IDs, training bounds, all inner candidate scores, selected params, scaler state, predictions/probabilities, label definition, seed, elapsed time, hashes. Define fold-score weighting. Replace `assert` with explicit errors. | `scripts/model_cv.py:245,362` | 028 |
| 27 | P1 | G | Register every material trial, including failed variants and manual changes. ↪ Freeze and hold out in 037. | `feature_set_comparison.py:745`, `PROJECT_CONTEXT.md` | 028 |
| 60 | P2 | G | Verify the OS start method and use runtime thread-pool controls. Timeouts, cancellation, memory limits, per-run checkpoints. Fix repeated sklearn/joblib warnings (51.6 MB log, 83,464 warnings). Promise statistical, not bitwise, reproducibility. | `feature_set_comparison.py:229` | 028 |
| 33 | P1 | D+G | Persist per-ticker success/failure, exception type, config, per-seed records and aggregation rules. Nonzero exit on an unusable run (currently an all-failed run writes an empty CSV and exits 0). Expose estimator choice (ridge is currently fixed). | `multi_ticker_comparison.py:112,357` | 029 Fair comparison protocol |
| 31 | P1 | G | Precompute features with prior history. Start every funded strategy and baseline on the same session with the same cash, tradability and costs. Save the covered-session mask. | `multi_ticker_comparison.py:212` | 029 |
| 32 | P1 | G | Add baselines: always-up (53.54% — above logistic's 52.99%), rolling-prior, zero-return and training-mean regression, cash, momentum, vol-managed exposure. Keep every random path. Compare turnover and exposure. Never average Sharpe or drawdown into a fictional strategy. | `ma_crossover_backtest.py:59`, `multi_ticker_comparison.py:112` | 029 |
| 34 | P1 | R | Predeclared 2×2 ablation — levels/ratios × raw/scaled — with folds and policy held fixed and date-based fold layout shared. | `estimators.py:203`, `feature_set_comparison.py:129`, `logistic_baseline.py` | 029 |
| 37 | P2 | R | Model event information intervals explicitly. Purge labels not yet available at fit time. Keep extra embargo only for a stated dependence concern. Validate calendar boundaries and horizon domains. Don't delete safeguards without proving the replacement. | `scripts/walk_forward_cv.py:21` | 030 CV/model contract |
| 39 | P2 | G | Specify HGB early-stopping behaviour before the pooled panel crosses its threshold. Handle single-class folds per estimator. Freeze or copy registry dictionaries. | `scripts/estimators.py:96` | 030 |

**Then run spec 013 for real** on this foundation (the held Stage 0.1 item).

### Stage 3.4 — Integrated portfolio simulation (work order 4): 5 findings

Pass condition:
- Quantities, cash, risk and costs agree.
- A restart preserves halts.
- Same-period baselines and exposure attribution exist.

| ID | P | Type | Change | Where | Spec |
|---|---|---|---|---|---|
| 05 | P0 | G | Portfolio runner plus order-sizing adapter from 017 target weights to the funded ledger. Keep `portfolio_risk` a pure decision component. Replay test: a drawdown triggers the guard, blocks new or larger exposure, allows reductions and charges every trade. Includes a replay-restore test (the simulation side of 06). | `scripts/portfolio_risk.py:482`, new runner | 031 Weight-based execution |
| 43 | P1 | G | Enforce halt/no-add on executable quantities, not target weights, after gaps and equity changes. Validate lot sizes, fractional shares, price bands and cash reserves. ↪ Phase 4: pending orders in exposure. | `scripts/portfolio_risk.py:445` | 031 |
| 40 | P1 | R | Replace binary presence-based overlap with exposure-sensitive risk (regularized covariance, `w'Σw`, marginal risk contributions, sector/factor limits). Probe: a 1e-12 neighbour halves a 0.25 weight. Acceptance: tiny exposures have tiny effects; limits are continuous. | `scripts/portfolio_risk.py:360` | 032 Portfolio risk v2 |
| 41 | P1 | R | Distinguish per-asset inverse-vol sizing from portfolio vol targeting (median gross 0.38, 69% removed). Compare risk-normalized allocations, cash returns and turnover. Ledoit-Wolf is already in scikit-learn. | `scripts/portfolio_risk.py:306` | 032 |
| 44 | P2 | R | Preregistered stress set: correlation shocks, gaps, vol jumps, turnover costs. Reject asymmetric or invalid correlation matrices. Measure sell-after-loss / rebuy-after-recovery behaviour instead of assuming the guard helps. | `scripts/portfolio_risk.py:167` | 032 |

032 also records the simulated 07 policy definitions (halt new orders vs
cancel open orders vs reduce/flatten) and decides on an all-time drawdown
latch with operator reset. It also carries **Research C** (covariance-aware
risk with a turnover no-trade band).

### Stage 3.5 — Frozen economic experiment (work order 5, Phase 3 exit): 7 findings

| ID | P | Type | Change | Where | Spec |
|---|---|---|---|---|---|
| 09 | P1 | G | Cost model with base and adverse scenarios: spread, opening auction, order size, minimum commissions, partial fills, participation caps. Report break-even cost; keep a simple model for unit tests. ↪ Phases 4/5: calibrate from real fills. | harness cost model | 033 Cost scenarios |
| 25 | P1 | R | Prediction-to-utility contract. `exp(E[log r]) ≠ E[r]`, so estimate the actionable conditional payoff or its distribution, with uncertainty and costs. Select the trade policy inside training/validation only. MSE and log loss stay diagnostics. | `ml_signal.py:125`, `model_cv.py:193` | 034 Decision policy |
| 26 | P1 | G | The classification path is not cost-aware: it holds on hard class 1. Keep probabilities, calibrate chronologically, combine with conditional up/down payoffs — or keep classification only as a benchmark. (Wording fix ships in 018.) | `scripts/ml_signal.py:236` | 034 |
| 42 | P1 | G | Define conviction before it multiplies a weight: calibrated win probability, normalized expected utility, uncertainty-adjusted edge, or abstention score. Kelly stays out until payoff distribution and estimation error are known. | `portfolio_risk.py:306`, spec 017 `research.md` | 034 |
| 28 | P1 | G | Time-aware inference: paired block bootstrap, date-block resampling across the panel, confidence intervals, effect sizes. Validate on simulated nulls. | `feature_set_comparison.py:348,410` | 035 Inference and multiple testing |
| 30 | P1 | G | Predeclare the test family and correction (4 tests at p<0.10 is not a 10% family-wide test). PSR/DSR on valid net returns with a justified probability threshold, minimum sample and economic effect — not "DSR > 0". (Gate text fix ships in 018.) | `reports/api/routes/capital_gate.py` | 035 |
| 21 | P1 | G | Predefined point-in-time tradable universe including failed and delisted names, lifecycle events, liquidity and an appropriate benchmark. Hold out by time and by asset or sector. Don't broaden only until a profitable subgroup appears. | `multi_ticker_comparison.py`, ADR 0001 | 036 PIT universe |

034 carries **Research A** (execution-aligned, uncertainty-aware decision
policy: `max μ'w − (λ/2)w'Σw − cost(w − w_prev)` with a no-trade region;
start with a calibrated simple baseline plus a small quantile tree, not a
transformer). 036 carries **Research B** (one narrow cross-sectional
hypothesis with an economic mechanism, residualized against market and
sector, split by global date).

Final step — **037 Strategy freeze and untouched forward holdout** (the freeze
part of 27). Freeze the strategy, then evaluate on genuinely new forward
dates. Dates already inspected cannot be made unseen.

### Stage 3.6 — Engineering and workflow lane (parallel, any time): 11 findings

| ID | P | Type | Change | Where | Spec |
|---|---|---|---|---|---|
| 52 | P1 | D | Guard the 7 parallel fetches per state change with AbortController, generation IDs or keyed queries, so ticker B never shows A's late responses. Responses carry run/ticker IDs. Clears lint warning `App.tsx:93`. | `reports/web/src/App.tsx:93` | 038 Terminal reliability |
| 53 | P1 | D+G | Separate loading, empty, stale and failed states, with retry, last-success timestamp and data freshness. Share run identity across panes. Refresh capital-gate state. ↪ Phase 4: readiness covers data/model availability. | `App.tsx:94`, `services/api.ts` | 038 |
| 55 | P2 | G | Browser tests (ticker races, errors, parameter validation, real artifact values, keyboard). Semantic buttons, labeled tabs and panels, modal focus, cues that don't rely on color alone. ResizeObserver charts, preserved zoom, disclose/paginate the 100-trade limit. | `reports/web/src/components` | 038 |
| 56 | P2 | D+G | Package the core library instead of repeated `sys.path` edits (`parents[2]` resolves to `reports/`). Generate frontend types from OpenAPI. Enable strict TypeScript incrementally; replace `any`. | `reports/api/routes/data.py:14`, `schemas.py`, `web/src/types/api.ts` | 039 Packaging and contracts |
| 61 | P1 | G | `pyproject.toml`, supported Python (CI 3.12 vs local 3.13.14) and Node (24.19) versions, runtime/test/UI dependency groups, reproducible lock, runnable entry points. Separate offline research from serving precomputed results. ↪ Phase 4: small process or container deployment. | `requirements.txt`, `reports/requirements-ui.txt`, `reports/web/package.json` | 039 |
| 63 | P1 | G | Minimal workflow token permissions, action refs pinned to SHAs, workflow timeout/concurrency/budget limits, server-side protected-branch rules. Keep `pip check` and `npm audit` running in CI. | `.github/workflows/claude.yml` | 040 CI and agent hardening |
| 64 | P2 | D | `.claude/settings.json` is empty (not valid JSON). Agent and command frontmatter is escaped as `\---`. The test hook runs forbidden git, uses whatever `python` is on PATH, truncates to 5 lines and loses the exit code. Fix, then verify tools actually recognize them. | `.claude/hooks/run-tests.ps1`, `.claude/settings.json`, `.claude/agents/quant-reviewer.md`, `.claude/commands/spec-status.md` | 040 |
| 65 | P2 | D | One configured spec path with a dry-run test. Harmonize template git and review steps with local policy. (The path fix itself is Stage 0.5.) | `.specify/scripts/bash/create-new-feature.sh:200`, `.claude/skills/speckit-specify/SKILL.md` | 041 Workflow and governance |
| 66 | P2 | D | Issue dedupe key namespaced by feature (`017:T001`, not a global `T001`). Idempotent reruns. | `.claude/skills/speckit-taskstoissues/SKILL.md` | 041 |
| 67 | P2 | G | Present-tense status links to evidence. Separate implemented, verified and research success. Keep history. Don't call mechanics proven because a model performs poorly. (The initial cleanup is Stage 0.6.) | `docs/PROJECT_CONTEXT.md`, spec `tasks.md` files | 041 |
| 68 | P2 | R | Independent equation and timing review for high-risk math. Falsification experiments and source-backed evidence. Less repetitive prose and fewer brittle exact-import AST checks. Constitution edits happen in Camden's dedicated commit. | `.claude/agents/quant-reviewer.md`, constitution, `.specify/templates` | 041 |

---

## PHASE 4 — Paper trading (work order 6): 4 findings, plus ↪ parts

Pass condition:
- No duplicate orders, unexplained positions or trading on stale data.
- Durable restart and reconciliation demonstrated.
- Forward decision/fill audit complete.
- Judged by enough independent decisions and failure scenarios, not "1–2 months elapsed". Compare shadow decisions made at the same time; paper returns need not match the backtest's returns.

**Rule 7 applies:** once broker credentials exist, `exec/` is excluded from every autonomous lane.

| ID | P | Type | Change | Bundle |
|---|---|---|---|---|
| 06 | P0 | G | Persist risk state — anchors, high-water marks, latch reasons, last observation, config — and restore it by deterministic event replay (probe: a fresh guard forgets the weekly halt). Treat deposits and withdrawals separately from trading P&L. Acceptance: a crash at every state transition restarts without relaxing limits. | P4-a Durable risk state |
| 08 | P0 | G | Order lifecycle and recovery: durable client/intent IDs; acknowledged/rejected/partial/cancelled states; reconcile uncertain outcomes after a timeout before retrying; handle duplicate and reordered events; check broker vs local positions. Acceptance: replay partial fills, duplicates, disconnect after accepted submit, restart with open orders. | P4-b OMS and broker adapter |
| 07 | P0 | G | A loss trigger is not a guaranteed loss limit. Separate halt-new-orders / cancel-open-orders / reduce-flatten policies, each with failure behaviour. Stale-data, broker-disconnect and buying-power checks. Account-level emergency stop. | P4-c Safety interlocks |
| 62 | P1 | G | Unattended operation: service supervision, data-ready and decision deadlines, maximum staleness, restart policy, single active trader, model rollback, disk/log limits, backup-restore drill, alert routing, runbook. SLOs built around daily decisions. Monitor coverage, feature drift, calibration, turnover, exposure, slippage and broker reconciliation. | P4-e Ops and monitoring |

Carried into Phase 4 from Phase 3:
- 43 — pending orders in exposure.
- 51 — TLS, auth, allowed hosts, separate execution-API boundary.
- 53 — data/model readiness checks.
- 15 — stale input → "unavailable".
- 61 — deployment.
- 09 — calibrate from paper fills.

**Research D → P4-d, replayable research-to-paper pipeline:**
- Chain: immutable raw snapshots → causal features and known-label masks → experiment runner → versioned approved model/policy → target portfolio → order intents and broker adapter → fill/cash/risk journal → read-only API/UI.
- The same decision and risk code consumes historical and paper events through different adapters.
- Offline fitting stays out of HTTP.
- An automated research report is produced after each run.
- A paper-vs-simulation report attributes differences to data, timing, signal, sizing and fills.

## PHASE 5 — Capped live capital (work order 7): 2 findings, plus ↪ parts

| ID | P | Type | Change |
|---|---|---|---|
| 69 | P1 | G | Choose the software license (no LICENSE file exists). Keep third-party notices. Keep proprietary strategy artifacts separate per ADR 0001. Check Yahoo/yfinance terms (personal-use limits) and the real vendor agreement before charging customers or redistributing data. |
| 70 | P1 | G+R | Business model and economic hurdle. Own capital, licensed software, sold signals and managing others' money are different products with different legal and support duties. Check that the dollar opportunity justifies research and data costs ($10k at 15% = $1,500 pre-tax — arithmetic, not a forecast). The Stage 0.4 definition comes first. |

Also:
- Revalidate 06–09 against live behaviour.
- Monitor actual live friction.
- All-time drawdown kill switch with operator reset (07).
- Explicit risk budget.
- Valid broker and data rights.
- Human approval (Rule 7).

---

## Also recorded from the audit

**Keep — do not rewrite:**
- signal/fill separation
- explicit purge and horizon parameters
- chronological outer CV with training-only inner tuning
- linear preprocessing inside fold-fit pipelines
- seeded stochastic controls
- the careful hurdle derivation
- adversarial risk tests
- 017's boundary validation
- the measured serial/parallel speedup

**Non-goals until a measured bottleneck or edge justifies them:** GPU training, reinforcement learning, broad hyperparameter sweeps, HFT, Kubernetes, Kafka, additional dashboards.

**Unknowns — Camden's decisions:**
- intended capital and income target
- broker and account constraints
- data commercialization rights
- private-repo state
- remote CI branch protection
- recoverability under real outages
- genuinely unseen forward performance

**Gate-criteria guidance:**
- Don't require a null strategy's Sharpe to sit below a fixed value (the current "Sharpe ≤ 0.3" gate text). Evaluate a null distribution and false-positive rates.
- The target is a process that rejects bad strategies cheaply.

**What the saved results establish:**
- `feature_set_comparison.json` is a prediction-quality comparison (113 folds, 2,359 pairs, purge 1, embargo 1, seed 42), not a costed experiment.
- Logistic scale-free accuracy is 52.99%, **below** always-up at 53.54%.
- Ridge's MSE gain is 0.0844% relative, with no established economic value.
- The SMA tearsheet's 233.64% return / 0.17 Sharpe / −72.36% drawdown use a $24.63 one-share denominator. They are not funded-account results and not ML results.

**Clean at audit time (keep running):**
- 541 unit tests pass.
- Web build passes.
- `pip check` is clean.
- `npm audit` shows 0 vulnerabilities.
- The main cache has no duplicates, nulls, nonpositive or nonfinite prices, OHLC violations or internal gaps.

**Resolved during the audit (no action):** spec 017's T033/T034 ticks, stale clarification note and status.
