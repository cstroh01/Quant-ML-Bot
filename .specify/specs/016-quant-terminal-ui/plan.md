# Implementation Plan: Quant-ML-Bot Research & Trading Terminal (UI)

**Spec**: `016-quant-terminal-ui`

## Module Layout

```
Quant-ML-Bot/
├── reports/                      <-- Owns UI, dashboards, tearsheets (Lane C)
│   ├── __init__.py
│   ├── api/                      <-- FastAPI backend bridge
│   │   ├── __init__.py
│   │   ├── main.py               <-- App entrypoint, CORS, static mounting
│   │   ├── schemas.py            <-- Pydantic response/request models
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── data.py           <-- /api/data/* (OHLCV, gaps, stats)
│   │       ├── diagnostics.py    <-- /api/diagnostics/* (VIF, conditioning, tests)
│   │       ├── backtest.py       <-- /api/backtest/* (equity curve, trade log, 3-way table)
│   │       └── capital_gate.py   <-- /api/capital_gate/* (5-gate status)
│   └── web/                      <-- React / TypeScript / Vite frontend
│       ├── package.json
│       ├── vite.config.ts
│       ├── tsconfig.json
│       ├── tailwind.config.js
│       ├── index.html
│       └── src/
│           ├── index.css
│           ├── main.tsx
│           ├── App.tsx
│           ├── types/api.ts
│           ├── services/api.ts
│           ├── hooks/useTerminalData.ts
│           ├── components/
│           │   ├── layout/
│           │   │   ├── Header.tsx
│           │   │   └── TabNavigation.tsx
│           │   ├── common/
│           │   │   ├── StatCard.tsx
│           │   │   ├── AccessibleTable.tsx
│           │   │   └── ColorblindToggle.tsx
│           │   ├── charts/
│           │   │   ├── CandlestickChart.tsx
│           │   │   ├── EquityCurveChart.tsx
│           │   │   └── DrawdownChart.tsx
│           │   └── views/
│           │       ├── MarketDataView.tsx
│           │       ├── FeatureDiagnosticsView.tsx
│           │       ├── CrossValidationView.tsx
│           │       ├── BacktestTearsheetView.tsx
│           │       └── CapitalGateView.tsx
└── tests/
    └── test_reports_api.py       <-- Pytest API suite
```

## Step 1: Python Dependencies & Backend API Bridge
1. Add `fastapi` and `uvicorn` to Python environment.
2. Build `reports/api/schemas.py`: Pydantic models for prices, statistics, feature diagnostics, backtest summary, and capital gate checklist.
3. Build `reports/api/routes/data.py`:
   - Load from `data/cache/` using existing functions in `scripts.data` without touching them.
   - Format bars into Lightweight Charts schema: `{ "time": "YYYY-MM-DD", "open": float, "high": float, "low": float, "close": float, "volume": float }`.
4. Build `reports/api/routes/diagnostics.py`:
   - Expose condition numbers and VIF data.
5. Build `reports/api/routes/backtest.py`:
   - Expose existing AAPL results and on-demand backtests reconciled to $10^{-9}$ tolerance via `scripts.metrics`.
6. Build `reports/api/routes/capital_gate.py`:
   - Expose the 5-Gate status based on repository state.
7. Build `reports/api/main.py`: Assemble routers, CORS, and optional SPA static mounting.

## Step 2: Modern Web Frontend
1. Initialize `reports/web` with Vite, React 19, TypeScript, Tailwind CSS, Lucide icons, and Lightweight Charts.
2. Build responsive dark terminal theme with high-contrast surfaces (`#0A0D12` / `#121721`), monospace tabular numerals, and colorblind-safe toggle.
3. Implement `CandlestickChart.tsx` using `lightweight-charts` with crosshairs and volume histogram.
4. Implement `EquityCurveChart.tsx` and `DrawdownChart.tsx` with peak-to-trough markers.
5. Implement `BacktestTearsheetView.tsx` displaying the 3-way baseline comparison and sortable trade ledger.
6. Implement `FeatureDiagnosticsView.tsx` displaying VIF tables and condition numbers.
7. Implement `CrossValidationView.tsx` with purged/embargoed timeline visualization.
8. Implement `CapitalGateView.tsx` displaying live audit checklist for the 5 Capital Gates.
9. Implement keyboard navigation (`g d`, `g f`, `g c`, `g b`, `g g`, `?`).

## Step 3: Verification & Test Suite
1. Create `tests/test_reports_api.py` validating that endpoints return 200, conform to Pydantic schemas, and match `scripts/metrics.py` calculations.
2. Verify production static build: `npm run build`.
