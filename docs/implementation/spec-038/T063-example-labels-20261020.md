# 038 T063: same-line illustrative labels and inventory links

The existing D4 task covers five documents with illustrative inputs or mechanical
oracles and the audit's two broken inventory links. Eighteen selected numeric
lines now carry `EXAMPLE — NOT A RESULT` on that same line; existing compliant
labels remain. Both inventory links resolve to committed `coverage.json`.

The change preserves every numeric token and all task states in spec017. It does
not recalculate an example, change an approved threshold or label any real result
as a synthetic fixture. The absent-source figures owned by other 038 tasks, pinned
panels, unsupported quickstart row and human gates remain outside this unit.

The new consuming guard failed against the original documents in six intended
contracts before any document change. Each row has a clean control and an in-memory
mutation moving its label off the numeric line; each coverage link has a broken-link
mutation. The standalone driver under `tests/mutation/` invokes the same guard and
checks that the actual documents remain unchanged. Exact red/green/full-suite XML,
mutation output, source hashes and numeric-token proofs are in the private packet.

No new result, dependency, network call, broker action, protected path or production
ledger/cache write. This does not complete the remaining 038 disclosure sweep.
Publication serializes after the prepared T064 unit, which shares the static guard
and task tracker; tests on a private composition do not certify a future GitHub head.
