# Review 018 — Terminal Truthfulness

**Verdict: REQUEST CHANGES.** PRs A–C materially reduce the immediate risk of
showing fabricated p-values, forecast probabilities, and pass counts, but they
do not close findings 45, 46, 47, 57, or 58 under the acceptance language in
`AUDIT.md`. Findings 03, 04, 48, 49, and 50 remain open because PRs D and E have
not started. The current tree also violates the new Constitution Rule 11 in the
terminal surfaces that 018 edits.

**Reviewed source state:** uncommitted working tree inspected on 2026-09-14.
The spec identifies `555343e` as the line-number reference commit
(`.specify/specs/018-terminal-truthfulness/spec.md:23-25`), but no Git command
was run, so this review does not claim that commit as the exact parent of every
working-tree hunk. Evidence below is from the files and line numbers present at
review time.

**Method:** static inspection only. No Git command and no test command was run.
That preserves the instruction to write exactly one file: this review. Test
results mentioned below are claims recorded by the implementing agent, not
results independently reproduced in this review.

## Closure ledger

| Audit finding | PR A–C status | Review conclusion |
|---|---|---|
| 03 | D not started | Open |
| 04 | D not started | Open |
| 45 | Literal values removed | Harm contained; audit acceptance not met |
| 46 | Literal forecast removed; some labels changed | Partially fixed; still mislabeled and prescriptive |
| 47 | Gates forced to unknown; status enum added | Harm contained; evidence and invalidation contract absent |
| 48 | E not started | Open |
| 49 | Relative-volume sentence improved | Mostly open; known false tutoring remains |
| 50 | D not started | Open |
| 57 | Fixtures, dependency file, app factory, web CI job added | Implementation plausible; closure not demonstrated while suite is red |
| 58 | Literal scanner and mutation runner added | Partial; required independent oracles absent and mutation control is red |

## Finding R018-01 — Finding 45 is contained, not closed

**Claim.** The significance endpoint no longer fabricates the four audited
p-values, but replacing every result with `not_computed` does not satisfy the
audit finding's artifact-backed acceptance condition. The implementation must
not be described as closing finding 45.

**Evidence.** `AUDIT.md:141` requires validated artifacts keyed by ticker,
dataset, model, and run, and requires a selected-run change to update the
displayed value. It also records that a saved experiment exists. The endpoint
does not inspect a ticker, dataset, model, run, or artifact; it returns the same
status and reason for every ticker (`reports/api/routes/diagnostics.py:84-101`).
The rewritten test positively requires this permanent all-ticker behavior
(`tests/test_reports_api.py:90-100`). The spec deliberately defers real artifact
loading (`.specify/specs/018-terminal-truthfulness/spec.md:65-70`), which is a
valid staging decision but not audit closure.

**Severity.** High — false closure claim on a P0 audit finding. The dangerous
numeric output is gone, so this is not as severe as continuing to show the old
figures.

**Recommended action.** Mark 45 as **contained / open** in 018. Use an explicit
`unavailable` result keyed to the requested ticker/run while no validated reader
exists. Close 45 only when a saved result with dataset ID, model ID, run ID,
calculation timestamp, and source hash drives the response and a run-selection
test proves the displayed value changes.

## Finding R018-02 — The terminal still labels the rule pane “ML”

**Claim.** Finding 46 and FR-002 are not closed because the header still calls
the indicator-only pane “ML Rundown.”

**Evidence.** The audit requires rule commentary to be labeled honestly and not
presented as fitted-model output (`docs/audit-2026-09-12/AUDIT.md:143`). The spec
is stricter: no pane, tab, or header label may call the readings ML or model
output (`.specify/specs/018-terminal-truthfulness/spec.md:123-130`). The pane
body says “Indicator Rule Readings” (`MLRundownPane.tsx:44-52`), but the header
button visible to every user still says `ML Rundown`
(`reports/web/src/components/layout/Header.tsx:93-105`). The UI scanner's model
pattern only recognizes “ML model,” “machine-learning model,” or a small verb
list (`tests/test_no_fabricated_values.py:30-36`), so the live violation passes.

