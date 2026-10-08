# 056 U4b2 evidence, 2026-10-08 (Linux, Python 3.13.16); fixtures synthetic, EXAMPLE — NOT A RESULT
Red first: collection failed (names absent). Green: 6 passed; unmutated-copy control green (6 passed).
| Mutant (planted in a /tmp copy, never committed) | Result |
|---|---|
| OpenFIGI batch of 10 jobs | killed |
| OpenFIGI answers misaligned with jobs accepted | killed |
| ALFRED vintage ignored (latest revision used) | killed |
| ALFRED `realtime_end` ignored | killed |
| ALFRED `api_key` kept in the manifest endpoint | killed |
| ALFRED truncated response (`count` > rows) accepted | killed |
| French reads past the first table into annual rows | killed |
| French percent not converted to decimal | killed |
| French -99.99/-999 missing codes kept as values | killed |
| French CIZ/FIZ label unchecked | killed |
| French month labelled at month start | killed |

First run: French row-length check survived; it was unreachable (blank line and second header already end
the table), so it was removed as dead code and replaced by the "reads past the first table" mutant above.
