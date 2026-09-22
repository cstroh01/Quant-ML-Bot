# Codebase audit and cleanup plan — 2026-09-18

## Expanded audit checkpoint

The follow-up request broadens this document beyond cleanup to a read-only codebase review. Only this Markdown file is edited during the expanded audit. The original cleanup findings C01–C12 and their evidence remain below; their exclusions describe that first pass, not this expanded pass.

**Current checkpoint:** the original expanded pass concluded; an additional read-only pass has saved **47 expanded findings (F01–F47) plus the 12 cleanup findings (C01–C12)** so far. Each completed batch is independently usable; no recovery work or resumption is required if the session stops. Unreviewed areas are coverage limits, never implied passes. No application, tests, build, dependency installer, broker operation or Git command was executed during these passes.

**Main conclusion:** the core has gained stronger funding, timing and provenance contracts, but its consumers and evidence workflows have not consistently migrated with them. The highest-priority findings concern safety-gate input/state transitions, broken execution/reporting integration, and incomplete trial/run provenance. Cosmetic cleanup can proceed independently, but cannot resolve these issues.

**Read next:** the final prioritization/coverage section at the end, then the referenced findings. The original cleanup ranking below applies only to C-items; it is not the priority order for the expanded audit.

**Evidence standard:** each new finding names the inspected code, concrete trigger/consequence, a proposed fix and acceptance evidence for future implementation. Static findings are not presented as reproduced runtime failures. Existing audit findings are rechecked against current files before being carried forward. Severity: P1 = materially misleading output, unreliable safety boundary or broken supported workflow; P2 = functional/reliability/maintenance issue; P3 = minor polish. This is source review, not certification or a claim of exhaustive defect discovery.

**Completed expanded batches:** A — reporting API/frontend (F01–F13); B — safety-gate state/reservations (F14–F20); C — registry, cache/data provenance and research integration (F21–F30); D — automation, validation and remaining numerical/report boundaries (F31–F37).

---

## Original cleanup pass

Status: COMPLETE for the static cleanup scope below. Twelve findings saved. No cleanup changes applied. Each item is independent; none requires continuing this session.

## Scope and guardrails

Organization, documentation navigation, redundant assets, dependency declarations, import plumbing, formatting and generated-file hygiene only. Quantitative correctness, machine learning behavior, tests and test configuration are excluded. No tests, application scripts, downloads, builds, installs or formatters are run. Application files are not changed. This is an audit, not an automatic cleanup campaign.

Benchmark: the repository's own documented layout and conventions, plus concrete maintenance criteria: one discoverable source of instructions, explicit ownership of generated artifacts, no unreferenced scaffolding, and consistent file/import conventions. No external standards or dependency currency claims are made.

The older `docs/audit-2026-09-12/AUDIT.md` remains the separate technical audit; this report does not change its conclusions or close its findings.

## Recommended order

Do the documentation and unused-scaffolding items first. Leave imports, file moves and shared-code extraction for a separate, validated change. A broad directory reshuffle or formatter sweep would create more review work than the current clutter justifies.

Scores use the tech-debt skill's `(impact + maintenance risk) × (6 − effort)`, each input on a 1–5 scale. These are subjective cleanup priorities, not financial or operational risk ratings. Time estimates are planning estimates, not measured results.

| Order | Finding | Impact / risk / effort | Score | Estimated effort |
|---|---|---|---|---|
| 1 | C02: root project map | 4 / 2 / 1 | 30 | 15–30 min |
| 2 | C01: frontend README | 3 / 2 / 1 | 25 | 15–30 min |
| 3 | C10: current versus historical notes | 4 / 2 / 2 | 24 | 30–60 min |
| 4 | C05: unused starter assets | 3 / 1 / 1 | 20 | 10–20 min |
| 5 | C11: escaped command Markdown | 2 / 2 / 1 | 20 | 5–10 min |
| 6 | C06: unused frontend dependency | 3 / 1 / 2 | 16 | 15–30 min |
| 7 | C04: line-ending comment | 1 / 1 / 1 | 10 | 2 min |
| 8 | C07: unused imports | 1 / 1 / 1 | 10 | 5 min |
| 9 | C08: duplicate plot outputs | 2 / 1 / 3 | 9 | 30–60 min |
| 10 | C09: scratch-script classification | 2 / 1 / 3 | 9 | 30–60 min |
| Deferred | C03: API path bootstrap | 3 / 3 / 3 | 18 | 1–2 hr plus validation |
| Deferred | C12: repeated HTTP helpers | 2 / 1 / 3 | 9 | 30–60 min plus validation |

C03's higher score does not override this audit's narrow scope: import behavior is a separate change.

## Findings

### C01 — Replace frontend template documentation (small, high value)

`reports/web/README.md:1` still describes the generic React/TypeScript/Vite starter. Replace it with this application's directory map, dependency installation, API/frontend launch commands, ports, and links to canonical project documentation. Validate commands against existing configuration, without running the application for this audit.

### C02 — Refresh the root project map (small, high value)

`README.md:4` calls the project Phase 0 while the same document lists a Phase 2 entry point at line 55; the filesystem now also contains the reporting API and frontend, trial registry and safety modules. `CLAUDE.md`'s module-responsibility table lists only four original modules. Update navigation and clearly label historical descriptions; do not rewrite strategy claims or quantitative results as part of cleanup.

### C03 — Consolidate duplicated API import bootstrap (deferred refactor)

Five modules mutate `sys.path`: `reports/api/main.py:15`, and routes `backtest.py:16`, `data.py:16`, `diagnostics.py:13`, `ml_rundown.py:21`. The copied `parents[2]` expression resolves correctly in `main.py`, but resolves to `reports/` inside the deeper routes directory, inserting the nonexistent `reports/scripts` path. Filesystem resolution is recorded in `checks.json`; runtime import failure was not tested. The main entry point's correct insertion can mask the route-local mistake.

Document the supported entry point now; consolidate path ownership in a separately validated change. Avoid a wholesale package migration as incidental cleanup. This finding concerns import plumbing only.

### C04 — Correct line-ending policy commentary (tiny)

`.gitattributes:2` claims Windows-native checkout endings, but line 3 specifies `* text=auto eol=lf`. Correct the comment to match the LF policy; avoid mass-renormalizing files as incidental cleanup.

### C05 — Remove unreferenced frontend starter files (small)

`reports/web/src/App.css` contains starter `.counter`, `.hero` and next-steps styles, but `src/main.tsx` imports only `index.css`; no application references to `App.css` were found. The following also have no references in inventoried application/configuration text: `src/assets/hero.png`, `src/assets/react.svg`, `src/assets/vite.svg`, and `public/icons.svg`. Search evidence is in `checks.json` (historical inventory mentions are not runtime references).

Remove these five files together after rechecking references at implementation time. Preserve `public/favicon.svg`, which `index.html:5` explicitly uses. Static absence of references is strong removal evidence here, not a universal proof against external consumers.

### C06 — Remove the apparently unused React Query dependency (small)

`reports/web/package.json:14` declares `@tanstack/react-query`. No references were found outside the manifest and lockfile; `src/App.tsx` uses local state/effects and `src/services/api.ts` uses native fetch. Remove the declaration and regenerate the lockfile together in a dedicated dependency cleanup. Do not introduce React Query just to justify its presence, and do not hand-edit the generated lockfile. No dependency installation or removal was performed here.

### C07 — Remove two unused Python imports (tiny)

