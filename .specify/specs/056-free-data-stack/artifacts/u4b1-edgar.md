# 056 U4b1 evidence, 2026-10-08 (Linux, Python 3.13.16); fixtures synthetic, EXAMPLE — NOT A RESULT
Red first: collection failed (names absent). Green: 5 passed; unmutated-copy control green (5 passed).
| Mutant (planted in a /tmp copy, never committed) | Result |
|---|---|
| EDGAR fact visible by period end instead of filed date | killed |
| EDGAR periods collapsed (3-month vs year-to-date share an end) | killed |
| acceptance `Z` trusted as UTC (filing visible ~4-5 h early) | killed |
| rate limit never waits | killed |
| EDGAR adapters get separate limiters (aggregate >10/s) | killed |
| SEC User-Agent not required | killed |

## Open questions
1. `acceptanceDateTime` ends in `Z`, but its wall clock is read as New York time (the later, conservative
   reading). UNVERIFIED: check one filing's index-page "Accepted" time during T006.
2. `facts_as_of` works at day granularity: a fact accepted 16:00-17:30 New York keeps filing date D, so it is
   visible at D's close. Callers deciding at D's close should use the prior session, or join
   `EdgarSubmissions.accepted_at` by accession. Needs a spec decision.
3. `facts_as_of` (U3) keys on `end` only; `EdgarCompanyFacts.as_of` groups by `start` so 3-month and
   year-to-date facts sharing an end do not collide. Keying U3 itself on (start, end) may be cleaner.
