# Feature Specification: Rule 11 / Rule 16 disclosure sweep

**Feature Branch**: `038-disclosure-sweep` (name only; Camden owns Git)
**Spec number**: 038, assigned by `docs/V1-FINISH-PLAN.md:132` (S7).
**Created**: 2026-10-05
**Status**: Draft `spec.md` only (queue Q13). No `plan.md`, `tasks.md`, code, test or run exists.
Plan and tasks follow once this is merged (queue Q17, Q18).
**Input**: `docs/implementation/spec-038/disclosure-audit-20261003.md` (the audit), and the
2026-10-03 decision on its Q1 recorded in `docs/autonomy/queue.json:122`.
**Blocks**: the v1.0 tag (`docs/SCOPE-V1.md:77`, DoD item 5, "Rule 11 clean").

## 1. What 038 owns, and what it does not

The audit lists every surface a reader could mistake for results that lacks provenance (Rule 11),
the provisional/undeflated Sharpe flag (Rule 15), or the §6 limitations (Rule 16). 038 closes
those gaps. Several neighbouring items already have owners, and 038 does not re-own them:

| Item | Owner | Evidence |
|---|---|---|
| Tearsheet `Drag` omits slippage; adjusted candles under unadjusted fills; null drawdown as `0.00%` | **047** (open PR #42) | `queue.json:122`; audit `:151-154` |
| Renaming or labelling `reconciliation_passed` so it cannot read as Rule 14 status | **035** FR-007 | `035 spec.md`, FR-007; `035 plan.md:71` (schema `description`) |
| Bundle provenance fields in CLI and API output | **036** FR-008 | `036 spec.md:431-433` |
| "costs modeled, not calibrated" on every Rule 13 result | **046** FR-007 | `046 spec.md:164-167` |
| Paper-run records and reports | **049** FR-008, T011 (queue Q21) | `049 spec.md:30`; `049 tasks.md:13` |
| Pinned 019 panels (`logistic_baseline.py`, `feature_set_comparison.py`) | **human lane** | `queue.json:122`; `docs/STATE.md`, Human gates |
| Removing the Rule 15 flag once DSR ≥ 0.95 passes | **033** Phases 8–9 | constitution Rule 15 |

038 builds the shared disclosure pieces those specs render through. Where 036, 046 or 047 lands
first, 038 adopts its field or wording and does not add a second one.

## 2. Current state (cited from the tree at `e2ed6f8`)

The audit was read at `659b2ec`. No file it cites under `scripts/`, `reports/`, `docs/audit-2026-09-12/`,
`docs/PROJECT_CONTEXT.md`, `NIGHT_RUN_SUMMARY.md`, `README.md`, `plots/` or the cited specs changed
between `659b2ec` and `e2ed6f8`, so its line numbers stand. One new surface exists:
`scripts/paper_targets.py`, which belongs to 049.

- **No surface shows a commit SHA or a run/trial id beside a result** (audit `:22-25`). The values exist:
  `trial_registry.source_identity` returns `git_sha` and `source_tree_hash` without running Git
  (`scripts/trial_registry.py:94-127`), and both result paths hold a live `research_attempt`
  (`scripts/ma_crossover_backtest.py:268`; `reports/api/routes/backtest.py:60`).
- **No surface carries the full §6 register** (audit `:26-30`). `README.md:36-42` lists five of the
  seven §6 items; it omits the dividend pay-date bound and "no real capital" (`SCOPE-V1.md:116-135`).
- **Sharpe without the Rule 15 flag** at `scripts/return_stats.py:98-113`, the tearsheet API
  (`routes/backtest.py:190`) and view, `docs/audit-2026-09-12/AUDIT.md:41` and
  `REMEDIATION_PLAN.md:294`. `docs/PROJECT_CONTEXT.md:826-828` says "Sharpe ratio output now trusted".
- **The tearsheet response type drops every provenance field** the API returns
  (`reports/web/src/types/api.ts:85-99` against `routes/backtest.py:181-186`), so no view can render them.
- **Figures are stamped nowhere at save time.** `plotting.save_figure` writes no provenance
  (`scripts/plotting.py:25-34`), and two scripts bypass it (`autocorrelation_check.py:42`,
  `stationarity_check.py:40`).
- **The adjusted-cache routes return no source identity.** `get_cached_ticker_data` picks the first CSV
  that matches (`reports/api/routes/data.py:36-65`) and returns no filename, hash or date.
- **Hard-coded figures beside live ones**: `BacktestTearsheetView.tsx:133`, `:159`, `:170`;
  `FeatureDiagnosticsView.tsx:45`, `:56`, `:117`; `MarketDataView.tsx:56`, `:98`;
  `CrossValidationView.tsx:10-18` (six placeholder folds without `EXAMPLE — NOT A RESULT`);
  `routes/capital_gate.py:62` ("Phase 3" readiness string).
- **No shared helper** exists for a provenance stamp, a limitations block or a Sharpe flag (audit `:34-37`).
- **No web test runner** exists in `reports/web/`. 047 raises the same gap as its D-1.

## 3. The disposition rule (decided 2026-10-03)

Every figure in the audit gets exactly one disposition. The three classes come from the decision
recorded at `queue.json:122`. The definitions below are this spec's, for review.

- **Q — Quotation.** The figure sits in a dated audit or history document whose purpose is to record
  what was said at the time. The document gets a quotation banner at its anchor (FR-006). The
  figure is left unchanged. A Sharpe figure also gets the Rule 15 flag on the same line as the number,
  because Rule 15 requires the flag on the same surface.
  **Conflict, flagged and not resolved here (D-5).** Rule 11's last paragraph says a figure whose
  source artifact is absent "must be regenerated or removed before the PR that touches that surface
  can merge", and adding a banner touches the surface. So Q, applied to an X figure, conflicts with
  the constitution. Until D-5 is decided, Q covers only figures whose source is committed (the
  2026-09-12 probe JSONs, audit `:98-101`). X figures in audit/history documents are listed as
  Q-pending-D-5. X figures in closed specs default to S, because Q13 names only audit and history
  documents.
- **G — Regenerate.** The figure sits on a live surface (the terminal, `reports/`, `README.md`,
  `docs/PROJECT_CONTEXT.md`, an open spec) and a reader still needs it. It is regenerated from a
  committed small summary artifact (FR-007). It then carries that artifact's path, commit and date on
  the same line.
- **S — Strike.** The figure sits on a live surface and either no reader needs it, or it cannot be
  regenerated offline. It is deleted and replaced by a one-line pointer: to the trial ledger entry if
  one exists, otherwise to the quotation document that still holds it. Figures older than the ledger
  point to the quotation document only.

A runtime surface (a script panel, an API response, a web view) is none of these. It computes its
figures each time, so FR-001 to FR-005 stamp them as they render.

### Default dispositions (plan may refine; each change needs a reason)

| Surface (audit row) | Class | Note |
|---|---|---|
| `docs/audit-2026-09-12/AUDIT.md`, `REMEDIATION_PLAN.md`, `remediation-map.html` | Q (X rows: Q-pending-D-5) | The 014 figures (`AUDIT.md:30-37`) and 52.99% (`REMEDIATION_PLAN.md:145`) are X. Sharpe lines `AUDIT.md:41`, `REMEDIATION_PLAN.md:294` get the inline flag. Broken `coverage.csv` links (`AUDIT.md:11`, `:245`) point to `coverage.json`. |
| `NIGHT_RUN_SUMMARY.md`, `docs/cleanup-audit-2026-09-18/` | Q-pending-D-5 | X figures. `NIGHT_RUN_SUMMARY.md:176` probe arithmetic gets `EXAMPLE — NOT A RESULT`. |
| Closed specs 002, 006, 012, 014, 017 (results sections, audit `:119-125`) | S (default; D-5) | Every cited source is absent (X). |
| Closed spec 009 (`spec.md:58-59`) | S (default; D-5) | No source named (A). |
| `docs/PROJECT_CONTEXT.md:826-828` "Sharpe ratio output now trusted" | S | Replaced by a Rule 15 statement. Not a figure, but it contradicts Rule 15. |
| `docs/PROJECT_CONTEXT.md:240-263`, `290-294`, `385-428`, `595-598`, `765-767`, `810-821`, `833-839`, `874-875` | S | Every source is absent (X). Each block is replaced by a pointer. D-2 decides whether any is G instead. |
| `plots/*.png` (six files) | S | No source, run or date. Three byte-identical pairs. Regenerated only through FR-004 if D-2 names one. |
| Labelling-only lines (audit `:128-133`) | label | `EXAMPLE — NOT A RESULT` on the same line. No figure changes. |
| `FeatureDiagnosticsView.tsx:45`, `:56`, `:117`, `:125`, `:155` | S | Historical literals and unconditional threshold claims beside live values. A live value replaces a literal only where the API already returns it. `:178` (missing cell as `0`) renders unavailable. |
| `BacktestTearsheetView.tsx:171` Sharpe bands | S | They invite reading an undeflated Sharpe as evidence (audit `:80`). |
| `routes/backtest.py:170` `holding_bars=1` | S | A constant sent as data (audit `:71`). 047 hands it to 038. Removed, or computed from the trade's own entry and exit sessions. |
| Equity-curve drawdown anchor (`routes/backtest.py:145-146` vs `metrics.max_drawdown`) | runtime | 047 hands it to 038. The served curve and the card must use one stated anchor. A test asserts they agree. |
| `routes/data.py:82-84` fallback ticker list | S | Hard-coded when the cache is empty. An empty cache returns an empty list with a reason. |
| `routes/ml_rundown.py:37-222`, `MLRundownPane.tsx:86-184` | runtime | Stamped by FR-005. `as_of_date` keeps its meaning (last bar) and is labelled so. |
| `MarketDataView.tsx:56` | S | `MarketDataView.tsx:98` gains the partial-reconciliation limitation. |
| `CrossValidationView.tsx:10-18` | label or G | D-3. |
| `routes/capital_gate.py:62`; `CapitalGateView.tsx:72-74` | S | The TutorCard renders the API's gate definitions (`capital_gate.py:24-58`) instead of its own copy. |
| `README.md:36-42` | G | It gains the two missing §6 items. It holds no result figure today. |
| `reports/web/README.md` | G | The Vite template is replaced by a statement of what the terminal shows, plus the limitations block. |

## 4. User scenarios

- **US1 — Every runtime figure names its source (P1).** A reviewer runs any in-scope script, or opens
  any results view. Beside the figures they see the source artifact, the commit, the run date and,
  where one exists, the trial id. *Accept:* FR-001 to FR-005 hold on every runtime row in audit §1–§2
  that is not pinned and not owned in §1.
- **US2 — Every result names its limits (P1).** Every runtime surface that reports a result carries the
  §6 register, either inline or as a reference on the same surface, and every Sharpe carries the flag.
- **US3 — Static documents cannot be mistaken for results (P1).** Every audit §3 row has a disposition
  from §3. A guard (FR-008) fails if a Q-class document loses its banner at its anchor, or if a
  Sharpe line loses its flag.

### Edge cases (Rule 5, where time is involved)

- **Run date is the run's UTC date, not the data's last bar.** `ml_rundown.py:217` `as_of_date` is the
  last bar (audit `:75`). Both are shown, each labelled. The off-by-one case is a run just after
  midnight UTC on a session date. The test pins a fixed clock on both sides of midnight.
- **Session labels stay naive.** A data window is shown as session labels. The run time is an aware UTC
  instant (`CLAUDE.md`, Timestamps). The stamp never localizes a session label.
- **No commit available.** `source_identity` returns `git_sha: None` outside a checkout
  (`trial_registry.py:119`, `:127`). The stamp shows `commit: unknown` and never an empty string, a guess or a
  stale cached value.
- **No trial id.** Descriptive scripts (`return_stats.py`, diagnostics) run no `research_attempt`. The
  stamp shows `trial: none (descriptive, not a trial)`.
- **Null metric.** A null Sharpe or drawdown renders as unavailable, never as `0`. The tearsheet case is
  047's. 038 applies the rule to `FeatureDiagnosticsView.tsx:178` (a missing cell shown as `0`).

## 5. Requirements

- **FR-001 — One register.** A single constant holds the §6 limitations, one entry per bullet at
  `SCOPE-V1.md:120-135`, with the wording kept. Every Python and API surface reads it, and the web
  receives it through the API. A test parses `SCOPE-V1.md` §6 and fails if the constant and the file
  disagree, in either direction. The module that holds it is D-1.
- **FR-002 — Provenance stamp (Python).** One function returns the stamp as plain `list[str]`: source
  artifact (path, plus SHA-256 of the file or the manifest), commit (`source_identity(root)["git_sha"]`
  or `unknown`), `workspace_state`, trial id or the descriptive marker, and run time as aware UTC. It
  takes an injectable clock and a `root` argument (determinism). It runs no Git and makes no network
  call. Every in-scope script panel (audit §1, minus pinned files) prints the stamp before its first
  figure, and prints the register (FR-001), or a one-line reference to it, on the same output.
- **FR-003 — Sharpe flag.** Every printed, served or rendered Sharpe carries "provisional, undeflated
  (Rule 15)" on the same line (text) or the same card (web). Removing the flag is 033's job, once
  DSR ≥ 0.95 passes on that series. `return_stats.py:106`'s comment "not evidence of skill" becomes
  printed text.
- **FR-004 — Figures are stamped.** `plotting.save_figure` takes the stamp as a `list[str]` and draws
  it in the figure margin. `plotting` imports neither the disclosure module nor `trial_registry`. A
  call without a stamp raises. Every caller is updated in the same unit: `ma_crossover_backtest.py`,
  `return_stats.py`, `data_pipeline_sanity_check.py:88`, and `autocorrelation_check.py` and
  `stationarity_check.py`, which move off their direct `savefig` calls.
- **FR-005 — API and web.** The tearsheet response adds a `provenance` object (commit, workspace state,
  trial id, run time UTC, and the source fields 036 FR-008 already names), plus `limitations` and
  `sharpe_status`. It also returns the fields it now drops: `risk_free_rate_annual`, `interpretation`
  (`scripts/metrics.py:359-360`), and the ledger's `oos` / `ineligible_reason`
  (`scripts/trial_runner.py:114-116`). The data, diagnostics and ml_rundown routes return the CSV
  filename, its SHA-256 and the run time. `api.ts` declares every new field. Each results view
  renders one shared provenance banner and one limitations block. Literals that restate an API value
  (`BacktestTearsheetView.tsx:133`, `:159`, `:170`) read that value instead. For
  `reconciliation_passed`, 038 adopts 035's schema `description` (`035 plan.md:71`) on the view and
  adds no wording of its own.
- **FR-006 — Quotation banner.** Every Q document carries one exact banner line at a declared anchor:
  "QUOTATION — figures below are recorded as stated on <date>; they are not current results.
  Limitations: docs/SCOPE-V1.md §6." `plan.md` lists one anchor per document: the first content line
  for markdown, the first element of `<body>` for HTML (`remediation-map.html`).
- **FR-007 — Summary artifacts for G figures.** Each G figure is regenerated by a script that writes a
  small, committed summary under `docs/implementation/spec-038/artifacts/`. The summary holds the
  figure, its inputs' hashes, the producing `source_identity` `git_sha` and `source_tree_hash` (a file
  cannot hold its own commit), and the date. A regeneration that needs market data is a HUMAN GATE
  task. A G figure that cannot be regenerated becomes S. Nothing is written under `data/cache/` for
  commit, or under `docs/trials/` at all.
