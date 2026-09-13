# Review plan

Six review units maximum; each at most 400 added/deleted production and test
lines. PRs must be assembled by the human: this lane forbids every git command
and has no authority to publish branches. Handoff records exact boundaries.

1. Funded single-asset ledger and rejection/validation oracles.
2. Ledger-backed metrics and pre-trade capital anchor.
3. Executable targets, endpoint validity and horizon metadata.
4. Full-calendar features, masked CV and prefix-stable decisions.
5. Price-basis boundary and explicit corporate actions.
6. Remaining metric conventions and reusable mutation evidence.

Tests precede implementation in each unit. Use the installed Python,
`-B -m pytest -p no:cacheprovider` and only this lane's new tests. The venv
has no pytest; the final venv run loads the existing system pytest (handoff).
Mutants
execute source copies in memory, patch module functions temporarily, verify
unmutated controls, and never overwrite shared source. This follows 012's
deliberate defect injections and 017's control/source-integrity discipline.
Verified: 003 and 007 do not contain mutation suites. No new dependencies.

Lookahead proof per unit belongs in the handoff: distinguish outcomes from
information available at a decision, and never let missing rows shift fills.