**Severity.** High — direct failure of a P0 finding and an explicit acceptance
requirement.

**Recommended action.** Rename the visible button to `Indicator Readings` and
remove the remaining ML naming from user-visible navigation. Add a rendered or
semantic component assertion for the accessible button name; do not rely on a
regex that happens not to match the current wording.

## Finding R018-03 — Indicator commentary still gives unsupported trading advice

**Claim.** Removing the fabricated model probability did not make the rundown
truthful. It still converts unvalidated indicator thresholds into directional
and position-management advice.

**Evidence.** The endpoint tells the user to wait for mean reversion, favors
trend continuation, proposes a trailing stop, says sellers are in control, and
tells the user when to buy (`reports/api/routes/ml_rundown.py:97-112`). It labels
a moving-average sign as a market “regime” and says “Long only” or “Cash or
Short” (`ml_rundown.py:114-125`). It prescribes position reduction and wider
stops from fixed volatility thresholds (`ml_rundown.py:127-145`). None of those
claims is supported by a fitted model, validated policy, payoff study, or source
artifact. The pane relabels `how_to_plan` as “Limits of This Reading,” but then
renders the same prescriptive strings (`MLRundownPane.tsx:170-178`). The audit
requires unsupported model explanations to be removed, not merely moved below
a not-computed banner (`AUDIT.md:143`).

**Severity.** Critical — a user can act on directional advice in the exact
terminal surface intended to stop unsupported decision output.

**Recommended action.** Until an evidence artifact exists, restrict every item
to mechanical, non-predictive description: formula, observed value, timestamp,
and “predictive/economic meaning not evaluated.” Delete buy/sell/short/stop/size
instructions and bullish/bearish presentation. If an advisory policy is later
desired, make it a separately versioned artifact with its own causal evaluation
and provenance.

## Finding R018-04 — The rundown does not select the “most recent complete bar”

**Claim.** Short, halted, zero-volume, or otherwise incomplete frames can cause
a 500 response or a false directional state because the implementation reads
the final row without enforcing feature eligibility.

**Evidence.** The code comment says “most recent complete bar,” but the code is
`features_df.iloc[-1]` (`reports/api/routes/ml_rundown.py:45-52`). The feature
builder explicitly retains all source sessions, marks finite rows with
`Inference_Eligible`, and converts infinite ratios caused by halted/zero-volume
windows to NaN (`scripts/features.py:131-139`, `scripts/features.py:166-186`).
NaN comparisons fall through as non-positive, potentially producing bearish
states; `int(last_row['Volume'])` or response serialization may instead fail
(`ml_rundown.py:67-70`, `ml_rundown.py:147-152`). An empty frame fails at
`iloc[-1]`. The only rundown API test uses a long, complete, strictly positive
panel (`tests/api_fixtures.py:32-62`; `tests/test_reports_api.py:133-147`).

**Severity.** High — normal market/data adversity can produce a confident-looking
wrong state or an unhandled server error.

**Recommended action.** Filter on `Inference_Eligible`, select the last eligible
session, and return a typed unavailable state if none exists. State whether the
selected observation is the latest expected session or merely the latest
available row. Add empty, one-row, warm-up-only, zero-volume halt, missing-tail,
and nonfinite-final-row tests.

## Finding R018-05 — Gate “evidence” is an unchecked string, not provenance

**Claim.** The new schema prevents a known status with `None`, but it does not
make gate states evidence-backed, signed/versioned, or invalidatable as finding
47 requires.

**Evidence.** `CapitalGateItem.evidence` is only `str | None`, and the validator
accepts any nonempty string for passed, failed, or stale
(`reports/api/schemas.py:116-132`). The schema has no artifact ID, run ID,
commit, dataset hash, policy version, produced-at time, expiry rule, signature,
or dependency graph. The schema test proves the weakness by accepting the
literal `"a recorded artifact"` (`tests/test_no_fabricated_values.py:144-151`).
`AUDIT.md:145` requires signed/versioned artifacts and invalidation when data,
source, costs, or policy changes.