- **FR-008 — Guard.** One offline test enforces three things. Every Q document has the FR-006 banner at
  its listed anchor. Every line in a Q or G document matching the stated Sharpe pattern carries the
  flag. The pattern is case-insensitive and matches a number on either side of the word (for
  example `0.17 Sharpe` at `AUDIT.md:41` and `Sharpe ratio = 0.5`), within the same sentence.
  `README.md` names every §6 item from FR-001's register. The view check (M9) is in this guard only
  if 047 D-1 adds a web test runner, so that it can be a render test. A source scan of `.tsx` is
  vacuous (047 §5 rules it out). Without a runner, the view wiring is a declared known gap, and it is
  not counted as a kill.
- **FR-009 — Offline.** No test opens a socket, reads `data/cache/` or depends on a gitignored file.
  Fixtures are synthetic.
- **FR-010 — No new figure.** The sweep adds no result figure to any surface. It only stamps, flags,
  labels, regenerates or strikes the existing ones.

## 6. Rule 12 — planted defects (each killed, each with a clean control)

| Id | Plausible defect | Gate | Oracle |
|---|---|---|---|
| M1 | The register drops "Dividend payment dates are a declared conservative bound" (the item `README.md` already misses). | FR-001 parity test | Fails, naming the missing bullet. Control: the unmutated constant passes. A second mutant edits SCOPE instead (in a temp copy) and must also fail. |
| M1b | `README.md` drops one §6 item. | FR-008 README parity | Fails, naming the item. Control: the updated README passes. |
| M2 | The stamp reads a cached commit from an earlier run instead of `source_identity(root)`. | FR-002 | A temp tree whose `HEAD` changes between two calls, with `GITHUB_SHA` cleared by monkeypatch (`source_identity` prefers it, `trial_registry.py:99`). The second stamp must show the new SHA. Control: an unchanged tree gives the same SHA. |
| M3 | The run date is taken from the data's last bar. | FR-002 | An injected UTC clock on a date after the last bar. The stamp must show the clock date. Control: the unmutated stamp. |
| M3b | The stamp uses local `date.today()` or a naive `now()`. | FR-002 | `TZ=America/New_York`, clock at 02:00Z. The stamp must show the UTC date, which is one day later than the local date. Control: clock at 12:00Z, where both dates agree. |
| M4 | `return_stats` prints the Sharpe without the flag. | FR-003 | Captured stdout. Every line matching the FR-008 Sharpe pattern contains the flag, and the control asserts at least one line matches. The test reads the printed line, which is what a reader sees. |
| M5 | `save_figure` accepts a call with no stamp. | FR-004 | The call must raise. Control: a stamped call writes a file. |
| M6 | The tearsheet response serves `limitations: []` or omits it. | FR-005 | The test asserts `limitations` equals FR-001's register, entry for entry. Control: the full response passes. |
| M7 | A Q document loses its banner line. | FR-008 | The guard fails, naming the file. Control: the bannered tree passes. |
| M8 | A Q document's Sharpe line loses its flag (`AUDIT.md:41`, number before the word). | FR-008 | The guard fails, naming file and line. Control: the flagged line passes. |
| M9 | A results view stops rendering the banner component. *Conditional on 047 D-1.* | FR-008 render test | The guard fails, naming the view. Control: all listed views pass. Without a runner, M9 is a known gap, not a kill. |

