# Tasks — 016 Quant-ML-Bot Research & Trading Terminal (UI)

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Backend API Bridge (`reports/api/`)

- [x] **T001** Install `fastapi` and `uvicorn` in virtual environment. Justify in PR per Rule 6.
- [x] **T002** Create `reports/__init__.py` and `reports/api/__init__.py`.
- [x] **T003** Create `reports/api/schemas.py` with Pydantic models: `BarData`, `MarketStatsResponse`, `CollinearityResponse`, `BacktestSummaryResponse`, `CapitalGateStatus`.
- [x] **T004** Implement `reports/api/routes/data.py` providing `/api/data/tickers`, `/api/data/ohlcv`, `/api/data/gaps`, `/api/data/stats`.
- [x] **T005** Implement `reports/api/routes/diagnostics.py` providing `/api/diagnostics/collinearity` and `/api/diagnostics/significance`.
- [x] **T006** Implement `reports/api/routes/backtest.py` providing `/api/backtest/baseline` and `/api/backtest/run`.
- [x] **T007** Implement `reports/api/routes/capital_gate.py` providing `/api/capital_gate/status`.
- [x] **T008** Implement `reports/api/main.py` configuring FastAPI, CORS middleware, and route registrations.
- [x] **T009** Create `tests/test_reports_api.py` validating API responses, schema conformity, and metric reconciliation.

---

## Phase 2 — Modern Web Terminal (`reports/web/`)

- [x] **T010** Initialize `reports/web` with Vite, React 19, TypeScript, Tailwind CSS, Lucide icons, and `lightweight-charts`.
- [x] **T011** Configure Tailwind theme (`#0A0D12` background, `#121721` surfaces, tabular font-mono, custom scrollbars).
- [x] **T012** Implement API client service in `reports/web/src/services/api.ts` and React state hooks.
- [x] **T013** Build terminal layout: `Header.tsx` (ticker selector, system status, colorblind mode toggle) and `TabNavigation.tsx`.
- [x] **T014** Implement `CandlestickChart.tsx` using `lightweight-charts` with OHLCV bars, volume sub-pane, and crosshairs.
- [x] **T015** Implement `EquityCurveChart.tsx` and `DrawdownChart.tsx` for cumulative returns and underwater drawdowns.
- [x] **T016** Implement `BacktestTearsheetView.tsx` with the mandatory 3-way baseline table (Strategy vs Buy & Hold vs Random) and sortable trade ledger.
- [x] **T017** Implement `FeatureDiagnosticsView.tsx` with condition number gauges, VIF comparison tables, and correlation matrix.
- [x] **T018** Implement `CrossValidationView.tsx` with interactive purged/embargoed walk-forward timeline visualizer.
- [x] **T019** Implement `CapitalGateView.tsx` with the 5 Capital Gates live audit checklist and evidence links.
- [x] **T020** Implement keyboard shortcuts (`g d`, `g f`, `g c`, `g b`, `g g`, `?`) and accessible tabular view fallbacks.

---

## Phase 3 — Integration, Static Build & Verification

- [x] **T021** Run backend API test suite `pytest tests/test_reports_api.py` and ensure 100% pass.
- [x] **T022** Build production bundle in `reports/web` (`npm run build`) and configure FastAPI static mount.
- [x] **T023** Perform end-to-end manual verification of all views and interactions.
