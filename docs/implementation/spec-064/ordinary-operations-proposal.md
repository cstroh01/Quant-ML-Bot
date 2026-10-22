# 064 T004: ordinary cloud operation proposal

2026-10-21. Proposal only. No installed workflow, ordinary LIVE service,
schedule, broker authority or operational acceptance is established here.
Existing source baseline: daec58bf3c79221e9951f1fdce258f2dbff89c69;
numbered preparation contract: spec064, PR283 head51745cc9e805e8c9a4432f73b582dd58058350fe.

## Smallest runtime

Retain private GitHub Actions for bounded daily jobs, existing ops-state,
ops_runtime due-run/lease/outbox primitives, and the reviewed execution gateway.
The existing fidelity-preview host remains preview only. Ordinary execution
needs a distinct reviewed fixed entry point; adding a submit switch to that
host would cross its explicit command contract.

The allocation remains monthly. A daily due run may reconcile and report
without making a new trade. An eligible settled deposit is not a new rebalance.
Actions is scheduled compute: delayed/missed launches must be detectable,
and a job must refuse a missed authorization window instead of trading late.
This design needs no continuous daemon or LLM inference dependency.

## Ordered admission and run protocol

1. Earn 057 T010 hosted preview/holdings, notification, restore and PC-off
   acceptance. Preserve the current09:35inclusive–12:00exclusive Eastern
   preview window. Schedule/ordinary-runtime acceptance remains057 T011.
2. Review the actual ordinary-runtime numbered extension, fixed source pin,
   entry point and allowed market/session window separately. Do not assume the
   preview window or a coding heartbeat grants order authority.
3. On each authorized due run, acquire the shared private-state concurrency
   group, restore verified state and validate the exact pin, profile/account,
   session, KILL/HALTED, state schema and pending intent ownership.
4. Reconcile unknown submissions and pending/partial orders before decisions.
   Unknown outcome retains reservations and stops new exposure; no resend.
5. Consume only attributable transfer evidence from an accepted source. Apply
   the journal acknowledgement at the same durable snapshot boundary as the
   cash-flow-adjusted loss observation. Ambiguity quarantines new exposure.
6. Compute targets using bot-owned assets, settled cash net of commitments,
   fractional/broker minimums and the unchanged200USD pilot/arming mandate.
   Existing gateway and every SafetyConfig value remain authoritative.
7. Persist intent before any permitted broker write. Reconcile the response;
   persist terminal/unknown state, then produce the summary and deduplicated
   incident. A notification failure cannot erase an order outcome or lease.
8. Persist final state and private backup on failure as well as success.
   A separate bounded due-run monitor may flag a missing job only under the
   separately reviewed operations plan; no speculative trading retry.

## Recovery and acceptance matrix

| Failure | Required behavior and evidence |
|---|---|
| Duplicate/concurrent invocation | Exactly one claim; losing worker places zero orders. |
| Crash before send | Durable intent/reservation survives; recovery reconciles before deciding. |
| Crash after send/unknown reply | No blind resend; match actual broker identity/status, retain uncertainty. |
| Auth challenge | Latched halt and incident; personal intervention, no bypass. |
| Missing/corrupt/stale state or data | No new exposure; preserve original bytes and report sanitized reason. |
| Deposit/withdrawal/pending transfer | Settled attributable flows once, no loss masking or cap increase. |
| Outbox delivery failure | Durable deduplicated pending notification; no false receipt. |
| Backup restore | Restore a private test copy and reproduce ownership/intents/latches without reset. |
| Host powered off | Accepted cloud job completes with the development PC off and real notification receipt. |
| Missed session/window | Explicit missed-run incident; no credit for a non-run or out-of-window trade. |

Offline controls and plausible consuming defects must precede real acceptance.
The current fake tests, successful PAPER read-only diagnostic and template
source do not prove any row's hosted acceptance. Ten completed/reconciled PAPER
sessions per profile with per-order modeled/actual costs, five clean Fidelity
preview/holdings sessions and Camden's personal LIVE arming remain separate.

## Personal recovery procedure

On an incident, leave state, reservations, leases and latches intact. Identify
the exact run/pin/profile and inspect sanitized summaries, then reconcile actual
account ownership, cash and pending orders through the approved private path.
Resolve authentication personally when needed. Prepare a reviewed recovery
intent; do not delete state or reuse a consumed day to get a green status.
No secret or raw account payload belongs in an issue, public artifact or chat.

The development heartbeat coordinates code only. Pause it when finite offline
work is complete or solely personal/calendar-blocked. It never runs this plan.
