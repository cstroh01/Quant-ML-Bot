# 054 U2 evidence, 2026-10-08 (Linux, Python 3.13.16)

Red first: `tests/test_054_ownership.py` failed collection (`CapabilityError` absent). Green: 23 passed
(31 with U1). Synthetic snapshots only, EXAMPLE — NOT A RESULT. Mutants planted in a temporary copy by a
throwaway driver outside the repo, running `tests/test_054_*.py`; control: 31 passed.

Decisions taken where the spec was silent:
- Stale means more than 1 NYSE session has opened after the export's New York date
  (`data.trading_days`, no network). Friday evening export: fresh Monday, stale Tuesday.
- Stale or missing holdings refuse every proposed LIVE buy: unknown external exposure has no bound,
  so any buy "could breach". Fresh holdings use 051 `concentration_refusals` (bot + external).
- Bot lots (051) are subtracted from imported quantity; a lot the import cannot cover refuses.
- `Position.currency` defaults to USD: Fidelity's US Positions export has no currency column.

| Mutant | Result |
|---|---|
| missing as_of accepted | killed |
| stale snapshot treated as fresh (threshold 1 -> 2) | killed |
| stale snapshot treated as fresh by the buy guard (cached status) | killed |
| missing holdings read as zero | killed |
| stale exposure replaced by zero | killed |
| stale data checked for concentration instead of refusing | killed |
| external position marked bot-owned | killed |
| read capability accepted for order submit | killed |
| unknown capability label accepted | killed |
| unknown source accepted | killed |
| footer/disclaimer parsed as position | killed |
| money-market sweep counted as a position | killed |
| non-USD row kept | killed |
| bot lots not subtracted (double count) | killed |
| bot lot exceeding import clipped silently | killed |
| calendar days instead of NYSE sessions | killed |
| exchange holidays ignored (weekdays only) | killed |
| session date taken in UTC, not New York | killed |
| future as_of accepted | killed |
| external holdings ignored by fresh guard | killed |
| bot holdings ignored by fresh guard | killed |
