# Private candidate inventory

Offline data-collection screening only: no fetch, training, portfolio, broker or execution authority. Keep vendor data/inventories private until publication rights are verified.
Reference CSV: `instrument_id,symbol,asset_type,exchange,listed_on,delisted_on,leveraged,inverse,observed_at,effective_date,source`.
Use sourced immutable IDs, `common_stock`/`etf`, MIC exchanges, ISO dates, aware observations and explicit true/false flags. Observation means actual receipt; never backdate current snapshots. Blank delisting means no known delisting.
Timestamp fields must be valid; other reference contents are validated only for versions visible at the as-of cutoff. Unknown visible classifications are not accepted.
Raw bars CSV: `instrument_id,Date,Close,Volume`. Dates are naive midnight exchange sessions; close is nominal dollars and volume nominal shares. Never relabel adjusted volume as nominal.
All supplied post-listing bars through as-of are validated, including old gaps/malformed rows; only the liquidity median uses the configured trailing window. This does not reconstruct history absent from the input.

EXAMPLE — NOT A RESULT. Choose explicit thresholds for a preregistered future research family; these are not execution limits or proof that smaller stocks are executable:
```text
python scripts/research_universe.py --reference PRIVATE/reference.csv --bars PRIVATE/raw-bars.csv --as-of 2026-10-16 --price-basis raw --min-sessions 252 --min-price 2 --min-dollar-volume 1000000 --out PRIVATE/new-inventory
```
Use a new, exclusive output path per run. Both files are staged beside it before publication; errors leave no inventory and existing targets are refused.
`candidates.csv` retains each visible ID and exclusions. `receipt.json` binds input/output/implementation hashes, policy, run identity, generation date, counts and limitations; stdout repeats the full receipt and its path.
Candidates still need complete OHLCV/actions, independent reconciliation, rights, research and broker acceptance. Current survivor snapshots do not reconstruct historical membership. No edge, promotion or LIVE permission is inferred. No dependency is added.
