# Contracts: CLI Exit, Tearsheet 503, `data.py` Surface

## 1. `python scripts/ma_crossover_backtest.py [--manifest PATH]`

| Condition | stdout | stderr | Exit | Files written | Trial ledger |
|---|---|---|---|---|---|
| Exactly one valid AAPL bundle (or a valid `--manifest`) | provenance header, trade log, three-row comparison | nothing | 0 | trades CSV and figure under `data/cache/` | one `started` record plus its terminal record, as today |
| No bundle | nothing | `AAPL: unadjusted price data unavailable (missing): <dir searched>` | 1 | none | unchanged |
| More than one bundle | nothing | `... (ambiguous): <sorted paths>` | 1 | none | unchanged |
| A bundle fails any manifest check | nothing | `... (invalid): <check message>` | 1 | none | unchanged |

- `main(argv=None, *, cache_dir=UNADJUSTED_CACHE_DIR)` is the testable
  signature. The `__main__` block converts `UnadjustedDataUnavailable` into
  `SystemExit(str(error))`, which prints the message to stderr and exits with
  status 1.
- **Never:** a call to `download_market_data`, a read of `data/cache/*.csv`, or
  a stale trades CSV or figure overwritten on failure.

## 2. `GET /api/backtest/tearsheet` [D-3]

**503 Service Unavailable**, returned whenever `UnadjustedDataUnavailable` is raised:

```json
{
  "detail": {
    "error": "unadjusted_price_data_unavailable",
    "ticker": "AAPL",
    "reason": "missing | ambiguous | invalid",
    "check": "<message>"
  }
}
```

This follows the precedent at `routes/safety.py:32` (503 for a state that is
not configured). An invalid ticker symbol also returns 503 with
`reason: "invalid"`. It is never looked up on disk. Request-domain 4xx
validation stays with 018 T025.

**200 OK.** The existing `BacktestTearsheetResponse` gains:

| Field | Type |
|---|---|
| `starting_capital` | `float` |
| `liquidate_at_end` | `bool` |
| `source_name` | `str` |
| `downloaded_at_utc` | `str` (ISO, UTC) |
| `capital_gate_eligible` | `bool` |
| `source_limitations` | `list[str]` |
| `source_manifest_sha256` | `str` |

The new fields are additive. `services/api.ts` ignores unknown fields, so the
frontend keeps compiling unchanged.

**Never:** `get_cached_ticker_data` on this route. It stays in `routes/data.py`
for the research views.

## 3. `scripts/data.py` public additions

```python
class UnadjustedDataUnavailable(LookupError): ...          # ticker, reason, check
def resolve_unadjusted_manifest(ticker: str, cache_dir: Path = UNADJUSTED_CACHE_DIR) -> Path: ...
def load_unadjusted_for_ticker(ticker: str, cache_dir: Path = UNADJUSTED_CACHE_DIR,
                               *, manifest_path: Path | None = None) -> pd.DataFrame: ...
```

Unchanged: `load_unadjusted_market_data`, `execution_price_frame`,
`download_market_data`, and every `_validate_*` function.

## 4. `scripts/ma_crossover_backtest.py` public addition

```python
def research_close_signal(nominal: pd.DataFrame, short_window: int, long_window: int) -> pd.DataFrame: ...
```

- **Input:** a frame from `load_unadjusted_for_ticker`.
- **Output:** the same nominal rows and attrs, plus `Buy_Next_Open`,
  `Sell_Next_Open`, `Short_SMA_Research` and `Long_SMA_Research`.
- **Refuses:** anything that `execution_price_frame` refuses.

`baseline_results` and `mean_holding_bars` keep their current signatures (021
contracts §1).
