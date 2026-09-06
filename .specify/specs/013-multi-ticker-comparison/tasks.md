# Tasks — 013 Multi-Ticker Comparison Table

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Universe and per-ticker runner

- [ ] **T001** `TICKER_UNIVERSE` — explicit named constant,
  `["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]`. Already decided; not a
  placeholder. (FR-001)
- [ ] **T002** `run_one_ticker` — full pipeline composition
  (features -> estimator -> cost-aware signal -> backtest -> performance
  summary + both baselines), exceptions caught and returned as a structured
  failure rather than propagated. (FR-002)

## Phase 2 — Aggregation

- [ ] **T003** `run_comparison` — loops every ticker independently; one
  failure never stops the rest; returns `(results_frame, failures)`.
  (FR-003, FR-004)
- [ ] **T004** Mandatory honesty columns: `Median hurdle (bps)` and
  `|pred| q90 (bps)` on every ML row, plus fold count, purge, embargo,
  commission, slippage, capital base, `random_state`, and the random
  baseline's seed count and dispersion. (FR-005)
- [ ] **T005** Write output via `data.cache_path` as one CSV with a
  ticker-namespaced filename — the existing
  `phase2_logistic_baseline_results.csv` is not namespaced and a naive loop
  would overwrite it per ticker. (FR-006)
- [ ] **T006** End-to-end `main()` three-way comparison per ticker
  (cost-aware ML vs. buy-and-hold vs. random), reusing
  `ma_crossover_backtest.baseline_results` and `mean_holding_bars` rather
  than duplicating them. Absorbed here from spec 012, which would otherwise
  build a single-ticker runner one spec before this replaces it.

## Phase 3 — Tests (Rule 5, FR-009), synthetic/network-free data

- [ ] **T007** [P] Isolated-failure case: one ticker too short for a fold;
  others complete; failure named with reason. (SC-001)
- [ ] **T008** [P] All-succeed case: one row per (ticker, strategy), three
  strategies per ticker. (SC-002)
- [ ] **T009** [P] All-fail case: runner completes and reports every
  failure rather than raising on the first. 
- [ ] **T010** [P] Cost-parameter consistency across every row. (SC-003)
- [ ] **T011** [P] CSV round-trip via `cache_path`. (SC-004)

## Phase 4 — Evidence

- [ ] **T012** Mutation check — at minimum: let one ticker's exception
  propagate and stop the loop; silently drop a baseline for one ticker.
  Each must fail at least one test. (SC-005)
- [ ] **T013** Full suite passes; record the new total in this file's PR.
- [ ] **T014** Prerequisite (Camden, not an agent): the 10-year download,
  since the agent lane cannot reach Yahoo.

  ```powershell
  ./venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'scripts'); from data import download_market_data; download_market_data(['AAPL','MSFT','GOOGL','NVDA','AMZN'], period='10y')"
  ```

  Writes `data/cache/AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv` (the cache key is
  sorted and deduped — `data.py:253-259`). The runner must fail with a
  message naming this exact command when the cache is absent.
- [ ] **T015** Replace `docs/PROJECT_CONTEXT.md`'s spec-005 AAPL figures with
  the real run's, and state plainly what the cost-hurdle result means.