A kill counts only when the expected gate refuses with its own message. Mutants are applied in memory or
in a scratch copy, never committed to the module they mimic. Drivers live under `tests/mutation/` and
invoke pytest (`CLAUDE.md`, Tests).

## 7. Success criteria

- **SC-001**: every audit row has a disposition (§3) or an owner (§1), recorded in `plan.md`, with no row
  left unassigned.
- **SC-002**: FR-001 to FR-005 hold on every runtime surface in scope. A reviewer can trace each runtime
  figure to a source, a commit and a run date without leaving the surface.
- **SC-003**: M1–M8, M1b and M3b are killed, and M9 too if 047 D-1 adds a runner. Their controls
  pass. The full suite is no worse than a baseline recorded before the first code task.
- **SC-004**: the ledger is unchanged: `docs/trials/trials.jsonl` byte-identical before and after.
- **SC-005**: SCOPE-V1 DoD item 5 can be checked against this spec, except for the pinned panels, which
  are listed as open human-lane items.

## 8. Decisions

- **D-1 — Helper placement (open; Camden).** A new `scripts/disclosure.py`, or functions added to an
  existing module. A new module needs a row in `CLAUDE.md`'s module table. That is a governance edit,
  flagged here and not made. Proposed: the new module. It owns disclosure text and stamps, and must not
  know about signals, fills, sizing or P&L.
