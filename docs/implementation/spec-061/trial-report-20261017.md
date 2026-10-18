# Fresh buffered equal-weight allocation — 2026-10-17

ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED

Camden selected the 7%-reserve variant after seeing 059 T004. This is a fresh,
post-hoc, in-sample allocation trial, not adoption of historical B-BH. A1 and
the old B-BH trial remain unchanged. This report does not deploy the allocation.

| Fresh series | Annualized Sharpe | PSR at own family N=1 |
|---|---:|---:|
| B7-EW, 93% gross target | 0.266148 | 0.929295 |
| Unbuffered monthly equal-weight comparator | 0.284112 | 0.941736 |
| Random baseline, mean across 20 seeds | -0.008746 | not aggregated |
| Random baseline, sample standard deviation | 0.108214 | not aggregated |

All figures: **ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED**. Random seeds are
20261015 through 20261034; the random book uses 93% gross when nonempty and
long/flat draws at probability 1/2 on monthly decisions. Cadence is matched;
exact realized turnover is not matched. No strategy superiority is claimed.

Costs, identical for all 22 series: commission $0 per fill; spec 046 primary
EDGE half-spread plus square-root impact Y=1, 21-session windows, on raw nominal
OHLCV; quantities converted by decision-close notional. Not flat bps. Research
capital $100,000; no cash interest or final liquidation. One single research
pass with no fitted parameters; CV fold count, purge and embargo do not apply.
The initial panel session is 1993-01-29; 7,722 daily funded log-return rows run
from 1993-02-01 through 2023-09-29. No holdout evaluation was performed.

## Verified provenance

- Candidate: `8d4dfeda-10ef-4951-bf0e-147090ea9731`.
- Fresh unbuffered comparator: `ad83b64c-edb0-4490-8bef-fac665439370`.
- Family: `061-buffered-allocation`; one candidate and 21 comparisons completed,
  zero failed; all 22 starts preceded the first completion.
- Declaration: `docs/trials/families/061-buffered-allocation.json`;
  hash `4a154bfb27bd89dc484b466066b83e01baca20dc98f577c7beb4f4ca24f3b55f`.
- Candidate return sidecar: `docs/trials/returns/8d4dfeda-10ef-4951-bf0e-147090ea9731.jsonl`;
  SHA-256 `1d5ffbfc2a1a253cccb1d2367499aa9c36c30079ccc57e2458f7437b45234c18`.
- Candidate weight-book hash:
  `d3cbd02ff1bac43dd3b3e874f93877a895d7d59f88ad7bfbd99a891a3037014a`.
- Research panel:
  `3b80b330039b0c1b07b404371005ef71d064e2af093816c324d3546bcc9c7065`;
  existing T008 bodies with T009 checks/exclusions, no download.
- Recorded source base: `8244bca441a1a0dd787bc710b23063f5d0c6b907`;
  **workspace unknown, with local draft code**, not a claim that main contains
  this implementation. Recorded source-tree hash:
  `c1caa1c5eb6f791e2f4ccc1a6b8af3a192f42642dc567b80c4c993ec1b962876`.
- Candidate completed at `2026-10-17T15:47:53.043068+00:00`.
- Final verified ledger: 898 lines, head
  `c510408010dd8af4e1cdbeeb2c686706a8f33b0aa052272c2353e840ebcc17cc`;
  SHA-256 `6c3c416edba3ea9b52d05ea59967d20be7b755204787312d731250fc53e7e65e`.
  The historical 854-line prefix is byte-identical.
- Fresh versus historical unbuffered comparison: identical session labels and
  total log return; maximum per-row difference 3.35e-16. The sidecars differ in
  bytes and are not represented as an exact byte-for-byte reproduction.

## Limitations

The ETF universe is a static survivor basket, excluding closed funds; corporate
actions are free-tier and partially reconciled; no point-in-time fundamentals;
daily bars only; slippage is modeled and has not been calibrated to real fills.
Dividend payment dates use the declared conservative bound. The 7% reserve is
a pre-cost target at rebalance, not a guaranteed cash floor after price moves
or costs. Actual execution additionally uses rounding, minimums, deployment
caps and deferred buys. These $100,000 research results do not establish that
all eight orders are executable in a $200 account. No real capital has been
deployed; all capital, PAPER and preview gates still apply.
