# Spec 034 Handoff

**Status**: REQ-034-001 through REQ-034-005 implemented and verified.

**Completed at**: `2026-09-23T04:02:13.0859213Z`

## Delivered

- `scripts/order_gateway.py` is the single fail-closed order-submission seam.
  It evaluates through `LiveSafetyGate` exactly once and never invokes the
  caller-supplied submission callback unless the outcome is exactly `ALLOW`.
- `scripts/live_safety_gate.py` exposes the role-explicit `LiveSafetyGate`
  alias, allows the inner rolling halt to clear while the outer kill latch
  remains active, and excludes unfilled sells from exposure-reducing netting.
- The existing nonpositive-equity floor remains before all downstream sizing
  math and has explicit zero, negative, and planted-mutant proof.
- `reports/api/routes/safety.py` owns the five Gate 5 endpoints. It receives a
  request-scoped gate dependency and fails closed with HTTP 503 when no reviewed
  bootstrap supplies one.
- `reports/api/schemas.py` received only new `Safety*` models. Existing
  `CapitalGateItem` and `CapitalGateStatusResponse` definitions were not edited.
- `reports/api/main.py` registers the new safety router.
- `/speckit-plan` generated `plan.md`, `research.md`, `data-model.md`,
  `contracts/safety-api.md`, and `quickstart.md`; `/speckit-tasks` generated
  `tasks.md` before implementation.

## Tests-first evidence

| Requirement | Red evidence | Green evidence |
|---|---|---|
| REQ-034-001 | `tests/test_order_gateway.py` initially stopped at collection with `ModuleNotFoundError: No module named 'order_gateway'`. | Six chokepoint/static-guard tests pass; the fake submitter is unreachable for `DENY` and unknown outcomes. |
| REQ-034-002 | `test_both_latches_clear_inner_rolling_then_outer_kill` failed with `ValueError: cannot reset a rolling halt while the kill switch is active.` | The rolling latch clears first, kill remains latched, and kill then clears second; the full safety file passes. |
| REQ-034-003 | `test_unfilled_pending_sell_does_not_create_capacity_for_new_buy` failed because the candidate returned `OK` instead of `MAX_POSITION_PCT_BREACH`. | Pending exposure sums positive quantities only; the new candidate is denied and reservations remain durable. |
| REQ-034-004 | The current checkout already contained the pre-division `equity <= 0` guard, so direct zero/negative cases were green before any production edit. A planted mutant removing that guard is killed by the same oracle. | Zero and negative equity both return `NON_POSITIVE_EQUITY`; no redundant production check was added. |
| REQ-034-005 | `tests/test_safety_router.py` initially stopped at collection with `ModuleNotFoundError: No module named 'reports.api.routes.safety'`. | Six endpoint/dependency tests pass, including all five routes, 409 business refusals, 422 naive timestamps, 503 missing injection, and registration through `create_app`. |

An intermediate router run exposed SQLite thread affinity when one connection
was shared across TestClient threads. The final dependency contract constructs
and closes a request-scoped gate in the serving thread; SQLite's safety default
was not weakened with `check_same_thread=False`.

## Verification

- Pre-change safety baseline:
  `python -m pytest tests/test_live_safety_gate.py -q` -> `61 passed`.
- Final focused spec-034 run:
  `python -m pytest tests/test_live_safety_gate.py tests/test_order_gateway.py tests/test_safety_router.py -q`
  -> `77 passed in 5.66s`.
- Canonical full suite:
  `python -m pytest tests` -> `18 failed, 833 passed, 9 errors in 290.44s`;
  `860` items collected.
- Phase 7 comparison baseline:
  `18 failed, 817 passed, 9 errors`.
- Differential: `+16 passed`, `+0 failed`, `+0 errors`. The failed and error
  node IDs exactly match `docs/implementation/spec-033/canonical-phase7.txt`;
  there are no new failures or errors to name.

The full suite remains historically red. This work did not attempt to repair
those pre-existing model-CV, feature-set, multi-ticker, reports-API, or target
equivalence failures.

## Protected boundaries

- `reports/api/routes/capital_gate.py` pre-work and final SHA-256:
  `9ca1f16f8de9c85f4acdf3f41c5a848b63ad6abb1e47baa21083139c485855c3`.
  It is unchanged.
- No broker adapter, broker SDK, network call, credential, or `exec/` code was
  added.
- No change was made to `scripts/portfolio_risk.py` or the HAC bandwidth work.
- No Git command was run.

## Files in the spec-034 implementation surface

- `scripts/live_safety_gate.py`
- `scripts/order_gateway.py` (new)
- `reports/api/main.py`
- `reports/api/schemas.py` (additive `Safety*` models only)
- `reports/api/routes/safety.py` (new)
- `tests/test_live_safety_gate.py`
- `tests/test_order_gateway.py` (new)
- `tests/test_safety_router.py` (new)
- `.specify/specs/034-live-safety-gate-remediation/` planning, task, contract,
  quickstart, and handoff artifacts
- `.specify/feature.json`, written by the Spec Kit setup workflow to select spec 034

## Open work

- A future reviewed deployment/bootstrap spec must supply the real
  `LiveSafetyGate` dependency with Camden-approved limits and a durable database
  path. The current default intentionally returns HTTP 503.
- When a broker is selected, extend the AST guard's explicit broker-client root
  list if its SDK is not already covered. Building that adapter remains outside
  this spec and outside autonomous `exec/` work.
- Gate 5's read-only capital-cockpit row remains separate from this operational
  router, exactly as the spec requires.
