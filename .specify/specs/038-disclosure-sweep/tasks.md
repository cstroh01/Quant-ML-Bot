# Tasks: Rule 11 / Rule 16 disclosure sweep (spec 038)

Queue Q18, report-only. Built from merged `spec.md` (PR #43) and `plan.md` (PR #52) against main
`f49bd8b4ba2fb877772f34b5f230abd0cb888d1b`, 2026-10-07. Every task is unchecked. This file authorizes
no code, test, dependency, figure regeneration, deletion or result. Spec.md governs; plan.md orders.
D-1–D-5 stay open, and a task that consumes one waits for the human decision recorded in spec.md §8.

## Conventions (apply to every unit)

- **Admission.** One unit = one review PR, ≤300 added+removed lines including tests, evidence and
  status, measured against pre-unit copies without Git. A unit whose complete file set exceeds the cap
  stops before implementation and needs a `plan.md` subdivision PR. Never compress code or drop a test.
- **Re-anchor first.** Each unit re-reads its anchors by string before editing; the line numbers below
  are from `f49bd8b` and drift.
- **Evidence per unit.** `python -m pytest tests` before and after (exit, passed/failed/xfailed/errors,
  Python version); SHA-256 of every `docs/trials/` file before/after and `docs/trials/returns/` absent;
  line count. Camden's Windows venv is the acceptance gate; Linux or CI runs are separate evidence.
- **Rule 12.** Each new guard has a contract test that is red before the unit's change, green after it
  unmutated, killed by its named mutant with the guard's own assertion message (not an import, type or
  compile error), and a clean control. Mutants run in copies or memory; drivers live in `tests/mutation/`.
  `mutation_support_019` catches any `AssertionError`, so each oracle has one contract assertion and
  setup does not assert.
- **Offline.** No socket, no `data/cache/` read or write, no `docs/trials/` write, no gitignored input.
- **Ownership.** 047 owns `BacktestTearsheetView.tsx`, `routes/backtest.py`, `schemas.py` and `api.ts`
  until it releases them; 035 owns the `reconciliation_passed` label (FR-007); 036 owns bundle fields
  (FR-008); 046 owns modeled-cost wording (FR-007); 033 owns DSR, lifetime-N, Sharpe-flag removal and
  `routes/capital_gate.py` while Phases 8–9 run; 049 owns paper surfaces (`paper_report.py`,
  `paper_monitor.py`, `paper_targets.py`). 038 adopts their fields and adds no second copy.
- **Pinned files** (`logistic_baseline.py`, `feature_set_comparison.py`, `multi_ticker_comparison.py`)
  are human lane. No autonomous unit edits them; the 043 T025 exception does not extend to 038.
- `<D1>` below means the module D-1 selects. No task assumes `scripts/disclosure.py` before D-1.

## Phase 0 — human gates (no lane unit consumes an open one)

- [ ] T001 **HUMAN GATE — D-1, Camden.** Choose helper placement. If a new module, the `CLAUDE.md`
  module-table row is a human governance edit. Blocks T020–T022 and every unit that consumes them.
- [ ] T002 **HUMAN GATE — D-4, Camden.** Inline register or same-surface reference, per surface class.
  Blocks T030–T033 (panel form), T050, T055–T059 and T064.
- [ ] T003 **HUMAN GATE — D-3, Camden.** CrossValidationView: `EXAMPLE — NOT A RESULT` labels or real fold
  configuration served from `walk_forward_cv.py`. A served configuration is a new API contract. Blocks T059.
- [ ] T004 **HUMAN GATE — D-2, Camden.** Any PROJECT_CONTEXT or plot figure moved from S to G, with its
  named source. Regeneration needing market data is a separate human network task. Default S stands.
- [ ] T005 **HUMAN GATE — D-5, Camden.** Q versus Rule 11 for absent-source (X) figures: (a), (b) or (c).
  Option (a) may need a constitution amendment, which is outside every lane. Blocks T065.
