# Spec 044 SC-004: split-table cross-check (DRAFT, primary-citation half only)

Drafted 2026-09-30 by Claude (chat lane), not the lane that wrote spec 044.
Method: each SEC URL was fetched on 2026-09-30 and the ratio/dates extracted by
the fetch tool's summarizer. Camden must open at least one URL per ticker and
confirm it (SC-004). The "provider value" column stays PENDING until the P-1
probe records the yfinance split table.

Basket (scripts/feature_diagnostics.py CACHE_TICKERS): AAPL, AMZN, GOOGL, MSFT, NVDA.
Scope: splits that matter for a window starting 2016 are those dated after the
window start. Earlier splits (AAPL 2014, GOOGL 2014) never enter F(t) for t >= 2016.

| Ticker | Ratio | First split-adjusted session (ex-date) | Primary source (fetched 2026-09-30) | Provider value |
|---|---|---|---|---|
| AAPL | 4:1 | 2020-08-31 | Press release 2020-07-30 (Ex. 99.1 to 8-K): https://www.sec.gov/Archives/edgar/data/320193/000032019320000060/a8-kexhibit991q3202062.htm ("trading will begin on a split-adjusted basis on August 31, 2020"); 8-K filed 2020-08-07: https://www.sec.gov/Archives/edgar/data/320193/000119312520213158/d49399d8k.htm | PENDING P-1 (yfinance showed Stock Splits=4.0 on 2020-08-31, Camden's diagnostic) |
| AMZN | 20:1 | 2022-06-06 | 8-K filed 2022-03-09: https://www.sec.gov/Archives/edgar/data/1018724/000101872422000009/amzn-20220309.htm ("Trading is expected to begin on a split-adjusted basis on June 6, 2022") | PENDING P-1 |
| GOOGL | 20:1 | 2022-07-18 | 8-K filed 2022-06-03: https://www.sec.gov/Archives/edgar/data/1652044/000119312522167375/d294315d8k.htm ("Trading is expected to begin on a split-adjusted basis on July 18, 2022") | PENDING P-1 |
| NVDA | 4:1 | 2021-07-20 | Press release 2021-05-21: https://www.sec.gov/Archives/edgar/data/1045810/000104581021000056/pr-may2021.htm (distribution after close 2021-07-19) | PENDING P-1 |
| NVDA | 10:1 | 2024-06-10 | Q1 FY25 press release 2024-05-22: https://www.sec.gov/Archives/edgar/data/1045810/000104581024000113/q1fy25pr.htm ("Trading is expected to commence on a split-adjusted basis ... Monday, June 10, 2024") | PENDING P-1 |
| MSFT | none in window | n/a | UNVERIFIED. No primary source fetched. Only secondary pages surfaced in search; none cited here. | PENDING P-1 |

## Not established
- Any split by any basket ticker from 2026-01-01 through the download date: UNVERIFIED (no primary check done; search returned only commentary articles). Splits after the window end still enter F(t), so this matters. Check each issuer's 2026 8-Ks before P-1 is judged.
- Announcement sources give the planned first split-adjusted date; the actual ex-date should be confirmed against the provider row (P-1) and, if available, the exchange notice.
- Extraction was done by a summarizing fetch tool, not by reading full filings.