AST name-use scanning found `statistics` in `reports/api/routes/backtest.py:5` and `Any` in `reports/api/schemas.py:5`. A text search confirmed each name occurs only at its import in that file. Remove `statistics` and remove only `Any` from the typing import, preserving `Literal`. The scan covered all inventoried application Python modules and found no other candidates under this simple rule. This is not whole-program dead-code analysis.

### C08 — Give generated plots one naming and retention policy (small, requires coordination)

SHA-256 comparison shows three exact duplicate pairs in `plots/`: `AAPL_acf.png` / `aapl_log_returns_acf.png`, `GOOGL_acf.png` / `googl_log_returns_acf.png`, and `MSFT_acf.png` / `msft_log_returns_acf.png`. Both naming schemes have active writers: `scripts/autocorrelation_check.py:42` and `scripts/stationarity_check.py:40`.

Deleting one set alone will recreate clutter on the next run. Decide whether these are retained evidence or disposable output; document that choice, then align output names/locations and references in a separate change. Preserve historical evidence. Do not alter calculation code or add a blanket image ignore rule. The bytes saved are minor; the benefit is removing ambiguous copies.

### C09 — Classify scratch scripts before relocating them (optional)

`scripts/scratch_aapl_correlations.py:1` and `scripts/scratch_multiticker_collinearity.py:1` describe one-off investigations and use a specifically named cache CSV. They share the same directory as maintained modules and runnable tools. Label them in the project map as historical investigations with their provenance and input requirements.

Do not infer that the word `scratch` means safe to delete: spec 018's plan and library-boundary contract explicitly reference the multiticker script. Relocation to a documented exploration/archive directory is optional and requires updating references and root-relative paths; classification alone is the low-risk first step. Their calculations were not evaluated.

### C10 — Separate current guidance from historical run records (medium)

`docs/PROJECT_CONTEXT.md` is 874 lines in this snapshot, combining current status near the top, earlier implementation notes, personal working instructions and an old `Housekeeping — Confirm First` block at line 791 describing a previous uncommitted state. `NIGHT_RUN_SUMMARY.md:1` is a dated spec 017 run report at the repository root. A reader has to infer which instructions and statuses are current.

Add a short current-status index and explicit historical labels first. Later, move run records under a dated documentation directory while updating incoming links. Spec 017 tasks and quickstart reference the root summary, so moving it silently would break traceability. Keep old audit outputs intact; the two root review logs total only 466 bytes and are not a worthwhile storage-cleanup target. Do not reinterpret old evidence as a current run.

### C11 — Repair escaped Markdown in the custom status command (tiny)

`.claude/commands/spec-status.md:1` begins with literal `\---`, its list uses escaped numbering and checkbox text, and lines contain literal `&#x20;`. These are export/escaping artifacts, unlike the ordinary Markdown used elsewhere. Restore plain delimiters, normal list numbering and indentation while preserving the command's intent. The escaped frontmatter is not a valid plain `---` delimiter; command-loader behavior was not exercised. Do not run this command during the cleanup audit because its instructions inspect tests.

### C12 — Consider a small shared HTTP request helper (optional, deferred)

`reports/web/src/services/api.ts:14` onward repeats fetch, status checking, error construction and JSON parsing across request wrappers. A private typed helper could centralize that mechanical pattern while leaving endpoint-specific parameters and public functions explicit. Keep response shapes, error messages and request behavior unchanged. This is a modest maintainability opportunity, not an observed functional defect; skip it unless this file is already being edited. No request orchestration or ML/UI logic refactor is proposed.

## Coverage and limits

- `inventory.json`: 231 files mechanically inventoried with byte lengths and SHA-256 hashes, spanning application code, frontend, specs, docs, agent support files, templates, manifests and plot assets. All 27 `scripts/` Python files and the inventoried API Python files were parsed for structural import/name checks. This is broad static coverage, not a claim that every line received semantic review.
- `checks.json`: reference-search results, path declarations/resolution, selected artifact metadata and final hash verification. All 231 inventoried files retained their recorded hashes at the final recheck. Audit artifacts themselves are excluded from that inventory.
- Focused manual review covered entry points/import plumbing, active documentation, frontend starter files and imports, manifests, generated-plot writers, scratch-script headers and selected agent tooling. Spec/template content was considered for organization and references only. No quant or ML conclusions were drawn.
- Excluded from substantive review: tests and test infrastructure, vendor environments, generated builds, cache/data contents, Git internals, local secrets/settings, logs and prior audit execution results. Some support/test-related manifests and historical evidence files appear in the mechanical inventory; that is not an audit of their behavior or results.
- An inline local Markdown-link check outside historical audit/spec directories found no missing file targets. It does not validate heading fragments, plain code-formatted paths, template placeholders or external links.
- Exact duplicate detection also grouped two empty files, `.claude/settings.json` and `docs/trials/trials.jsonl`. They have different roles and are not duplicate-removal candidates. Large source files alone were not promoted into refactor findings.
- No tests, builds, application execution, lint autofixes, dependency changes, source moves, deletions or network research were performed. Cleanup findings do not certify runtime correctness.

## Interruption-safe follow-through

The audit is finished; no run needs resuming. Future cleanup should take one numbered item at a time and record completion beside that item only after the change is finished. Start with documentation and unused scaffolding. Keep code/import/dependency changes separate from file moves, preserve evidence and runtime state, and stop between items whenever usage runs low.

For repeated hygiene work, a small read-only local script can emit duplicate hashes, asset-reference candidates and a documentation-link report. Keep it advisory, with exclusions for tests, generated output, dependencies and historical evidence. No new CI gate or automatic deletion is warranted for this optional work. Such automation was not installed in this audit.

Process note: `git status --short` and `git ls-files` were run read-only before the repository's no-local-Git instruction was discovered. No further Git commands are used; no version-control mutation occurred.

---

## Expanded findings — batch A: reporting and frontend

All findings in this batch are based on current source inspection, not execution. The earlier audit's similar findings are background, not proof of present behavior.

### F01 — P1: tearsheet route has not migrated to the funded execution contract

**Evidence:** `reports/api/routes/backtest.py:45–83`, `scripts/backtest_harness.py:35–71`, `scripts/ma_crossover_backtest.py:71`. The route reads ordinary CSVs, constructs a frame without verified price provenance, calls `run_backtest` without `starting_capital`, and calls `baseline_results` without its required `starting_capital` and `liquidate` arguments. The harness now rejects undeclared prices and missing capital. Fixing only the first rejection exposes the next incompatible call. There is no exception-to-unavailable translation in this route.

**Plan:** migrate the whole route to the validated unadjusted loader, explicit funding and end-of-data policy; return an honest unavailable response when the execution dataset is missing. Never label legacy adjusted CSVs unadjusted just to bypass validation. **Acceptance:** a verified synthetic bundle produces the complete response; a legacy/unavailable bundle returns a documented 4xx/503 response, not an uncaught exception. This is an integration defect, not a defect in the harness's refusal.

### F02 — P2: HTTP input contracts stop at primitive types

**Evidence:** tearsheet query declarations at `reports/api/routes/backtest.py:36–42` have no bounds or cross-field validation for windows, costs or slippage; ticker parameters across routes accept arbitrary strings. `scripts/signals.py:7` and the execution layer can reject values, but routes do not map those failures to client errors.

**Plan:** establish supported ticker syntax, finite cost domains, positive integer window bounds and `short < long` at the API boundary. Bound requests before expensive work. **Acceptance:** invalid values receive field-specific 422/400 responses without starting data analysis; valid boundary values retain their meaning. Do not conflate this with F01's migration work.

