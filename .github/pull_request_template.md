<!-- Required by CLAUDE.md "Pull request requirements". Delete lines that do not apply; never leave a metric without its context. -->

## Spec
Spec / task ids:

## What changed and why it is correct

## Lookahead / leakage check
<!-- Rule 1/5: for every row timestamped t, is every value computable from data at or before t? -->

## Metrics (only if any are reported)
Folds · purge · embargo · commission · slippage model (Rule 13; flat bps is not reportable):
Beside buy-and-hold and random-signal baselines, same period, same costs (strategy changes only):

## Tests
Before → after (passed / failed / xfailed), Python version:
Rule 12 planted defect and the test it turns red:
Test files changed (list every one):

## Ledger
`docs/trials/` unchanged? (trials.jsonl line count + SHA-256)

## Dependencies
New dependency and what it does that existing ones cannot (Rule 6):

## Merge bar (Camden)
- [ ] CI green, including `test-windows`
- [ ] No open P0/P1 review findings
- [ ] Local numerics check if numpy / scipy / statsmodels changed
- [ ] Limitations disclosed on any result surface (Rule 16)
