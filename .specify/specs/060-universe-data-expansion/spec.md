# Feature Specification: Expanded ETF universe and free-data additions

**Spec number**: 060
**Created**: 2026-10-12
**Status**: Draft. D-1 and D-2 recorded from Camden's chat answers of 2026-10-12.
**Related**: 052 (point-in-time registry), 056 (free data stack), 035 (unadjusted cache), 058
(its preregistered 25-ETF family is NOT changed by this spec), 059 (allocation),
`docs/SCOPE-V1.md` §2, §6, §11.2, constitution Rules 1, 11, 14, 16.

## 1. Purpose
Broaden the tradable universe from 25 to about 100 liquid US-listed ETFs, and add the free data
sources Camden chose, each verified before code depends on it.

## 2. Recorded decisions (Camden, chat, 2026-10-12)
- **D-1 Universe.** "~100 liquid ETFs" — not single stocks.
- **D-2 Data.** Alpaca, Tiingo, SEC EDGAR, FRED/ALFRED, EODHD free, plus Massive (Camden has a key),
  plus "more research into possible free ones that would be useful".
- **D-3 Class coverage (PR #180; Camden, chat, 2026-10-12 19:25 CT: "Yes to all" (decision list `claude/decisions-20261012.md`)).** One reserved slot per asset class; the $20M floor and
  every other §3 screen still apply to it.
- **D-4 Vintage lag (PR #184; Camden, chat, 2026-10-12 19:25 CT: "Yes to all" (decision list `claude/decisions-20261012.md`)).** FR-003 uses a strict `<`, matching the merged adapter.

## 3. Universe rule (fixed now)
An ETF is eligible on date `d` when all hold, using only data known at `d` (Rule 1):
1. Flagged `ETF = Y` in the Nasdaq Trader `otherlisted.txt` directory, or listed on Nasdaq and
   identified as an ETF by issuer reference data; not a test issue.
2. Not leveraged, inverse, or volatility-linked (ETP name and issuer category screen, reviewed list).
3. At least 3 years of daily history at `d`.
4. Trailing 252-session median dollar volume ≥ $20 million at `d`.
5. Asset-class tag from a fixed taxonomy: US equity broad, US equity sector, US equity factor/style,
   international developed, emerging, Treasuries by duration, TIPS, IG credit, high yield, munis,
   real estate, commodities broad, gold/precious, currency.

The v1 list is the ~100 highest-dollar-volume eligible ETFs on 2026-10-01, capped at 12 per class so
no class dominates, with one slot reserved per class for that class's highest-dollar-volume eligible
ETF (a class with no eligible ETF is reported absent with its reason, not refused) (D-3), stored as `docs/universe/etf_universe_v1.csv` with listing date, class and the
reason any candidate was excluded (spec 052). Disclosed: chosen as of 2026, so closed ETFs are
absent (survivorship, Rule 16).

**Spec 058 is untouched.** Its 25-ETF family stays as preregistered; this list feeds spec 059's
future revisions and later preregistered families only.

## 4. Data sources (verification required before use; each record in `research.md`)
| Role | Source | Free terms (checked 2026-10-12 unless noted) | Status |
|---|---|---|---|
| Primary daily bars | Alpaca raw SIP | Adopted in 056 | Adopted |
| Independent price check | Tiingo EOD | 500 unique symbols/month on free; ~100 ETFs fits | Adopted (056) |
| Filings, corporate-action evidence | SEC EDGAR | Free, ~10 requests/s | Adopted (056) |
| Macro with vintages | FRED / ALFRED | Free key | Adopted (056) |
| Last-year corporate actions | EODHD free | 1 year history | Adopted (056) |
| 2-year corporate actions, reference tickers incl. inactive | Massive Stocks Basic | $0, 5 calls/min, 2 years, end-of-day, "individual use" (massive.com/pricing) | Candidate: verify ETF coverage and inactive-ticker listing |
| ETF flag, symbol directory | Nasdaq Trader `otherlisted.txt` | Public FTP directory with ETF and test-issue fields | Candidate: verify HTTP access from the runner |
| Cash rate | US Treasury daily yield curve | Public | Candidate |
| Stress-window labels | Cboe VIX daily history | Public CSV | Candidate |
| Factor attribution | Kenneth French data library | Public | Candidate, attribution only |
| Tertiary price check | Stooq | API key required since March 2026 | Not adopted unless the key is free |

## 5. Requirements
- **FR-001 Universe builder.** Offline function applying §3 to a registry snapshot and bar panel;
  every exclusion carries a reason.
- **FR-002 Massive adapter.** Corporate actions and reference tickers (active and inactive), rate
  limited to 5/min, key from environment only, manifests per 056, offline fakes in tests.
- **FR-003 Macro and rates adapters.** FRED/ALFRED by real-time vintage (a value is usable at `d`
  only if its vintage start < `d`: ALFRED vintages carry dates without times, so a same-day vintage
  is treated as known the next session) (D-4); Treasury yields by publication date.
- **FR-004 Cross-source reconciliation.** Massive joins Tiingo/EODHD/EDGAR as an independent
  corporate-action source in spec 035's reconciliation; disagreements are disclosed, never resolved
  silently (Rule 14).
- **FR-005 Fetches.** Real fetches are bounded runs in the Codex lane (keys as secrets); raw vendor
  data stays private; manifests are public.

## 6. Rule 12 mutants
An ETF admitted before 3 years of history; dollar volume computed with a future window; a leveraged
ETF passing the screen; an ALFRED value used before its vintage; a Massive key read from a file in
the repo; a disagreeing corporate action accepted silently.