### F03 — P1: reporting data selection is ambiguous and bypasses the new manifest boundary

**Evidence:** `reports/api/routes/data.py:36–68` prioritizes hard-coded legacy filenames and then the first matching CSV yielded by a directory scan. Preferred-file parsing is outside the fallback's exception handling. There is no dataset ID, explicit freshness requirement or unadjusted manifest validation. `list_available_tickers:71–85` advertises five hard-coded tickers even when none can be loaded.

**Plan:** use one explicit dataset resolver with stable selection, metadata and failure reasons; return the actual available universe. Treat corruption as corruption, not a reason to silently substitute a different snapshot. **Acceptance:** multiple snapshots, a corrupt preferred file and an empty directory each produce deterministic, truthful responses. Preserve adjusted research versus executable data distinctions.

### F04 — P2: ticker-derived cache path is not contained

**Evidence:** `reports/api/routes/data.py:42–48` inserts user-controlled `ticker` into `f"{ticker}_2y.csv"` and joins it to `cache_dir` without a containment check. `ticker.upper()` does not remove path separators or traversal components. A suitable file outside the cache can be selected if the constructed filename exists; ordinary endpoint response schemas limit what is returned, so this is not a demonstrated arbitrary-file disclosure exploit.

**Plan:** validate ticker syntax and resolve/contain every candidate under the intended dataset directory; preferably remove filename construction from HTTP parameters entirely. **Acceptance:** traversal, absolute paths and platform separators are rejected before file reads; legitimate symbols work. No exploit was attempted.

### F05 — P2: nonfinite diagnostics have no wire representation

**Evidence:** `scripts/feature_diagnostics.py:87–110` has no explicit singular/undefined result variant: condition numbers can be nonfinite, while constant-column correlations can make the pseudoinverse fail before serialization. `reports/api/routes/diagnostics.py:53–80` casts/rounds successful results into plain float schema fields without a nonfinite policy. `reports/api/routes/data.py:118–154` similarly forwards skewness/kurtosis without checking finite values after calculation. Degenerate inputs can therefore produce calculation errors, invalid/nonportable JSON or serialization errors rather than meaningful diagnostics. Exact framework behavior was not exercised. F36 addresses a separate mathematical defect in the finite VIF values.

**Plan:** represent undefined/infinite statistics explicitly with a nullable value plus status/reason, preserving the distinction from zero. **Acceptance:** constant prices, constant features, duplicate features and insufficient samples serialize successfully into documented unavailable/singular states and render clearly.

### F06 — P1: older requests can overwrite the newly selected ticker

**Evidence:** `reports/web/src/App.tsx:92–117` starts a request group on ticker/parameter changes and unconditionally writes all resolved values. The effect has neither cancellation nor a generation/key check. If selection A resolves after B, A's data replaces B's while the header still shows B. An old completion can also clear the current loading flag.

**Plan:** key responses by ticker plus parameters and commit only the current request; cancel abandoned fetches where supported. **Acceptance:** deliberately reordered A/B responses cannot render A beneath B's heading, including rapid parameter changes and component cleanup.

### F07 — P2: failures render as indefinite loading, and unrelated requests share one state

**Evidence:** `App.tsx:95–107` converts failures to empty arrays/null without retaining error details. `BacktestTearsheetView.tsx:78`, `MarketDataView.tsx:30`, `FeatureDiagnosticsView.tsx:19`, and `CapitalGateView.tsx:25` use `loading || !payload` for loading presentation. Capital-gate fetching runs separately from the ticker request group but is presented using the group's loading flag.

**Plan:** give each resource explicit loading/success/empty/unavailable/error states and request identity. Display reasons and a retry action; fetch resources according to their own dependencies. **Acceptance:** failed, empty and not-computed responses settle into distinct stable views; a slow ticker request does not obscure an already fetched gate status.

### F08 — P2: displayed durations, costs and missing values are not faithful to data

**Evidence:** `reports/api/routes/backtest.py:159–169` emits `holding_bars=1` for every trade; `BacktestTearsheetView.tsx:92–93` labels a commissions-only calculation as friction drag while explanatory text includes slippage; line 143 turns unknown drawdown into `0.00%`. `FeatureDiagnosticsView.tsx:178` substitutes zero for a missing correlation entry. The random baseline route also substitutes zero summaries when the helper returns no random results and does not expose `random_error`.

**Plan:** derive durations from session positions, expose actual cost components, and represent missing/unavailable values without numeric defaults. Pass through random-baseline failure reasons. **Acceptance:** a multibar trade has its actual duration, nonzero slippage appears in cost attribution, and unavailable drawdown/correlation/baselines never appear as measured zero.

### F09 — P2: API schema truncates fractional holdings and chart drawdown omits initial capital

**Evidence:** `scripts/backtest_harness.py:110–114` multiplies quantity by a split ratio, permitting fractional holdings; `reports/api/routes/backtest.py:149` casts curve positions to `int`, and `reports/api/schemas.py` declares `EquityPoint.position: int`. The route computes `curve['Equity'].cummax()` without the pre-trade capital anchor that `scripts/metrics.py` explicitly preserves. After F01 is repaired, split positions can be misrepresented and first-session losses understated in chart drawdown.

**Plan:** preserve the execution quantity type end to end and obtain drawdown from the same anchored metric convention as the summary. **Acceptance:** a fractional reverse-split position retains its quantity; a first-bar fee loss appears identically in chart and summary drawdowns. These are downstream integration findings, not grounds to round execution quantities silently.

### F10 — P2: gate tutoring contradicts the actual gates and current rules

**Evidence:** `CapitalGateView.tsx:72` explains a different five-gate sequence from `reports/api/routes/capital_gate.py:25–61`. The latter still describes fixed 5 bps as realistic costs and positive DSR as the threshold, while Constitution Rules 13 and 15 prescribe different reporting requirements. `BacktestTearsheetView.tsx:170` embeds default cost assumptions despite adjustable parameters.

**Plan:** derive explanations from one versioned definition and render actual run assumptions. Keep all unsupported gate states unknown. **Acceptance:** each gate number/title/explanation agrees with its source definition; changing costs cannot leave default-cost tutoring beside the result. This checks internal consistency, not external endorsement of the chosen statistical policy.

### F11 — P2: chart controls lose viewport state and miss container-only resizing

**Evidence:** `CandlestickChart.tsx:66–213` recreates the chart for overlay, palette and data changes and calls `fitContent()` each time; selected timeframe state is applied only by the click handler at line 216 onward. The highlight can stay on `1Y` while the chart returns to the full range. All three chart components listen to window resize rather than container resize, while the ML pane can change available width without resizing the window.

**Plan:** preserve/apply the selected viewport after updates and observe container dimensions. Prefer updating series/options over reconstructing the whole chart where practical. **Acceptance:** overlay/palette changes retain the selected range, and opening/closing the side pane resizes charts without a browser-window resize.

### F12 — P2: shortcut modal has incomplete dismissal and keyboard behavior

**Evidence:** `KeyboardShortcutsModal.tsx:26–56` promises outside-click dismissal but attaches no backdrop click handler. It provides no dialog semantics, focus trap/restoration or accessible name on the icon-only close button. `App.tsx`'s global shortcut listener remains active while the modal is open.

**Plan:** implement the promised dismissal, dialog labeling and focus lifecycle; restrict background shortcuts while modal interaction owns focus. **Acceptance:** keyboard-only opening, cycling, Escape and closing restore focus correctly, outside click dismisses, and the underlying tab does not change while using the dialog. Browser verification remains future work.

