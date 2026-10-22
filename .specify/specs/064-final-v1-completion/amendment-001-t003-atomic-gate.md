# Spec 064 Amendment 001 — T003 needs an atomic gate unit

**Status:** DRAFT proposal, **not admitted**. Changes nothing in `spec.md`,
`plan.md` or `tasks.md` until Camden admits it.
**Authored by:** Claude (cloud session). **Not independently reviewed.**
**Verified against:** `main` at `bbd4e26ac8a6a72f0d92f911b660cf73fe2f1ae2`.
All `file:line` citations below are at that SHA.

## 1. Problem

FR-003 (`spec.md:92-104`) admits only `exec/live_loop.py` and
`tests/test_064_live_cash_flows.py`, yet requires: "Persist journal
acknowledgement together with the corresponding snapshot boundary; a crash
before/after acknowledgement must neither lose nor double-apply flow"
(`spec.md:97-99`). The journal module says the same: its acknowledgement "must
be persisted atomically with the consuming snapshot" (`scripts/cash_flow_journal.py:6-7`).
Those two files cannot meet that requirement.

Source facts:

- The loop builds every order snapshot with a hard-coded zero flow,
  `BrokerSnapshot(now_fn(),'OK',market_value+cash,0.0,positions,prices)`
  (`exec/live_loop.py:167`), and passes it to `submit_order`
  (`exec/live_loop.py:178`).
- `BrokerSnapshot.external_cash_flow` is a finite float, "excluded from every
  loss and drawdown computation" (`scripts/live_safety_gate.py:287-313`).
- `observe_equity` runs freshness then `_observe_equity_locked` inside one
  `BEGIN IMMEDIATE`/`COMMIT` (`scripts/live_safety_gate.py:740-766`).
- `_observe_equity_locked` computes
  `adjusted_equity = prev_adjusted + (raw_change - snapshot.external_cash_flow)`
  (`:785`) and writes `last_raw_equity` and `adjusted_equity` to `kv_state`
  (`:806-815`, `:768-839`). On the very first observation it seeds from raw
  equity and ignores the flow (`:775-780`).
- `evaluate_order` opens its own transaction (`:571-578`) and calls
  `_observe_equity_locked` inside it (`:614`). `reset_rolling_halt` is a third
  caller (`:980`, `:1006`).
- The gate's only durable store is SQLite: `kv_state`, `pending_orders`,
  `evidence_log` (`:417-438`).

So `kv_state` (`last_raw_equity`, `adjusted_equity`) is the only snapshot
boundary. A journal stored anywhere else is a second store:

- **Journal written before the gate COMMIT:** a crash between them loses an
  applied flow. The journal says "applied", the boundary never saw it, and the
  next observation reads the deposit as a trading gain.
- **Journal written after the gate COMMIT:** a crash between them re-applies
  the flow on retry.
- An atomic file rename (`atomic_write`, used for the order book at
  `exec/live_loop.py:173`) commits one file, not two stores.
- `live_loop` opening or borrowing the gate's private connection or
  `_observe_equity_locked` crosses the module boundary in `CLAUDE.md:116`.

## 2. Amendment

- Split T003. **T003a** (new, earlier): `scripts/live_safety_gate.py` and a new
  `tests/test_064_cash_flow_gate.py`. **T003b**: the original two FR-003 files,
  started only after T003a merges.
- `scripts/live_safety_gate.py` is a Camden path. It defines `SafetyConfig`
  (`scripts/live_safety_gate.py:231`), whose values Rule 7a keeps out of every
  autonomous lane (`.specify/memory/constitution.md:151-157`), and Rule 9b
  condition 2 excludes "the LIVE money path and `SafetyConfig` values"
  (`constitution.md:233-235`); Rule 9a names the file outright
  (`constitution.md:208`). T003a is Camden-reviewed and Camden-merged.
- No change to any `SafetyConfig` value, arming, bot budget, the $200 cap or any
  acceptance policy.

## 3. Proposed API (names provisional)

```python
SafetyGate.observe_equity_with_flows(
    snapshot, *, observation_id, events, account_fingerprint,
    approved_sources, now,
) -> FlowObservation
```

(`LiveSafetyGate` is an alias of `SafetyGate`, `scripts/live_safety_gate.py:1253`.)
Everything below happens in **one** `BEGIN IMMEDIATE` transaction, rolled back
on any exception:

- **(a) Freshness first.** Run `_check_freshness` (`:676-686`) before anything
  else, as `observe_equity` does. A stale or non-OK snapshot latches the
  reconciliation halt, commits only that, and consumes no flow.
- **(b) Idempotency.** Compute a canonical digest over the snapshot fields,
  events and policy. An `observation_id` already committed with the same digest
  returns the stored result and writes nothing. The same ID with a different
  digest raises and writes nothing.
- **(c) Reconcile.** Read the prior journal from a new gate table (or
  `empty_journal(account_fingerprint, approved_sources)` if absent), then call the
  pure `reconcile(journal, events, *, account_fingerprint, approved_sources,
  as_of=snapshot.as_of)` (`scripts/cash_flow_journal.py:50`, `:129`). It returns
  `JournalResult(journal, net_flow: Decimal, quarantined)` (`:24-29`); events are
  plain dicts with the ten fields at `:17-18`. A `ValueError` from journal or
  policy validation is a refusal: roll back, apply nothing.