- [ ] T006 **HUMAN GATE — 047 D-1 runtime view test runner, Camden.** M9 and every render claim wait on
  the runner 047 actually adopts. A TypeScript source scan cannot certify rendering.
- [ ] T007 **HUMAN GATE — HTML anchor, Camden.** `remediation-map.html` has no literal `<body>` or
  `</head>`; its first body element is `<div class="wrap">` at `:220`. Confirm that as the FR-006 anchor
  and how the guard locates it, or revise plan.md. Blocks T060 for that file.
- [ ] T008 **HUMAN GATE — JSON evidence, Camden.** `docs/cleanup-audit-2026-09-18/checks.json`,
  `inventory.json` and the 2026-09-12 `*.json` evidence cannot carry a Markdown banner. Decide whether
  they are outside Q (machine evidence, not a reader surface) or need a plan revision.

## Phase 1 — B: baseline and exact inventory (evidence only; no source edit)

- [ ] T010 Record the baseline: source revision, Python version, full-suite counts and exit, all
  `docs/trials/` hashes, `returns/` absent, and hashes of the three pinned files and every `save_figure`
  caller. Output: `docs/implementation/spec-038/baseline-<YYYYMMDD>.md`. SC-003's "no worse than" uses it.
- [ ] T011 Re-verify the register below at the unit's revision. A surface found in the tree but absent
  here fails admission until plan.md assigns it. Confirm `docs/cleanup-audit-2026-09-18/AUDIT.md` holds
  no outcome figure (none matched at `f49bd8b`; its numbers are evidence citations), and record it.

### Static register at `f49bd8b` (Q / Q-pending-D-5 / S / G / label)

