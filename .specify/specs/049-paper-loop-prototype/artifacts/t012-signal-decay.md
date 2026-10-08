# 049 T012 evidence, 2026-10-08 (Linux, Python 3.13.16)

`scripts/signal_decay.py` builds on the merged `paper_monitor.monitor` (PR #51), which owns state and outcome.
As of session s, per ticker: hits of the long state (`paper_targets` rule) over the last `window` decisions
with t+1 <= s. The panel is cut at s first; only rows whose outcome session matured are read.
Flat state and zero or missing returns are excluded, never counted as misses. Exact two-sided binomial
p-value vs 0.5 (`math.comb`). Seeded matched-frequency random baseline (`default_rng([seed, column])`).
`Decay` = at least `min_obs` long calls and hit rate strictly below `threshold`. Output carries the
Rule 16 block at top and bottom.

Red first: collection failed (module absent). Green: 15 passed.

| Mutant | Result |
|---|---|
| hit counted on its own decision day (full panel, decision-date filter) | killed (6) |
| panel cut removed only | killed by the provenance-hash check |
| decision-date filter only | killed (window shifts) |
| seed ignored | killed |
| global RNG used for draws | killed |
| p-value one-sided | killed |
| flat state counted as a miss | killed (5) |
| zero move counted as a miss | killed |
| decay flag ignores `min_obs` | killed |
| decay flag at equality | killed |
| bottom disclosure dropped | killed |
| window ignored | killed |
| random baseline drawn from long calls only | killed |

Anti-lookahead test perturbs Close at s+1, the one close that decides r(s -> s+1).

Synthetic example (EXAMPLE — NOT A RESULT): ticker A, as of 2024-03-14, 20 long calls, 11 hits, p 0.8238.
