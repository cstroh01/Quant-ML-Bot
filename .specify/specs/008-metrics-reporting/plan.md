# Implementation Plan — 008 Metrics Reporting Layer

**Spec**: `.specify/specs/008-metrics-reporting/spec.md`

---

## Scope

- `scripts/constants.py` — **new**. `TRADING_DAYS_PER_YEAR`,
  `RISK_FREE_RATE_ANNUAL` (FR-010)
- `scripts/metrics.py` — **new**. The reporting layer (FR-001 – FR-009)
- `scripts/return_stats.py` — imports the two constants instead of defining
  them; nothing else changes (FR-011)
- `tests/test_metrics.py` — **new** (FR-013)

Explicitly **not** touched: `scripts/backtest_harness.py` (FR-002),
`signals.py`, `data.py`, `plotting.py`, `logistic_baseline.py`,
`walk_forward_cv.py`, `ma_crossover_backtest.py`.

**No new dependency.** numpy and pandas only.

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 3 — Costs mandatory | `commission_per_trade` and `slippage_bps` are required keyword arguments with no defaults, and both are echoed in `performance_summary`'s output and the curve's `attrs`. The capital base is treated the same way: any denominator a headline number divides by is recorded beside it. `test_costs_reach_the_metric` proves costs actually change the reported Sharpe. |
| 4 — Baselines | This spec supplies the common denominator Rule 4 needs. Comparing a strategy to buy-and-hold in dollars-on-one-share is not a comparison; on a stated capital base it is. |
| 5 — Tests | The module indexes and aligns on timestamps throughout. Coverage: off-by-one (one-bar hold), boundaries (bar 0, final bar, `e == x`), gap (missing session), plus the validation guards. |
| 6 — Dependencies | None added. |
| 8 — Layer separation | `metrics.py` imports only `constants`, numpy, and pandas. It reads the harness's *output*, never its code, and the harness is not modified. |
| 9 — The merge gate | The mechanism is one identity: the four-part per-bar attribution telescopes to `X - E - 2c`, which is the harness's own P&L expression. |
| 10 — Version control | No `git` run outside the Actions lane. |

---

## Design

### Per-bar attribution

For a trade entered at bar `e`, exited at bar `x`, with the log's recorded
(already slipped) prices `E`/`X` and commission `c`:

```
bar e            :  Close[e]  - E          - c
bars i in (e, x) :  Close[i]  - Close[i-1]
bar x            :  X         - Close[x-1] - c
bars not held    :  0
```

Summing collapses every intermediate `Close` and leaves `X - E - 2c` —
`backtest_harness.py:75` term for term. `equity_curve` **checks** this at
runtime and raises if it fails, so a future change to either side cannot
drift silently.

Two properties of the harness make this simpler than it looks:

- **No open positions.** `run_backtest:87-98` unconditionally marks any
  still-open position to the final `Close`. Every log row is a completed
  round trip. There is no open-at-end branch.
- **Recorded prices, not re-derived ones.** The exit price for a normal sell
  comes from `Open` and for an end-of-data exit from `Close`. Because the
  attribution reads `trade["Exit Price"]` rather than re-deriving it from the
  price frame, that distinction never has to be re-litigated here.

### Two conventions that had to be chosen

**Capital base.** A one-share P&L stream has no denominator, so "return" and
"drawdown %" are undefined without one. Return-on-invested-notional
(`pnl_i / Close[i-1]`, zero on flat bars) was rejected in favour of a fixed
base `C0 + cumsum(pnl)`: only the fixed base gives a well-defined drawdown,
and Rule 4 needs a single denominator shared with buy-and-hold. `C0` defaults
to the first bar's `Close` and is recorded in `attrs` and in
`performance_summary`.

**`Position` means shares held at that bar's close.** So a bar whose position
was sold at the open reads `Position = 0` while still carrying P&L for the
gap from the previous close to the exit fill, and a same-bar round trip reads
`0` on every bar. The alternative — marking the exit bar as held — would make
`bars_in_market` overcount by one per trade.

### Anchoring, and why it matters for drawdown

`Equity` is `capital_base + cumsum(bar_pnl)`, so bar 0's equity already
includes bar 0's P&L, and `capital_base` itself is the implicit high-water
mark going in. Anchoring at bar 0's *post-P&L* equity instead would make bar
0 its own peak and silently hide a first-bar loss — the same point
`return_stats.cumulative_price_index` makes about anchoring at the first
close. `test_equity_is_anchored_so_a_bar_zero_drawdown_is_captured` pins it.

### Degenerate results are `nan`, never `0.0`

Sharpe returns `nan` for fewer than two observations, zero variance, or any
NaN from an equity series that reached zero. `0.0` would read as a real but
mediocre result and `inf` as an extraordinary one; both are worse than
"undefined". Max drawdown returns a genuine `0.0` for a curve that never
declined, because that is a real zero.

**Given Phase 3's cost hurdle, the empty-trade-log path is the expected
default outcome**, so it is tested as a first-class case rather than an
afterthought: flat curve, `nan` Sharpe, `0.0` drawdown, and a
`performance_summary` dict with every key present so a formatter never
branches — the same shape `_format_ml_comparison:251-257` already uses for a
random baseline that did not run.

### The validation guards

`.loc` against a duplicated label returns *every* match rather than raising,
which would build a longer array than the trade log and a wrong curve with no
exception anywhere. `download_market_data` returns a long frame sorted by
Ticker then Date, so a five-ticker frame has duplicate dates — slicing one
ticker out and forgetting `reset_index(drop=True)` is the realistic route in.
Hence: unique dates, monotonic dates, 0-based `RangeIndex`, and every trade
date present, all enforced with `ValueError`.

### Why `constants.py` rather than restating the values

`logistic_baseline.py:26-31` restates the cost model locally on the grounds
that a shared illustrative *value* is not a real coupling. That reasoning
does not transfer to a risk-free rate: two Sharpe ratios in one repository
computed against different rates, one of which someone updated, are silently
incomparable. `constants.py` is importless by design so any module can depend
on it without dragging in scipy, matplotlib, or yfinance — which is exactly
why `metrics.py` could not simply import `return_stats`.

---

## Verification — as run

```powershell
./venv/Scripts/python.exe -m unittest discover -s tests
```

**Result: 152 tests, OK.** Suite was 123 after spec 007; 29 added here.

### Mutation check — the tests have teeth

29 tests passing on the first run is weak evidence on its own, so three
deliberate defects were injected into `metrics.py` and the suite re-run:

| Injected defect | Result |
|---|---|
| exit bar reads `closes[exit_pos]` instead of `closes[exit_pos - 1]` | **FAILED** (11 errors) |
| `position[entry_pos:exit_pos + 1] = 1` (off-by-one) | **FAILED** (1 failure) |
| entry bar reads `closes[entry_pos + 1]` | **FAILED** (7 errors) |

The reconciliation guard inside `equity_curve` is what converts most of these
into loud errors rather than quiet wrong numbers.

### FR-011 — `return_stats.py` unchanged

```
return_stats.TRADING_DAYS_PER_YEAR = 252
return_stats.RISK_FREE_RATE_ANNUAL = 0.0378
annualize([...]) = (1.26, 0.18782971010998234)   # identical to the inline computation
```

`test_return_stats_uses_the_shared_constants` asserts identity (`is`), not
equality, so a future re-definition in `return_stats.py` fails the test
rather than passing by coincidence.