| Path:line | Figure(s) | Class | Source note |
|---|---|---|---|
| `docs/audit-2026-09-12/AUDIT.md:1` | — | Q banner anchor (first content line) | FR-006 |
| `AUDIT.md:41` | $57.54/$293.14/$95.81; 233.64%; 0.17 Sharpe; −72.36% | Q + same-line Rule 15 flag | committed `probe-results.json:289-293` |
| `AUDIT.md:30-37` | 014 accuracy/MSE/p-values | Q-pending-D-5 | absent `data/cache/feature_set_comparison.json` |
| `AUDIT.md:34` | always-up 53.540% | Q | committed `direction-baseline.json` |
| `AUDIT.md:11`, `:245` | link `coverage.csv` | relink to `coverage.json` | file absent |
| `docs/audit-2026-09-12/REMEDIATION_PLAN.md:1` | — | Q banner anchor, above the derived-document header | FR-006 |
| `REMEDIATION_PLAN.md:145`, `:292` | 53.54% (Q); 52.99% (Q-pending-D-5) | mixed line | 52.99% absent source |
| `REMEDIATION_PLAN.md:294` | 233.64% / 0.17 Sharpe / −72.36% | Q + same-line flag | committed probe |
| `docs/audit-2026-09-12/remediation-map.html:220` | — | Q banner anchor (T007) | FR-006 |
| `remediation-map.html:361`, `:483` | 52.99% (pending) vs 53.54% (Q) | mixed | as above |
| `remediation-map.html:362`, `:476` | 0.0844% MSE gain | Q-pending-D-5 | 014 cache absent; `:476` new since audit |
| `remediation-map.html:364` | 233.64%, $24.63 | Q | committed probe |
| `NIGHT_RUN_SUMMARY.md:1` | — | Q banner anchor | FR-006 |
| `NIGHT_RUN_SUMMARY.md:125-137` | overlap 3.24, gross 0.38, 69%, peak 4.48 | Q-pending-D-5 | scratchpad only (`:205`) |
| `NIGHT_RUN_SUMMARY.md:148` | 52.99% → 1.65× | Q-pending-D-5 | 014 cache absent |
| `NIGHT_RUN_SUMMARY.md:176` | 0.25 → 0.125 | label `EXAMPLE — NOT A RESULT` | probe arithmetic |
| `.specify/specs/002-backtest-costs-baselines/spec.md:215-216`, `plan.md:124` | 8 trades, 50%, ~$33 | S | X, uncosted |
| `.specify/specs/006-embargo-window-semantics/spec.md:232-234` | 0.519/0.542; $47.25/$126.71/$74.26±$19.00 | S | X |
| `.specify/specs/009-selectable-target/spec.md:58-59` | 0.519 vs 0.542 | S | no source named |
| `.specify/specs/012-cost-aware-entry-rule/spec.md:89-90` | p = 0.0122/0.0313/0.433/0.263 | S | X |
| `.specify/specs/014-scale-free-features/spec.md:47-52`, `:86`, `:302` | 0.998, 36.2, 268; 0.325/0.865; ~0.53 | S | X |
| `014/plan.md:135-139`; `014/tasks.md:122-124`, `:146-149` | κ, VIF, max abs ρ; McNemar/Wilcoxon table | S | X |
| `.specify/specs/017-position-sizing-risk/spec.md:106-108`; `research.md:28-33` | 52.99%, σ 181 bps, Kelly 3.3×/1.65× | S | X |
| `017/tasks.md:182-196` | overlap/gross table, weights | S | input CSV absent |
| `docs/PROJECT_CONTEXT.md:240-263`, `:290-294` | 52.99%, 1.65×; 4.68× speedup, p-values | S unless T004 | X |
| `PROJECT_CONTEXT.md:385-428`, `:874-875` | κ 36.17→2.15, VIF, ρ; p = 0.0122/0.0313 | S unless T004 | X |
| `PROJECT_CONTEXT.md:595-598`, `:765-767` | 0.519/0.542, P&L; 8 trades +$33 | S | X / uncosted |
| `PROJECT_CONTEXT.md:810-821`, `:833-839` | vol/skew/kurtosis; drawdowns with dates | S unless T004 | console output only |
| `PROJECT_CONTEXT.md:826-828` | "Sharpe ratio output now trusted" | S → Rule 15 statement | contradicts Rule 15 |
| `plots/AAPL_acf.png`, `GOOGL_acf.png`, `MSFT_acf.png` | 30-lag ACF | S (no deletion before T067) | no source/run/date |
| `plots/aapl_log_returns_acf.png`, `googl_…`, `msft_…` | byte-identical to the three above | S | pairs `0824…`, `18a5…`, `90b7…` |
| `.specify/specs/017-position-sizing-risk/tasks.md:197` | daily −3.54%, weekly −4.5% | label | halt example output |
| `017/quickstart.md:79-80` | −4.5%, −3.5% | **unassigned** (not in audit or plan) | needs plan.md row before T063 |
| `.specify/specs/020-unadjusted-price-data/spec.md:111` | ~$105 vs ~$25 | label | illustrative |
| `docs/audit-2026-09-12/CODEX_LANE_HANDOFF.md:120-128` | fixture oracles | label | synthetic fixture |
| `docs/implementation/spec-033/SPEC_CORRECTION_PROPOSAL.md:14-15`, `:20`, `:27` | paper DSR values | label | paper oracle |
| `README.md:36-42` | register (5 of 7 items) | G text | adds pay-date bound, no real capital |
| `reports/web/README.md:1` | Vite template | G text | replaced by terminal statement + register |

## Phase 2 — R: shared register and provenance (depends T001, T002, T010)

- [ ] T020 R contract red. Files: `tests/test_038_register.py`, `tests/test_038_stamp.py`. Register parity
  parses SCOPE-V1 §6 bullets by actual section boundaries and compares both directions. Stamp contracts:
  injected aware UTC clock, `root`, `commit: unknown` when `git_sha` is None, `trial: none (descriptive, not
  a trial)`, no Git or network, model and descriptive stamps distinct. Red before T021 (missing module).
- [ ] T021 R implementation. Files: `scripts/<D1>` only; the `CLAUDE.md` row is T001's separate human edit. Register
  constant copied verbatim from `SCOPE-V1.md:120-135`; `sharpe_status` string; stamp as plain `list[str]`.
  Unmutated green: T020. Cap: T020–T022 ship as one unit, ≤300 lines.