### F13 — P2 locally / P1 before exposure: API access policy is broader than its localhost intent

**Evidence:** `reports/api/main.py:47–54` allows wildcard origins, methods and headers with credentials; routes expose dataset/report reads without authentication. The bundled launcher binds to `127.0.0.1`, limiting direct network exposure, but the application itself does not enforce a deployment access boundary. The expensive tearsheet is a GET and recomputes multiple runs on each request.

**Plan:** retain local binding and explicit local origins; require an explicit authenticated/rate-limited deployment design before exposing the service. Cache or bound costly computation under a run identity. **Acceptance:** an unapproved origin cannot read the API through a browser; any remote deployment has access controls and a bounded computation policy. No claim of remote compromise or credential leakage is made.

## Expanded findings — batch B: safety-gate boundaries

The gate is a standalone decision engine with durable SQLite transactions, not an installed broker adapter. The following are blockers to relying on this engine as an independent safety authority; they do not establish that any real order was placed. Examples are hypothetical counterexamples derived from branches, not measured trading results.

### F14 — P1: nonfinite position quantities can turn limit checks into ALLOW

**Evidence:** `scripts/live_safety_gate.py:287–313` validates snapshot time, status, equity type and cash-flow value, but not the `positions` mapping. `_check_freshness:668–678` checks equity, not quantities. `_worst_case_exposure:680–708` converts position quantities to float and accumulates notionals; the cap checks at lines 653–661 use `>=` without first checking finite exposure. A NaN position makes the relevant notional/gross comparisons false, allowing execution to reach reservation. A negative order can also reach the reduce-only branch with a NaN current position because `new_qty < 0` is false.

**Plan:** validate every position's key, finite quantity and supported sign before any decision; validate the final exposure arithmetic as finite independently. Copy or otherwise freeze snapshot mappings to prevent mutation after validation. **Acceptance:** NaN, infinity, invalid types, negative holdings under the long-only contract and overflow cannot produce ALLOW; evidence names the invalid input.

### F15 — P1: signed pending-order netting is not worst-case exposure

**Evidence:** `_read_pending:503–508` sums signed quantities. `_worst_case_exposure` adds that signed sum to confirmed holdings. A pending sell therefore frees capacity for a buy before the sell fills. Separately, the reduce-only check at `live_safety_gate.py:618–645` compares only the candidate with confirmed holdings, ignoring already reserved reductions. Two individually permitted sells can collectively exceed the position. SQLite serialization prevents a database race but does not correct this calculation.

**Plan:** model adverse fill order: pending reductions must not grant new buying capacity; reserve sellable quantity separately or require independently enforced broker reduce-only semantics. **Acceptance:** with ten confirmed shares, two outstanding sells of six cannot both receive unrestricted permission; a pending sell cannot make an otherwise over-limit buy permissible. Include partial fills and canceled reductions.

### F16 — P1: account observations are neither ordered nor idempotent

**Evidence:** `_observe_equity_locked:760–844` stores session/date and equity, but no accepted observation ID or timestamp. Any different session, including an older one, takes the session-rollover branch. Every call subtracts `external_cash_flow` again; `evaluate_order` calls this observation path for every candidate. Reusing one fresh broker snapshot for multiple orders can therefore count its deposit/withdrawal repeatedly. Timestamp freshness alone does not enforce monotonic sequence or single application of a cash-flow event.

**Plan:** persist a broker observation/event identity and monotonic ordering rule; deduplicate cash flows and consume each observation once. Reject or explicitly reconcile older observations without resetting anchors. **Acceptance:** replaying the same deposit/withdrawal snapshot is a no-op, multiple intents against one snapshot do not change adjusted equity, and out-of-order snapshots cannot move the active session backwards or remove a daily halt.

### F17 — P1: simultaneous kill and rolling halts cannot be reset through the public API

**Evidence:** `reset_kill:913–962` rejects while `rolling_halt_active`; `reset_rolling_halt:966–1020` rejects while `kill_latched`. Once both are active, even a fully reconciled recovered account has no first permitted reset. `adopt_new_config` rejects both states as well. This is a recovery deadlock, not permission to bypass either safeguard.

**Plan:** define an auditable reset order or an atomic recovery operation that preserves the remaining protection while clearing only the validated condition. **Acceptance:** from both latches active, recovery succeeds through documented operator calls after all evidence requirements are met; neither latch can be cleared merely by restart or database manipulation.

### F18 — P1: configuration consistency is enforced unevenly across mutating methods

**Evidence:** `evaluate_order:585–590` rejects durable-versus-instance config mismatch. `observe_equity:732–758` and reset paths call `_observe_equity_locked` using `self._config` without that comparison. A long-lived process can continue updating persistent halt calculations with stale thresholds after another process adopts new config. `adopt_new_config:1073–1082` also omits the daily-halt check despite its docstring promising refusal during any halt. Changing timezone mid-session is permitted without migrating stored session anchors.

**Plan:** check config generation inside every state-changing transaction, reject adoption during an active daily halt, and define explicit migration rules for session/window changes. **Acceptance:** two processes cannot mix old calculations with new durable config; active daily protection cannot be bypassed by adopting a new timezone or limits. Distinguish safe config migration from ordinary runtime updates.

### F19 — P1: releasing reservations is not tied to a reconciled position snapshot

**Evidence:** `record_order_outcome:1102–1135` removes a reservation from exposure accounting based on `terminal` and an arbitrary reason. It carries no outcome kind, filled quantity, broker sequence or reconciled position version. A buy can be marked terminal/filled, then another candidate evaluated against a still-fresh pre-fill snapshot after the reservation stops counting. A fully filled order is terminal but its exposure still exists. The adapter is expected to reconcile, yet that prerequisite is not expressible/enforced by the gate's API.

**Plan:** tie fill/release and position acknowledgment to a durable broker sequence or transactional reconciliation record. Distinguish filled, canceled-unfilled and uncertain outcomes. **Acceptance:** a filled order remains counted until an accepted position snapshot includes it; older snapshots cannot be used after release; duplicated/out-of-order outcome updates are idempotent.

### F20 — P2: safety persistence and operator APIs need explicit deployment contracts

**Evidence:** `SafetyGate.__init__:401–410` creates one default SQLite connection, while the class docstring promises serialization across threads as well as processes; the connection's default thread affinity is not overridden or documented. Operator APIs accept an arbitrary nonempty `operator` string rather than authenticated identity, and `BrokerKillQuery`/`record_order_outcome` do not enforce exact booleans at runtime. These are integration assumptions, not proof that external authentication is absent from a future adapter.

**Plan:** document one gate/connection per owning thread or implement a supported concurrency wrapper; require authenticated adapter context and validated broker response types at the boundary. **Acceptance:** supported thread/process usage is explicit; malformed truthy values cannot confirm broker state, and recording an operator's name is never treated as authentication. Do not add broker credentials to this module.

## Expanded findings — batch C: provenance, storage and research integration

### F21 — P1: registry source-revision defaults are incorrect and dirty state is fabricated

**Evidence:** `scripts/trial_registry.py:105–120` returns `False` on every path in `_read_git_dirty`, including paths where no repository was found. `_normalize_record:175–183` resolves the repository as `path.resolve().parents[1]`; for the default `docs/trials/trials.jsonl`, that is `docs/`, not the repository root. Automatic commit discovery therefore fails for the default path, while caller-supplied commits can be paired with an unjustified clean-state claim.

