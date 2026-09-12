# Contract — `scripts/portfolio_risk.py`

The module's public surface, and what each function guarantees. Types and
column meanings are in `../data-model.md`; this file does not repeat them.

**Import set (FR-013), exactly:** `__future__`, `dataclasses`, `numpy`,
`pandas`, `constants`.

---

## Configuration

```python
@dataclass(frozen=True)
class RiskConfig:
    target_volatility: float
    max_weight: float
    max_gross: float
    volatility_window: int
    correlation_window: int
    daily_loss_limit: float
    weekly_loss_limit: float
    weekly_drawdown_limit: float

RECOMMENDED_CONFIG: RiskConfig
```

- Raises `ValueError`/`TypeError` on construction for any value outside its
  domain. Never clips.

---

## Estimation (Rule 1, Rule 5)

```python
def log_returns(closes: pd.DataFrame) -> pd.DataFrame
```

- `ln(C[t] / C[t-1])` by row position. Row 0 and any row touching a missing
  close are `NaN`.
- Raises on a non-positive close or an invalid session index.

```python
def realized_volatility(
    closes: pd.DataFrame, *, window: int,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> pd.DataFrame
```

- Row `t` = sample std (`ddof=1`) of the `window` returns ending at `t`, times
  `sqrt(periods_per_year)`; `NaN` unless all `window` exist.
- Row `t` is bit-identical under any change to rows after `t`.

```python
def trailing_correlation(
    closes: pd.DataFrame, session: pd.Timestamp, *, window: int,
) -> pd.DataFrame
```

- Pearson correlation of the `window` returns ending at `session`, pairwise;
  `NaN` for a pair unless both names have all `window` returns.
- Truncates `closes` at `session` before computing anything.
- Raises if `session` is not in the index.

---

## Allocation (User Stories 1 and 2)

```python
def volatility_target_weights(
    confidence: pd.Series, volatility: pd.Series, *, target_volatility: float,
) -> pd.Series
```

- `confidence × target_volatility / volatility`, uncapped, on `confidence`'s
  index.
- Missing confidence → 0. Missing, zero volatility → 0.
- Raises on confidence outside `[0, 1]`, negative volatility, or mismatched
  ticker sets.

```python
def position_overlap(weights: pd.Series, correlation: pd.DataFrame) -> pd.Series
```

- For each active name (`weight > 0`): `1 + Σ_{j active, j≠i} max(ρ_ij, 0)`.
  `NaN` for inactive names.
- Raises on a missing correlation between two active names, a value outside
  `[-1, 1]`, or mismatched ticker sets.

```python
def correlation_adjusted_weights(
    weights: pd.Series, correlation: pd.DataFrame,
) -> pd.Series
```

- `weights / position_overlap(...)`; inactive names stay 0.
- Never increases a weight.

```python
def apply_gross_cap(weights: pd.Series, *, max_gross: float) -> pd.Series
```

- Unchanged (same values) if `Σ weights ≤ max_gross`; otherwise every weight
  scaled by `max_gross / Σ weights`.

```python
def apply_entry_halt(
    target: pd.Series, current: pd.Series, *, halted: bool,
) -> pd.Series
```

- Not halted: `target` unchanged. Halted: elementwise `min(target, current)`.
- Raises on a missing or negative `current`, or mismatched ticker sets.

```python
def target_weights(
    closes: pd.DataFrame,
    confidence: pd.Series,
    current_weights: pd.Series,
    *,
    session: pd.Timestamp,
    config: RiskConfig,
    entries_halted: bool,
) -> pd.DataFrame
```

- Truncates `closes` at `session` first. Then, in order: volatility and
  correlation → standalone → per-name cap → overlap → gross cap → halt.
- A name is sizeable only if its volatility is finite and positive and its
  correlation window is complete; otherwise its weight is 0.
- Output is bit-identical under any change to `closes` after `session`.
- Returns the per-step frame described in `data-model.md`.

---

## Loss caps (User Story 3)

```python
@dataclass(frozen=True)
class LossCapStatus: ...

class LossCapGuard:
    def __init__(self, *, daily_loss_limit: float, weekly_loss_limit: float,
                 weekly_drawdown_limit: float) -> None
    @classmethod
    def from_config(cls, config: RiskConfig) -> LossCapGuard
    def observe(self, session: pd.Timestamp, equity: float) -> LossCapStatus
```

- `observe` implements the transition in `data-model.md`.
- Raises on an invalid or non-increasing session, or a non-finite or
  non-positive equity. A rejected observation leaves the guard's state
  unchanged.

```python
def loss_cap_history(
    equity: pd.Series, *, daily_loss_limit: float, weekly_loss_limit: float,
    weekly_drawdown_limit: float,
) -> pd.DataFrame
```

- Runs one fresh `LossCapGuard` over `equity` in order; one row per session.
- Row `t` is identical under any change to equity after `t`.

---

## Not in this contract

- No function computes a fill, a trade, a trade log, or P&L.
- No function downloads, caches, or reads files.
- No Kelly sizing.
