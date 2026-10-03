# Spec 038 — Rule 11 / Rule 16 disclosure audit, 2026-10-03

Report only. It changes no code, test, spec, checkbox or ledger byte. It lists
every surface a reader could mistake for results that lacks Rule 11 provenance,
the Rule 15 provisional/undeflated Sharpe flag, or the Rule 16 limitations from
`docs/SCOPE-V1.md` §6. It feeds `docs/V1-FINISH-PLAN.md` S7 and SCOPE-V1 §3
item 5. No `.specify/specs/038-*` directory exists yet, so this report cites the
finish plan, not a spec.

**Provenance.** Source: `origin/main` at `659b2ec` (merge of PR #18). Produced
by an unattended cloud scheduled-session run on 2026-10-03, by reading files
only. No script, server, UI build or network fetch was run. Every `file:line`
was read in that tree; line numbers drift as files change.

**Codes.** A = source artifact not named. R = no commit or run id. D = no date
(a data window or download time is not a run date). S = Sharpe shown without
the Rule 15 flag. L = no §6 limitation on the surface. X = stale: the cited
source artifact is absent from the tree (Rule 11, last paragraph).

## Summary

- **No surface in the repository shows a commit SHA or run/trial id beside a
  result.** The ids exist (`trial_registry.source_identity`,
  `scripts/trial_registry.py:94-127`; the trial id the tearsheet route already
  holds at `reports/api/routes/backtest.py:60`) but are written to the ledger only.
- **No surface carries the full §6 limitations.** The closest is the unadjusted
  loader's `source_limitations` attrs (`scripts/data.py:1213-1218`), which name
  vendor gaps (delisted names, spinoffs, symbol changes, pay dates) but not the
  survivor basket, partial reconciliation, no PIT fundamentals, daily bars only,
  or modeled costs.
- **Four Sharpe surfaces lack the Rule 15 flag:** `scripts/return_stats.py:98-113`,
  the tearsheet API and view, and the 0.17 Sharpe at
  `docs/audit-2026-09-12/AUDIT.md:41` and `REMEDIATION_PLAN.md:294`.
- **No shared helper exists** for a provenance stamp, a limitations block, or a
  Sharpe flag. Fixing surfaces one by one will drift; a helper per layer
  (Python print, API schema, React banner) is the cheaper route. That is a
  design choice for the 038 spec, not made here.

## 1. Terminal panels (`scripts/`)

Files that print no result figure: `metrics`, `selection_bias`, `model_cv`,
`ml_signal`, `estimators`, `backtest_harness`, `portfolio_risk`,
`live_safety_gate`, `order_gateway`, `trial_*`, `features`, `targets`,
`signals`, `cost_utils`, `constants`, `_project`. Data-shape diagnostics in
`data_pipeline_sanity_check.py`, `walk_forward_cv.py:131-134` and
`multi_ticker_comparison.py:458-463` are excluded (no outcome figure).

| File:line | Figures | Missing | Notes |
|---|---|---|---|
| `scripts/ma_crossover_backtest.py:273-292` | Trade log, per-trade and cumulative P&L | R, D, L (partial) | **The only partly compliant panel.** Prints `source_name`, `downloaded_at_utc`, `source_limitations`, `source_manifest_sha256` (274-276) and `pay_date_disclosure` (277-278). The trial id from `research_attempt` (268) is not printed. |
| `scripts/ma_crossover_backtest.py:304-305` → `format_comparison` (183-250) | Strategy vs buy-and-hold vs random: trades, P&L, win rate, random mean ± sd | A, R, D, L inside the block | Relies on `main()`'s header; the block alone carries nothing if rendered elsewhere. Costs are stated but not labelled modeled-not-calibrated. |
| `scripts/ma_crossover_backtest.py:307-329` | Price/SMA chart with fills (title 323) | A, R, D, L | Saved via `plotting.save_figure`, which stamps nothing (`scripts/plotting.py:25-34`). |
| `scripts/logistic_baseline.py:89-93`, `122-128` | Fold accuracy, overall and majority-class accuracy | R, D, L; A partial | **Pinned file** — fixing it is a human gate. 322 prints the output CSV path, not the input source. |
| `scripts/logistic_baseline.py:337-351`, `363-364` → `_format_ml_comparison` (236-310) | Trade log; logistic vs baselines | A, R, D, L | Pinned. No source header and no `pay_date_disclosure`, unlike the MA script. |
| `scripts/feature_set_comparison.py:695-699`, `1004-1005` → `format_report` (786-863) | p-values, accuracy/MSE A→B, verdict | A, R, D, L | Pinned. Writes `data/cache/feature_set_comparison.json` (`CHECKPOINT_PATH` 866-868, written by `_checkpoint` 890-932) but never cites it on the panel. |
| `scripts/feature_diagnostics.py:240-250` → `format_report` (166-222) | Correlations, VIF, condition number | A, R, D, L | Prints ticker and period only. |
| `scripts/return_stats.py:90-96` | Vol, skew, kurtosis, max drawdown | A, R, D, L | |
| `scripts/return_stats.py:98-113` | Annualized return, **Sharpe** | A, R, D, **S**, L | The only Sharpe printed by a script. "Not evidence of skill" (106) is a code comment, never printed. |
| `scripts/return_stats.py:115-149` | Return histograms (titles 142, 148) | A, R, D, L | |
| `scripts/autocorrelation_check.py:30-33`, `36-43` | ACF table and plot | A, R, D, L | Plot bypasses `save_figure` (`savefig` at 42), so a stamp added there would miss it. |
| `scripts/stationarity_check.py:33-41`, `58-64`, `67-76` | ACF; ADF statistic, p-value, verdict | A, R, D, L | Plot also bypasses `save_figure` (40). |
| `scripts/scratch_aapl_correlations.py:67-113` | Correlation matrix, ranked pairs | A, R, D, L | Reads `CSV_PATH` (12) without printing it. |
| `scripts/scratch_multiticker_collinearity.py:124-234` | Correlations, condition numbers, VIF | R, D, L; A partial | 126 prints the CSV path, without hash or date. |

## 2. `reports/` — API and web terminal

| File:line | Figures | Missing | Notes |
|---|---|---|---|
| `reports/api/routes/backtest.py:38-196` (tearsheet) | P&L, return, **Sharpe** (119, 190), drawdown, equity curve, trade log, baseline table | R, D, **S**, L (partial) | Returns `source_name`, `downloaded_at_utc`, `source_manifest_sha256`, `capital_gate_eligible`, `source_limitations`, `dividend_pay_date_disclosure` (181-186). Dropped on the way out: the trial id held at 60; `performance_summary`'s `risk_free_rate_annual` and its `interpretation` caveat (`scripts/metrics.py:359-360`); and the ledger's `oos: False` / `ineligible_reason` for this run (`scripts/trial_runner.py:114-116`). |
| `reports/api/routes/backtest.py:192` | `reconciliation_passed=True` | label | Reached only after `equity_curve` (71) passes its cash-plus-positions check at `RECONCILIATION_TOLERANCE` = 1e-9 (`scripts/metrics.py:25`, `94-96`); a failure becomes HTTP 500, so the field can never be `False`. Nothing states what the check covers. |
| `reports/api/routes/backtest.py:170` | `holding_bars=1` on every trade | A | Constant sent as data. |
| `reports/api/routes/data.py:88-175` (`/ohlcv`, `/stats`, `/gaps`) | Bars; vol, skew, kurtosis, drawdown; missing bars | A, R, D, L | Reads whichever adjusted cache CSV `get_cached_ticker_data` finds (39-65); no filename, manifest or hash returned. |
| `reports/api/routes/data.py:82-84` | Fallback ticker list | A | Hardcoded when the cache is empty. |
| `reports/api/routes/diagnostics.py:28-81` | Condition numbers, VIF, correlation matrix | A, R, D, L | Same untracked CSV. |
| `reports/api/routes/ml_rundown.py:37-222` | Price/volume readings embedded in strings | A, R, L; D partial | `as_of_date` (217) is the last bar, not the run date. Literal `252` at 63. |
| `reports/api/routes/capital_gate.py:62` | `overall_readiness` "Phase 3" | A | Hardcoded string; rendered at `CapitalGateView.tsx:62`. |
| `reports/web/src/types/api.ts:85-99` | — | — | **The key UI gap.** `BacktestTearsheetResponse` omits every provenance and limitation field the API returns, so no view can render them. |
| `BacktestTearsheetView.tsx:99-146` | Net P&L, return, **Sharpe**, drawdown cards | A, R, D, **S**, L | 133 hardcodes "Rf = 3.78% (3m T-Bill)"; 143 renders a null drawdown as `0.00%`. |
| `BacktestTearsheetView.tsx:92-93`, `158-159` | "Drag: -$X"; "✓ 1e-9" | A | Comment says drag includes slippage; 93 computes commission only. "✓ 1e-9" matches the real tolerance but is a literal that ignores `reconciliation_passed`. |
| `BacktestTearsheetView.tsx:165-173` (TutorCard) | Rf, "$1/trade", "5 bps", "reconciled down to 1e-9", Sharpe bands | A, S | "Reconciled down to 1e-9" is true only of cash-plus-positions equity, and reads as broader. Sharpe bands invite reading an undeflated Sharpe as evidence. |
| `BacktestTearsheetView.tsx:350-518` | Equity/drawdown tables and charts, candles with fills, baseline table with Sharpe (453), trade ledger | A, R, D, S, L | Candles come from the adjusted CSV (`/api/data/ohlcv`) while fills come from the unadjusted bundle, so unadjusted fills are drawn on adjusted candles. |
| `MarketDataView.tsx:43-157` | Vol, kurtosis, skew, drawdown, session count, gaps, candles with trades | A, R, D, L | 56 hardcodes "Fat tails (3.0 - 12.0)"; 98 says "Split/dividend adjusted daily bars" without the partial-reconciliation limitation. |
| `FeatureDiagnosticsView.tsx:45`, `56`, `117`, `125`, `155` | "r=0.998", "$50…$200", "Zero models beat baseline", "κ = 422 and VIF = 54", "✓ 17x Improvement", unconditional threshold claims | A, R, D, L | Hardcoded historical figures beside live ones, unlabelled; they can contradict the live values. |
| `FeatureDiagnosticsView.tsx:74-201` | Live condition numbers, VIF, correlation matrix | A, R, D, L | 178 renders a missing cell as `0`. |
| `CrossValidationView.tsx:10-18`, `79-111` | Six "representative" folds, "1 bar" purge/embargo | A | Placeholder figures in a results-looking panel without `EXAMPLE — NOT A RESULT`. Not fetched. |
| `CapitalGateView.tsx:72-74` (TutorCard) | Gate definitions, "focus on finishing Gate 4" | A | Disagrees with the API's gate definitions (`capital_gate.py:24-58`) and implies progress no evidence supports. |
| `MLRundownPane.tsx:86-184` | "As of" date, readings | A, R, L; D partial | |
| `reports/web/README.md` | — | L | Unmodified Vite template: no statement of what the terminal shows or its limitations. |

Compliant today: `NotComputed` for significance, forecast and test run
(`schemas.py:10-19`, `NotComputedNotice.tsx`), `CapitalGateItem.evidence`
validation (`schemas.py:135-142`), "TESTS: NOT REPORTED" (`Header.tsx:107-114`).

## 3. Repository markdown, spec results sections, committed figures

Most cited source artifacts below live under `data/cache/` (gitignored, absent
from any clone) or in a past agent scratchpad; read literally, Rule 11 makes
those stale (X). Exception: the 2026-09-12 audit's SMA tearsheet figures and
always-up rate are committed in `docs/audit-2026-09-12/probe-results.json:289-293`
(`cached_sma_tearsheet`) and `direction-baseline.json`, linked from
`AUDIT.md:245`, so those rows are not X; they still lack a same-line citation.
See Q1 below.

| File:line | Figures | Missing | Notes |
|---|---|---|---|
| `docs/audit-2026-09-12/AUDIT.md:41` | $57.54 vs $293.14 vs $95.81; 233.64% return; **0.17 Sharpe**; −72.36% drawdown | A (on the line), R, **S**, L | Says "not reliable funded-account results" but not provisional/undeflated. Highest misreading risk. |
| `docs/audit-2026-09-12/AUDIT.md:30-37` | 014 accuracy/MSE and p-values; always-up 53.540% | R, L; X for the 014 figures | 014 figures cite absent `data/cache/feature_set_comparison.json`; the always-up rate is in committed `direction-baseline.json`. |
| `docs/audit-2026-09-12/AUDIT.md:11`, `245` | Links to `coverage.csv` | X | Only `coverage.json` and `coverage-initial.json` exist. |
| `docs/audit-2026-09-12/REMEDIATION_PLAN.md:145`, `291-294` | 53.54% / 52.99%; 233.64%; **0.17 Sharpe**; −72.36% | A, R, D, **S**, L; X for 52.99% | Header says "DERIVED — NOT AUTHORITATIVE" (1-7) but the figures render without provenance. |
| `docs/audit-2026-09-12/remediation-map.html:358-366`, `483` | 52.99% vs 53.54%; 0.0844% MSE gain; 233.64% on $24.63 | A, R, L | Committed HTML panel titled "What today's results show"; same class as REMEDIATION_PLAN. |
| `docs/PROJECT_CONTEXT.md:826-828` | "Sharpe ratio output now trusted" | **S** | Contradicts Rule 15. No number, but the claim is the problem. |
| `docs/PROJECT_CONTEXT.md:810-821`, `833-839` | 2y vol, skew, kurtosis; max drawdown with dates | A, R, D, L, X | Console output of `return_stats.py`; no artifact ever existed. |
| `docs/PROJECT_CONTEXT.md:595-598` | Accuracy 0.519 vs 0.542; P&L $47.25 / $126.71 / $74.26 ± $19.00 | A, R, D, L, X | Costs at 589; no fold/purge/embargo. Superseded per spec 006 but not marked here. |
| `docs/PROJECT_CONTEXT.md:385-428`, `874-875` | 014 condition number, VIF, correlations; McNemar/Wilcoxon table | R, D, L, X | |
| `docs/PROJECT_CONTEXT.md:240-263`, `290-294` | 52.99%, half-Kelly 1.65×; overlap 3.24, gross 1.22→0.38; p-values | A, R, D, L, X | |
| `docs/PROJECT_CONTEXT.md:765-767` | 8 trades, 50% win, +$33 | A, R, D, L | Marked superseded (766-767), still rendered; uncosted (Rule 3). |
| `NIGHT_RUN_SUMMARY.md:125-137` | Sizing diagnostic: overlap, gross, exposure removed, peak overlap | A, R, L, X | 205-206 say the real-data diagnostic stayed "Scratchpad only". |
| `NIGHT_RUN_SUMMARY.md:148`, `176` | 52.99% → 1.65×; 0.25 → 0.125 | A, R, D, L, X | 176 is probe arithmetic; needs the example label or a citation. |
| `.specify/specs/014-scale-free-features/tasks.md:146-149` | McNemar/Wilcoxon table | R, D, L, X | Cites absent cache JSON (126, 139). Folds, purge, embargo given. |
| `.specify/specs/014-scale-free-features/tasks.md:122-124`, `plan.md:135-139`, `spec.md:47-52`, `86`, `302` | Condition number, VIF, correlations | A, R, D, L, X | |
| `.specify/specs/012-cost-aware-entry-rule/spec.md:89-90` | 014 p-values | A, R, D, L, X | Re-quoted without citation. |
| `.specify/specs/017-position-sizing-risk/tasks.md:182-196`, `spec.md:106-108`, `research.md:28-33` | Overlap/gross table, weights; 52.99%, σ ≈ 181 bps, Kelly | R, D, L, X; A for spec.md and research.md | Input CSV absent. research.md's source column names specs, not artifacts. |
| `.specify/specs/006-embargo-window-semantics/spec.md:232-234` | 0.519 vs 0.542; $47.25 / $126.71 / $74.26 | A, R, D, L, X | Self-declared superseded (236-239). |
| `.specify/specs/009-selectable-target/spec.md:58-59` | 0.519 vs 0.542 | A, R, D, L | |
| `.specify/specs/002-backtest-costs-baselines/spec.md:215-216`, `plan.md:124` | 8 trades, 50%, ~$33 | A, R, D, L, X | Uncosted. |
| `plots/*.png` (six files) | 30-lag ACF on real data | A, R, D, L | Only on-image text is the title. Three byte-identical pairs (`docs/cleanup-audit-2026-09-18/AUDIT.md:90`). No markdown states their source data, run or date. |

Labelling-only gaps (illustrative values without `EXAMPLE — NOT A RESULT` on
the same line): `017/tasks.md:197` (−3.54% / −4.5%),
`020-unadjusted-price-data/spec.md:111` (~$105 vs ~$25),
`docs/audit-2026-09-12/CODEX_LANE_HANDOFF.md:120-128` (fixture oracles),
`docs/implementation/spec-033/SPEC_CORRECTION_PROPOSAL.md:14-15`, `20`, `27`
(paper-oracle DSR values on unlabelled lines).

`README.md` shows no result figure. Its limitations table (35-41) omits the §6
dividend pay-date bound; that matters once a result is added (SCOPE-V1 §3
item 7). `review_018.log` and `review_019.log` hold only a spend-limit error.

## Questions for Camden (not decided here)

1. **Historical figures whose source is gitignored.** Rule 11 says a figure
   whose source artifact is absent is stale and must be regenerated or removed.
   Most historical results in §3 cite `data/cache/` or a scratchpad (the
   committed 2026-09-12 probe JSONs are the exception). Options:
   regenerate with a committed small summary artifact; strike the figures and
   leave a pointer to the ledger; or mark audit/history documents as quotation
   rather than results. This is a scope call for the 038 spec.
2. **Pinned files.** Three panels (`logistic_baseline.py`,
   `feature_set_comparison.py`) are pinned 019 files; their fixes need the human
   lane or a lifted pin.
3. **Tearsheet defects found in passing** (commission-only "Drag" labelled as
   including slippage; adjusted candles under unadjusted fills; null drawdown
   shown as `0.00%`) are correctness defects, not only disclosure gaps. They may
   belong in a separate spec.

## Method

Three read-only passes over `scripts/`, `reports/`, and the repository's
markdown, committed HTML and `plots/`, an independent re-check of 40+ citations
(which corrected several lines and the reconciliation claim), then spot-checks of the highest-risk rows against the
tree (`return_stats.py:98-113`, `ma_crossover_backtest.py:273-279`,
`backtest.py:190-193`, `api.ts:85-99`, `BacktestTearsheetView.tsx:92-93,
157-160`, `CrossValidationView.tsx:10-18`, `FeatureDiagnosticsView.tsx:45`,
`PROJECT_CONTEXT.md:826-828`, `AUDIT.md:41`, `014/tasks.md:146-149`).
`docs/trials/` was not read beyond confirming it exists.