**Plan:** require explicit verified revision/worktree provenance or discover the repository root correctly through an approved metadata mechanism; represent unknown dirty state honestly rather than False. Respect the local no-Git-command rule. **Acceptance:** the default path works under its documented contract, custom registry locations do not change revision identity, and modified/unknown source cannot be recorded as verified clean.

### F22 — P1: `validate_for_gate` verifies presence rather than trustworthy return evidence

**Evidence:** `trial_registry.py:131–150` accepts a truthy return path/hash plus nonempty frequency/convention. It does not require funded returns, validate hash syntax, read/re-hash the artifact or check its sampling/content. `_normalize_record:283–302` accepts a supplied hash without checking the file, and accepts numeric conversion of nonfinite comparable Sharpe values. `_canonical_json:54–55` permits Python's nonstandard NaN/Infinity output. `verify_chain` checks metadata-chain consistency, not the underlying artifact.

**Plan:** separate basic record ingestion from strict gate validation. Resolve paths under an explicit artifact root; verify actual bytes and return schema, finite numeric fields, funding/cost provenance and dataset identity before eligibility. **Acceptance:** missing files, changed bytes, bogus hashes, NaN values and unfunded series cannot pass an eligibility check. A valid metadata hash chain alone must not confer eligibility.

### F23 — P1: complete trial history is neither captured nor representable for failed runs

**Evidence:** a source-reference search finds no production caller of `log_trial` outside its definition. `_normalize_record:307–311` requires successful gate provenance for every record, even though `ALLOWED_OUTCOMES` includes abandoned/rejected/exploratory. A failed candidate with no OOS artifact cannot be logged under that contract. Spec 033 explicitly describes this migration as upcoming work; the existence of the module is not evidence of complete search accounting.

**Plan:** record trial intent before evaluation and terminal outcome afterward, including failed/canceled candidates with reasons and nullable artifacts. Make gate eligibility a later independent decision. Integrate all production search paths and document unrecoverable pre-ledger history. **Acceptance:** failure before the first prediction still leaves a traceable trial; repeated candidates and each searched configuration are accounted for without pretending missing return evidence exists.

### F24 — P1: registry append operations lack concurrency and durable-tail protection

**Evidence:** `trial_registry.py:391–403` verifies, reads/normalizes, then appends without a lock or transaction. Two writers can use the same predecessor and append incompatible chain links. There is no explicit fsync/recovery policy for a torn last line. `verify_chain:367–388` accepts a valid prefix, including an empty file, so suffix deletion is undetectable without a separately trusted last-record/count anchor. Duplicate caller-supplied trial IDs are not rejected.

**Plan:** serialize append operations, validate uniqueness, flush durably according to the chosen persistence contract, and define detectable/recoverable tail failure. Preserve a trusted checkpoint of the committed chain head/count if completeness claims depend on it. **Acceptance:** concurrent append stress preserves one ordered chain; interrupted writes fail clearly without silent record loss; suffix truncation and reused IDs are detected. A plain chain is tamper-evident only relative to a trusted anchor.

### F25 — P1: cache publication can mix concurrent snapshots and their provenance

**Evidence:** `scripts/data.py:362–371` uses a fixed `.csv.tmp` sibling. `cache_unadjusted_market_data:887–921` overwrites data and action members separately, hashes the files on disk afterward and publishes a manifest last. Another writer can replace a member between write and hash, producing a manifest whose source metadata belongs to writer A but whose bytes came from B. Even without concurrency, interruption can invalidate the prior bundle because its referenced members were overwritten. The docstring acknowledges fail-closed invalidation, so this is an availability/provenance improvement, not a claim of silent acceptance on every interrupted write.

**Plan:** publish immutable generation-specific members using unique temporary files, hash the exact payload being published, and atomically switch the manifest/pointer only after the whole generation validates. **Acceptance:** concurrent refreshes cannot cross-bind provenance; readers see either the prior complete generation or the next complete generation, and abandoned temporary generations can be identified safely.

### F26 — P2: adjusted-data validation and requested coverage remain weaker than manifest validation

**Evidence:** `download_market_data:396–444` accepts cache hits by ticker presence, loops over the original ticker list even though only the filename is deduplicated, and does not apply finite/OHLC/unique-session checks in `_tidy`. Duplicate requested symbols can duplicate rows; all-NaN ticker blocks can still be cached. The unadjusted validator checks completeness only between actual first/last rows (`data.py:568–578`); the publisher does not compare received coverage with the requested `start/end`. `find_missing_bars` also intentionally measures internal gaps, not freshness.

**Plan:** canonicalize ticker requests before downloading; validate adjusted research frames on both read and write; separately record requested versus actual coverage and expected latest session. Preserve legitimate listing/delisting limits as explicit metadata. **Acceptance:** duplicates/bad OHLC are rejected, and a contiguous but truncated provider response cannot be mistaken for a complete requested/current dataset.

### F27 — P1: command-line research/backtest integration is only partially migrated

**Evidence:** `scripts/ma_crossover_backtest.py:207` and `scripts/logistic_baseline.py:312` still source `download_market_data`, which now marks output `research_adjusted`; both reach the funded harness. Their explicit funding updates do not make adjusted prices executable. `scripts/multi_ticker_comparison.py:231–265` additionally omits starting capital entirely. Its `main:360–390` checks a combined-universe cache but individual runs request single-ticker caches, catches failures per ticker, writes even an empty results frame and returns without a failure exit code.

**Plan:** migrate supported execution entry points to verified input bundles and explicit policies together; reuse one selected snapshot across ticker slices; emit a structured run status and nonzero exit for total failure. **Acceptance:** documented CLI paths either complete from supplied verified data or stop with an actionable unavailable status; all-ticker failure cannot look like a successful batch to a scheduler. Do not weaken the harness to keep legacy commands running.

### F28 — P2: exact one-sided classification comparison uses an incorrect discrete tail

**Evidence:** `scripts/feature_set_comparison.py:398–400` derives the unfavorable direction as `1 - two_sided/2`. For an exact discrete test, complementing a tail this way omits the observed probability mass. EXAMPLE — NOT A RESULT: zero B-only wins and two A-only wins produce a two-sided value of 0.5 and this code returns 0.75, although the B-better tail is `P(X >= 0) = 1`. Equal discordance counts also expose the issue.

**Plan:** compute the intended one-sided exact binomial tail directly with the direction explicitly stated. **Acceptance:** enumerate small discordance tables, ties and both directions against the exact summed binomial probabilities. Separately assess temporal dependence before interpreting any paired-test output as research evidence; that inferential question was not independently resolved here.

### F29 — P1 for reported results: governance requirements exceed implemented evidence pathways

**Evidence:** Constitution Rules 13–15 now require a richer cost model, independent corporate-action verification and DSR-gated/provisionally labeled reporting. `backtest_harness.py` still implements constant-bps fills; `metrics.performance_summary` returns a descriptive Sharpe without DSR status. The provisional yfinance adapter correctly declares itself ineligible and rejects missing payment dates; no implemented second-source cross-check or operational DSR evaluator was found among inventoried application modules. Spec 033 is planning, not an operational evaluator.

**Plan:** explicitly distinguish implemented research primitives from eligible report generation. Until the prescribed evidence exists, make reporting eligibility/provisional status visible on each applicable surface. Implement each required evidence pathway under its own reviewed spec rather than merely changing labels to imply completion. **Acceptance:** reports cannot claim compliance based on a manifest hash, fixed-cost parameter or spec file alone. This is a gap against local rules, not a claim that those rules themselves establish profitability.

### F30 — P2: research artifacts do not retain enough run identity for reproducible comparisons

