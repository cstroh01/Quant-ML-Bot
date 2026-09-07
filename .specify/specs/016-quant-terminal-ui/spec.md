# Feature Specification: Quant-ML-Bot Research & Trading Terminal (UI)

**Feature Branch**: `016-quant-terminal-ui`

**Created**: 2026-09-07

**Status**: Draft / In Progress

**Lane**: Lane C (Antigravity)

**Input**: Camden's approval to construct an institutional-grade, accessible web terminal for Quant-ML-Bot that serves as an open-source portfolio centerpiece, an AFML diagnostics viewer, and an interactive auditor for the 5-gate Capital Gate checklist (§12).

**Owns / must not know about** (per CLAUDE.md & Constitution Rule 8):
`reports/` owns all reporting, tearsheet rendering, Web APIs, and UI dashboards. It imports and consumes `scripts.data`, `scripts.metrics`, `scripts.feature_diagnostics`, and `scripts.backtest_harness` as read-only utilities. It must **never** modify any quantitative algorithms, feature definitions, model fitting loops, signal generation rules, or accounting logic in `scripts/`. It has zero access to live broker credentials or order routing (`exec/`).

---

## Background & Motivation

Quant-ML-Bot has established an institutional quant pipeline adhering to Marcos López de Prado's *Advances in Financial Machine Learning* (AFML):
- Purged and embargoed walk-forward cross-validation ([Rule 2](file:///C:/GitHub/Quant-ML-Bot/.specify/memory/constitution.md#L48-L69)).
- Mandatory friction modeling (commissions + slippage) ([Rule 3](file:///C:/GitHub/Quant-ML-Bot/.specify/memory/constitution.md#L71-L89)).
- Mandatory 3-way baseline comparisons against Buy & Hold and Random Signals ([Rule 4](file:///C:/GitHub/Quant-ML-Bot/.specify/memory/constitution.md#L91-L107)).
- Scale-free feature matrix conditioning and paired significance testing (Spec 014).

However, exploring results currently requires running standalone scripts in the terminal and viewing static PNG plots in `plots/` or inspecting CSV logs.

To achieve Camden's long-term vision (**Project Instructions v2.1 §12**), the bot requires a unified, modern web console that makes these quantitative and statistical insights accessible, transparent, and verifiable without adding comprehension debt.

---

## Architectural Guardrails & Non-Negotiables

1. **Strict Read-Only Decoupling ([Rule 8](file:///C:/GitHub/Quant-ML-Bot/.specify/memory/constitution.md#L153-L165))**:
   - `reports/api/` reads existing cached data (`data/cache/*.csv`) and invokes calculation functions in `scripts/metrics.py` without mutating state.
   - Zero modifications to `scripts/*.py`.
2. **Public Framework vs. Private Edge Compliance (§12)**:
   - Operates fully on public cached datasets (AAPL, AMZN, GOOGL, MSFT, NVDA) and baseline strategies.
   - Zero hardcoded API keys or live broker credentials.
3. **Accessibility (WCAG 2.1 AA)**:
   - Keyboard navigation shortcuts (`g d`, `g f`, `g c`, `g b`, `g g`).
   - Colorblind-safe palette mode for P&L (Cyan/Amber toggle alongside Emerald/Rose).
   - Tabular fallbacks (`View as Table`) for every canvas/SVG chart.
4. **Performance**:
   - TradingView Lightweight Charts handles 10+ years of daily OHLCV bars at 60 FPS.
   - Fast client bundle built with Vite + React 19 + TypeScript.

---

## Functional Requirements

- **FR-001 (Market Ingestion & Session Inspector)**: Render interactive candlestick (OHLCV) and volume charts for cached tickers. Display NYSE calendar missing-bar gaps (FR-009) and return statistics (annualized vol, skewness, excess kurtosis).
- **FR-002 (Backtest Tearsheet & Cost Transparency)**: Display the reconciled per-bar equity curve alongside drawdown underwater area charts. Display the mandatory 3-way baseline comparison table (Strategy vs Buy & Hold vs Random Signal) with explicit commission ($1.00) and slippage (5 bps) figures.
- **FR-003 (Feature & Matrix Diagnostics Lab)**: Render VIF scores, condition number comparisons (comparing `levels` vs `scale_free`), and feature correlation matrices. Show paired significance test outcomes (McNemar and Wilcoxon signed-rank).
- **FR-004 (Walk-Forward CV Explorer)**: Visually represent expanding train windows, purge zones, and embargo gaps across time folds.
- **FR-005 (Capital Gate Audit Cockpit)**: Interactive status board auditing the 5 Capital Gates (§12) with verification indicators.
- **FR-006 (FastAPI Bridge)**: Type-safe REST API in `reports/api/` serving cached market data, diagnostics, and backtest results.
- **FR-007 (Standalone Static Serving)**: FastAPI optionally serves the production-compiled frontend assets from `reports/web/dist` on a single port for zero-Node deployment.

---

## Dependency Justifications ([Rule 6](file:///C:/GitHub/Quant-ML-Bot/.specify/memory/constitution.md#L127-L135))

- `fastapi` & `uvicorn`: Required to provide non-blocking asynchronous REST/SSE endpoints and OpenAPI documentation; Python's standard library `http.server` lacks async I/O, route decorators, and schema validation.
- `pydantic`: Required for strict type-validation of quantitative API payloads.
- Frontend packages (`react`, `vite`, `tailwindcss`, `lightweight-charts`, `lucide-react`, `@radix-ui/*`): Isolated inside `reports/web/package.json`; does not affect Python environment or CI quant runs.
