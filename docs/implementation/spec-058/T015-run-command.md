# 058 T015 run command (queue Q133), 2026-10-15

EXAMPLE evidence only — synthetic bodies and ledgers. T015 itself is Camden's run.

## Commands (Camden, Windows, repo root)
```powershell
$py = ".\venv\Scripts\python.exe"
$raw = "C:\Users\Owner\OneDrive\Building Skills\Quant Project Claude\finish-20261007\codex-lane\raw\058-tiingo-202610092125350463950000"
& $py scripts\run_058_t015.py --panel $raw --dry-run
# read the summary (25 tickers, sessions end 2023-09-29, excluded/splices per ticker); if right:
& $py scripts\run_058_t015.py --panel $raw --record-trial --out "C:\Users\Owner\OneDrive\Building Skills\Quant Project Claude\T015-run"
```
Record `docs/trials/trials.jsonl` line count and SHA-256 before and after (174 lines, `1bb5dbfe…` on 2026-10-15).

## What the run does
- Panel (`data_sources.load_058_panel`, D-10 B): finds the 25 `/prices` bodies by SHA-256 (T008 manifest = T009
  `panel_hash_input`), reproduces T009's panel hash `3b80b330…`, drops rows after RESEARCH_END before any frame.
  P&L on in-repo back-adjusted raw OHLC; T009 exclusions are NaN (not tradable; ffill marks bridge them).
- **Action-mismatch sessions (45) are spliced:** zero return from the last included session before the ex-date
  to the first included one after. An unverified dividend or split never prints as a loss (e.g. XLF 2016-09-16/19,
  the XLRE special distribution). The ticker's market move over that gap is also not booked — disclosed.
- Pre-2016 actions are single-source Tiingo, applied, disclosed (D-10).
- Costs: spec 046 primary (Y = 1.0) on raw nominal bars, `volume_basis=provider_nominal`, split sessions from
  `splitFactor != 1`; fill quantity converted by notional at the decision close. Commission $0 per fill
  (US ETF retail); recorded explicitly. Starting capital $100,000.
- Preflight (named refusals before any ledger byte): family verifies; declared gate3 risk-free equals the
  recorded one; data check VERIFIED/EXCLUSIONS with matching panel hash; no prior 058-edge candidate unless
  `--rerun "<reason>"`; `git status` clean under scripts/; CostConfig primary.
- Order: 15 candidates as declared, B-BH, then B-RND 15 x 20 seeds (316 trials). First error stops the run.

## Fixed in this unit
`edge_walk_forward` recorded `risk_free` 0.0 while the declared gate3 rate is 0.0378. `build_matrix` excludes
any trial whose risk-free differs (`risk_free_mismatch`), so every T015 trial would have been dropped and
Gate 3 would have had no matrix. Trials now record `{"annual_rate": 0.0378, "days_per_year": 252}`.

## Runtime
Synthetic full-size panel (25 tickers x 6,478 sessions, real `estimate_fill_cost`): ~30 s per configuration
on the cloud runner (H1-12 29 s, H8 25 s). 316 runs ≈ 2.6 h; allow 3-5 h on the laptop. No caching needed (< 8 h).

## Verification
`tests/test_058_t015.py` 13 passed; `tests/test_058_walk_forward.py` 28 passed. `run_058_t015_mutants.py`:
control PASS, 8/8 killed (M1 raw-close P&L, M2 unconverted quantity, M3 data-check preflight, M4 truncation,
M5 silent rerun, M6 order, M7 splice removed, M8 risk-free 0), sources restored.