**Evidence:** `feature_set_comparison._checkpoint:856–903` overwrites a fixed checkpoint path and fixed temporary sibling with only the result list; concurrent runs can collide. `model_cv.nested_walk_forward:495–530` reduces detailed inner scores to winning parameters and summary counts, then discards the full candidate table. `multi_ticker_comparison` writes an output named only by ticker universe, omitting period/model/settings/run status from identity.

**Plan:** use immutable run IDs and a manifest containing input hashes, configuration, environment/revision, candidate scores, failures and completion state. Keep a separate explicit pointer for the latest successful run. **Acceptance:** two runs with different settings coexist, an interrupted run is distinguishable from a completed one, and each reported comparison can reconstruct which candidates and rows it used without rerunning expensive training.

## Expanded findings — batch D: tooling and remaining validation boundaries

### F31 — P2: local test hook contradicts both runner and Git policy

**Evidence:** `.claude/hooks/run-tests.ps1:1–2` runs `git rev-parse`, invokes unittest discovery instead of the canonical pytest command and prints only the last five output lines. It does not explicitly propagate the native runner exit code. By contrast `.github/workflows/test.yml` installs development dependencies and invokes `python -m pytest tests`; its frontend job runs install/lint/build.

**Plan:** locate the root using a filesystem marker or the hook's own location, use the canonical runner and preserve diagnostic output plus failure status. **Acceptance:** the hook discovers parametrized/function tests, visibly reports failures and returns a failing process status; it performs no prohibited Git call. No hook was invoked in this audit.

### F32 — P2: automation privileges need verification beyond natural-language rules

**Evidence:** `.github/workflows/claude.yml:14–25` triggers on text mentioning the agent and grants repository/PR/issue write and OIDC permissions; action references are version tags. The workflow has no explicit actor/association condition of its own. The action may apply its own authorization checks, and remote branch protections were not inspected, so this is a control-verification gap rather than a demonstrated unauthorized-write vulnerability.

**Plan:** document the actual trigger authorization and allowed branch/ref, minimize permissions per job and verify protected-branch enforcement independently of instructions in Markdown. Assess immutable action pins under the project's maintenance policy. **Acceptance:** an untrusted trigger cannot acquire an authorized agent run or write path; the permitted lane cannot write to protected branches. No remote settings or action internals were reviewed here, so exploitability remains unestablished.

### F33 — P2: tasks-to-issues deduplication conflates separate specs

**Evidence:** `.claude/skills/speckit-taskstoissues/SKILL.md:71–75` matches repository-wide issue titles using only `T001`-style IDs, then skips a task if that ID occurs anywhere. Each spec starts its own task numbering. An existing task from one feature can suppress creation for an unrelated feature. The same instructions call local Git despite repository governance.

**Plan:** use a canonical compound identity such as spec ID plus task ID in a machine-readable issue marker and scope deduplication to that identity. Obtain repository identity through the approved lane. **Acceptance:** repeated invocation is idempotent within one spec, while two specs' T001 tasks produce distinct issues. Do not run issue creation as part of this audit.

### F34 — P2: existing checks need boundary-specific cases, not just stronger success assertions

**Evidence:** `tests/api_fixtures.py` marks an in-memory panel unadjusted, then serializes it to CSV; that operation does not preserve DataFrame attrs or create a verified manifest. `tests/test_reports_api.py:104` still expects a successful tearsheet from this old fixture path. `test_live_safety_gate.py:358` verifies releasing a canceled order but does not establish safe release of a filled order against a lagging position snapshot. `test_trial_registry.py:162` deletes a middle record, which does not demonstrate detecting removed tail records.

**Plan:** migrate execution fixtures through the real validated source boundary and add discriminating cases for F14–F19/F24. Retain paired positive controls, per Constitution Rule 12. **Acceptance:** each new guard is observed rejecting the realistic defect it claims to catch, and its control succeeds. Static test inspection is not a test run; this audit does not assert a current failure count or that these are the only missing cases.

### F35 — P2: reusable CV splitter accepts invalid purge/embargo domains

**Evidence:** `scripts/walk_forward_cv.py:54–73` checks only positive month sizes and `embargo_bars >= label_horizon`; it does not enforce integer nonnegative/positive domains or unique session labels. In the split loop, a nonpositive horizon bypasses purging entirely, and a negative embargo produces a reversed/empty exclusion interval. A direct caller can supply both values negative and satisfy the sole comparison. Model wrappers constrain availability spans when attrs exist, but that does not validate this public helper's own inputs.

**Plan:** establish exact integer domains, reject booleans and invalid horizons, and require one ordered unique observation per declared session contract. **Acceptance:** negative, fractional, boolean and duplicate-session cases fail before yielding a split; legitimate existing configurations retain their folds. This finding does not claim current main callers use those invalid arguments.

### F36 — P1 for diagnostic interpretation: pseudoinverse diagonal is not valid singular-matrix VIF

**Evidence:** `scripts/feature_diagnostics.py:92–110` computes `diag(pinv(correlation))` and claims singular redundancy produces reassuringly large finite values. EXAMPLE — NOT A RESULT: for two identical standardized columns the correlation matrix is all ones; its pseudoinverse is all 0.25, so this code reports VIF 0.25 for perfect collinearity. That contradicts the function's own `1/(1-R²)` definition, where `R²=1` is singular. `scripts/scratch_multiticker_collinearity.py:112` still has a duplicate implementation requiring the same review.

**Plan:** compute VIF using a method that explicitly classifies exact dependence and constant predictors; propagate undefined/infinite status through the API contract from F05. **Acceptance:** independent, duplicated and constant columns have mathematically appropriate distinct outcomes verified against an independent regression-based reference. This current source recheck confirms older audit finding 35 remains relevant; it is not being inferred merely from its historical listing.

### F37 — P2: exported trade tables are insufficient to reconstruct funded results

**Evidence:** `scripts/backtest_harness.py:146–152` stores the event ledger, capital and cost/end policy in DataFrame attrs. `metrics.equity_curve:76` requires that funded ledger. CLI writers such as `scripts/logistic_baseline.py:331` export only `trade_log.to_csv(...)`; attrs, open-position marks, receivables and rejected orders are not preserved by that export. A closed-trade CSV is useful as a view, but it is not a complete durable run artifact.

**Plan:** persist ledger events and metadata alongside derived trade views under the immutable run identity from F30, with input hashes and a versioned schema. **Acceptance:** loading a saved funded run without rerunning the strategy reproduces equity and open positions; a trade-only CSV is explicitly labeled incomplete and never relabeled as a funded ledger.

## Prioritized implementation plan — planning only

No item below was implemented. Scope one reviewable change at a time; do not combine a directory cleanup with contract changes. Existing specs are inputs to planning, not evidence that a task is complete.

