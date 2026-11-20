# 069 — Fidelity fill observation (LIVE money path)

Date: 2026-11-19 America/New_York. Status: decisions D-1 to D-4 adopted by Camden on 2026-11-19
("Accept all four"); ready for implementation.
Baseline: public main `5b8e4fbd8cb47a435865b29b7ddaf019518abc55` (= both pins). LIVE armed. The
2026-11-19 run halted; Camden released TLT and cleared HALTED the same day (FR-005 step 1).

Every `exec/` file this spec changes is the LIVE money path (constitution Rule 7a). Changes come
through the reviewed lane only: Camden reads every line and merges (Rules 7 and 9). No agent merges,
repins, arms, clears a latch or writes to the private repo.

## Why

Spec 068's "Known risk" happened. Evidence: private runs 44332474704 (2026-11-18) and 44551739454
(2026-11-19), their FR-013 records in `live_fidelity/runs.jsonl` on `ops-state`, private issues
#57 and #58, and Camden's check of the account on 2026-11-19.

- 2026-11-18: all eight sleeves previewed `"V"` and placed `"A"` (`place_calls` 8). `live_loop`
  reconciles before each next order, so the first seven read `FILLED` from Fidelity's order-status
  list seconds after placement and were applied. TLT, placed last, was never looked up again that run.
- 2026-11-19: the order-status list no longer showed the TLT order under its confirmation number.
  With no FR-003 marker, `order_status` returned `None`, reconciliation raised
  `ReconciliationBlocked` ("... unknown"), HALTED latched, nothing was sent.
- Camden's account view on 2026-11-19: TLT 0.292 shares held, bought 2026-11-18; the other seven
  quantities equal the bot ledger. The halt was fail-closed and correct; the order had filled.

**Defect.** The adapter learns an order's outcome only from Fidelity's status list, and only at the
next reconciliation. For every order except a session's last, that is seconds later; for the last it
is the next session, when the list (the pinned wheel's `get_order_status`, which takes no date
range) no longer holds it. So every LIVE session that trades will halt the next morning until its
last order is released by hand (as in the 2026-11-19 packet).

**What is known and what is not.**

- Known: on 2026-11-18 the status list reported `FILLED` for each of the first seven orders within
  seconds of placement; the next session's list did not show the eighth.
- Not known: how long Fidelity keeps an order in that list (end of session, overnight, a fixed
  count); whether it ever shows a previous session's order. One observation; this spec assumes
  neither.
- The pinned wheel's status rows carry `amountDetail.qtyExec` (`OrderAmountDetail.qty_exec`) beside
  the status. Its transaction-history call (`get_transaction_history`) takes a date range but its rows
  carry no confirmation number, and this account has never called it.

## FR-001 — Observe the outcome right after placement

`FidelityLive.submit`, after a placement that returns a confirmation number (068 FR-002.3), looks the
order up through the read-only status lookup (a new `status_detail`, to which the existing `status`
call now delegates) under every recorded confirmation number, at the delays
D-1 fixes, until Fidelity reports a status in `fidelity_reconcile.TERMINAL` (the adapter's existing
`TERMINAL_STATUSES` is the same set; a test keeps them equal) or the delays run out.

- A terminal status is recorded durably (FR-002) before `submit` returns.
- A working or missing status after the last delay records nothing; the order stays as today
  (unapplied, looked up at the next reconciliation).
- The observation never changes the placement's result: `submit` returns the same confirmation
  number whether the observation found a status, found none, or failed. A `SecurityChallenge` during
  it still halts (`HaltProfile`), as every other call does. Any other error ends the observation and
  records nothing.
- No order is previewed, placed, cancelled or retried by this step. Read-only status calls only.

## FR-002 — The observation record

The record extends 068's per-client-id outcome file (`order-outcomes/<client id>.json`, written
atomically, persisted with the run). It holds the confirmation numbers and the observed status code
only: no quantities, prices, amounts or message text (068 D-2).

- Written only for a terminal status. For `FILLED`, only when the reply's executed quantity, when
  present, equals the ordered quantity to within half the 0.001 order step (0.0005); a `FILLED` row whose executed
  quantity differs records nothing (the order then stays unknown and blocks, for Camden to read).
- A placement already marked `placed` (068 FR-002.3, a second number) is superseded by the
  observation for the same numbers; any other existing record still refuses, as 068's `_mark` does.
- A malformed record refuses and blocks, as in 068.

## FR-003 — Next-session status

`FidelityLive.order_status(client_id)`, unchanged in order: Fidelity's status list is asked first
under every recorded number, and a listed order keeps Fidelity's status. Only when the list shows
none does an observation record answer, returning its recorded terminal status. Without a record,
behavior is exactly 068's (none found stays unknown and blocks).

So the existing reconciliation releases the reservation and `live_loop`'s book applies the order as
it does for any `FILLED` status today. `exec/live_loop.py` is not changed (its hash is pinned by
§11.3 item 7). The next run's ownership check (`fidelity_session.ownership`) still compares every
position with the account to 1e-8 and halts on any difference, so a wrong record cannot add shares
the account does not hold.

## FR-004 — What a run reports

The FR-013 run record gains, per submitted order, the observation's outcome: the reduced status code,
or `none` (still working or not found), or `quantity_mismatch` (FR-002), or `error` with the
exception type only. No numbers. (A broker object without the status-detail call, which only test
fakes are, is not observed and adds no entry.)

