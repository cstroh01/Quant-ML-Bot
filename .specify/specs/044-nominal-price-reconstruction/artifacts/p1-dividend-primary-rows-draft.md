# Q-P3 primary dividend rows (DRAFT; to be converted into p1-declared-dividends.csv once the schema exists)

Fetched 2026-09-30 by Claude (chat lane) from SEC-hosted documents; values extracted by the
fetch tool's summarizer. Camden must open at least one URL per ticker (SC-004). Provider values are
PENDING the P-1 run, except the AAPL row, where Camden's read-only diagnostic already showed 0.205.

| # | Ticker | Declared amount (as stated) | Basis stated by issuer | Declared on | Record date | Payable | Later splits (factor applies) | Expected provider value if adjusted | Source |
|---|---|---|---|---|---|---|---|---|---|
| 1 | AAPL | $0.82 per share | nominal (stated before the 4:1 split, which takes effect 2020-08-31) | 2020-07-30 | 2020-08-10 | 2020-08-13 | 4:1 (2020-08-31) | 0.205 (observed 0.205 on 2020-08-07, Camden's diagnostic) | https://www.sec.gov/Archives/edgar/data/320193/000032019320000060/a8-kexhibit991q3202062.htm |
| 2 | NVDA | $0.16 per share | nominal (pre-split; 4:1 distributed 2021-07-19) | 2021-05-26 | 2021-06-10 | 2021-07-01 | 4:1 (2021-07-20), 10:1 (2024-06-10), cumulative 40 | 0.004 | https://www.sec.gov/Archives/edgar/data/1045810/000104581021000063/q1fy22pr.htm |
| 3 | NVDA (control, F=1) | $0.10 pre-split = $0.01 post-split | both stated | 2024-05-22 | 2024-06-11 (after the 2024-06-10 split) | 2024-06-28 | none | 0.01 (no factor; ex-date is after the split) | https://www.sec.gov/Archives/edgar/data/1045810/000104581024000113/q1fy25pr.htm |

Notes
- Ex-dates are not in these documents. The provider row's date is the ex-date under test; the probe must
  compare on the provider's ex-date, not the record date. Under T+1 (from 2024-05-28) ex-date equals record date.
- AMZN and GOOGL pay no dividend around their 2022 splits (Alphabet's first dividend came after its split),
  and MSFT has no basket-window split. So Q-P3 can rest on rows 1 and 2, with row 3 as a boundary control. Basket-wide
  coverage is therefore two informative cases, which the spec's coverage rule must state explicitly.
- Not established: each row's provider value except AAPL; whether the provider's ex-date row matches the declared
  per-share amount on a same-day split/dividend (none of these rows has that case).
