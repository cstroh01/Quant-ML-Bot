# 051 U2 evidence, 2026-10-07 (Linux, Python 3.13.16)

Red first: `tests/test_051_sizing.py` failed collection (names absent). Green: 11 passed.
Inflated broker cash ($1,000,000) leaves spend at the $1,000 daily cap of a $5,000 budget.
| Mutant | Result |
|---|---|
| sizing equity taken from broker balance | killed |
| daily cap ignored | killed |
| settled cash ignored | killed |
| fractions for a non-fractionable instrument | killed |
| fractional quantity rounded instead of floored | killed |
| broker minimum ignored | killed |
| already-deployed notional not counted | killed |
