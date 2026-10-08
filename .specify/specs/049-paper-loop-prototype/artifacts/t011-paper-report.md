# 049 T011 evidence, 2026-10-08 (Linux, Python 3.13.16)

Extends the merged `scripts/paper_report.py` (PR #50) with the daily report; no second module.
`render_run` and its contract are unchanged. CLI: `paper_report.py [log] [--profile NS] [--date D] [--out P]`,
default log `data/live_safety/paper-runs/runs.jsonl`, profile log `data/live_safety/<NS>/paper-runs/runs.jsonl`.

Report: grouped by New York run date; per day the runs (source line, session, mode, profile, equity,
safety config, example label), aborted runs with reason, reconciliation rows, actions grouped by outcome,
and every outcome other than `SUBMITTED`/`DRY_RUN` (a missing outcome included) with its reason. The Rule 16
block (`LIMITATIONS` plus each run disclosure verbatim) is printed at top and bottom. No return, Sharpe or
equity change is computed. Malformed lines (bad JSON, rejected record, zoneless `run_at_utc`) are listed with
file:line and error; exit 1. Contract change: the old CLI exited 2 on the first malformed line.

Red first: 5 of 16 tests failed (`render_daily`, `log_path`, `LIMITATIONS` absent). Green: 16 passed.
Mutants planted in a copy outside the repo (`/tmp/.../mut-tree`), restored byte-identical; green control first.

| Mutant | Result |
|---|---|
| bottom disclosure block dropped | killed |
| limitations dropped from the block | killed |
| aborted runs skipped | killed (2) |
| malformed line skipped silently | killed |
| refusals list only `DENIED` | killed |
| missing outcome read as `SUBMITTED` | killed |
| equity-change percentage planted | killed (3) |
| `--out` may overwrite the input log | killed |
| example label dropped from run rows | killed |
| profile name may be a path (`..`, `a/b`) | killed |
| zoneless `run_at_utc` accepted | killed |
| `--date` filter ignored | killed |
| exit 0 despite malformed lines | killed |

Full suite: 1388 passed. `docs/trials` sha256 manifest identical before and after.
Fixtures are synthetic. EXAMPLE — NOT A RESULT.
