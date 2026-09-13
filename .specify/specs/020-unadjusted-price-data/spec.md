# Feature Specification: Unadjusted Price Data and Corporate Actions

**Feature Branch**: `020-unadjusted-price-data`  
**Specification File**: `.specify/specs/020-unadjusted-price-data/spec.md`  
**Created**: 2026-09-12  
**Status**: Draft / Ready for Review  
**Authority**: Audit 2026-09-12 Work Orders 2 & 3; Findings 13, 14, 15, 21. Feeds the frozen execution-price and corporate-action contract defined in `.specify/specs/019-funded-ledger-and-timing/spec.md`.

---

## 1. Context & Problem Statement

`scripts/backtest_harness.py` raises `ValueError("funded ledger requires declared unadjusted dollar prices")` unless prices carry `attrs["price_basis"] == "unadjusted_dollars"`. Similarly, `scripts/data.py:execution_price_frame` raises `ValueError("verified unadjusted dollar prices required")`.

The repository's only cache (`data/cache/AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv`) was downloaded via `yfinance.download(..., auto_adjust=True)`. In that cache, historical prices are retrospectively divided by dividend and split adjustment factors. `scripts/data.py:_tidy` stamps these with `price_basis = "research_adjusted"`. Consequently, **no data in this project can satisfy the backtest guard, and the backtester is completely unrunnable**.

This specification defines the ingestion, validation, storage, and anti-forgery layer that fetches and persists raw unadjusted prices and corporate actions for `["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]`.

---

## 2. Universe & Survivorship Bias

### 2.1 Universe
Target universe is fixed to:
```python
UNIVERSE = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]
```

### 2.2 Survivorship Bias Handling
- **Retrospective Winner Selection**: The universe is defined as of 2026. All five constituents are mega-cap technology winners that survived and compounded over the 10-year period (2016–2026). Companies that suffered bankruptcy, distress, or delisting over this decade are absent.
- **Harness / Smoke-Test Boundary**: In accordance with Audit Finding 21, this basket is strictly a **computational smoke-test panel and accounting harness**, not an investable alpha universe. Backtest results across this panel cannot be cited as evidence of generalizable equity strategy alpha.
- **Mandatory Metadata Tag**: All dataset manifests, cache records, and downstream reports must explicitly declare:
  `"universe_policy": "static_survivor_basket"`
- **Forward Extensibility**: The schema separates universe membership from bar series so dynamic point-in-time constituent tables `(Date, Ticker, is_member)` can be attached in future milestones without changing bar schemas.

---

## 3. Data Contract, Provenance & Point-in-Time Guarantees

### 3.1 Raw Unadjusted OHLCV (`raw_ohlcv`)
Stores historical trades in nominal dollar units as transacted on the exchange.

| Column | Type | Unit | Provenance | Point-in-Time Guarantee |
|---|---|---|---|---|
| `Date` | `datetime64[ns]` | Naive ISO session (`YYYY-MM-DD`) | Exchange calendar | Normalized trading day; denotes session, not an instant. |
| `Ticker` | `string` | Canonical uppercase symbol | Request list | Fixed symbol identifier. |
| `Open` | `float64` | Historical nominal USD | Opening auction fill (`auto_adjust=False`) | Knowable at the market open auction of `Date`. Executable fill for next-open entry. |
| `High` | `float64` | Historical nominal USD | Intraday exchange high | Knowable strictly after session close of `Date`. |
| `Low` | `float64` | Historical nominal USD | Intraday exchange low | Knowable strictly after session close of `Date`. |
| `Close` | `float64` | Historical nominal USD | Closing auction fill | Knowable strictly after session close of `Date`. |
| `Volume` | `float64` | Nominal share count | Consolidated tape | Knowable strictly after session close of `Date`. |

**Invariants**: Finite positive prices (`> 0.0`); `Low <= Open <= High`; `Low <= Close <= High`; `Volume >= 0.0`; `(Date, Ticker)` unique and sorted ascending by `Ticker`, then `Date`.

### 3.2 Corporate Actions (`corporate_actions`)
Stored in a separate table to isolate corporate capital restructurings from market transactions.

