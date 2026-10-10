# Research: spec 035 candidate sources (T002)

**Compiled**: 2026-10-10, cloud lane (queue Q36), from the tree at `5f20d98`.
**Input**: the T001 records merged in PR #127 only: `docs/implementation/spec-035/fr001-tiingo-20261009.md`,
`fr001-alpaca-20261009.md`, `fr001-eodhd-20261009.md` (and their `README-20261009.md`). The yfinance
row cites 044's evidence, as T002 directs. Nothing here was fetched, re-derived or inferred beyond
those records. No price, ratio or amount is published, because the records publish none.

**This file decides nothing.** D-1 to D-4 are recorded in spec §8 (2026-10-09). Where a row below
bears on a recorded decision, the consequence is listed at the end for review, not acted on.

## Checklist

### A. Fields every T001 record must carry (FR-001; T001 acceptance)

- A1 `source`, and `fetched_at` as a UTC timestamp (`+00:00`).
- A2 `windows` containing AAPL with split `2020-08-31` and NVDA with split `2024-06-10`.
- A3 every request: `endpoint_path`, `parameters`, `requested_at_utc`; no parameter named like a key,
  token, secret or auth header (FR-003).
- A4 `observations` answering every §3 question: `nominal_or_adjusted_ohlc`, `split_dividend_fields`,
  `corporate_action_history_depth`, `dividend_amount_basis`, `coverage_start`. Each has a `state`;
  an `UNVERIFIED` state carries a non-empty `reason`.

### B. Rules every row below must meet (T002 acceptance; Rule 11)

- B1 One row per spec §3 row, in §3's order and naming §3's candidate, with claim, observation,
  state, date and evidence.
- B2 The state is one of the four below. An `OBSERVED` or `PARTIAL` row cites only its own source's
  T001 record, as `file#key`; that key exists in the record with a state other than `UNVERIFIED`, and
  the row's date equals the record's `fetched_at` date. An `OBSERVED` row leaves no part of its claim
  unestablished. Only the yfinance row may be `ESTABLISHED`, citing 044's evidence.
- B3 An `UNVERIFIED` row states why.
- B4 No figure appears without a cited record. Vendor claims are quoted with their `SCOPE-V1.md` line.

States: `OBSERVED` (every part of the claim has a cited observation), `PARTIAL` (some parts do; the
rest are named UNVERIFIED in the row), `ESTABLISHED` (cited non-T001 evidence T002 names),
`UNVERIFIED`.

## Rows (spec §3, in order)

