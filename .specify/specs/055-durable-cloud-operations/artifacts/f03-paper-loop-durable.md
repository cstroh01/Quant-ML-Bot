# 055 F03a (exec/, Rule 7): deterministic ids, account binding, restart block (split 1 of 3 from #107)

Split from #107 (`8316d6e`) to meet the ≤300 changed-line unit cap (044 SC-007 / 045 FR-005).
Stack: F02b3 (tree == #104) → F03a (this) → F03b durable send → F03c storage identifiers; F03c's
tree equals #107's. Fakes only (049 FakeClient with a synthetic account number). EXAMPLE — NOT A RESULT.

## Changes (`exec/paper_loop.py`)
- Client ids: `ops_runtime.client_order_id(profile or "default", today, ticker, side)` instead of
  random uuids; a same-session rerun is denied by the gate's duplicate check.
- Restart: a submit run aborts while reconciliation leaves any reservation the broker has no record
  of ("unresolved ... reconcile by hand before any new exposure").
- Account: with a profile and a real client, sha256 of the broker's `account_number` must equal the
  profile's `account_fingerprint` (same hash as `make_profiles_json.py`), else abort before any order.
- `tests/test_051_paper_loop_profile.py`: its broker fake reports the synthetic account its profile
  fingerprints (the new check correctly aborted without it).

## Red
Recorded on #107 against an inert stub on 8279582: random ids, no restart block, wrong account
accepted (causal assertion failures, not import errors).

## Rule 12
`python tests/mutation/run_055_f03_mutants.py` → 3/3 killed (random ids, unknown reservations
ignored, account not verified).
