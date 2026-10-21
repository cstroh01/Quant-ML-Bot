# 064 — Final v1 completion: bounded offline preparation

Date: 2026-10-21 America/New_York. Status: admission draft; publish/review this
numbered packet before implementation. This packet changes no production source.

## Authority and scope

Camden's latest instruction: "All I want is a finalized project with all of my
v2 wants in documentation." He requires Fidelity buy/sell integration, ordinary
autonomy, capital-change resilience and operation with his PC off; he retains
free-only services and spec061's buffered monthly allocation, NO EDGE CLAIMED.
His current request authorizes this bounded admission preparation and coordinated
offline development, not broker activity, secret entry by agents or deployment.

Read constitution, CLAUDE, SCOPE, STATE and 051/055/057/061 before each unit.
Baseline public main: `daec58bf3c79221e9951f1fdce258f2dbff89c69`; refresh via
GitHub GET before delivery. Local Git remains forbidden, including subprocesses.
Private 063 manual_budget drafts remain historical, unadopted proposals. This
spec does not adopt manual_budget, remove the $200 pilot, edit SCOPE 11.3,
change SafetyConfig, arm LIVE or satisfy the original release DoD by declaration.
Any successor account-scoped mandate remains a separate reviewed decision.

## FR-001 — Secure local provisioning helper (T001)

New files only: `scripts/fidelity_provision.py`, `tests/test_064_fidelity_provision.py`.
The helper runs personally in Camden's local interactive terminal after review;
development/tests use synthetic inputs, injected prompts and a fake child runner.
Credential handling remains a protected draft for Camden's line-by-line review.
Its only permitted external write is fixed-argv `gh secret set NAME --repo
cstroh01/Quant-ML-Bot-private`, with the value supplied solely on stdin,
shell disabled, and no automatic retries. No configurable repository or names.
Require explicit apply intent before writes; default refuses remote mutation.

Read all five personal values with getpass, without echoed fallback, validate
everything and construct the profile before any write. ACCOUNT and FP_KEY must
be personally reconciled with the existing native-vault identity: never generate
or replace them, and coding workers never read the vault. Their current source
is not assumed known. No status mode reads credential values; names-only remote
metadata may be checked during the personal invocation. The fixed names are
FIDELITY_LIVE_USERNAME, FIDELITY_LIVE_PASSWORD, FIDELITY_LIVE_TOTP,
FIDELITY_LIVE_ACCOUNT and FIDELITY_LIVE_FP_KEY. The sixth and final write is
QMB_FIDELITY_PROFILES_JSON, a generated JSON list containing only live_fidelity.
Construct only in memory from a supplied reviewed nonsecret profile template.
Require exactly those five credential_refs, live_fidelity identity/namespaces,
mode LIVE, broker fidelity and the unchanged $200 pilot. Preserve its approved
deployment/instrument/fractional fields; safety_config_version must come from
that reviewed template and match the installed allocation contract. Never invent
risk configuration or supply a new default. Validate with current load_profiles.
The fingerprint is HMAC-SHA256 over the account's exact UTF-8 bytes, keyed by
the 32 bytes decoded from FP_KEY; require exactly 64 lowercase hex characters.
Do not normalize the account silently, substitute plain SHA or expose its digest.

Keep values and generated profile in memory and child stdin only: no plaintext
files, command arguments, environment mutation, prints/logs, raw child output,
exceptions or secret-derived output. Parent environment is unchanged. Suppress
child stdout/stderr and sanitize failures to fixed categories; stop at first
failure and return sanitized completed names only; refuse automatic retry or
overwrite after partial failure pending personal review. Six writes are not
atomic; never claim rollback or verification of unreadable secret values.
Do not touch PAPER secrets/profiles, variables, workflows, pins, state markers,
leases, holdings, arming, schedules, broker endpoints or market data.

## FR-002 — Pure attributable cash-flow journal (T002)

New files only: `scripts/cash_flow_journal.py`, `tests/test_064_cash_flow_journal.py`.
Use Decimal for finite signed USD amounts, never float arithmetic; reject
booleans/nonfinite values. An event carries stable transfer identity, account
fingerprint, source identity and immutable evidence reference, direction, amount,
observed/effective aware timestamps and explicit settlement status. Raw account
identifiers, secrets and invented attribution are prohibited.

