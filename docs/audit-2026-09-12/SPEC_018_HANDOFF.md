# Spec 018 handoff

_Updated 2026-09-12 by the agent that owns the API, web and CI lane for this
run. A second agent was rewriting the core modules at the same time. No `git`
command of any kind was run. Everything below is uncommitted in the working
tree for Camden to review and commit._

- [spec.md](../../.specify/specs/018-terminal-truthfulness/spec.md)
- [tasks.md](../../.specify/specs/018-terminal-truthfulness/tasks.md), which holds the full evidence

---

## 1. Re-scope: the audit wins

The earlier draft scoped spec 018 to the 15 findings `REMEDIATION_PLAN.md`
assigns to Stage 3.1, although `AUDIT.md:229` (work order 1) lists 10. The
plan is derived from the audit, so the audit is authoritative. The earlier
§4g, which followed the plan, is reversed.

### In scope: exactly work order 1

| ID | P | Summary | PR |
|---|---|---|---|
| 45 | P0 | Literal significance p-values | B |
| 46 | P0 | Literal P(Up)/logit; indicator rules presented as a model | B, C |
| 47 | P0 | Hardcoded Gate 1 pass, "301", header "311/311" | B, C |
| 03 | P0 | NaN fills/signals yield a normal tearsheet; literal reconciliation flag | D, not started |
| 04 | P0 | Cost checks accept NaN/inf; slippage 10000 accepted | D, not started |
| 50 | P1 | Invalid requests return 500 or 200 | D, not started |
| 48 | P1 | `holding_bars=1`; commission-only friction; rounded export | E, not started |
| 49 | P1 | Gate decoder, p-value tutoring, Kelly, 0.00 correlation, volume narrative | B (rundown part, done), E (rest) |
| 57 | P1 | API tests fail on a clean checkout; CI cannot import them | A |
| 58 | P1 | Oracles; mutation scripts in the repository | C (regression, runner); D (all-NaN oracle) |

### Moved to later specs

Names and numbers are the plan's proposals (`REMEDIATION_PLAN.md:9`).

| ID | Moves to | Reason |
|---|---|---|
| 29 | Inference and multiple testing (proposed 035) | Audit work order 5. It fixes the research comparison's statistics; no terminal value depends on it, and all four saved entries lie in the direction the old formula gets right. |
| 35 | Diagnostics correctness (proposed 020) | In no work order. A library VIF defect that fabricates no terminal value. |
| 36 | Diagnostics correctness (proposed 020) | In no work order. Best restated beside the VIF fix that changes the numbers it interprets. |
| 51 | Terminal reliability (proposed 038) | Audit work order 6. The API already binds loopback and serves read-only routes. |
| 54 | Terminal reliability (proposed 038) | Audit work order 6. Honest run and fold labels need finding 53's run identity. |

**Numbering flag.** The plan proposed 019 for "Boundary validation", but 019
is now the other lane's spec. The plan's numbers from 019 on need
reassigning.

### Sizes

| File | Before | After |
|---|---|---|
| `spec.md` | 49,568 bytes | 14,950 bytes (limit: under 15 KB) |
| `tasks.md` | 43,106 bytes | 12,442 bytes |

The other 018 documents (`plan.md`, `research.md`, `data-model.md`,
`contracts/`, `quickstart.md`, `checklists/`) were not rewritten. `spec.md`
declares them superseded wherever they conflict.

---

## 2. What was implemented: 3 PRs, uncommitted

Diff sizes are changed lines (+ and −), measured with GNU `diff -u` against a
snapshot taken before any edit.

| PR | Findings | Lines | Content |
|---|---|---|---|
| A | 57 | 333 | Cache dependency seam, app factory, generated fixtures, `requirements-dev.txt`, CI install and a `web` job, API tests moved onto fixtures |
| B | 45, 46, 47 (API) | 391 | Not-computed significance, gate and forecast responses; gate schema requires evidence; the three fabricated-value tests rewritten; significance screen, header badge |
| C | 45, 46, 47 (screens), 58 | 401 | Capital gate view, rundown pane, fake-number regression, in-repository mutation runner |

Four files are split across PRs by hunk:
- `diagnostics.py`: A holds the seam and complete-row diagnosis; B holds significance.
- `ml_rundown.py`: A holds the seam; B holds the rest.
- `test_reports_api.py`: A holds the fixtures and seams; B holds the three rewritten tests.
- `types/api.ts`: B holds `NotComputed`, significance, `test_run` and `model_forecast`; C holds the gate status union. The union must ship with `CapitalGateView.tsx`, or B fails type-checking.

**Between B and C**:
- The gate view shows `unknown` gates as the old gray "PENDING".
- It still says "of 5 Gates Passed".
- The rundown pane is still titled "ML Model Decision Rundown" over honest rule readings.

Nothing numeric is fabricated in that state.

**The three tests that passed only by asserting fabricated values** were
rewritten to assert the not-computed contract:
- `test_significance_screening`
- `test_capital_gate_status`
- `test_ml_rundown`, for its forecast

`test_list_tickers`, which passed on the empty-cache fallback list, now
asserts the fixture's tickers. The fallback list itself is finding 18.

**The fake-number regression**, `tests/test_no_fabricated_values.py`:
- Against the pre-018 sources, its route and UI layers report 25 and 11 violations.
- Against the pre-B/C API it failed 4 tests and errored 1.
- After the change: 7 run, OK.

**The mutation check** follows spec 017's T030 shape, but lives in
`tests/mutation/` as finding 58 asks:
- 14 of 14 mutants caught.
- Source hashes identical before and after.
- The control has 1 pre-existing failure (§4a).

