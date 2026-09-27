# Data Model: Wire Funded-Ledger Callers to the Unadjusted Pipeline

## `UnadjustedDataUnavailable` (new, `scripts/data.py`)

`class UnadjustedDataUnavailable(LookupError)`

| Field | Type | Meaning |
|---|---|---|
| `ticker` | `str` | Canonical upper-case symbol, or the raw input if canonicalization failed |
| `reason` | `Literal["missing", "ambiguous", "invalid"]` | Category |
| `check` | `str` | Human-readable detail: the manifest check message, the matched paths for `ambiguous`, or the directory searched for `missing` |

`str(error)` renders as:

```
{ticker}: unadjusted price data unavailable ({reason}): {check}
```

**Why `LookupError`:** unavailability is "the thing asked for is not there in
usable form". It is not a `ValueError` about the caller's arguments, so a
caller can catch it without also catching validation bugs in its own code.

## Resolver rules

`resolve_unadjusted_manifest(ticker, cache_dir=UNADJUSTED_CACHE_DIR) -> Path`

1. Canonicalize: `ticker.strip().upper()`. It must fully match `[A-Z0-9.-]+`,
   else `invalid`.
2. If `cache_dir` does not exist, the result is `missing`.
3. Match file names against the exact stem regex ([research R-2](research.md#r-2-resolving-a-ticker-to-a-manifest)).
4. Zero matches is `missing`. More than one is `ambiguous`, and the matches
   are listed sorted. Exactly one is returned.

No network access, and nothing is written.

## `load_unadjusted_for_ticker`

`load_unadjusted_for_ticker(ticker, cache_dir=UNADJUSTED_CACHE_DIR, *, manifest_path=None) -> pd.DataFrame`

- If `manifest_path` is given, it is used as-is and the resolver is skipped.
- `FileNotFoundError` or `ValueError` from `load_unadjusted_market_data` becomes
  `invalid`.
- On success, it returns exactly what `load_unadjusted_market_data` returns:
  nominal OHLCV plus `Split`, `Dividend` and `Dividend_Pay_Date`, with
  `price_basis = "unadjusted_dollars"` and the provenance attrs.

## Frame lineage in the crossover

```
bundle (disk)
  └─ load_unadjusted_for_ticker ──► nominal            attrs: price_basis=unadjusted_dollars, provenance
        └─ execution_price_frame ─► research view      + Research_Close, Research_Volume (not funded)
              └─ Close := Research_Close; sma_crossover_signal
                    └─ copy Buy_Next_Open, Sell_Next_Open, *_SMA_Research ──► nominal (funded)
                          ├─ run_backtest (strategy)
                          └─ baseline_results (buy-and-hold, random × 20)
```

**Invariant:** every frame passed to `run_backtest` is the nominal frame, or a
copy of it, with its attrs intact. No adjusted value is present at any point.

## Provenance surfaced to readers (FR-008)

These are taken from the loaded frame's attrs:

- `source_name`
- `source_method`
- `downloaded_at_utc`
- `capital_gate_eligible`
- `source_limitations`
- `source_manifest_sha256`

The CLI prints them in a header block. The API adds them as fields on
`BacktestTearsheetResponse` ([contracts](contracts/cli-and-api.md)).
