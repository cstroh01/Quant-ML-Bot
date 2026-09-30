# Spec 041 Unit 4 evidence (T013-T014, recording and disclosure)

Date: 2026-09-29 (Claude Code, local Windows session). No Git command was run.
Nothing here is a strategy result. Every test value is `EXAMPLE — NOT A RESULT`.
Environment: Windows 11, repository venv, `python -m pytest`, from `C:\GitHub\Quant-ML-Bot`.

## Files changed

| File | Change (lines) |
|---|---|
| `scripts/backtest_harness.py` | +10 / -3 (T013; net +7) |
| `scripts/ma_crossover_backtest.py` | +20 (T014 renderer and CLI call) |
| `reports/api/routes/backtest.py` | +2 / -1 (T014 import and field) |
| `reports/api/schemas.py` | +2 (T014 response field) |
| `tests/test_041_pay_date_bound.py` | +146 / -1 (12 new cases; net +145) |
| `tasks.md` | T013-T014 checked; Unit 4 evidence section |
| this file | new |

`scripts/data.py` was not edited (SHA-256 still
`2c0d1ccf003f13125ff8a1f21cccd0347604f35f2f3e0fc799d704274202e4b8`). Every edited
file was uniformly CRLF before and is uniformly CRLF after. The test file was
normalized to LF by the editor, then restored to CRLF on every line.

Post-edit SHA-256: `backtest_harness.py` `48a25596177941291afe2294274bdef284974d809641ffd6524d2449ffaa6bb1`,
`ma_crossover_backtest.py` `389c2310796c38bcfe0a9158aa95522b5a447212c665829dd88d85f2f92fe65e`,
`routes/backtest.py` `c2836285590ca3be72c5836995680b2370b7b08fcfd2979787ea42c84571c50b`,
`schemas.py` `8bdfbd7c80f45f330e2089b106d04eeb4a34716032e33f82d856f0c53367d6ff`,
`test_041_pay_date_bound.py` `2db8be1f5444e33fdd66b3ee527b157154e6a090e70d837e9dcbdd8ab0adc6e0`.

## What was implemented

- **T013 (FR-003, harness).** `run_backtest` adds a `Pay_Date_Basis` column to
  every ledger event. It is set only on `dividend` events, to the
  `Dividend_Pay_Date_Basis` value the frame handed in, and is null on all other
  events. It is recorded as `unspecified` when the column is absent **or** null
  on that row, and never inferred as `sourced`. No arithmetic line changed: the
  basis is read in one place, the `dividend` branch's `record` call. `metrics.equity_curve`
  reads ledger fields by name, so the extra column does not affect reconciliation.
- **T014 (FR-007, disclosure).** One renderer,
  `ma_crossover_backtest.pay_date_disclosure(attrs) -> str | None`. It returns
  `None` unless `dividends_bound > 0`. Otherwise it returns
  `Dividend pay dates: declared bound (policy=<policy>), <k> of <n> dividends; NOT vendor data.`
  with ` dividend cash never becomes buying power within this run.` appended
  for `unbounded`. Here `n = dividends_bound + dividends_sourced`, and a version-1
  `None` is counted as 0. Both FR-008 surfaces call it:
  - **CLI:** `main()` prints the line right after the provenance keys, only when
    it is not `None`.
  - **API:** `BacktestTearsheetResponse` gains
    `dividend_pay_date_disclosure: str | None = None`, filled from the same
    function. `source_limitations` is unchanged, as FR-008 requires.

## Tests (12 new cases)

| Test | Cases | What it proves |
|---|---|---|
| `test_harness_records_the_basis_it_was_handed_and_nothing_else_changes` | 4: `sourced`, `bound`, null, column absent | The dividend event records the handed basis; null or absent gives `unspecified`; other events are null; every other ledger column is `assert_frame_equal` to the sourced control (FR-006) |
| `test_pay_date_disclosure_renderer` | 4: version 1, all sourced, unbounded, `bound_sessions:5` | No line without bound dividends; `k of n` counts sourced too; the unbounded suffix appears only for `unbounded` |
| `test_cli_process_discloses_bound_pay_dates` | 2: bound, all-sourced | A real process runs the script as `__main__`; stdout carries exactly the FR-007 line, or no such line |
| `test_tearsheet_api_discloses_bound_pay_dates` | 2: bound, all-sourced | `/api/backtest/tearsheet` returns the FR-007 line, or `null` |

The expected line is spelled out verbatim from FR-007 in the test (`DISCLOSURE`),
not rebuilt from the renderer. The synthetic bundle has 160 sessions and three
dividends: one vendor-dated `sourced` row plus two `bound` rows under
`unbounded`, which gives "2 of 3". The control has three `sourced` rows under
`sourced`, so it has dividends yet must print nothing.

## Runs