| Column | Type | Unit | Provenance | Point-in-Time Guarantee |
|---|---|---|---|---|
| `Date` | `datetime64[ns]` | Naive session (`YYYY-MM-DD`) | Regulatory filings / exchange | **Ex-date**: the exact session the event becomes effective. |
| `Ticker` | `string` | Canonical symbol | Request list | Fixed symbol identifier. |
| `Split` | `float64` | Multiplier: new shares / old share | Issuer filing / vendor actions feed | **Effective before the market opens on `Date`**. 1.0 means no split. A 4:1 split is 4.0; a 1:2 reverse split is 0.5. Finite and $> 0.0$. |
| `Dividend` | `float64` | Nominal USD / post-split share | Issuer filing / vendor actions feed | **Entitlement determined before open on `Date`** for positions held overnight from `Date - 1`. Becomes an unspendable receivable at open of `Date`. Finite and $\ge 0.0$. |
| `Dividend_Pay_Date` | `datetime64[ns]` | Naive session (`YYYY-MM-DD`) | Issuer declaration notice | **Payment date**: session cash is credited to buying power. Must satisfy `Dividend_Pay_Date >= Date`. Required (non-null) if `Dividend > 0`. |

**Spec 019 Contract Alignment**:
- Splits adjust share quantity before the open on `Date`.
- Dividends accrue as account receivables on `Date` open and convert to cash strictly on session `Dividend_Pay_Date`.

---

## 4. On-Disk Schema & Anti-Forgery Stamping

### 4.1 Storage Layout
Unadjusted data is isolated in a dedicated subdirectory to prevent collisions:
```
data/cache/
├── legacy_adjusted/                 # Quarantined auto-adjusted caches
│   └── AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv
└── unadjusted/                      # Unadjusted store
    ├── universe_5_10y_raw_ohlcv.csv # Raw nominal bars
    ├── universe_5_10y_actions.csv   # Corporate actions table
    └── universe_5_10y.manifest.json # Cryptographic provenance manifest
```

### 4.2 Manifest Schema (`universe_5_10y.manifest.json`)
```json
{
  "manifest_version": 1,
  "created_at_utc": "2026-09-12T21:30:00Z",
  "provider": "yfinance",
  "download_params": {
    "auto_adjust": false,
    "actions": true,
    "period": "10y"
  },
  "universe": ["AAPL", "AMZN", "GOOGL", "MSFT", "NVDA"],
  "universe_policy": "static_survivor_basket",
  "price_basis": "unadjusted_dollars",
  "files": {
    "raw_ohlcv": {"path": "universe_5_10y_raw_ohlcv.csv", "sha256": "..."},
    "corporate_actions": {"path": "universe_5_10y_actions.csv", "sha256": "..."}
  }
}
```

### 4.3 Anti-Forgery Protection
Because pandas DataFrame `attrs` are not preserved across CSV serialization, `attrs["price_basis"] = "unadjusted_dollars"` must be applied at load time. To ensure an adjusted frame can **never be forged** onto an unadjusted basis:

1. **Cryptographic Checksum Gate**: The loader checks SHA-256 hashes of CSV files against the locked manifest.
2. **Historical Price Level Assertion**: Historical nominal baselines are enforced (e.g., AAPL traded at $\sim\$105$ in September 2016, whereas adjusted AAPL is $\sim\$25$; the loader asserts pre-2020 AAPL close $> \$80.00$).
3. **Split Discontinuity Oracle**: In unadjusted data, a stock split of ratio $S$ creates a discrete nominal jump across the ex-date:
   $$\frac{\text{Close}[t-1]}{\text{Open}[t]} \approx S$$
   In adjusted data, this ratio is smoothed to $\approx 1.0$. The loader checks known splits (e.g., AAPL 4:1 on 2020-08-31; NVDA 10:1 on 2024-06-10; GOOGL 20:1 on 2022-07-18; AMZN 20:1 on 2022-06-06). If the ratio across the split date fails to match the split ratio within $\pm 15\%$ market drift, the loader rejects the frame with `ValueError("Adjusted data detected: split step discontinuity absent")`.
4. **Single Blessed Entry Point**: Only `load_unadjusted_market_data()` in `scripts/data.py` performs these verifications and attaches `attrs["price_basis"] = "unadjusted_dollars"`. Generic loaders and `_tidy` cannot apply this stamp.

---

## 5. Migration Path for Existing Auto-Adjusted Cache

1. **No Algorithmic "Reverse-Adjustment"**:
   Reconstructing unadjusted prices by compounding adjusted data with historical action series introduces compounding rounding errors, vendor formula discrepancies, and missing payment dates. Reverse adjustment is strictly forbidden.