**Severity.** Critical — one arbitrary string is enough to turn an unknown gate
into a green pass in any future route change.

**Recommended action.** Replace the string with a structured evidence reference
containing at minimum artifact path/ID, content hash, run ID, source revision,
dataset ID, policy/config hash, produced-at time, and verified-at time. Compute
staleness from those dependencies. Reject a known status unless the referenced
artifact exists, validates, and matches the gate's policy.

## Finding R018-06 — The gate API still asserts unsourced readiness and policy figures

**Claim.** Forcing every chip to `unknown` does not neutralize the rest of the
gate response. The endpoint still publishes unsupported numeric policies and an
unsourced current-readiness claim.

**Evidence.** Gate 1 publishes `Sharpe <= 0.3` and `2x cost stress`; gate 2
publishes `$1.00/trade` and `5 bps`; gate 4 publishes `1-2 months`
(`reports/api/routes/capital_gate.py:23-50`). The response independently asserts
`overall_readiness="Phase 3: Quantitative Model Calibration & Feature
Refinement"` (`capital_gate.py:61-66`). The audit warns specifically that
elapsed months are not a substitute for independent decisions/failure scenarios
(`docs/audit-2026-09-12/AUDIT.md:237`). No artifact or policy source backs these
values or the current phase.

**Severity.** Critical under Constitution Rule 11; High under finding 47.

**Recommended action.** Remove `overall_readiness` or return it as unknown until
it is derived from verified gate evidence. Replace gate prose with stable policy
IDs and source links/hashes; render numeric thresholds only from the versioned
policy artifact. In the interim, use figure-free descriptions such as “No
approved threshold artifact is loaded.”

## Finding R018-07 — Rule 11 is violated throughout touched terminal surfaces

**Claim.** PRs B and C cannot merge under the new Rule 11 because touched UI
files still render unsourced figures that a reader can mistake for findings,
thresholds, or evidence.

**Evidence.** Rule 11 requires every human-rendered number to carry its source
artifact, producing commit/run ID, and date; unsourced or stale figures must be
removed from any touched surface (`.specify/memory/constitution.md:212-228`).
The touched diagnostics view still asserts `$150/$149`, `$50/$200`, condition
number `422`, VIF `54`, `~24`, `<3.0`, `17x Improvement`, and fixed thresholds
without provenance (`FeatureDiagnosticsView.tsx:42-57`,
`FeatureDiagnosticsView.tsx:74-125`). It also claims that no correlation exceeds
`0.55` (`FeatureDiagnosticsView.tsx:148-156`). The touched capital-gate view
contains numbered gate narratives and “currently” directs work toward specific
gates despite every gate being unknown (`CapitalGateView.tsx:66-75`). The
rundown emits prices, moving averages, percentages, volume, and thresholds with
only an as-of date, not artifact/run/source identity
(`ml_rundown.py:54-64`, `ml_rundown.py:97-152`).

**Severity.** Critical — the constitution says a violating PR is rejected on
sight (`.specify/memory/constitution.md:3-6`).

**Recommended action.** Treat Rule 11 as a merge blocker for every 018-touched
report and component. Add a shared provenance envelope to computed API
responses and a visible source/run/date disclosure in each panel. Remove all
illustrative/result-like constants or label a genuine example on the same line
as `EXAMPLE — NOT A RESULT`. Policy thresholds must cite a versioned policy,
not be embedded in component prose.

## Finding R018-08 — The truthfulness scanner is too lexical and already misses violations

**Claim.** The new regression proves absence of a small blacklist of spellings,
not absence of fabricated or unsourced evidence.

**Evidence.** The scanner recognizes only five text families and three field
names (`tests/test_no_fabricated_values.py:24-45`). It intentionally disables
the p-value-figure rule for UI code and disables model-attribution checks outside
two files (`test_no_fabricated_values.py:96-106`). Consequently, the current
`ML Rundown` label, false p-value tutoring, hardcoded condition/VIF claims,
gate-policy figures, prescriptive trading advice, and unsourced current phase
all pass. The numeric differential only rejects values identical across two
panels (`test_no_fabricated_values.py:110-137`); a fabricated value derived from
row count, ticker length, or a checksum would differ and pass without being a
valid computation.