## Tests and mutation (Rule 12)

`tests/test_069_fill_observation.py`, fakes shaped like the pinned wheel's `OrderStatusResponse`:

- placement then `FILLED` at the first look: record written, `submit` returns the placement's number.
- `WORKING` at every delay, or no row: nothing recorded; next-session lookup stays unknown (068).
- `FILLED` with executed quantity different from the order: nothing recorded.
- the status call raising `BrokerError`: nothing recorded and `submit` still returns the number;
  raising the challenge path: `HaltProfile`.
- next session, empty list + record: returns the recorded status; list showing the order with
  another status: Fidelity's status wins; no record: `None` (unchanged).
- an existing `placed` record is superseded for the same numbers; a different existing record refuses.
- the delays use an injected sleep (no real waiting in tests); total wait never exceeds D-1's bound.
- replay of 2026-11-18 to 11-19 through `live_loop.run_once` with a fake broker whose next-session list
  is empty, on a $200 budget that may all deploy in one session: day one places eight and observes all
  eight `FILLED`; day two reconciles with no unknown, applies the last order, passes ownership with the
  eight quantities, and sends nothing (`place_calls` 0, no actions). The same replay with the
  observation disabled reproduces the 2026-11-19 `ReconciliationBlocked`.
- `tests/mutation/run_069_fill_observation_mutants.py`: skip the observation; record a non-terminal
  status; record `FILLED` despite a quantity mismatch; let the record outrank a status Fidelity lists;
  let an observation error change `submit`'s result; record a quantity or price. Every mutant killed.

## FR-005 — Path back to LIVE (Camden, in order)

1. Done before this spec, 2026-11-19 ~19:58Z: the packet `post-v1-068-tlt-release` released TLT as
   `FILLED` (ops-state `d8681a2`) and cleared HALTED (`17da50b`), on Camden's attestation. LIVE runs on
   5b8e4fb meanwhile; the next trades are expected at the December rebalance
   (`allocation-state.json`: `executed_decision` 2026-11-02).
2. Review and merge the implementation PR (Rule 7 line by line).
3. §11.3 item 1 refresh at the merge SHA (full suite and every mutation driver, including 069's).
4. Repin (not weekdays 08:00-12:00 ET) and re-arm with the new digest (not weekdays 09:30-12:00 ET),
   before the December rebalance session. If it lands later, that session's last order halts the next
   morning exactly as on 2026-11-19, and the same hand release applies.

## Decisions (Camden, 2026-11-19: "Accept all four")

- **D-1 Observation delays.** Adopted: look at about 2, 5, 10 and 20 seconds after placement (at
  most 20 seconds of waiting per order plus the lookups; under 3 minutes for eight orders, inside the
  09:35-12:00 ET window). Market orders for these ETFs filled within seconds on 2026-11-18.
  _Corrected 2026-11-19 before implementation: the draft Camden accepted said "about 37 seconds at
  most per order; about 5 minutes at most for eight", an arithmetic error (it summed the look times).
  The look times themselves are unchanged._
- **D-2 No transaction-history fallback.** Adopted: out. Its rows carry no confirmation number, its
  shape on this account is unverified, and a symbol-and-quantity match is weaker evidence than
  Fidelity's own status for the order. A miss stays fail-closed and is released by hand.
- **D-3 Fill prices stay unrecorded.** Adopted: out of this spec. `avgExecPrice` would let LIVE
  compare realized with modeled cost (as §11.3 item 4 does for PAPER), but it adds amounts to a record
  068 D-2 keeps free of them. A separate spec can decide where such figures live.
- **D-4 Observe every order, not only the last.** Adopted: every order. `live_loop` does not tell the
  adapter which order is last, and finding out would need a `live_loop.py` change (item 7).

## Known risk, not fixed here

An order still working after the last delay (a halted symbol, a slow fill) behaves as today: it
blocks the next session if Fidelity's list has dropped it. A fix for that would need a second source
of truth (D-2) and is its own spec.

Found by the 2026-11-20 independent review; each fails closed (the next session blocks, the run
halts, or the ownership check refuses) and none is fixed here:

- The lookup takes the first recorded number Fidelity lists (as `order_status` does): a working
  status under the preview's number hides a terminal one under a different placement number. On
  2026-11-18 the two numbers were equal.
- A runner cancel during the waits (now up to 20 s per order) escapes `submit` before the run
  record is written; a `SecurityChallenge` while looking halts with no `observations` entry.
- The 09:35-12:00 ET window is judged once, at the run's start; the looks add up to about 3 minutes
  for eight orders, so a run that starts just before 12:00 can place after it. (The arming expiry is
  re-checked before every order at the wall clock; an expiry mid-run halts before the next order.)
- A terminal status other than `FILLED` is recorded without a quantity check; a partly filled
  `CANCELLED` order then fails the next run's ownership check.
- `error` usually names `BrokerError`, because the adapter's call wrapper re-raises other errors as it.

## Out of scope

068's open FR-005 gap (`orderConfirmMsgs` codes and `errorCategories` values); the item 6 flag that
the gate preview sessions never checked `respTypeCode`; the `challenge=true` mislabel; any change to
`live_loop.py`, the wheel, `SafetyConfig`, the allocation or the budget; retries; recording fill prices
(D-3).