| # | Role, candidate | Claim (source) | Observation | State | Date | Evidence |
|---|---|---|---|---|---|---|
| 1 | Primary bars, Tiingo EOD (free key) | 30+ years; 1,000 requests/day; 500 symbols/month (`SCOPE-V1.md:179`) | Provider metadata `startDate` is 1980-12-12 for AAPL and 1999-01-22 for NVDA. The record calls this metadata, not an observed free-tier entitlement to full history, so the 30-year claim stays UNVERIFIED. The request and symbol limits are UNVERIFIED (not observed). Whether the key used was a free key is not stated in the record. | PARTIAL | 2026-10-09 | `fr001-tiingo-20261009.md#coverage_start` |
| 2 | Primary bars, Tiingo EOD | Whether `open/high/low/close` are nominal; whether split and dividend fields exist (`SCOPE-V1.md:179`; tension with `:49`) | `close` is labelled NOMINAL across both splits (AAPL 2020-08-31, NVDA 2024-06-10). `open`, `high` and `low` basis is not established. The EOD prices response carries `divCash` and `splitFactor` fields; their values and history depth are not established. This is the prices endpoint, so the `:49` claim about the corporate-actions API is neither confirmed nor refuted. Dividend amount basis is UNVERIFIED. | PARTIAL | 2026-10-09 | `fr001-tiingo-20261009.md#nominal_or_adjusted_ohlc`; `fr001-tiingo-20261009.md#split_dividend_fields` |
| 3 | Second source, Alpaca Basic (free key) | Daily bars since 2016; 200 requests/min (`SCOPE-V1.md:180`) | Raw SIP daily bars were returned (HTTP 200) for AAPL and NVDA over 2016-01-04 to 2016-01-08. The record keeps coverage start UNVERIFIED: a requested window is not provider coverage. The rate limit was not observed. Whether the key used was a Basic-plan key is not stated in the record. | UNVERIFIED | 2026-10-09 | Reason: the cited record's `coverage_start` is UNVERIFIED and no rate limit was observed. The 2016 request is in `fr001-alpaca-20261009.md` `requests`. |
| 4 | Second source, Alpaca | Corporate-action history depth; whether bars can be requested raw (`SCOPE-V1.md:180`) | `adjustment=raw` close is labelled NOMINAL across both splits; `adjustment=all` is labelled ADJUSTED for both. The corporate-actions endpoint, asked for splits and cash dividends, returned forward-split rows with `ex_date`, `old_rate`, `new_rate` and `payable_date` fields. **No cash-dividend field was observed** in either window. History depth and dividend amount basis are UNVERIFIED. | PARTIAL | 2026-10-09 | `fr001-alpaca-20261009.md#nominal_or_adjusted_ohlc`; `fr001-alpaca-20261009.md#split_dividend_fields` |
| 5 | Cross-check, EODHD free | Splits and dividends with `paymentDate`, capped at 1 year (`SCOPE-V1.md:49`, verified 2026-09-25) | The dividend response for NVDA carries `paymentDate` and `unadjustedValue`; the AAPL dividend response had no rows; the split responses carry `split`. Each EOD price request returned one row per symbol with a `warning` field, which the record says does not establish the window or free history entitlement. The 2026-09-25 verification has no T001 record, so the 1-year cap is not re-observed here. | PARTIAL | 2026-10-09 | `fr001-eodhd-20261009.md#split_dividend_fields` |
| 6 | Cross-check, yfinance `auto_adjust=False` | Split-adjusted despite the flag (044 §1) | `history(auto_adjust=False)` returned pre-split Open and Close already split-adjusted for AAPL; the split check refused the 4:1 action. Dividend and volume basis are not established there. | ESTABLISHED | 2026-09-30 | `.specify/specs/044-nominal-price-reconstruction/spec.md#1` (from `.specify/specs/041-dividend-pay-date-bound/artifacts/aapl-bundle.txt`) |
| 7 | Cross-check, SEC EDGAR | Spot checks of individual splits from filings (`V1-FINISH-PLAN.md:66-67`) | No recorded split spot-check exists. `044 artifacts/split-table-crosscheck.md` is a draft extracted by a summarizing fetch tool and awaits a person's confirmation; `docs/implementation/spec-044/t006-sec-edgar-20261009.json` retrieves and hashes a 2013 10-K and is marked PARTIAL; it records nothing about any split. | UNVERIFIED | — | Reason: no confirmed split spot-check record. |

Evidence paths without a directory are under `docs/implementation/spec-035/`.

## Not covered by any T001 record (stay UNVERIFIED)

- Dividend amount basis, for every source (each record: `dividend_amount_basis` UNVERIFIED).
- Corporate-action history depth, for every source.
- EODHD history depth and free entitlement (`README-20261009.md`).
- Any SEC EDGAR split spot-check (row 7).
- Any observation for an instrument other than AAPL and NVDA, including the spec 058 ETF universe.
- Publication rights for derived results (each record's `rights_note`).

## Consequences for later tasks (for review; nothing here changes a decision)

1. **D-1 and FR-004.** D-1 names Alpaca as the second source, and FR-004 reconciles dividends against
   it. No Alpaca cash-dividend field has been observed (row 4). T013 requires "the D-1 source's
   `research.md` row is verified"; rows 3 and 4 are not. T013 cannot meet that acceptance until a
   further FR-001 observation records Alpaca dividends.
2. **T015.** Tiingo `close` is NOMINAL across both splits (row 2), but `open`, `high` and `low` are not
   established. Whether that meets "free EOD bars as nominal across both splits" is for T015's
   reviewer; this file does not void or un-void it.
3. **Retarget.** Every observation is for AAPL and NVDA. None covers an ETF from spec 058 §4.
4. **Same window, two sources.** Over the same NVDA window (2024-06-03 to 2024-06-17), the EODHD
   dividend request returned one row (`fr001-eodhd-20261009.md`, `requests`), while the Alpaca
   corporate-actions request, which asked for `cash_dividend`, returned only forward-split rows
   (`fr001-alpaca-20261009.md`, `requests`). The records do not say why. This bears on D-1 and
   FR-004 and is listed for review, not resolved here.