**Severity.** High — the suite can certify terminal truthfulness while the
terminal visibly violates both the spec and Rule 11.

**Recommended action.** Make provenance structural, then test the structure:
every result-bearing response must reference a validated artifact/policy and
every rendered figure must expose that reference. Keep lexical scans only as a
backstop for the exact historical literals. Add component/browser assertions
for accessible labels and unavailable states.

## Finding R018-09 — The mutation runner cannot establish a green mutation result

**Claim.** Finding 58 and SC-002 are not closed because the mutation control is
known to fail and the runner exits nonzero.

**Evidence.** The task record says the control has one failure and the runner's
exit code is 1 (`.specify/specs/018-terminal-truthfulness/tasks.md:149-153`).
The runner itself returns failure whenever the control is nonempty
(`tests/mutation/run_spec_018_mutants.py:121-138`). Despite that, the handoff
summarizes “14 of 14 mutants caught” (`SPEC_018_HANDOFF.md:97-106`). A red
baseline cannot demonstrate that the post-change system satisfies SC-002, and
the audit asks for independent financial/pipeline oracles rather than only
restorations of known strings (`AUDIT.md:169`).

**Severity.** High — mutation evidence is being reported as success when its own
runner rejects the run.

**Recommended action.** Do not record mutation success until the control is
green. Land the T024 unavailable contract first, rerun from a clean declared
environment, and record the complete command, environment lock, source-state
identifier, full hash, timestamp, and output artifact. Keep finding 58 open
until its all-NaN and later financial/pipeline oracles land in their owning
specs.

## Finding R018-10 — Mutation-style survivor inventory for every new guard/assertion family

**Claim.** Each new guard or assertion family admits a behavior-breaking source
mutation that the present tests would still accept. The list below is the
required adversarial mutation review, not hypothetical test polish.

**Evidence.** The new assertions are concentrated in
`tests/test_reports_api.py:30-183` and
`tests/test_no_fabricated_values.py:110-185`; the only production guard is the
gate evidence validator (`reports/api/schemas.py:127-132`). Surviving mutations:

| New guard/assertion | Behavior-breaking mutation that still passes |
|---|---|
| Health response shape | Leave `status="healthy"` while every data dependency is unavailable; the test checks no dependency readiness. |
| Fixture ticker list | Hardcode `['AAPL','NVDA']` instead of reading the fixture; the exact-list assertion passes. |
| OHLCV response | Preserve only the first open and corrupt/reverse every later bar; only length, first-bar keys, date punctuation, and first open are checked. |
| Market statistics | Return any positive volatility and negative drawdown constants; the test checks signs, not an independent calculation. |
| Missing-bar response | Always return integer zero; the test checks only ticker and Python type. |
| Collinearity response | Return two fabricated condition numbers with scale-free smaller than levels; the sole quantitative relation still holds. |
| Significance status | Return `not_computed` forever even after an eligible artifact exists; the test requires that stale behavior for both tickers. |
| Tearsheets | Keep the endpoint unavailable or fail before assertions; the control is already red, so no green behavioral baseline exists. |
| Gate route | Hardcode all gates `unknown` forever and ignore newly present artifacts; every route assertion still passes. |
| Gate evidence validator | Use `evidence="x"` for a passed gate; the validator and its explicit schema test accept it. |
| Rundown forecast | Replace every insight calculation with nonsense derived from `len(raw_df)` while keeping forecast `not_computed`; shapes pass and the two panel lengths make numbers differ. |
| Static app factory | Use the injected directory only when its path looks temporary, otherwise silently fall back to `DIST_DIR`; the temp-directory test passes while production configurability breaks. |
| Cache dependency seam | Bypass injection only for an untested ticker such as MSFT; the sentinel and AAPL/NVDA fixture paths still pass. |
| Dev-pin parity | Remove the workflow's `-r requirements-dev.txt` install while leaving the files equal; the parity unit test does not inspect CI wiring. |
| Fabricated-text response scan | Spell a result as “odds are fifty-four percent” or use a synonym outside the regex; no pattern matches. |
| Fixed-number differential | Compute a fake “confidence” from row count or ticker length; it changes across fixtures without representing price evidence. |
| Structural-number allowlist | Reuse an allowlisted ordinal as a decision score; the checker reasons only from JSON path, not semantics. |
| Route AST scan | Assign `fake = 84 / 1000` and pass `p_value=fake`, or construct `**{'p_value': fake}`; the keyword-constant rule misses it. |
| UI source scan | Render `{'ML ' + 'Model'}` or the already-present `ML Rundown`; the line regex misses the semantic label. |
| Scanner self-test | Keep the historical strings detectable while adding a differently worded fabrication; self-testing the blacklist does not bound future wording. |

