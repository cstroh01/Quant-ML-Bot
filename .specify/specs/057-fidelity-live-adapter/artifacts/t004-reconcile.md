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

## Codex follow-up (2026-10-08 23:49 CT)
Red on 8944bed: a returned `UNKNOWN` or any unrecognized status counted as working and let
decisions proceed.
```
FAILED tests/test_057_reconcile.py::test_unrecognized_or_unknown_status_blocks_new_decisions[UNKNOWN]
FAILED tests/test_057_reconcile.py::test_unrecognized_or_unknown_status_blocks_new_decisions[unknown]
FAILED tests/test_057_reconcile.py::test_unrecognized_or_unknown_status_blocks_new_decisions[Verifying]
FAILED tests/test_057_reconcile.py::test_unrecognized_or_unknown_status_blocks_new_decisions[]
FAILED tests/test_057_reconcile.py::test_unrecognized_or_unknown_status_blocks_new_decisions[SUSPENDED?]
5 failed, 16 passed in 0.33s
```
Now only an explicit allowlist (`WORKING`: OPEN, ACCEPTED, PENDING, NEW, WORKING, PARTIALLY_FILLED;
spaces normalized to `_`) is working. Anything else is `unrecognized` and blocks; terminal codes
release as before. Controls: OPEN, ACCEPTED, "Partially Filled", pending allow decisions and stay open.

## Rule 12
`python tests/mutation/run_057_t004_mutants.py` → 7/7 killed.
