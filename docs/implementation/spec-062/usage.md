# Private candidate inventory

This command only screens data-collection candidates. It never fetches data,
trains a model, selects a portfolio or contacts a broker. Keep vendor files
and generated inventories private until their publication rights are verified.

Reference CSV columns: `instrument_id,symbol,asset_type,exchange,listed_on,delisted_on,leveraged,inverse,observed_at,effective_date,source`.
Use sourced immutable IDs, `common_stock` or `etf`, ISO MIC exchange codes,
ISO dates, aware observation timestamps and explicit true/false product flags.
Observation time is when the reference fact was actually obtained; never
backdate a current snapshot. A blank delisted date means no known delisting.

Raw bars CSV columns: `instrument_id,Date,Close,Volume`. Dates are naive midnight
exchange sessions. Close is raw nominal dollars and volume is nominal shares;
provider-adjusted volume must not be relabeled as nominal.

EXAMPLE — NOT A RESULT. Supply explicit research thresholds appropriate to a
preregistered future research family; these example thresholds are not approved
execution limits or evidence that smaller stocks are executable:

```text
python scripts/research_universe.py --reference PRIVATE/reference.csv --bars PRIVATE/raw-bars.csv --as-of 2026-10-16 --price-basis raw --min-sessions 252 --min-price 2 --min-dollar-volume 1000000 --out PRIVATE/new-inventory
```

The output directory must be new. `candidates.csv` retains every visible ID
and named exclusion. `receipt.json` binds input/output and implementation
hashes, policy, run identity, generation time and limitations. A candidate
still needs full OHLCV/action checks, rights, research and broker acceptance.

The CLI stages both files beside the new output directory before publishing it.
Write/publication errors leave no candidate directory; existing targets are refused.
Use an exclusive output path per run. Stdout repeats the complete receipt and path,
including run/date/hash provenance and limitations. No dependency is added.