**Severity.** High — multiple mutants break the claimed contract while retaining
a green targeted suite.

**Recommended action.** Convert the table into executable semantic mutants.
Prioritize artifact authenticity/staleness, invalid final rows, nonfinite data,
gate evidence forgery, ticker-specific cache bypass, derived-but-fake values,
and rendered accessible labels. A mutant is caught only by an independent
behavioral oracle, not by scanning for the mutant's spelling.

## Finding R018-11 — Finding 57 is not yet demonstrably closed

**Claim.** PR A addresses the three recorded clean-checkout causes, but finding
57 cannot be closed while the declared test command fails and CI has not run.

**Evidence.** The workflow now installs both requirement files and adds a web
lint/build job (`.github/workflows/test.yml:8-38`). The app and cache seams are
real (`reports/api/main.py:33-68`; `reports/api/routes/data.py:26-36`). However,
the implementing record says 12 of 13 API tests pass, the tearsheet test errors,
the mutation control is red, Python 3.12 was not run, and CI was not run
(`.specify/specs/018-terminal-truthfulness/tasks.md:117-153`). The audit's
acceptance is a clean installation and clean directory, not merely removal of
the original cache/dist causes (`docs/audit-2026-09-12/AUDIT.md:167`).

**Severity.** High — the change cannot currently pass its own merge workflow.

**Recommended action.** Credit PR A as fixing the identified dependency/cache/
static seams, but keep finding 57 open. After R018-13 lands, run the exact CI
commands in Python 3.12 and Node 24 from a clean checkout/install with no cache
or dist, require zero skips and zero failures, and preserve the logs as a
Rule-11-compliant verification artifact.

## Finding R018-12 — The fixtures omit the adversarial market cases the review requires

**Claim.** The generated panels are deterministic happy paths, not adversarial
fixtures for missing data, halts, gaps, corporate actions, or empty frames.

**Evidence.** `synthetic_panel` creates every weekday, strictly positive prices,
and strictly positive volume (`tests/api_fixtures.py:32-62`). It has no split,
dividend, payment-date, halt, missing-session, duplicate-session, stale-tail,
NaN, infinity, or empty-panel mode. Its comment says nothing depends on the
exchange calendar (`api_fixtures.py:35-40`), yet the API gap test calls the
exchange-calendar missing-bar function and asserts only that the result is an
integer (`tests/test_reports_api.py:68-73`). PR D's all-NaN oracle is explicitly
not started (`.specify/specs/018-terminal-truthfulness/tasks.md:92-104`).

**Severity.** High — malformed and unavailable market states are precisely where
a truthfulness terminal must fail closed.

**Recommended action.** Add table-driven fixtures for empty ticker slice,
all-NaN OHLCV, single-row/warm-up-only data, nonfinite final row, zero-volume
halt, missing interior session, stale tail, duplicate/out-of-order session,
split, dividend ex-date, delayed payment, and post-action price discontinuity.
For each, assert an exact unavailable/4xx contract or a hand-computed value; do
not assert merely that a field exists.

## Finding R018-13 — T024 must be split across 018 and 020, without forging price basis

**Claim.** The truthful immediate fix belongs in 018 PR D; the successful data
path must wait for spec 020. Waiting entirely for 020 leaves 018/CI red, while
stamping the adjusted frame as unadjusted would create a material accounting
falsehood.

