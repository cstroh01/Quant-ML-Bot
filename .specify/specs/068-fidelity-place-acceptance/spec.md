# 068 — Fidelity placement acceptance (LIVE money path)

Date: 2026-11-16 America/New_York. Status: decisions D-1 to D-4 adopted by Camden on 2026-11-16
("Accept all four"); ready for implementation.
Baseline: public main `ed267531b49aca6c4981df1a5c49ac7c16dff4c4` (tag `v1.2`). LIVE pin `0a6b5ff`, HALTED.

Every `exec/` file this spec changes is the LIVE money path (constitution Rule 7a). Changes come
through the reviewed lane only: Camden reads every line and merges (Rules 7 and 9). No agent merges,
repins, arms, clears a latch or writes to the private repo.

## Why

First LIVE session, 2026-11-16 (private run 43893476063, pin `0a6b5ff`; FR-013 record in
`live_fidelity/runs.jsonl` on the private `ops-state` branch; private safety-gate database; Camden's
check of the account the same day):

- Login, settled cash ($201.22) and positions (none) succeeded. The safety gate allowed one buy
  (DBC, 0.755 shares). The adapter previewed it (confirmation number returned) and called placement
  (`place_calls` 1); the placement HTTP reply was 200 for the dedicated account.
- Fidelity has no such order: the order-status lookup about a second later found none, and Camden
  found nothing under Activity & Orders. The reconciliation before the next order raised
  `ReconciliationBlocked` ("1 reservation(s) without a known outcome"), latched HALTED and sent none
  of the other seven sleeves. Nothing was bought.

**Defect.** `LibraryBroker.place` (`exec/fidelity_live.py:490-499`) treats any placement reply for
the right account as placed. It never reads `respTypeCode`, which the pinned wheel
(`fidelity-trader-api` 0.2.2, sha256 `f5a94056…`) exposes as `EquityPlaceResponse.is_accepted`
(`"A"` = accepted; `fidelity_trader/models/equity_order.py:266-271`), and which the wheel's own CLI
checks before reporting success (`fidelity_trader/cli/_orders.py:147-155`). On a reply without a
confirmation number it returns the preview's. `LibraryBroker.preview` (`:482-488`) likewise never
checks `is_validated` (`"V"`). The run failed closed, as designed, but for the wrong recorded reason.

**What is known and what is not.**

- Known: fractional previews work. The five gate preview sessions (2026-11-03 to 11-09, pin
  `89bad88`) previewed fractional quantities (for example 0.737, 0.391, 0.228 on 2026-11-09, plus
  1.0 and 0.01 probes) and each returned a confirmation number; so did the 11-16 DBC preview.
- Not known: the placement reply's `respTypeCode`, and why Fidelity refused. The wheel's response
  models drop every field they do not declare, so the refusal reason never reached our code, and the
  FR-013 record keeps status codes only. Whether the previews' codes were `"V"` is also unrecorded.
- Hypotheses, none assumed here: a fractional order needs something at placement that the wheel's
  place body does not send (Fidelity marks every fractional order "Not Held"); DBC is not eligible
  for fractional placement; the wheel's place body (`previewInd`, `confInd`) no longer matches
  Fidelity. This spec makes the next refusal diagnosable; it does not guess a cause.

## FR-001 — A preview counts only when validated

`LibraryBroker.preview` raises `BrokerError` unless the reply `is_validated` (`respTypeCode == "V"`)
and carries a confirmation number. The message names only the reduced code (FR-005). The refusal
happens before `record_intent`, so nothing is recorded as sent and placement is never called.
`FidelityLive.submit` records a not-sent marker for the client id (FR-003) before re-raising.

## FR-002 — A placement counts only when accepted

`LibraryBroker.place`, after its existing account check:

1. Reply not `is_accepted`: raise a new `PlacementRejected(BrokerError)` naming the reduced code.
   `FidelityLive.submit` re-raises it as itself, never as `SubmissionUnknown`, after recording a
   rejected marker (FR-003).
2. Reply accepted without a confirmation number: `SubmissionUnknown` (the order may exist).
3. Reply accepted with a confirmation number: return that number, never the preview's. When it
   differs from the preview's, it is recorded with the intent so status lookups use both (plan
   decides the record shape; the intent log stays append-only).

Exceptions raised by the send itself keep today's `SubmissionUnknown` path unchanged.

## FR-003 — A refused order is a known outcome, and only when Fidelity agrees

Markers live in the profile state directory beside the intent log, written atomically and persisted
with the run. `FidelityLive.order_status(client_id)` returns `REJECTED` (already in
`fidelity_reconcile.TERMINAL`) only when both hold:

- a not-sent (FR-001) or rejected (FR-002) marker exists for that client id; and
- for a rejected marker, Fidelity's status list shows no order under the preview's or the
  placement's confirmation number. If it shows one, its real status wins and the marker is ignored.

So the existing reconciliation releases the reservation and `live_loop`'s book marks the order
applied with no position. Without a marker, behavior is unchanged: no order found stays unknown and
blocks. `exec/live_loop.py` is not changed (its hash is pinned by §11.3 item 7).

A rejection still ends the run: the exception propagates, the run aborts and HALTED latches (D-1).
After Camden clears HALTED, the next run releases the reservation and proceeds.

