# 055 F03a–F03b (exec/, Rule 7): ids, account, restart; durable send (splits 1–2 of 3 from #107)

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

- **F03b:** `Durable(intents_dir, persist)`. The gateway's submit callable (runs only after the gate
  reserved the order) records the intent (session, ticker, side, qty, notional), calls `persist`,
  and only then calls the broker. A persist failure → `PersistFailed`: the reservation is marked
  terminal `NOT_SENT_PERSIST_FAILED` and no further order in the run is sent.
- **F03b:** today's earlier buy intents (sent or not) count as `deployed_today_usd` for
  `bound_buys`, across invocations and even with a fresh gate DB.
- **F03b:** CLI `--persist-command`; `--submit --profile` without it aborts before any network call.
  The workflow passes `bash ops/persist_state.sh <state> intent <profile>`; a test parses the line.

## Red
Recorded on #107 against an inert stub on 8279582: random ids, sends with nothing persisted, a persist failure still sending, no restart block,
wrong account accepted, deployed notional read as 0 (causal assertion failures, not import errors).

## Rule 12
`python tests/mutation/run_055_f03_mutants.py` → 9/9 killed (F03a's 3 plus send before persist,
intent not recorded, persist failure keeps sending, unsent reservation kept open, earlier
deployment ignored, CLI submits without persist).

## F03c: storage identifiers and assertion witnesses (split 3/3)
- `state_paths` refuses any `log_namespace` that isn't one portable component, and any path not
  directly under `data/live_safety`. Lease filenames and `ops_runner.run_once` refuse non-identifier
  profiles. Red on 5152d15: 17 of 18 new storage cases failed.
- Integration with #95: the tests corrupt a VALID profile after construction (`corrupted()`), so
  `state_paths` itself receives the bad value. Under #95's validation, the old `replace()` fixture
  failed at construction (12 failed / 6 passed).
- **Correction (Codex):** the 4074fc6 claim "kills are assertion failures only" was wrong. Its
  summary filter couldn't tell an `IndexError`/`RuntimeError` inside a test from an assertion
  ("send before persist" died on `persist.snapshots[-1]`). Now:
  - the submit watch asserts `ORDERING: broker send happened before any successful durable persist`
    before indexing;
  - the failed-persist fake raises `AssertionError("ORDERING: order sent although its persist failed")`;
  - the CLI test asserts `CLI: reached broker or network ...`;
  - lease and runner refusals are separate tests.
  No assertion was removed or loosened; no production code changed.
- The driver reads pytest's JUnit report. A kill needs a `failure` (not `error`) in the intended test,
  with an assertion message containing its witness, after a green control. Each mutant must compile,
  and source bytes are checked restored.
- Negative control: the 4074fc6 tests under this driver leave 3 mutants alive (send before persist,
  persist failure keeps sending, CLI submits without persist).
- Rule 12: `python tests/mutation/run_055_f03_mutants.py` → 13/13 killed by named witnesses on this
  branch AND with #95 (`773251b`) `mode_config.py` + tests overlaid (117 focused tests pass).