**Evidence.** The tearsheet route loads the generic CSV and drops it into a new
DataFrame, with no verified price-basis or corporate-action source
(`reports/api/routes/backtest.py:34-57`). The funded harness rejects any frame
without `price_basis == "unadjusted_dollars"`
(`scripts/backtest_harness.py:37-48`). The existing loader stamps legacy data as
`research_adjusted`, and downloads with `auto_adjust=True`
(`scripts/data.py:302`, `scripts/data.py:359`). Spec 020 owns the new unadjusted
store, manifest, hashes, action data, and blessed loader
(`.specify/specs/020-unadjusted-price-data/spec.md:72-130`). Its own statement
confirms that no current repository cache can satisfy the harness
(`spec.md:11-17`).

**Severity.** Critical — a fake attr assignment would silently mix adjusted
research prices with dollar cash accounting; leaving the exception unhandled
keeps CI red and presents valid requests as server failures.

**Recommended action.** In 018 PR D, make the route detect the absence of a
verified execution-price source and return a documented, machine-readable
`unavailable` result (or a deliberate 503 problem response) with no tearsheet
body. Rewrite `test_backtest_tearsheet` to expect that state from the adjusted
fixture, and add a mutant that stamps `unadjusted_dollars` inside the route; the
test must kill it. In spec 020, implement and validate the manifest-backed
unadjusted OHLCV/actions loader, then add the separate successful-tearsheet
integration test. Do not reverse-adjust and do not assign the attr in 018.

## Finding R018-14 — No new lookahead is confirmed, but Rule 5 coverage is incomplete

**Claim.** Static inspection found no new forward price read introduced by PRs
A–C. That favorable result is narrow: the new fixtures and endpoint tests do not
prove correct behavior across time boundaries, gaps, or the latest incomplete
row.

**Evidence.** The new diagnostics hunk drops rows only on same-row feature
completeness before matrix diagnostics (`reports/api/routes/diagnostics.py:44-51`).
The feature implementation computes trailing windows and backward returns and
keeps the forward label outside the feature lists (`scripts/features.py:131-139`,
`scripts/features.py:152-186`). The rundown reads those feature columns, not the
label (`reports/api/routes/ml_rundown.py:54-70`). However, the fixtures have
regular weekday spacing only (`tests/api_fixtures.py:37-44`), and the tests do
not perturb `t+1`, truncate the tail, or insert missing/halted sessions. Rule 5
requires off-by-one, boundary, and gap tests for timestamp-touching code
(`.specify/memory/constitution.md:109-122`).

**Severity.** Medium — no leak is demonstrated, but the proof obligation for a
time-sensitive terminal path is unmet.

**Recommended action.** Add endpoint-level future-perturbation invariance for a
fixed as-of session, first/last/short-frame boundaries, and irregular calendar
spacing. Explicitly assert that `as_of_date` and every rule value are invariant
to bars strictly after the selected session. Keep execution-price/corporate-
action timing tests in 020/019, where those boundaries are owned.

## Finding R018-15 — The recorded evidence itself violates Rule 11

**Claim.** The implementation notes report human-facing test and mutation
figures without a durable source artifact, source-state identity, or complete
provenance.

**Evidence.** `tasks.md` reports test counts, failures, a truncated source hash,
and mutation counts (`.specify/specs/018-terminal-truthfulness/tasks.md:117-176`).
`SPEC_018_HANDOFF.md` repeats changed-line counts, test results, mutation totals,
and tool results (`docs/audit-2026-09-12/SPEC_018_HANDOFF.md:64-109`). The notes
provide a date and commands, but no immutable output artifact and no exact
uncommitted source-state manifest. Rule 11 applies to reports and documents as
well as UI (`.specify/memory/constitution.md:212-225`). The recorded mutation
hash is truncated, so it cannot identify or verify the reviewed source set.

**Severity.** High — these documents are being used as merge evidence, yet the
new constitution forbids unsourced figures in reports.