- [ ] T022 Mutants M1 (drop dividend-bound item), M1-scope (temp SCOPE copy edit), M2 (cached commit after
  synthetic HEAD change, `GITHUB_SHA` cleared), M3 (last-bar date), M3b (`TZ=America/New_York`, clock 02:00Z;
  control 12:00Z). Driver: `tests/mutation/run_038_register_stamp_mutants.py`. Control: unmutated T020 green.

## Phase 3 — P: terminal panels (each separately admitted; depends T021)

- [ ] T030 P1. Files: `scripts/return_stats.py`, `scripts/feature_diagnostics.py`,
  `tests/test_return_stats.py`, `tests/test_038_panels_p1.py`. Stamp before first figure, register line,
  printed Rule 15 flag on the Sharpe line (`return_stats.py:99-112`); `:106` comment becomes printed text.
  Red: captured-stdout contract. Mutant M4 (flag removed; control asserts ≥1 Sharpe line matched).
- [ ] T031 P2. Files: `scripts/autocorrelation_check.py`, `scripts/stationarity_check.py`,
  `tests/test_038_panels_p2.py`. Panel stamp/register only; plots move in T040. Red: stdout lacks stamp.
  Mutant: stamp printed after first figure. Control: stamped stdout.
- [ ] T032 P3. Files: `scripts/scratch_aapl_correlations.py`, `scripts/scratch_multiticker_collinearity.py`,
  `tests/test_038_panels_p3.py`. Input filename, SHA-256 and run time (`CSV_PATH` `:12`; `:126`). Synthetic
  CSV fixture. Mutant: hash of a different file. Control: hash of the read file.
- [ ] T033 P4. Files: `scripts/ma_crossover_backtest.py` (`main` and `format_comparison` `:183`),
  `tests/test_038_panels_p4.py`. Adds the live trial id from `research_attempt` and the register; keeps
  036 bundle fields and 046 modeled-cost wording as found. Mutant: trial id from a stale attempt. Control:
  actual attempt id. Hash before/after; 021 close-out stays unresolved if the fingerprint changes.

## Phase 4 — F: stamped figures (depends T021 and T030–T033 where shared)

- [ ] T040 F. Files: `scripts/plotting.py` (`save_figure` `:25`), `scripts/ma_crossover_backtest.py:329`,
  `scripts/return_stats.py:149`, `scripts/data_pipeline_sanity_check.py:88`, `scripts/autocorrelation_check.py:42`,
  `scripts/stationarity_check.py:40`, `tests/test_return_stats.py`, `tests/test_data_pipeline_sanity_check.py`,
  `tests/test_038_figures.py`. Stamp is a required `list[str]`; reserved margin; `plotting` imports no
  `<D1>`, trial or strategy module. All five callers in this unit; no broken intermediate signature. If the
  complete set exceeds 300 lines, stop and subdivide plan.md. Red: stampless call accepted. Mutant M5.
  Control: stamped call writes a file into a temp dir. Render one stamped file and inspect it for clipping.

## Phase 5 — A: API (each waits on the 047 release of shared files)

- [ ] T050 A1 tearsheet. Files: `reports/api/routes/backtest.py`, `reports/api/schemas.py`,
  `tests/test_038_api_tearsheet.py`. Adds `provenance` (commit, workspace state, trial id, UTC run time,
  036 source fields), `limitations`, `sharpe_status`, `risk_free_rate_annual`, `interpretation`, `oos`,
  `ineligible_reason`. Keeps 047 friction/bar fields and 035's label. Red: fields absent. Mutant M6
  (`limitations: []`). Control: full register entry for entry. Depends T001, T002, T021, 047 release.
- [ ] T051 A2 data/diagnostics. Files: `reports/api/routes/data.py` (`get_cached_ticker_data` `:36`,
  fallback list `:84`), `reports/api/routes/diagnostics.py`, `reports/api/schemas.py`,
  `tests/test_038_api_data.py`. Selected CSV filename, SHA-256, run time; empty cache returns `[]` with a
  reason. Mutant: hash of the first candidate, not the selected file. Control: selected file.