**Web**: `tsc -b --noEmit` exits 0, and `oxlint` exits 0 with only the
pre-existing `App.tsx:93` warning.

---

## 3. CI root cause (finding 57) and the fix

**Root cause: three independent faults.**

| # | Fault | Evidence | Fix |
|---|---|---|---|
| 1 | CI cannot import the API test module | `.github/workflows/test.yml` installed only `requirements.txt`; `tests/test_reports_api.py` imports `fastapi.testclient`; `fastapi` and `httpx` were declared only in `reports/requirements-ui.txt`. Discovery raises `ImportError` before any assertion runs. | New `requirements-dev.txt` (fastapi, httpx, pinned to the UI file, with a test that fails on drift), installed by the workflow. `requirements.txt` untouched. |
| 2 | Six tests read the developer's gitignored `data/cache/` | Routes read module-level `CACHE_DIR` with no seam, so a clean checkout reaches the 404. | `get_cache_dir` FastAPI dependency. Tests write seeded synthetic panels to a temporary directory and override it. A sentinel test fails if any route bypasses the dependency. |
| 3 | One test needs the built frontend | `main.py` mounted `reports/web/dist` at import time, only if it existed. | `create_app(dist_dir=…)`. The test serves a directory it creates. A separate `web` CI job runs `npm ci`, lint and build. |

**Why it went unnoticed.** Three of the four tests that passed on a clean
checkout were asserting fabricated or fallback values.

**Verification.**
- The mutation runner's control runs in a copy with no `data/cache/` and no
  `reports/web/dist/`. There, 19 of 20 tests pass.
- The one failure is not caused by a missing cache or build (§4a).
- CI itself was not run: that needs a push. The `web` job is untested
  remotely.

---

## 4. Flags for Camden

**a. The CI Python job will be red until the lanes reconcile.**
- The core lane's in-flight `scripts/backtest_harness.py:37-38` now requires
  `prices.attrs["price_basis"] == "unadjusted_dollars"`.
- The tearsheet route reads the auto-adjusted cache (finding 13), so it cannot
  honestly make that declaration. `test_backtest_tearsheet` therefore errors.
- I did not patch around it. This is tasks T024, for whichever lane merges
  second.

**b. The same lane's `build_features` started keeping warm-up rows mid-run.**
This broke the collinearity endpoint (`SVD did not converge`). The route now
diagnoses complete rows only (T008), which is a no-op under the old contract.

**c. Ownership of the library halves of 03 and 04.**
- Those halves live in modules owned by spec 019.
- The in-flight harness already validates costs and prices.
- Decide whether 019 closes them, or 018 PR D takes them afterwards (T023).

**d. PR C is 401 lines**, at the approximate 400 limit. The whole three-PR run
is 1,125 lines.

**e. `httpx` as a test dependency** conflicts with CLAUDE.md's "no test
dependencies". You directed `requirements-dev.txt`; the conflict itself is
unresolved.

**f. Two conventions not yet in the constitution.** It has no rule forbidding
unsourced figures in a report or UI, and none requiring the suite to pass on
a clean checkout. Spec 018 enforces both by test; neither is a rule.

**g. Gate descriptions still state rule texts.** "Sharpe <= 0.3", "remains
positive" and "1-2 months" appear as what each gate would require. No gate
claims them. They belong to findings 30 and 49.

**h. Tooling state.**
- pytest is not installed, so `-p no:cacheprovider` could not apply. Tests ran
  under `python -B -m unittest` against spec 018's modules only.
- `tsc -b` updates its build-info under `reports/web/node_modules/.tmp/`.

---

## 5. Every file touched

**Created**
- `requirements-dev.txt`
- `tests/api_fixtures.py`
- `tests/test_no_fabricated_values.py`
- `tests/mutation/run_spec_018_mutants.py`
- `reports/web/src/components/common/NotComputedNotice.tsx`

**Modified**
- `.github/workflows/test.yml`
- `reports/api/main.py`
- `reports/api/schemas.py`
- `reports/api/routes/data.py`
- `reports/api/routes/diagnostics.py`
- `reports/api/routes/backtest.py`: the cache seam only
- `reports/api/routes/capital_gate.py`
- `reports/api/routes/ml_rundown.py`
- `reports/web/src/App.tsx`
- `reports/web/src/types/api.ts`
- `reports/web/src/components/layout/Header.tsx`
- `reports/web/src/components/layout/MLRundownPane.tsx`
- `reports/web/src/components/views/CapitalGateView.tsx`
- `reports/web/src/components/views/FeatureDiagnosticsView.tsx`
- `tests/test_reports_api.py`
- `.specify/specs/018-terminal-truthfulness/spec.md`
- `.specify/specs/018-terminal-truthfulness/tasks.md`
- `docs/audit-2026-09-12/SPEC_018_HANDOFF.md`

**Not touched**
- **The core modules and their tests.** `scripts/` files were read for their
  contracts and copied, read-only, into temporary directories by the mutation
  runner.
- **Other off-limits paths**: `requirements.txt`, `.specify/feature.json`,
  `CLAUDE.md`, the constitution, `docs/PROJECT_CONTEXT.md`,
  `REMEDIATION_PLAN.md`, `remediation-map.html`, `portfolio_risk.py` and its
  tests, and `.specify/specs/019-*`.
- **`data/cache/`**: never read by any test or written.

**Earlier run, recorded for history.** The Spec Kit path fix (`specs/` →
`.specify/specs/`) is at `.specify/scripts/bash/create-new-feature.sh:200`
and `.claude/skills/speckit-specify/SKILL.md:84-93`. It was verified by a
dry run, and its manifest-hash caveat still stands (finding 65).