**Recommended action.** Save full machine-readable logs for Python tests, web
lint/build, clean-checkout verification, and mutation runs. Attach a manifest
of every reviewed file and SHA-256, the full command/environment versions,
timestamp, and eventual commit/run ID. Link each reported count to that
artifact. Until then, label the recorded numbers “unverified agent report” and
do not use them as gate evidence.

## Finding R018-16 — D and E remain merge-blocking for the spec-level acceptance claim

**Claim.** PRs A–C cannot support a claim that spec 018 or audit work order 1 is
complete because all malformed-input work and most derived/explanation work are
explicitly absent.

**Evidence.** The audit's work-order pass condition combines removal of
fabrication, rejection of malformed inputs, and clean API fixtures
(`docs/audit-2026-09-12/AUDIT.md:225-230`). Tasks T023–T027 for findings 03, 04,
50, and the all-NaN oracle are unchecked
(`.specify/specs/018-terminal-truthfulness/tasks.md:92-104`). Tasks T028–T031
for holding bars, cost decomposition, unrounded values, gate decoder, p-value
tutoring, Kelly text, and unknown correlation are also unchecked
(`tasks.md:106-115`). Current production code still defaults every holding
period to one and hardcodes reconciliation success
(`reports/api/schemas.py:72-80`; `reports/api/routes/backtest.py:144-170`). The
known false statistical tutoring and `?? 0` correlation remain visible
(`FeatureDiagnosticsView.tsx:49-57`, `FeatureDiagnosticsView.tsx:177-193`).

**Severity.** Critical for spec/work-order completion; expected for an
intermediate A–C review.

**Recommended action.** Keep A, B, and C reviewable as intermediate units, but
do not mark spec 018 or work order 1 complete. Resolve the critical B/C issues
above, implement D with the T024 split described in R018-13, then implement E.
Require the complete green, provenance-backed acceptance run only after all five
PR units are present.

## Finding R018-17 — No 018 module-boundary breach was found, with one verification limit

**Claim.** The declared 018 edits stay in the API/web/CI/test/spec lane and do
not modify the core data, signal, or accounting modules owned by 019. The
complete-row diagnostics change is route-local and does not cross the core
layer boundary. This is a pass, not a defect.

**Evidence.** The handoff lists every claimed created/modified file and
explicitly identifies core modules as untouched by 018
(`docs/audit-2026-09-12/SPEC_018_HANDOFF.md:176-213`). The lane boundary forbids
018 edits to `data.py`, `features.py`, `targets.py`, `metrics.py`,
`backtest_harness.py`, `ml_signal.py`, `estimators.py`, and `model_cv.py`
(`.specify/specs/018-terminal-truthfulness/spec.md:53-63`). The 018 production
changes inspected are confined to `reports/`, plus CI/dependency seams; core
validation remains in the separately modified 019 files. Repository
responsibilities place data adjustment in `scripts/data.py`, signal decisions
in `scripts/signals.py`, and fills/P&L in `scripts/backtest_harness.py`
(`CLAUDE.md:70-80`).

**Severity.** Informational / pass.

**Recommended action.** Preserve this partition. Implement only the route-side
unavailable contract in 018. Do not add an unadjusted loader, action join, attr
stamp, fill policy, or accounting workaround to `reports/api/routes/backtest.py`;
those belong to 020/019. Because Git was prohibited and no standalone pre-018
snapshot was present, Camden should use GitKraken to confirm that the actual
staged A–C paths match the handoff list before committing.

## Final recommendation

Do not merge B or C as finding-closing PRs in the current state. Fix the visible
ML label, remove unsupported trading advice, make final-row availability
explicit, and apply Rule 11 structurally. Do not call 45 or 47 closed until
artifact selection and invalidation exist. PR A's seams are directionally
correct, but finding 57 remains open until the full clean CI run is green.

For T024, proceed now in 018 with an honest unavailable response and a test that
rejects forged price basis. Let 020 exclusively provide verified unadjusted
OHLCV, corporate actions, manifests, and the later successful tearsheet. This
keeps both module ownership and accounting truth intact.