2. **Quarantine Legacy Caches**:
   Existing cache files (`AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv`, `AAPL_2y.csv`) are moved to `data/cache/legacy_adjusted/`. Their loader path remains available for legacy statistical baselines and continues to return `attrs["price_basis"] = "research_adjusted"`.
3. **Dedicated Ingestion Function**:
   `download_unadjusted_market_data()` in `scripts/data.py` downloads raw data with `auto_adjust=False, actions=True`, builds the split and dividend tables with payment dates, writes atomic temp files, and saves the data and manifest to `data/cache/unadjusted/`.
4. **Causal Bridge to Research Series**:
   `scripts/data.py:execution_price_frame` consumes the verified unadjusted frame and corporate actions, outputting:
   - Unadjusted `Open`, `Close` for execution in `run_backtest`.
   - `Research_Close` (causally forward-compounded total-return index) for ML feature and target construction.

---

## 6. Pre-Implementation Validation Tests (Red Evidence)

The following tests in `tests/test_020_unadjusted_data.py` must fail against the current codebase and pass once Spec 020 is implemented:

### Test 1: Cold unadjusted load fails cleanly
- **Assertion**: Calling `load_unadjusted_market_data()` when cache is missing raises `FileNotFoundError` or triggers a governed download.
- **Pre-implementation failure**: `AttributeError: module 'data' has no attribute 'load_unadjusted_market_data'`.

### Test 2: Legacy adjusted cache rejected for unadjusted basis
- **Assertion**: Passing `data/cache/AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv` to the unadjusted loader raises `ValueError` and refuses to stamp `unadjusted_dollars`.
- **Pre-implementation failure**: Unadjusted loader does not exist; existing `_tidy` outputs `research_adjusted`.

### Test 3: Anti-forgery catches forged adjusted frames via split discontinuity
- **Assertion**: An adjusted frame without the AAPL 2020-08-31 split price jump (where $\text{Close}[t-1] / \text{Open}[t] \approx 1.0 \ne 4.0$) fails the split discontinuity oracle.
- **Pre-implementation failure**: Split jump validator does not exist.

### Test 4: Corporate actions contract validation
- **Assertion**: Action validator rejects non-positive splits (`Split <= 0`), negative dividends (`Dividend < 0`), null payment dates (`NaT`) when `Dividend > 0`, and payment dates preceding ex-dates (`Dividend_Pay_Date < Date`).
- **Pre-implementation failure**: Actions validator does not exist.

### Test 5: End-to-end backtester execution unblocked
- **Assertion**: Loading unadjusted data for `AAPL` via `load_unadjusted_market_data()`, passing through `execution_price_frame()`, and running `backtest_harness.run_backtest()` succeeds without raising `ValueError`.
- **Pre-implementation failure**: Raises `ValueError: funded ledger requires declared unadjusted dollar prices`.

---

## 7. Open Questions

1. **Vendor Historical Dividend Payment Date Availability**:
   Yahoo Finance's `yf.Ticker.actions` provides dividend amounts on ex-dates, but historical payment dates are often omitted or only available for the latest upcoming dividend.
   - *Question*: For the 10-year historical panel, if `yfinance` lacks historical payment dates, which source will provide them? Options:
     - (a) Querying SEC EDGAR / company investor relations filings.
     - (b) Sourcing from a secondary API (e.g., Alpaca Corporate Actions or Polygon.io).
     - (c) A curated, immutable historical payment date table committed for the 5 tickers.
2. **Vendor Dividend Nominal Representation (Pre- vs Post-Split)**:
   Vendors differ in whether historical per-share dividends are reported in nominal dollars as of the ex-date or retroactively split-adjusted. Spec 019 requires "dollars per post-split share".
   - *Question*: Does yfinance with `auto_adjust=False` report pre-split or post-split dividend amounts? The ingestion suite must verify this convention against primary filings.
3. **Missing Sessions and Halts on Action Dates**:
   If an exchange halt delays trading on an ex-date or payment date, how should the join align? Spec 019 specifies payment occurs on the stated session or first observed session thereafter; the data layer must verify this alignment.
4. **On-Disk Format Evolution**:
   While CSV is the repo convention, it lacks native metadata.
   - *Question*: Should the unadjusted store adopt Apache Parquet in a subsequent spec to natively embed cryptographic hashes and schema metadata directly in file headers?