| Order | Work package | Findings | Why this order / completion boundary |
|---|---|---|---|
| 1, before any reliance on the live gate | Validate positions; correct pending exposure/reduction reservations; version account observations and reconciliation | F14–F16, F19 | These can admit an unsafe decision even though the database transaction succeeds. Complete with adversarial fill-order/replay cases and positive controls. |
| 2, same safety milestone | Resolve combined halt recovery, config consistency and integration contracts | F17–F18, F20 | Persistence must preserve both protection and a documented recovery route. No broker adapter should rely on the engine before these boundaries are demonstrated. |
| 3, restore supported workflows | Migrate API/CLI consumers and fixtures to verified funded input; preserve response quantities and initial-capital metrics | F01–F04, F09, F27, F34 | Use spec 021's existing migration planning where applicable. Its frozen-file boundaries mean comparison runners need their own explicitly scoped follow-up, not incidental edits under 021. |
| 4, make visible output honest | Separate request identity and resource states; fix display attribution, diagnostics and gate definitions | F05–F08, F10, F36 | A working endpoint is insufficient if the UI displays stale, undefined or mislabeled evidence. Finish with reproducible reordered/error/singular-input scenarios. |
| 5, make experiments traceable | Correct registry metadata, capture all trials, serialize appends and persist full immutable run artifacts | F21–F24, F30, F37 | Coordinate with draft spec 033; do not create another competing registry. Keep record completeness separate from statistical eligibility. |
| 6, strengthen repeatability | Publish whole cache generations, validate requested coverage, correct exact-tail math and CV parameter boundaries | F25–F26, F28, F35 | Complete with concurrency/interruption and small independent arithmetic cases; no need for an expensive historical model rerun just to verify boundaries. |
| Before governed result publication | Reconcile reporting eligibility with current cost, corporate-action and DSR requirements | F29 | This is a release/reporting constraint, not a request to upgrade model complexity. Planning files alone do not satisfy it. |
| Independent low-risk work | Improve charts/modal, hooks, issue identity, documentation and unused scaffolding | F11–F12, F31, F33, C-items | Small changes can stop independently. Keep import/dependency changes separately reviewable. |
| Before remote/automated exposure | Verify API and agent-workflow access controls | F13, F32 | Remote state and third-party action behavior were outside this local audit. Verification is required before making security assurances. |

### Improvements confirmed in current source, without claiming runtime closure

- The execution harness now requires explicit starting capital and declared unadjusted dollars, rejects nonfinite/nonpositive prices and conflicting/nonboolean order flags, tracks cash/quantity/receivables and records ledger events. The old audit's description of a wholly unfunded harness is no longer a current source description.
- `cost_utils.validate_costs` now rejects nonfinite costs and invalid slippage ranges. Risk-free conversion uses `log1p` consistently in the inspected metric path. This does not supply the richer cost model required by newer rules.
- Targets now use next-open entry/exit endpoints and mask invalid endpoints/action-spanning outcomes. Feature construction retains input sessions and defines training/inference eligibility; inspected model loops mask after constructing calendar splits. These changes address major mechanisms described in the older audit, but this pass did not rerun causal/timing tests.
- Significance/model forecasts are explicitly not computed and capital gates remain unknown without evidence. The schema requires an evidence reference for a known gate state. This is meaningful harm containment; it is not an implemented experiment store or eligibility evaluator.
- API test setup isolates local cache access, and CI now declares the development dependencies, canonical pytest runner and a frontend install/lint/build job. Static CI inspection does not establish that current jobs pass.
- `create-new-feature.sh:200` now targets `.specify/specs`, so older audit finding 65's path mismatch should not simply be copied forward as unchanged. Other tooling problems are separately recorded above.

These observations update the historical picture without declaring any entire historical finding closed. The original September 12 report and its run outputs were not edited or rerun.

### Coverage, method and confidence

**Mechanical coverage:** a fresh expanded-pass SHA-256 baseline covered 270 files outside the sole writable audit file. It excluded Git internals, data contents, dependency environments, generated builds, tool caches, local settings/secrets and log files. The same inventory was recomputed at the end: **no changed/deleted inventoried files and no added files within that scan scope**. The two JSON evidence files from the cleanup pass were not updated. The expanded pass's additional coverage/evidence is recorded here, not silently attributed to those older JSON files.

**Python syntax inspection:** stdlib AST parsing succeeded for 27 `scripts/` files, 9 reporting API files and 37 files under `tests/`. That is 73 parsed files, not 73 passed tests. No repository module was imported or executed for this check. The frontend source inventory contains 18 TypeScript/TSX files; references and selected implementations were inspected, but TypeScript compilation was not run.

**Deeper manual coverage:** funded execution/metric interfaces and event handling; data/cache loader, manifest validation and publisher boundaries; target/feature alignment and selected estimator/CV/search loops; trial registry normalization/validation/append; safety gate admission, reservations, observation/configuration and reset paths; API loading/report serialization and input handling; frontend request state, selected output views, charts and modal; CI and selected local/Spec Kit automation. Test bodies were read where needed to compare the claimed guard with the failure scenario, especially API fixtures, safety reservations and registry-chain tests.

**Partial/mechanical-only coverage:** most historical spec/plan prose, ancillary plotting/exploration scripts, every individual test assertion, all portfolio allocation mathematics, third-party dependencies and generated artifacts did not receive a full semantic review. The risk module's distinction between research target weights and an execution gate was inspected; no portfolio calibration conclusion is made. No live datasets were revalidated, no model was fitted, no numerical finding was independently reproduced by executing project code, and no vulnerability database, external dependency documentation, remote branch protection or broker configuration was checked.

**Confidence:** branch-level contradictions and missing arguments are high-confidence static findings; concurrency ordering, framework serialization, browser interaction and deployment authorization have explicit future reproduction/verification requirements. Findings concerning absent capabilities are gaps, not proof of an implementation regression. A clean syntax scan and unchanged file hashes say nothing about whether the existing suite passes.

### Safe stopping and future use

This is a finished, self-contained audit artifact with explicit limits. It does not start a background task or require a continuation after usage resets. If implementation is chosen later, select one work package, recheck its source locations against the current checkout, and finish that package independently. Do not treat proposed acceptance checks as already executed or lower required validation to make an implementation fit a usage budget.

For future repeated audits, reuse a read-only inventory/hash comparison plus per-finding checkpoints, with no automatic code changes. That gives useful partial results at every stopping point without leaving a half-completed refactor. No automation, new gate, issue, commit or external message was created in this pass.

## Additional audit — batch E: overlooked state and accounting boundaries

This batch follows the request to find additional changes. It preserves the same sole writable file and static-only method. The findings below are distinct from F01–F37, although some belong in the same implementation packages.

### F38 — P1: kill confirmation survives contradictory broker evidence

**Evidence:** `scripts/live_safety_gate.py:887–904` sets `kill_confirmed=True` on a successful confirmation. Later calls reporting working orders, disabled state false, or unavailable evidence log a different status but never clear that stored boolean. `reset_kill:938` accepts the historical boolean without a fresh query or evidence timestamp. `BrokerKillQuery` itself has no `as_of` field. A once-confirmed kill can therefore remain reset-eligible after a newer query contradicts its confirmation. This is separate from F17's simultaneous-latch deadlock.

**Plan:** bind confirmation to the active kill generation and dated broker evidence; invalidate it when newer evidence is contradictory or unknown, and require fresh reset evidence. Distinguish confirmation that the broker is disabled from verification that it is safe to re-enable. **Acceptance:** confirmed → working-order/disabled-false/unknown sequences cannot leave an unexplained valid confirmation; stale evidence cannot authorize reset. Keep the local kill latched throughout uncertainty.

### F39 — P1: cash-flow-adjusted safety equity can become a zero denominator

**Evidence:** `live_safety_gate.py:775–801` validates positive raw equity but computes adjusted equity by subtracting external cash flows from cumulative dollar changes. It then divides by adjusted day-start equity/high-water values without checking their domains. EXAMPLE — NOT A RESULT: start with 100, deposit 900 (raw equity 1,000, adjusted equity 100), then lose 100 (raw equity 900, adjusted equity zero). On the next session, the code sets `day_start_equity=0` and divides by it. Raw equity is still valid. Existing halts do not avoid this because order evaluation observes equity before checking the latches.

