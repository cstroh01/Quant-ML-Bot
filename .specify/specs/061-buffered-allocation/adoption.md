# 061 T006 adoption review unit

Authority: Camden's 2026-10-17 instruction to retain the 7% reserve and record a
fresh costed trial, continuing his v1.2 build request. T005 is verified complete:
candidate 8d4dfeda-10ef-4951-bf0e-147090ea9731; declaration hash
4a154bfb27bd89dc484b466066b83e01baca20dc98f577c7beb4f4ca24f3b55f.
This document does not edit the frozen spec, declaration or research implementation.

- T006a: PAPER and dormant LIVE preview's shared planner uses buffered_weights,
  exactly once, at the latest monthly decision. The execution reserve cannot be
  overridden independently of the frozen rule. Preserve fractional rounding,
  daily deployment cap, sells-before-buys, no-trade band and every safety limit.
- T006b: Include policy/trial/declaration identities in PAPER records and input
  bundles. Persist policy identity with completed decisions; refuse legacy or
  other-policy decision state without deleting or migrating it automatically.
- T006c: Regenerate the allocation-bound replay on fresh simulated state, then
  prepare report and gate evidence. Do not reuse A1 replay acceptance for B7-EW.
- T006d: Prepare separate protected drafts for LIVE budget and explicit input/
  policy bindings; no LIVE file edits in the autonomous checkout, no broker
  calls, profile writes, pin changes or arming. Camden reviews and merges.

Red-first acceptance: planner targets equal the recorded B7-EW weight rule,
reject A1 and double buffering; future rows cannot affect past orders; stale
policy state refuses; matching state holds between decisions. The existing
Q110 target oracle is superseded by 061, not weakened; historical research
tests for A1 and B-BH remain unchanged. Run targeted tests and serial planted
mutants, then the full suite; production ledger prefix/head must stay unchanged
from the completed 898-line T005 state.

T006e: supervised hosted submits must check an explicit aware UTC deadline both
before persistence and immediately before every broker send. No sends at or
after Monday's 08:15 Chicago cutoff, including after a slow state push. Preview
commands still use the unchanged --preview interface and contain no submit flag.
T006f: qualifying session counts/fills must identify this exact policy and scope.
Historical A1, missing-policy records and explicitly nonqualifying drill records
never satisfy item 4. Keep excluded records on disk; do not relabel them.

T006g (057 Q135/Q138 operator handoff): an offline helper accepts only clean,
unarmed, policy-matched daily preview-session records. Copy allowlisted typed
fields, hash immutable per-day artifacts, and update item 6 atomically. Never
count refused/unsettled/challenged sessions or invent a CSV match. Require five
distinct NYSE days and a latest-day CSV match through the existing typed gate.
Windows automation is a local Task Scheduler replacement for the public-repo
self-hosted runner; no installation, arming or real broker call in this build.
