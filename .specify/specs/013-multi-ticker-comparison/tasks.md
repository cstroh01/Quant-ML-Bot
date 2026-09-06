# Tasks — 013 Multi-Ticker Comparison Table

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Universe and per-ticker runner

- [ ] **T001** `TICKER_UNIVERSE` — explicit named constant, placeholder
  list pending Camden's confirmation. (FR-001)
- [ ] **T002** `run_one_ticker` — full pipeline composition
  (features -> estimator -> cost-aware signal -> backtest -> performance
  summary + both baselines), exceptions caught and returned as a structured
  failure rather than propagated. (FR-002)

## Phase 2 — Aggregation

- [ ] **T003** `run_comparison` — loops every ticker independently; one
  failure never stops the rest; returns `(results_frame, failures)`.
  (FR-003, FR-004)
- [ ] **T004** Write output via `data.cache_path` as one CSV. (FR-005)

## Phase 3 — Tests (Rule 5, FR-008), synthetic/network-free data

- [ ] **T005** [P] Isolated-failure case: one ticker too short for a fold;
  others complete; failure named with reason. (SC-001)
- [ ] **T006** [P] All-succeed case: one row per (ticker, strategy), three
  strategies per ticker. (SC-002)
- [ ] **T007** [P] All-fail case: runner completes and reports every
  failure rather than raising on the first. 
- [ ] **T008** [P] Cost-parameter consistency across every row. (SC-003)
- [ ] **T009** [P] CSV round-trip via `cache_path`. (SC-004)

## Phase 4 — Evidence

- [ ] **T010** Mutation check — at minimum: let one ticker's exception
  propagate and stop the loop; silently drop a baseline for one ticker.
  Each must fail at least one test. (SC-005)
- [ ] **T011** Full suite passes; record the new total in this file's PR.
- [ ] **T012** Flag to Camden: confirm the real five-ticker universe before
  the real (non-synthetic) run replaces `docs/PROJECT_CONTEXT.md`'s stale
  AAPL figures.