## FR-004 — `ReconciliationBlocked` says why

`fidelity_reconcile.require_reconciled` keeps refusing exactly as today, but its message lists each
blocked client id with its state (`unknown`, `unrecognized`, `status_unavailable`) and, for
`unrecognized`, the reduced status code. On 2026-11-16 this would have read "unknown".

## FR-005 — Diagnostic facts for a refused preview or placement (the D-9 pattern)

On a non-validated preview or non-accepted placement, the FR-013 failure record gains one optional
`order_reply` fact, read from the raw reply JSON of that request only. It is captured by the
existing response hook that already records the request trace and the D-9 entitlement fact
(`exec/fidelity_live.py:320-345`), limited to the two order endpoints and held in memory, and is
emitted by `LibraryBroker.diagnostic()` beside `entitlement` and `cash_stamps` (`:347-355`). The
wheel and `live_loop.py` are unchanged.

- endpoint (`preview` or `place`) and the reduced `respTypeCode`;
- top-level, `orderConfirmDetail` and any message/error list's key names;
- for each message/error entry: short code, type and severity values.

Reduction follows 057 D-9: a value that is not short plain text, or holds three consecutive digits,
is `*`; at most 20 keys and 5 entries. Message text, account values, amounts, quantities and
confirmation numbers are never recorded (D-2).

## FR-006 — Releasing the 2026-11-16 DBC reservation (one time, Camden)

The open reservation `qmb-20261116-4f75a4a46e55e1699e9e86b5` has no marker, so FR-003 cannot release
it. A packet script, run by Camden on a fresh checkout of `ops-state` at the new pin, hash-checked:

- refuses unless the reservation and the bot-ledger order are exactly that client id, DBC, 0.755,
  not terminal and not applied; and unless Camden passes the attestation switch confirming the
  account shows no order for 2026-11-16;
- records the outcome through the real `LiveSafetyGate.record_order_outcome` as terminal
  `NOT_PLACED`, marks the ledger order applied with no position, appends an attestation record, and
  persists; it does not clear HALTED (that stays `clear-halted.ps1`).

## FR-007 — Path back to LIVE (Camden, in order)

1. Review and merge the implementation PR (Rule 7 line by line).
2. §11.3 item 1 refresh at the merge SHA (full suite and every mutation driver, including 068's);
   the manifest's item 1 digest changes, so the armed digest changes.
3. Repin (not weekdays 08:00-12:00 ET), FR-006 release, clear HALTED, re-arm with the new digest
   (not weekdays 09:30-12:00 ET). The current arming expires 2026-12-14T02:44Z regardless.
4. The next 10:10 ET session runs LIVE (D-3). A refusal halts again, buys nothing and records
   FR-005's facts; that record decides the next fix.

## Tests and mutation (Rule 12)

`tests/test_068_place_acceptance.py`, fakes shaped like the pinned wheel's models:

- place reply `"A"` with a number: returned (control). `"A"` without a number: `SubmissionUnknown`.
  Any other code, a missing `orderConfirmDetail`, or `None`: `PlacementRejected`, never the
  preview's number, marker written.
- preview not `"V"`: `BrokerError`; `record_intent` and `place` never called; marker written.
- `order_status`: marker plus empty broker list returns `REJECTED`; marker plus the order present
  under either number returns the broker's status; no marker returns `None` (unchanged).
- reconciliation releases a rejected reservation; the book order is applied with no position.
- replay of 2026-11-16 through `live_loop.run_once` with a fake broker (non-`"A"` place reply,
  empty status list): `PlacementRejected`, `place_calls` 1, HALTED, the other seven sleeves not
  sent; the next run (HALTED cleared) releases DBC and proceeds.
- FR-004 message and FR-005 reduction: digits, long labels and message text never appear.
- `tests/mutation/run_068_place_acceptance_mutants.py`: drop the `"A"` check; fall back to the
  preview number; drop the `"V"` check; return `REJECTED` without asking the broker; record message
  text. Every mutant killed.

## Decisions (Camden, 2026-11-16: "Accept all four")

- **D-1 Halt after a refused order.** Continuing to the other sleeves needs a
  `live_loop.py` change, which rebuilds §11.3 item 7. Halting keeps item 7 and buys nothing extra.
- **D-2 No message text, even in the private record.** Consistent with 057 D-9. The
  alternative, redacted text in the private record only, was not chosen.
- **D-3 Re-arm straight to LIVE.** A preview-only session would not exercise placement,
  and a refused placement is fail-closed and now diagnosable.
- **D-4 FR-006 attestation.** Camden's dated statement in the packet record, quoting what the
  account showed.

## Correction recorded here

Spec 057 D-13 and the PR #331 description said "all five gate previews used whole shares". That is
wrong: they previewed fractional quantities, as above. This spec's PR corrects the D-13 sentence.

## Known risk, not fixed here

Whether Fidelity's status list still shows an order on the session after it filled is unverified.
If it does not, a filled order would read as unknown the next day and block (fail-closed, no double
buy). The first clean LIVE week tests it; a fix would be its own spec.

## Out of scope

The FR-013 `challenge=true` label on non-challenge errors; dollar-based orders; any change to the
allocation, budget, `SafetyConfig`, `live_loop.py` or the wheel; automatic retries; continuing after
a refusal (D-1).
