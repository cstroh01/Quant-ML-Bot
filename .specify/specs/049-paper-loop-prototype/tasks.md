# Tasks: 049 paper-loop prototype

- [x] T001 `scripts/paper_targets.py`: trend confidence, `plan_next_open`, whole-share `order_deltas`, `PAPER_RISK_CONFIG`.
- [x] T002 `exec/alpaca_paper.py`: paper-only REST client (account, positions, clock, order status, market-on-open submit), credentials from env.
- [x] T003 `exec/paper_loop.py`: reconcile → data → decide → gate → submit → log; `--offline`, dry run, `--submit`.
- [x] T004 `tests/test_049_paper_loop.py`: 18 offline tests (fakes only).
- [x] T005 Rule 12: 8 planted defects, each killed (table below), files restored byte-identical.
- [ ] T006 Full suite on Windows (authoritative). Linux evidence: focused module 18 passed.
- [ ] T007 **Human gate (network):** `python exec/paper_loop.py --offline` on real data.
- [ ] T008 **Human gate (credentials):** Alpaca paper keys into `.env`; `python exec/paper_loop.py` dry run.
- [ ] T009 **Human gate (first submit):** `--submit` before 09:28 ET; confirm orders at Alpaca; next run releases reservations.
- [ ] T010 **Human gate:** D-1 to D-5 in spec §3.
- [ ] T011 Follow-on (lane-safe, `scripts/` only): `scripts/paper_report.py` daily markdown report from `runs.jsonl` with Rule 16 disclosure.
- [ ] T012 Follow-on (lane-safe): signal-decay monitor — rolling hit rate of the trend state vs next-session return against a coin-flip baseline.
- [ ] T013 Follow-on (reviewed lane, `exec/`): broker-vs-intended position reconciliation report.

## Rule 12 record (2026-10-04, Linux, Python 3.13)

| Mutant | Planted defect | Killed by |
|---|---|---|
| M1 | confidence reads the full panel, not `closes.loc[:session]` | `test_future_rows_change_nothing` |
| M2 | buys round up (`ceil`) | `test_buys_floor_sells_first_and_absent_names_flatten` |
| M3 | buys before sells | same |
| M4 | today's partial bar treated as completed (`<=`) | `test_todays_partial_bar_is_ignored` |
| M5 | dry run sends orders | `test_dry_run_submits_and_reserves_nothing` (+1) |
| M6 | submit bypasses `order_gateway` | `test_kill_latch_blocks_every_buy` (+2) |
| M7 | stale-session check removed | `test_stale_data_aborts` |
| M8 | unknown broker status releases the reservation | `test_reconcile_releases_only_terminal` |