The tripwire was checked before and after each run and matched every time:
`docs/trials/trials.jsonl` 174 lines, SHA-256
`1bb5dbfe90c9df370c65910650ade15dd9d0e0366d011e09baf303975275f30f`;
`trials.head.json` `f83b1b9be5a608d444d61496899d25139eb56184fd924acd030e61347d22d764`;
`docs/trials/returns/` absent; `tests/test_019_prices.py` `b7cc6cc4...c706` and
`tests/test_019_conventions.py` `05669610...157f` unchanged.

| Run | Command | Result | Tripwire (America/New_York) |
|---|---|---|---|
| U1 | `python -m pytest tests/test_041_pay_date_bound.py tests/test_020_unadjusted_price_data.py -q --tb=short -p no:cacheprovider` | 96 passed / 2 failed (API, see deviation 3) | 20:13:52 -> 20:14:03 OK |
| U2 | same, after the loopback fix | **98 passed / 0 failed** | 20:14:33 -> 20:14:45 OK |
| F1 | `python -m pytest tests -p no:cacheprovider -q --tb=short` | **986 passed / 0 failed, exit 0**, 1386 subtests passed, 275.93s | 20:15:02 -> 20:19:39 OK |

986 = 974 (Unit 3) + 12 = 903 (T001 baseline) + 83 (this file's cases). The two
warnings are the existing fastapi/starlette deprecations.
`data/cache/phase0_aapl_ma_crossover*` still carry their 2026-09-03 timestamps,
and nothing under `data/cache/` is newer than this unit's start.

## Deviations and flags

1. **036 shipped no renderer function.** FR-007 assumes "the one renderer 036
   introduces". In the merged code, provenance is printed inline in two places:
   the attrs loop in `ma_crossover_backtest.main` and the field list in
   `routes/backtest.py`. This unit adds one function and calls it from both
   surfaces, and the tests enumerate both. The function lives in
   `ma_crossover_backtest.py`, not `data.py`, because the API already imports its
   shared report constants from there and it keeps `data.py` untouched. No module
   boundary is crossed: the report layer reads bundle attrs it already read.
   Moving the function into `data.py` would be a small follow-up if Camden
   prefers the data layer to own it.
2. **The API needed a new response field.** FR-007 says the response "prints" the
   line, so it gets a dedicated nullable field. It is not appended to
   `source_limitations`, which is manifest-hashed provenance. No frontend
   consumes the tearsheet provenance fields today, so the JSON response is the
   surface.
3. **A loopback exception inside this module's network guard, scoped to the API
   tests.** The module's autouse `offline_only` blocks every `socket.connect`. On
   Windows, the TestClient's asyncio loop builds its self-pipe with
   `socket.socketpair()`, which falls back to a `127.0.0.1` connect. The
   `api_client` fixture re-patches `connect` to let only `127.0.0.1` and `::1`
   through, for those two tests only. Every other address still fails.
   `create_connection` stays blocked. The module-wide guard is unchanged.
4. **The CLI subprocess patches `data.cache_path`.** A plain run of the script
   writes `phase0_aapl_ma_crossover{_trades.csv,.png}` into the real
   `data/cache/`, overwriting Camden's outputs with synthetic ones. The
   subprocess therefore runs a short bootstrap. It points `data.cache_path` at
   `tmp_path`, then executes the unmodified script with `runpy.run_path(...,
   run_name="__main__")`, so the real `__main__` block, argument parsing and
   stdout are exercised. The child inherits the autouse `SPEC033_SYNTHETIC_ROOT`,
   and the test asserts that it is set, so its trials land in a labelled
   synthetic ledger.
5. **`unspecified` also covers a null basis on a dividend row**, not only an
   absent column. FR-003 names only the absent case. A null value is the same
   non-statement, and recording `NaN` would be a fourth, unnamed state.
6. **Rule 12.** T013 and T014 add recording and a disclosure, not gates. Each
   still has a plausible defect its tests would catch:
   - defaulting a missing basis to `sourced` fails the `absent` and null cases;
   - `n = k` fails "2 of 3";
   - printing unconditionally fails the all-sourced control;
   - dropping the unbounded suffix fails the bound CLI and API cases.

   No mutant was run in this unit. The Unit 3 flags (sentinel limit, M2 oracle
   gap, unproven new gates, the stale manual mutation-driver target) are
   unchanged and still owed at T015.
7. **Nothing looks too good.** No performance figure was produced or read. The
   CLI and API runs are on synthetic sine-wave bars, and their P&L output is not
   inspected by any assertion.

## Not done (out of scope)

T015 (`killed()` wiring and red proofs), T016-T017 final verification, T018
(Camden's online AAPL run), T019 hand-off. Rule 14 is still owed.

## For Camden to run on Windows

    python -m pytest tests/test_041_pay_date_bound.py tests/test_020_unadjusted_price_data.py -q --tb=short
    python -m pytest tests

Expect 98 passed, then 986 passed, both with 0 failed.
