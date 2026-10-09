# 056 U4a evidence, 2026-10-08 (Linux, Python 3.13.16); fixtures synthetic, EXAMPLE — NOT A RESULT
Red first: collection failed (names absent). Green: 13 passed; unmutated-copy control green (13 passed).
| Mutant (planted in a /tmp copy, never committed) | Result |
|---|---|
| Tiingo reads `adj*` fields into raw columns | killed |
| Alpaca requests `adjustment=all`, manifest still `raw` | killed |
| Tiingo adjusted-stamped-raw refusal removed | killed |
| Tiingo token sent as a URL parameter (reaches manifest) | killed |
| failure message echoes the transport error (URL/headers) | killed |
| Alpaca `end` only required to be past, not 15 minutes old | killed |
| session kept by midnight label instead of 16:00 New York close | killed |
| Tiingo cutoff without the 15-minute margin | killed |
| pagination ignored after the first page | killed |
| only the last page hashed | killed |
| Tiingo midnight-UTC label converted to New York (one-day shift) | killed |

## Open questions
4. A session counts as complete at its 16:00 New York close, ignoring early closes (conservative) and late SIP
   corrections; Tiingo publishes ~17:30 ET with evening corrections, so its cutoff may belong at next morning.
5. Alpaca daily `t` is assumed to be New York midnight written in UTC; the UTC date gives the same label, so
   no test can tell the readings apart. Confirm on the first authorized fetch (T006).