- **(d) Quarantine.** Any quarantine latches a durable `cash_flow_quarantine`
  kv flag. While set, `evaluate_order` denies add-exposure orders; reduce-only
  orders and every existing halt behave exactly as today. Quarantined amounts
  are never applied and never released into buying power. The journal's own
  latch is not self-clearing (`cash_flow_journal.py:139-140`); clearing the gate
  flag needs a separately named operator action, out of scope here.
- **(e) Apply once.** Pass `net_flow` (converted from `Decimal` only after
  `reconcile`) through the existing `_observe_equity_locked` arithmetic, e.g. on
  a `dataclasses.replace` of the snapshot. No second copy of the breaker math.
  Commit journal, observation ID, digest and resulting boundary together.
- **(f) No second channel.** The caller's `snapshot.external_cash_flow` must be
  `0.0`. Later order snapshots carry `0.0`; `last_raw_equity` already includes
  the flow, so it cannot be applied again. Once a journal row exists,
  `evaluate_order` refuses a non-zero `external_cash_flow`.

**Schema.** Only new tables (`cash_flow_journal`, `flow_observations`) plus one
kv flag, created with `IF NOT EXISTS` beside the existing three (`:417-438`). An
empty DB, or one with no journal row, behaves exactly as today; a missing flag
reads as unset.

**Disclosed residuals.**

- An equity change with no attributable event is still treated as P&L. That is
  conservative in both directions (an unseen deposit looks like a gain, an
  unseen withdrawal like a loss and may halt). It is never treated as a deposit.
- A flow consumed on the gate's first-ever observation is journaled as applied
  but has no arithmetic effect, because the baseline seeds from raw equity
  (`:775-780`). That is correct; the test plan pins it.

## 4. T003a tests

Fake-only, sockets blocked, written red-first against the baseline gate.

1. A deposit applied once leaves the breaker unchanged, and the next
   same-equity order snapshot (flow `0.0`) leaves it unchanged too.
2. An exception injected before COMMIT rolls back journal and boundary; the
   retry applies the flow exactly once.
3. A same-ID/same-payload retry after COMMIT returns the stored result with no
   new `evidence_log` rows; the same ID with a changed payload refuses.
4. A gate closed and reopened on the same path keeps its dedupe.
5. Each quarantine reason (`invalid_event`, `account_mismatch`,
   `source_not_approved`, `future_event`, `identity_conflict`,
   `cash_flow_journal.py:20-21`) latches the flag: add-exposure denied,
   reduce-only allowed, flag survives a reopen.
6. A stale snapshot halts and consumes nothing (journal and boundary unchanged).
7. A withdrawal is not a loss, as observed by the real daily-loss and
   rolling-drawdown consumers in `_observe_equity_locked`.
8. Non-zero `external_cash_flow` after a journal exists is refused.
9. First-ever observation with a settled deposit: journaled, no breaker effect.
10. Planted defects, each with a clean control: journal written outside the
    transaction; flow applied twice; digest ignored; quarantine not latched;
    quarantine blocks reduce-only; freshness checked after reconcile; sign
    inverted; `Decimal` coerced to float before `reconcile`.

## 5. T003b (after T003a merges)

- `exec/live_loop.py` calls the new API **once per run**, after the first
  `reconcile(live)` and before the first order snapshot. Today the loop's only
  `reconcile(live)` call sits inside the per-order loop (`exec/live_loop.py:96-97`,
  `:154-155`), so T003b hoists one reconciliation ahead of the loop or guards
  the first iteration. The loop's local `reconcile` shadows the journal's
  function name; import the journal's under an alias.
- The flow source is injected. Until a real feed passes the capability
  checklist, the only real source is `unsupported`: no events, today's
  behaviour.
- Never fabricate a `transfer_id` from amount, date or description.
- Order snapshots keep `external_cash_flow=0.0` (`exec/live_loop.py:167`).

## 6. Still blocked

- **The real transfer feed.** `fidelity-trader-api==0.2.2` (pinned in
  `requirements-fidelity-host.txt:7`) has `TransactionsAPI.get_transaction_history`,
  but the repo wrapper does not export it: `exec/fidelity_sdk.py:8-22` audits no
  transactions module and `client()` (`:26-56`) returns none. The typed schema
  has no stable transfer ID or revision, no USD/direction mapping, no explicit
  pending/settled status, no completeness guarantee and no immutable raw
  evidence. (SDK facts are from the session audit, not re-read here; the
  package is not installed in this container.) Resolving it needs a separately
  authorized, bounded transfer-history read plus separately named
  `exec/fidelity_sdk.py` and adapter units.
- Deposits stay ineligible for new exposure until then.
- The SCOPE §11.3 PAPER/Fidelity sessions (`docs/SCOPE-V1.md:267`) and
  Camden's arming are untouched.

## 7. Admission

Needs Camden. On admission, `tasks.md` T003 is split into T003a/T003b and
FR-003's file list is amended, in a separate change.
