# Data Model — 017 Position Sizing and Portfolio Risk Layer

Every entity here is an in-memory pandas object or a frozen dataclass. There
is no storage: this layer writes nothing to disk.

---

## Session index (shared by every time-indexed input)

| Property | Rule |
|---|---|
| Type | `pd.DatetimeIndex` |
| Timezone | naive (CLAUDE.md *Conventions → Timestamps*) |
| Time of day | midnight (`index == index.normalize()`) |
| Order | strictly increasing |
| Uniqueness | no repeated session |

Violations raise `ValueError`. Enforced by one private validator used by
every public entry point that takes a panel or a series.

---

## `closes` — price panel

| | |
|---|---|
| Shape | sessions × tickers (`pd.DataFrame`) |
| Index | session index (above) |
| Columns | ticker symbols, unique |
| Values | adjusted close; `NaN` allowed (missing bar); `≤ 0` raises |
| Source | caller — e.g. `download_market_data(...).pivot(index="Date", columns="Ticker", values="Close")` |

Derived:

- **log returns** — same shape. Row 0 `NaN`. `NaN` wherever this close or the
  previous row's close is missing.
- **volatility** — same shape. `NaN` until `volatility_window` consecutive
  returns exist.
- **correlation at `t`** — tickers × tickers. `NaN` for a pair unless both
  names have all `correlation_window` returns ending at `t`.

---

## Per-session vectors (`pd.Series`, indexed by ticker)

Every vector must carry exactly the same set of tickers as `closes.columns`.
Order may differ; alignment is by label. A different set raises.

| Vector | Domain | Missing means |
|---|---|---|
| `confidence` | `[0, 1]` | flat (0) |
| `volatility` | `≥ 0` | cannot size (0) |
| `current_weights` | `≥ 0`, finite | not allowed — raises |
| weights at every step | `≥ 0` | — |

---

## `RiskConfig` (frozen dataclass)

| Field | Type | Validation | Recommended |
|---|---|---|---|
| `target_volatility` | float | `> 0`, finite | 0.10 |
| `max_weight` | float | `0 < max_weight ≤ max_gross` | 0.25 |
| `max_gross` | float | `0 < max_gross ≤ 1` | 1.00 |
| `volatility_window` | int | `≥ 2`, not bool | 63 |
| `correlation_window` | int | `≥ 3`, not bool | 63 |
| `daily_loss_limit` | float | `0 < x < 1` | 0.02 |
| `weekly_loss_limit` | float | `0 < x < 1` | 0.04 |
| `weekly_drawdown_limit` | float | `0 < x < 1` | 0.05 |

`RECOMMENDED_CONFIG` is a module constant holding the right-hand column.
Nothing defaults to it: a caller passes it by name.

There is no Kelly field (FR-002).

---

## Target-weight decision (`pd.DataFrame`, one row per ticker)

Returned by `target_weights`. Every intermediate step is a column, so the
mechanism is inspectable (FR-012).

| Column | Meaning |
|---|---|
| `Confidence` | input, missing filled with 0 |
| `Volatility` | at the session; `NaN` if the name cannot be sized |
| `Standalone` | `confidence × target_volatility / volatility`, 0 if unsizeable |
| `Capped` | `min(Standalone, max_weight)` |
| `Overlap` | `Σ_{j active} max(ρ_ij, 0)`; `NaN` for an inactive name |
| `Adjusted` | `Capped / Overlap`; 0 if inactive |
| `Gross_Scaled` | `Adjusted`, scaled so `Σ ≤ max_gross` |
| `Current` | input holding |
| `Target` | `Gross_Scaled`, or `min(Gross_Scaled, Current)` under a halt |

`attrs`: `session`, `entries_halted`.

Invariants: `0 ≤ Target`; `Adjusted ≤ Capped ≤ max_weight`;
`Σ Gross_Scaled ≤ max_gross` (to float tolerance); under a halt
`Target ≤ Current`.

---

## `LossCapGuard` — state machine

State held between calls:

| Field | Meaning |
|---|---|
| `last_session` | last observed session (for ordering) |
| `last_equity` | last observed equity (daily anchor) |
| `week` | ISO `(year, week)` of the current week |
| `week_anchor` | equity at the last close before this week (first week: first equity) |
| `week_high` | running max of `week_anchor` and this week's closes |
| `weekly_latched` | a weekly cap has fired this week |

Transition on `observe(session, equity)`:

```
validate session (naive, midnight, > last_session) and equity (finite, > 0)
if ISO week of session != week:
    week_anchor    = last_equity if one exists else equity
    week_high      = week_anchor
    weekly_latched = False
    week           = ISO week of session
week_high = max(week_high, equity)

daily_return    = equity / last_equity − 1        (NaN on the first call)
weekly_return   = equity / week_anchor − 1
weekly_drawdown = equity / week_high − 1

daily_breach           = daily_return    ≤ −daily_loss_limit      (False if NaN)
weekly_loss_breach     = weekly_return   ≤ −weekly_loss_limit
weekly_drawdown_breach = weekly_drawdown ≤ −weekly_drawdown_limit
weekly_latched        |= weekly_loss_breach or weekly_drawdown_breach
entries_halted         = daily_breach or weekly_latched

last_session, last_equity = session, equity
```

---

## `LossCapStatus` (frozen dataclass) — one per observed session

`session`, `equity`, `daily_return`, `weekly_return`, `weekly_drawdown`,
`daily_breach`, `weekly_loss_breach`, `weekly_drawdown_breach`,
`weekly_latched`, `entries_halted`.

`loss_cap_history` returns these as a `pd.DataFrame` indexed by session.