- [ ] T052 A3 ml_rundown. Files: `reports/api/routes/ml_rundown.py`, `reports/api/schemas.py`,
  `tests/test_038_api_ml_rundown.py`. Run time UTC separate from `as_of_date` (`:217`, last bar). Clock pinned
  either side of UTC midnight. Mutant: run time = last bar. Control: injected clock.
- [ ] T053 A4 holding bars and drawdown anchor. Files: `reports/api/routes/backtest.py` (`holding_bars=1`
  `:170`; running-max drawdown `:145-146`), `tests/test_038_api_bars_drawdown.py`. Adopt 047 U1a's
  `mean_holding_bars` helper (`ma_crossover_backtest.py:72`) rather than add one; method chosen in the unit
  PR before code. Rule 5 tests: first/last trade, fold edge, calendar gap. Mutant: off-by-one session count.
  Control: curve minimum equals `metrics.max_drawdown`. Depends 047 release.
- [ ] T054 A5 capital gate. Files: `reports/api/routes/capital_gate.py` (`:62` readiness string),
  `tests/test_038_api_capital_gate.py`. Waits on 033 releasing the route. Strike the literal; serve the
  definitions at `:24-58`. Mutant: literal restored. Control: served definitions.

## Phase 6 — V: web views (each depends on its A unit, 047 release and T006)

Every V unit: render contract red under the runner 047 adopts, unmutated green, M9-style kill with that
runner's own assertion message, control rendering every listed view. Test paths follow that runner's
layout, fixed when T006 lands; they are named here as `<runner>/038-*.test.tsx`. Without the runner a V
unit may ship only with a declared known gap and claims no render acceptance (spec FR-008).

- [ ] T055 V0. Files: `reports/web/src/types/api.ts` (`:85-99` plus T051/T052 fields), new shared
  `ProvenanceBanner` and `LimitationsBlock` components, `<runner>/038-components.test.tsx`. Red: banner
  absent for a fixture response. Mutant: banner drops `commit: unknown`. Control: full fixture renders.
- [ ] T056 V1. Files: `BacktestTearsheetView.tsx`, `<runner>/038-tearsheet.test.tsx`. Banner/register;
  `:133` Rf and `:159` tolerance read API values; `:170-171` Sharpe bands struck (S); Sharpe card flag;
  `reconciliation_passed` shown with 035's schema description only. `:143` null drawdown stays 047's.
  Depends T050, T055. Mutant M9 (banner component removed). Control: fixture tearsheet renders all.
- [ ] T057 V2. Files: `MarketDataView.tsx` (`:56` S; `:98` partial-reconciliation limitation),
  `FeatureDiagnosticsView.tsx` (`:45`, `:56`, `:117`, `:125`, `:155` S; `:178` `?? 0` renders unavailable),
  `<runner>/038-data-views.test.tsx`. Depends T051, T055. Mutant: missing cell back to `0`. Control:
  present cell renders its value.
- [ ] T058 V3. Files: `reports/web/src/components/layout/MLRundownPane.tsx` (`:86-184`),
  `<runner>/038-ml-rundown.test.tsx`. Run time and last bar shown and labelled separately. Depends T052,
  T055. Mutant: last bar rendered as run time. Control: distinct fixture values both render.
- [ ] T059 V4. Files: `CrossValidationView.tsx` (`:10-18`), `<runner>/038-cv.test.tsx`. Per T003 only.
  Mutant: one fold row loses its label (or served value). Control: all six rows. Depends T003, T055.
- [ ] T059a V5. Files: `CapitalGateView.tsx` (`:62`, `:72-74`), `<runner>/038-capital.test.tsx`. Renders
  T054's served definitions instead of its TutorCard copy. Depends T054, T055 and 033's release.
  Mutant: hard-coded "Gate 4" copy restored. Control: fixture definitions render.

