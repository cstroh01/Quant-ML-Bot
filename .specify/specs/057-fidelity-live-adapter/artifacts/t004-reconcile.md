# 057 T004 (U2): reconciliation by client id; positions read for 054

Reviewed lane (`exec/`, Rule 7). Fakes only: a fake gate with LiveSafetyGate's two reservation
hooks and a fake adapter. No Fidelity call. EXAMPLE — NOT A RESULT. Stacked on #102 (U1).

## Red
`tests/test_057_reconcile.py` before `exec/fidelity_reconcile.py` existed:
```
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.33s
```

## What it does
- `reconcile(gate, adapter, now)` releases a reservation only on a terminal Fidelity status
  (FILLED/CANCELED/CANCELLED/EXPIRED/REJECTED). No record → `unknown`, failed lookup →
  `status_unavailable`, any other status → `working`; all stay open (FR-006). `HaltProfile` propagates.
- `require_reconciled` refuses any new decision while a reservation is `unknown`/`status_unavailable`.
- `read_holdings(adapter, now, prices, account_fingerprint)` → 054 `PositionsSnapshot` with source
  `fidelity_live_positions`. Quantities come from Fidelity, prices from the caller. Money-market
  sweep symbols are cash at $1. A missing, NaN or non-positive price, or a non-finite or negative
  quantity, refuses (never valued at zero). `holdings_import.SOURCE_CAPABILITIES` declares the
  source for `read_holdings` only (FR-008).

## Rule 12
`python tests/mutation/run_057_t004_mutants.py` → 6/6 killed.