- **D-2 — Which PROJECT_CONTEXT figures are G (open; Camden).** The default is S for all of them.
  Regenerating any of them needs market data, which is a HUMAN GATE.
- **D-3 — CrossValidationView (open; Camden).** Either label the six folds `EXAMPLE — NOT A RESULT`, or
  serve the real fold configuration from `scripts/walk_forward_cv.py` through the API. Proposed: the label.
- **D-4 — Inline register or reference (open; Camden).** Rule 16 allows "inline or by an unmissable
  reference on the same surface". Proposed: inline on the web tearsheet and the README; a one-line
  reference on script panels and other views.
- **D-5 — Quotation versus Rule 11 for absent sources (open; Camden; flagged per `CLAUDE.md`).** Rule
  11 requires an X figure to be regenerated or removed before a PR touching its surface merges, and it
  names spec results sections. The 2026-10-03 decision marks audit/history documents as quotation.
  Choose one: (a) Q applies to X figures in audit/history documents as a reading of Rule 11 (a
  constitution amendment may be needed, which is a governance edit outside this lane); (b) X figures
  are struck even there, and Q covers only figures with a committed source; (c) X figures are moved
  into a quarantined quotation file that no live surface links as results. Until decided, X rows stay
  Q-pending-D-5 and closed-spec X figures default to S.

## 9. Sequencing

- **047 first.** 047 and 038 share `BacktestTearsheetView.tsx`, `routes/backtest.py`,
  `schemas.py` and `api.ts`. PR #42 recommends 047 first. 038's web units wait on 047's.
- **036 and 046.** 038 adopts their field names when they land first. If 038 lands first, they adopt
  FR-001's register and FR-002's stamp, and add no second copy.
- **033.** Do not run 038 and 033 Phases 8–9 on `routes/capital_gate.py` in the same window
  (`V1-FINISH-PLAN.md:164`).
- Markdown-only units (FR-006, the labels, the PROJECT_CONTEXT strikes) touch no code and can start
  once this spec merges.

## 10. Out of scope

- The three tearsheet correctness defects (047); the Rule 14 rename (035).
- Pinned 019 files. Their panels get human-lane tasks in `tasks.md`; the lane does not edit them.
- Paper-loop surfaces (049).
- Any edit to the constitution, `CLAUDE.md`, `docs/SCOPE-V1.md`, `docs/autonomy/`, `.github/` or
  `docs/trials/`.
- Producing new results. 038 reports nothing that it did not find already on the surface.