**Plan:** specify cash-flow normalization and validate every derived anchor before division; when a measurement becomes undefined, commit an explicit reconciliation halt rather than raising after rolling back the entire observation. Preserve the evidence and a documented recovery path. **Acceptance:** valid deposit/withdrawal sequences cannot cause divide-by-zero, nonfinite ratios or an unexplained lost observation. Cover depleted adjusted equity and session rollover in addition to F16's replay cases.

### F40 — P2: dividend payment dates can contain times and silently delay cash availability

**Evidence:** `scripts/data.py:626–643` parses payment dates and checks their calendar date, timezone and ordering, but does not require midnight normalization. `execution_price_frame` and `run_backtest` also omit that normalization check for payment dates. In `backtest_harness.py:108–126`, a payment at 09:00 on the documented payment session is later than that row's midnight label, so neither the due-payment comparison nor same-day equality credits it until a later row.

**Plan:** enforce the declared payment-session type at every public boundary; reject intraday values or convert them through an explicitly documented adapter policy before they enter the bundle. **Acceptance:** a nonmidnight payment timestamp fails clearly; a valid payment session credits cash exactly on that session, including same-day ex/payment and insufficient-buying-power scenarios.

### F41 — P1 for reconciliation claims: the verifier checks present corporate actions but not omitted required events

**Evidence:** `scripts/metrics.py:110–164` validates split/dividend/payment records when encountered and rejects duplicate actions. It never checks that every applicable source action produced an event for a position entitled to it. A producer that omits a split or dividend event and consistently carries the wrong quantity/receivable through later marks can still satisfy cash-plus-position equality, trade reconstruction and source-price matching. Internal arithmetic reconciliation is weaker than source-event completeness.

**Plan:** independently derive required action/entitlement/payment events from source sessions and pre-action holdings, then compare expected event identities and timing with the ledger. **Acceptance:** remove an entitled split/dividend/payment event and consistently rebuild the resulting downstream balances: verification must still reject the omission. A no-position action remains a valid control and must not require an entitlement event. No mutation or runtime experiment was performed in this audit.

### F42 — P2: trade summaries can attach false cost metadata to already computed P&L

**Evidence:** `scripts/backtest_harness.py:155–188` validates and echoes caller-supplied costs, defaulting both to zero, without comparing them to the funded log's `commission_per_trade`/`slippage_bps` attrs. Calling `summarize_trades(funded_log)` can label a costed result as zero-cost; explicit inconsistent values are accepted too. `metrics.equity_curve` already performs the corresponding consistency check, so summary and account-reporting contracts differ.

**Plan:** require costs to match recorded run metadata, or derive them from authoritative metadata with a separate explicit contract for legacy trade tables. **Acceptance:** a costed log cannot be summarized under zero/different costs; matching inputs preserve current P&L and win-rate results. This is metadata integrity, not recalculation of P&L from the summary arguments.

### F43 — P2: risk windows treat absent sessions as adjacent daily observations

**Evidence:** `scripts/portfolio_risk.py:98–115` validates sorted unique normalized labels but not session completeness. `log_returns:223–246` computes adjacent-row returns; `realized_volatility:249` and `trailing_correlation:273` count rows. A missing row for every ticker is stitched across, unlike an existing row containing NaN. This contradicts the stronger wording that a gap can never become a multisession return labeled as one session. It is a separate consumer-boundary gap from F26's download/request coverage.

**Plan:** require or reconstruct an explicit expected session index before risk-window computation, preserving missing rows as unavailable observations. State the coverage interval/calendar provenance in the risk decision. **Acceptance:** deleting a real session and retaining that session as all-NaN cannot yield materially different eligibility merely because one representation compressed the index; weekend/holiday gaps remain valid through the calendar definition.

## Additional audit — batch F: remaining model and UI consumers

### F44 — P1: the legacy logistic path still uses the retired target/calendar contract

**Evidence:** `scripts/logistic_baseline.py:42–61` builds its own close-to-next-close label, drops rows missing features/labels and resets their index. Both local fit loops at lines 71 and 153 use literal one-bar purge/embargo values. This differs from the canonical `targets.py` next-open endpoints/availability span and `features.py` retained-session masks. Repairing only the CLI's input provenance/funding (F27) would still leave a different prediction problem and potentially compressed execution calendar.

**Plan:** explicitly classify this module as a frozen historical control or migrate its feature/target/prediction consumers together to the canonical contract. Prevent a historical-control result from being presented as a current executable-target result. **Acceptance:** an overnight-only movement and an internal missing-feature session distinguish the retired contract from the supported one; retained control artifacts state their target/timing version. The canonical target improvements recorded earlier in this audit do not apply to this duplicate implementation.

### F45 — P1 for displayed conclusions: indicator rundown interprets unknown values as bearish or calm

**Evidence:** `reports/api/routes/ml_rundown.py:52–104` takes the final feature row without checking `Inference_Eligible` or feature finiteness. Short/warm-up history yields NaN SMAs; `NaN > 0` is false, so two unknown trend rules become the negative direction score and the headline that both rules read down. At lines 132 onward, failed volatility comparisons similarly reach the calm/normal-sizing branch. Exact zero trend values also receive negative direction votes under `> 0`, while the individual panels use `>= 0` and label those same values bullish.

**Plan:** model each rule as up/down/flat/unavailable and evaluate it only on its required finite inputs. Aggregate only defined rules and expose insufficient history explicitly; never convert unknown volatility into a sizing recommendation. **Acceptance:** warm-up rows, missing volume, constant-price equality and mixed valid/invalid indicators produce internally consistent noninvented statuses. The existing `model_forecast=not_computed` field does not make these separate rule claims valid.

### F46 — P1: feature-set comparisons include inference-only rows whose labels are unavailable

**Evidence:** `model_cv.nested_walk_forward` intentionally predicts finite-feature test rows using `infer_ok`, retaining the latest rows without known targets. `_predictions_by_date` at `scripts/feature_set_comparison.py:181–195` copies all covered positions into both prediction and label series without a known-label mask. `pair_results:484–505` intersects prediction dates, then sends the labels to `compare_classification`/`compare_regression`. Classification casts them to integers; regression converts them to numeric arrays. With the canonical final `h+1` labels unavailable, normal sufficiently long input can now reach these conversions with missing labels and fail or generate invalid statistics. Keeping these predictions for inference is correct; scoring them is not.

**Plan:** preserve the full prediction output, but form the paired evaluation sample from the shared dates with observed, finite labels and valid predictions in both runs. Record excluded rows and require a nonempty/sufficient scoring sample. **Acceptance:** a normal dataset ending inside the last fold scores only realized targets while retaining current predictions; extending the dataset reveals labels without changing which historical prediction was made. Cover both classification and regression and an empty shared evaluation sample.

### F47 — P2: fetched ticker availability does not reconcile the selected asset

**Evidence:** `reports/web/src/App.tsx:36` initializes `currentTicker` to AAPL. The ticker fetch at lines 79–84 only updates `tickers`; it never checks whether the selected ticker exists in the returned universe, and it ignores an empty array. A dataset containing only another asset can leave the controlled selector with a value absent from its options while requests continue targeting AAPL. Combined with F07, the terminal can remain unusable despite valid data being available.

**Plan:** treat universe loading and current selection as one state transition: retain a valid current selection, otherwise select a documented available default, and render an explicit empty-universe state. **Acceptance:** non-AAPL-only, empty and changed-universe responses cannot leave an invisible invalid selection or issue requests for an unavailable default. This is distinct from F06's response-order race.