Pure functions accept an existing serializable journal, validated events,
expected account, explicit approved source identities and aware as_of; return a new journal, newly attributable signed
flow and bounded quarantine reasons. No broker/network/file I/O or wall clock.
Only explicitly settled transfers effective by as_of qualify. Pending transfers
with a future effective_at remain persisted but ineligible; this normal settlement
wait is not a quarantine or halt. They may settle later under the same identity
with unchanged immutable attributes. An observed_at after as_of, or a settled
transfer effective after as_of, quarantines rather than receiving early credit.
Repeated/reordered input and serialized restart never apply a transfer twice.
Conflicting identity/payload, wrong account/source, invalid future dates, missing identity
or provenance, invalid amounts and ambiguous/unidentified movements quarantine;
do not silently discard a conflict because its identity was seen previously.

Do not derive flows from equity/cash differences, prices, fills, dividends or
buying power. Do not classify a market gain as a deposit. Unknown movements
remain quarantined and ineligible for new exposure. A journal proposes cash-flow
accounting, never an increase in budget, arming, allocation weights or spending
authority. Settlement eligibility does not force a trade or reopen a completed
monthly allocation decision. Persistence/consumer acknowledgement belongs to T003.

## FR-003 — Separate protected consuming draft (T003)

After accepted T002, draft only `exec/live_loop.py` and
`tests/test_064_live_cash_flows.py` in a separate review unit. Feed validated
attributable flows into the actual safety snapshot/loss path and separate flows
from performance. Persist journal acknowledgement together with the corresponding
snapshot boundary; a crash before/after acknowledgement must neither lose nor
double-apply flow. Reconcile ownership, pending/partial orders and reservations
first; use settled cash net of commitments, retain bot-owned equity, $200 cap,
fractional minimums, monthly cadence, gateway and every existing halt/arming rule.
Unsupported source evidence quarantines/refuses; fake attribution proves no real
Fidelity capability. Adapter/session/profile changes need a further named unit.
No protected source is adopted or deployed by this packet; Camden owns its
line-by-line review/merge. No edits to SafetyConfig values or arming/budget policy.

## FR-004 — Ordinary operations proposal only (T004)

Write `docs/implementation/spec-064/ordinary-operations-proposal.md` only.
Specify pinned private cloud operation, due-run/concurrency, pre-send durability,
unknown-order reconciliation, authentication/stale-state halts, notification
delivery, backup/restore and recovery acceptance. Map existing 055 controls and
057 host evidence; distinguish preview installation from ordinary LIVE runtime.
057 T011 remains after accepted operations. This proposal installs/enables
nothing, adds no submit switch to the preview host and grants no schedule.

## FR-005 — Finite v1 documentation/dispositions (T005)

Write `docs/implementation/spec-064/final-v1-contract.md` and
`docs/implementation/spec-064/legacy-dispositions.md`. Record capability exits,
operating/recovery instructions and precise remaining human/calendar gates.
Classify relevant 033/035/038/044/046/047/060/062 obligations individually as
required exercised-path work, deferred V2 or superseded with cited authority;
preserve actual task status and all historical trials. Reference private
V2-BACKLOG.md without copying account/IP material into public documentation.
ML launch, expanded universe, intraday, crypto and new agent platforms are out.

## Acceptance and invariants

Each changed gate has a plausible planted semantic defect caught by its actual
consumer plus a clean control. T001 proves fixed destination/names/stdin,
correct HMAC/profile, validation-before-write, no leakage/environment mutation
and stop-on-partial-failure. T002 proves signed precision, settlement boundary,
conflicting duplicate, wrong provenance, repeated/reordered/restarted events and
ambiguous-flow quarantine. T003 proves real snapshot consumption, transfer versus
P&L, commitment handling, once-only crash recovery and unchanged protected bounds.

Tests are fake-only, external sockets blocked; no gh/broker/market invocation in
verification. Relevant focused/mutation evidence precedes one final exact-source
Python 3.12 `python -m pytest tests` from the isolated repo root. Reuse unchanged
baseline receipts honestly; changed bytes need new evidence. No new dependency.
Ordinary units <=600 added+removed lines, split before exceeding that bound.
Codex records two honestly labelled exact-head looks; same-author is not independent.
CI, no-hold, unchanged ledger and actual merge-tree/source binding remain required.

No docs/trials, .env*, data/cache, pinned019 or frozen whole-file source edits.
Ten reconciled PAPER sessions per profile with costs, five distinct clean
Fidelity preview/holdings sessions, actual cloud/notification evidence and
Camden's personal arming remain unevidenced until earned. Fidelity previews keep
09:35 inclusive–12:00 exclusive Eastern on a separately authorized NYSE date.
Implementation-complete, acceptance-pending, operationally-complete and
LIVE-armed are distinct. Current LIVE remains NOT ARMABLE.
