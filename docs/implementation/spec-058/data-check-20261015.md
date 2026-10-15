# 058 T009 data check, 2026-10-15

Status: **EXCLUSIONS; E4 complete, T009 unticked**.
Public source: `0e7a55179c81319e1465c40f2aca8f047184e4ab`; recorded D-10 present; T008 raw bodies 75/75 SHA-256 matched.
Only sessions through 2023-09-29 entered numeric parsing. No holdout, signal, strategy, P&L or Sharpe.
Prices, volumes, dividend amounts and diagnostic return values are absent; counts/dates only.

| Ticker | Rows | First | Last | Gaps | Close mismatch/missing | Actions verified/mismatched/single-source | Diagnostic flags | Exclusions |
|---|---:|---|---|---:|---:|---|---:|---:|
| DBC | 4444 | 2006-02-03 | 2023-09-29 | 0 | 3/0 | 3 / 1 / 3 | 4 | 4 |
| DIA | 6467 | 1998-01-20 | 2023-09-29 | 0 | 11/0 | 87 / 6 / 213 | 3 | 17 |
| EEM | 5152 | 2003-04-14 | 2023-09-29 | 0 | 8/0 | 16 / 0 / 27 | 16 | 8 |
| EFA | 5564 | 2001-08-17 | 2023-09-29 | 0 | 1/0 | 16 / 0 / 25 | 17 | 1 |
| GLD | 4748 | 2004-11-18 | 2023-09-29 | 0 | 4/0 | 0 / 0 / 0 | 0 | 4 |
| HYG | 4148 | 2007-04-11 | 2023-09-29 | 0 | 6/0 | 90 / 2 / 105 | 9 | 8 |
| IEF | 5332 | 2002-07-26 | 2023-09-29 | 0 | 0/0 | 91 / 1 / 161 | 0 | 1 |
| IWM | 5873 | 2000-05-26 | 2023-09-29 | 0 | 28/0 | 30 / 1 / 64 | 5 | 29 |
| LQD | 5332 | 2002-07-26 | 2023-09-29 | 0 | 6/0 | 91 / 1 / 161 | 0 | 7 |
| QQQ | 6181 | 1999-03-10 | 2023-09-29 | 0 | 0/0 | 28 / 3 / 46 | 0 | 3 |
| SHY | 5332 | 2002-07-26 | 2023-09-29 | 0 | 0/0 | 90 / 2 / 161 | 0 | 2 |
| SPY | 7723 | 1993-01-29 | 2023-09-29 | 1 | 20/0 | 28 / 3 / 93 | 5 | 28 |
| TIP | 4988 | 2003-12-05 | 2023-09-29 | 0 | 0/0 | 67 / 1 / 106 | 2 | 1 |
| TLT | 5332 | 2002-07-26 | 2023-09-29 | 0 | 1/0 | 91 / 1 / 161 | 1 | 2 |
| UUP | 4176 | 2007-03-01 | 2023-09-29 | 0 | 0/0 | 4 / 0 / 2 | 1 | 0 |
| VNQ | 4784 | 2004-09-29 | 2023-09-29 | 0 | 8/0 | 30 / 1 / 45 | 32 | 9 |
| XLB | 6233 | 1998-12-22 | 2023-09-29 | 0 | 11/0 | 29 / 2 / 68 | 14 | 13 |
| XLE | 6233 | 1998-12-22 | 2023-09-29 | 0 | 31/0 | 29 / 3 / 68 | 21 | 34 |
| XLF | 6233 | 1998-12-22 | 2023-09-29 | 0 | 47/0 | 28 / 4 / 68 | 15 | 51 |
| XLI | 6233 | 1998-12-22 | 2023-09-29 | 0 | 10/0 | 29 / 2 / 68 | 9 | 12 |
| XLK | 6233 | 1998-12-22 | 2023-09-29 | 0 | 9/0 | 29 / 2 / 42 | 1 | 11 |
| XLP | 6233 | 1998-12-22 | 2023-09-29 | 0 | 7/0 | 29 / 2 / 68 | 5 | 9 |
| XLU | 6233 | 1998-12-22 | 2023-09-29 | 0 | 12/0 | 29 / 2 / 69 | 19 | 14 |
| XLV | 6233 | 1998-12-22 | 2023-09-29 | 0 | 14/0 | 29 / 3 / 62 | 2 | 17 |
| XLY | 6233 | 1998-12-22 | 2023-09-29 | 0 | 3/0 | 29 / 2 / 68 | 2 | 5 |

Full per-ticker gap, mismatch, missing, action and exclusion session lists are in the JSON.
Tiingo raw close vs retained Alpaca raw SIP uses data_sources.close_mismatches, relative tolerance 1e-3.
Calendar checks use data.trading_days between each ticker's first/last observed research rows.
Four SPY calendar flags fall on January dates in 1994-1997; historical holiday treatment is UNVERIFIED.
They are conservatively excluded under the requested repo calendar, not claimed as proven vendor defects.
Diagnostic D-10 reconstruction applies dividends and splits backward only within the research window;
consecutive NYSE daily changes are compared with provider adjClose, flag threshold 1 bp. Never used as panel.

E4: Alpaca market-data corporate actions, 2 requests, all HTTP 200; no fallback.
Every key-free endpoint, status and response SHA-256 is recorded in the JSON fetch record.
2016-onward actions: 1022 verified ticker-sessions, 45
mismatched ticker-sessions (including source-only dates). Mismatches are excluded; no averaging.
Mismatch categories: {'tiingo_only': 22, 'alpaca_only': 2, 'dividend_value': 21, 'split_ratio': 0} (a date can have both value and ratio differences).
Pre-2016: 1954 action sessions are single-source, disclosed per D-10.
Provider-adjustment diagnostic flags total 183; no averaging or substitution.

Panel hash: `3b80b330039b0c1b07b404371005ef71d064e2af093816c324d3546bcc9c7065` (D-10 inputs and exclusions; T009 remains unticked).
Exact canonical input (sorted keys, compact UTF-8) is retained as panel_hash_input in the JSON;
Tiingo prices and Alpaca raw SIP bodies are sorted [ticker, SHA-256] pairs. No metadata bodies in that hash.
Totals: 141673 research rows; 240 close mismatches;
0 missing ticker-sessions; 290 excluded ticker-sessions.

Limitations: free-data survivor ETF basket; listing dates unverified; pre-2016 actions single-source;
Alpaca filters by process date. No statistical or capital-readiness claim. Camden owns T009 tick.
Ledger before/after: 174 lines, SHA-256 `1bb5dbfe90c9df370c65910650ade15dd9d0e0366d011e09baf303975275f30f`, unchanged. No T009 checkbox edit.