## Phase 7 — D: static documents (markdown only; can start after T011)

One guard file serves all D units: `tests/test_038_static_guard.py`, with drivers in
`tests/mutation/run_038_static_mutants.py`. Each unit extends it for its own rows and is red first.

- [ ] T060 D1 Q banners. Files: `AUDIT.md`, `REMEDIATION_PLAN.md`, `NIGHT_RUN_SUMMARY.md`, then
  `remediation-map.html` after T007, plus the guard. Exact FR-006 banner at the register anchors;
  same-line Rule 15 flag at `AUDIT.md:41` and `REMEDIATION_PLAN.md:294`. Q-pending-D-5 figures stay
  unchanged and listed as pending; a banner does not close them. Mutants M7 (banner removed from a copy)
  and M8 (`AUDIT.md:41` flag removed). Control: bannered, flagged tree. Sharpe matcher fixtures:
  `0.17 Sharpe`, `Sharpe ratio = 0.5`; false-positive controls `Logit Score=+0.17` (`AUDIT.md:143`) and a
  Sharpe sentence with no number.
- [ ] T061 D2a closed specs 002, 006, 009, 012; D2b spec 014; D2c spec 017 (files per register). S with a
  pointer to a ledger entry if one exists, else to the quotation document. A pointer to a pending
  quotation is not results provenance. Red: struck figure still present. Mutant: one figure restored in
  a copy. Control: pointer line present, figure absent. Each sub-unit separately admitted.
- [ ] T062 D3 `docs/PROJECT_CONTEXT.md` strikes per register; `:826-828` replaced by the Rule 15
  requirement. Split by block if over the cap. Same red/mutant/control shape as T061; the extra mutant
  restores "Sharpe ratio output now trusted".
- [ ] T063 D4 labels: `NIGHT_RUN_SUMMARY.md:176`, `017/tasks.md:197`, `020/spec.md:111`,
  `CODEX_LANE_HANDOFF.md:120-128`, `SPEC_CORRECTION_PROPOSAL.md:14-15`, `:20`, `:27`; `AUDIT.md:11`, `:245`
  relinked to `coverage.json`. Values unchanged. Mutant: one label moved off its figure's line.
  Control: labelled lines. `017/quickstart.md:79-80` waits for its plan.md row.
- [ ] T064 D5 `README.md` (register from T021) and `reports/web/README.md`. Mutant M1b (one item
  dropped). Control: full README. Depends T002, T021.
- [ ] T065 X quotations per T005. Not started while D-5 is open.
- [ ] T066 G regeneration per T004 only: summary under `docs/implementation/spec-038/artifacts/` with input
  hashes, `source_tree_hash`, producing `git_sha` and date. No cache write; no network in tests.
- [ ] T067 D6 **HUMAN GATE — plot removal, Camden.** Approve the exact six-path list above before any
  deletion. No figure is regenerated or deleted by a lane unit without it.

## Phase 8 — H: pinned panels (human lane)

- [ ] T070 **HUMAN LANE — Camden.** `logistic_baseline.py` panels (`:89-93`, `:122-128`, `:337-351`,
  `:363-364`) and `feature_set_comparison.py` report/checkpoint panel (`format_report`), with the same
  consuming tests and stamp rules. The sweep is not complete without these.

## Phase 9 — C: close-out

- [ ] T080 Acceptance matrix: FR-001–FR-005 runtime rows, static dispositions, M1–M8, M1b, M3b each red/
  restored-green with control, M9 or declared gap, full suite versus T010, all `docs/trials/` hashes
  unchanged and `returns/` absent, per-unit line counts, open human items. No closure on focused tests.

## Dependencies

T001→T020→T021→T022→(T030–T033)→T040. T050–T054 need T021 and 047/033 releases. V units need their A
unit and T006. T060–T063 need only T011 (T060 HTML needs T007; T064 needs T021). T065–T067 are human-gated.
T080 is last. Never run 033 Phases 8–9 and T054 on `capital_gate.py` in the same window.
