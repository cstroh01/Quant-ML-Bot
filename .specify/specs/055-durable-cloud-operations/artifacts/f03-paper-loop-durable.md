# 055 F03 (exec/, Rule 7): PAPER loop order identities and reservations durable before each send

Codex coordination 2026-10-08 23:49 CT, item 5. Fakes only (049 FakeClient with a synthetic
account number, recording persist hook). EXAMPLE — NOT A RESULT. Stacked on #104 → #103 → #101 → #97.

## Red: an inert `Durable` stub on 8279582 (causal assertions, not import errors)
```
E           AssertionError: assert 'b1d569aa6af3...073342c3bca90' == 'qmb-20261005...bf3c0666b2335'
E             + b1d569aa6af3425ab6d073342c3bca90
E       IndexError: list index out of range
_ test_failed_persist_sends_nothing_further_and_releases_the_unsent_reservation _
env = (PosixPath('/tmp/pytest-of-root/pytest-421/test_failed_persist_sends_noth0'), <live_safety_gate.SafetyGate object at 0x7fb68fb14b90>)
    def test_failed_persist_sends_nothing_further_and_releases_the_unsent_reservation(env):
E       AssertionError: assert [OrderIntent(...quantity=2.0)] == []
E         Left contains 3 more items, first extra item: OrderIntent(client_order_id='d27223e2f13b4e18a3a970867b3f77b0', instrument='AAPL', delta_quantity=2.0)
E         Use -v to get more diff
E       Failed: DID NOT RAISE RunAborted
E       AssertionError: assert [OrderIntent(...quantity=2.0)] == []
E         Left contains 3 more items, first extra item: OrderIntent(client_order_id='d403edf8f45642b9b9ba7737aea92fd0', instrument='AAPL', delta_quantity=2.0)
E         Use -v to get more diff
E       Failed: DID NOT RAISE RunAborted
E       assert 0 < 0
FAILED tests/test_055_paper_loop_durable.py::test_client_ids_are_deterministic_per_profile_session_ticker_side
FAILED tests/test_055_paper_loop_durable.py::test_each_send_happens_only_after_its_intent_and_reservation_were_persisted
FAILED tests/test_055_paper_loop_durable.py::test_failed_persist_sends_nothing_further_and_releases_the_unsent_reservation
FAILED tests/test_055_paper_loop_durable.py::test_restart_with_an_unknown_reservation_blocks_new_exposure
FAILED tests/test_055_paper_loop_durable.py::test_restart_after_terminal_statuses_proceeds_without_duplicates
FAILED tests/test_055_paper_loop_durable.py::test_credentials_for_another_account_abort_before_any_order
FAILED tests/test_055_paper_loop_durable.py::test_daily_deployment_counts_earlier_invocations_of_the_same_session
7 failed in 0.49s
```

## Changes (`exec/paper_loop.py`)
- Client ids: `ops_runtime.client_order_id(profile or "default", today, ticker, side)` instead
  of random uuids. A same-session rerun hits the gate's duplicate denial and Alpaca's duplicate
  client-id rejection rather than placing again.
- `Durable(intents_dir, persist)`: the gateway's submit callable (runs only after the gate
  reserved the order) records the intent (session, ticker, side, qty, notional) and calls
  `persist`, and only then calls the broker. A persist failure → `PersistFailed`; the reservation
  is marked terminal `NOT_SENT_PERSIST_FAILED`, and no further order in the run is sent.
- Restart: a submit run aborts if reconciliation leaves any reservation the broker has no record
  of ("unresolved ... reconcile by hand before any new exposure").
- Account: with a profile and a real client, sha256 of the broker's `account_number` must equal
  the profile's `account_fingerprint` (same hash as `make_profiles_json.py`), else abort.
- Daily deployment: today's earlier buy intents (sent or not, conservative) count as
  `deployed_today_usd` for `bound_buys`, across invocations and even with a fresh gate DB.
- CLI `--persist-command`; `--submit --profile` without it aborts before any network call. The
  workflow template passes `bash ops/persist_state.sh <state> intent <profile>`; a test parses
  the workflow command and asserts it.
- `tests/test_051_paper_loop_profile.py`: its broker fake now reports the synthetic account
  number its profile fingerprints (the new check correctly aborted without it).

## Known limits
- `exec/paper_loop.py` is 405 lines (346 before; the ≤300 unit size was already exceeded on #101).
  A split into a `paper_durable` helper module is a follow-up refactor, not done mid-integration.
- A reservation the broker never saw blocks every later submit until a human marks it terminal;
  that is deliberate (unknown is never read as "not sent").

## Storage identifiers (Codex follow-up 2026-10-09)
A profile with `log_namespace='paper_small/../paper_large'` made `state_paths` return paper_large's
gate DB and run log. Now `state_paths` refuses any namespace that isn't a portable single
component (`ops_runtime.require_storage_identifier`), and also any path that doesn't resolve
directly under `data/live_safety`. Lease filenames and `ops_runner.run_once` require the same
identifier for `profile`. `tests/test_055_storage_identifiers.py`: red on 5152d15, 17 failed /
1 passed (the valid-lease control); sibling control `paper_small` resolves separately from
`paper_large`. The 051 load-time rule is on #95 (773251b).

## Integration fix with #95 (Codex, 2026-10-09)
With #95's load-time rule, `dataclasses.replace(SMALL, log_namespace=...)` raised `ProfileError` at
construction, so the old fixture never reached `state_paths` (old file under a #95 overlay:
12 failed, 6 passed). The tests now build a VALID profile and corrupt it afterwards through the named
helper `corrupted()` (copy + `object.__setattr__`), so `state_paths` itself receives the bad value and
must raise `RunAborted` mentioning `log_namespace`; `""` is back in the bad cases. A helper test proves
only the named field changes. Verified on this branch and with #95 (`773251b`) `mode_config.py` and its
tests overlaid in a private copy: 58 and 112 focused tests pass.

## Rule 12
`python tests/mutation/run_055_f03_mutants.py` → 13/13 killed on this branch AND under the #95 overlay.
The driver now counts a kill only as an assertion failure (`exit 1`, summary has "failed" and no
"error"), never a collection or constructor error.
