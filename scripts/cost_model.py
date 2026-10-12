"""Per-fill Rule 13 cost estimate: EDGE half-spread plus square-root impact (spec 046 U1).

For a fill at session t+1, `estimate_fill_cost` reads one instrument's nominal
OHLCV history through session t only and returns the adverse slippage fraction
`S/2 + Y * sigma * sqrt(Q / ADV)`. Commission is separate. The caller supplies
the absolute share quantity Q; this module never chooses it, never prices the
t+1 quote, and knows nothing of signals, sizing, P&L, downloads or the ledger.

Sources (spec 046 T001, approved 2026-10-09):
- S: EDGE, Ardia, Guidotti & Kroencke (2024), JFE 161, 103916, Eqs. (23)-(25),
  p. 6, as specified by the authors' reference algorithm `bidask` v2.1.0.
  S is the full relative spread (Eq. (1), p. 3); a fill pays S/2. Negative S^2
  becomes sqrt(|S^2|), not the paper's reset to zero, which would trade free.
- Impact: Toth et al. (2011), Phys. Rev. X 1, 021006. Y = 1.0 is preregistered
  (D-1), not calibrated; 0.5 and 2.0 exist only as labelled robustness rows (U1b).
Rule 1: spread and ADV use sessions t-20..t; sigma uses 21 log returns from the
22 closes t-21..t. Anything missing is a `CostUnavailable`, never a zero.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
import pandas as pd

from data import trading_days

MODEL = "spread_plus_sqrt_impact"
WINDOW = 21
PERMITTED_VOLUME_BASES = frozenset({"nominal_reconstructed", "provider_nominal"})
ROBUSTNESS_COEFS = (0.5, 2.0)
# What estimate_fill_cost implements (plan §3). A config may only record these, never describe other arithmetic.
CONVENTIONS = {
    "estimator_version": "EDGE per bidask 2.1.0 reference algorithm (return de-meaning included)",
    "sigma_convention": "daily close-to-close log returns, 21 returns from the 22 closes t-21..t, "
                        "sample std ddof=1, not annualized",
    "volume_convention": "mean share volume over sessions t-20..t; volume_basis nominal_reconstructed or "
                         "provider_nominal only; a split in t-20..t refuses",
    "window_policy": "21 NYSE sessions trailing through cutoff t for a t+1 fill (sigma adds close t-21); "
                     "holidays are not sessions; a missing session refuses",
    "spread_handling": "S is the full relative spread, charged S/2 per fill; negative S^2 -> sqrt(|S^2|); "
                       "undefined S refuses",
    "warmup_policy": "refuse until 22 sessions through t exist; never zero, shortened or stale",
    "liquidation_cost_policy": "terminal close-out uses the preceding-session estimate",
}


class CostUnavailable(ValueError):
    """No valid estimate exists at this cutoff, so the order must not fill."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


@dataclass(frozen=True)
class CostConfig:
    """Canonical slippage config (FR-005): D-1/D-2 parameters, a role label and the recorded conventions.

    `role="primary"` has Y = 1.0. `role="robustness"` is one labelled 0.5/2.0 row (D-1), never a
    candidate for primary. Every field is in `as_mapping()`, so any change changes the config hash.
    """

    model: str = MODEL
    role: str = "primary"
    impact_coef: float = 1.0
    spread_window: int = WINDOW
    sigma_window: int = WINDOW
    adv_window: int = WINDOW
    source: str = ("EDGE: Ardia, Guidotti & Kroencke (2024) JFE 161 103916, Eqs. (23)-(25) p. 6; "
                   "impact: Toth et al. (2011) Phys. Rev. X 1 021006")
    estimator_version: str = CONVENTIONS["estimator_version"]
    sigma_convention: str = CONVENTIONS["sigma_convention"]
    volume_convention: str = CONVENTIONS["volume_convention"]
    window_policy: str = CONVENTIONS["window_policy"]
    spread_handling: str = CONVENTIONS["spread_handling"]
    warmup_policy: str = CONVENTIONS["warmup_policy"]
    liquidation_cost_policy: str = CONVENTIONS["liquidation_cost_policy"]

    def __post_init__(self) -> None:
        if self.model != MODEL:
            raise ValueError(f"cost model must be {MODEL!r}; got {self.model!r}")
        windows = (self.spread_window, self.sigma_window, self.adv_window)
        if any(type(w) is not int for w in windows) or windows != (WINDOW,) * 3:
            raise ValueError(f"windows are fixed at {WINDOW} sessions (spec 046 D-2)")
        if type(self.impact_coef) is not float:
            raise ValueError(f"impact_coef must be a float; got {self.impact_coef!r}")
        if self.role == "primary":
            if self.impact_coef != 1.0:
                raise ValueError("the primary impact coefficient is fixed at 1.0 (spec 046 D-1)")
        elif self.role == "robustness":
            if self.impact_coef not in ROBUSTNESS_COEFS:
                raise ValueError(f"robustness rows are Y in {ROBUSTNESS_COEFS} only (spec 046 D-1)")
        else:
            raise ValueError(f"role must be 'primary' or 'robustness'; got {self.role!r}")
        for name, value in CONVENTIONS.items():
            if getattr(self, name) != value:
                raise ValueError(f"{name} must record the implemented convention {value!r}")

    def as_mapping(self) -> dict:
        """Every field as plain JSON values, for the trial config and sidecar costs."""
        return asdict(self)


def robustness_configs() -> tuple[CostConfig, ...]:
    """The labelled D-1 robustness rows, in fixed order. Reported beside primary, never selected on."""
    return tuple(CostConfig(role="robustness", impact_coef=y) for y in ROBUSTNESS_COEFS)


@dataclass(frozen=True)
class CostEstimate:
    """One fill's adverse cost fractions and the evidence that produced them."""

    half_spread: float
    impact: float
    total: float
    spread_squared: float
    spread_handling: str
    sigma: float
    adv: float
    quantity: float
    as_of: pd.Timestamp
    window_start: pd.Timestamp
    volume_basis: str


def edge_squared(open_, high, low, close) -> float:
    """Signed EDGE S^2 (bidask 2.1.0 algorithm) for complete bars; NaN when undefined."""
    o, h, l, c = (np.log(np.asarray(x, dtype=float)) for x in (open_, high, low, close))
    m = (h + l) / 2.
    h1, l1, c1, m1 = h[:-1], l[:-1], c[:-1], m[:-1]
    o, h, l, m = o[1:], h[1:], l[1:], m[1:]
    r1, r2, r3, r4, r5 = m - o, o - m1, m - c1, c1 - m1, o - c1
    tau = ((h != l) | (l != c1)).astype(float)
    po = np.mean(tau * (o != h)) + np.mean(tau * (o != l))
    pc = np.mean(tau * (c1 != h1)) + np.mean(tau * (c1 != l1))
    if tau.sum() < 2 or po == 0 or pc == 0:
        return math.nan
    pt = np.mean(tau)
    d1, d3, d5 = (r - np.mean(r) / pt * tau for r in (r1, r3, r5))
    x1 = -4. / po * d1 * r2 - 4. / pc * d3 * r4
    x2 = -4. / po * d1 * r5 - 4. / pc * d5 * r4
    e1, e2 = np.mean(x1), np.mean(x2)
    v1, v2 = np.mean(x1 ** 2) - e1 ** 2, np.mean(x2 ** 2) - e2 ** 2
    vt = v1 + v2
    return float((v2 * e1 + v1 * e2) / vt if vt > 0 else (e1 + e2) / 2.)


def _window(history: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    index = history.index
    if not isinstance(index, pd.DatetimeIndex) or index.tz is not None \
            or not (index == index.normalize()).all() or index.has_duplicates \
            or not index.is_monotonic_increasing:
        raise CostUnavailable("malformed_history", "need naive, midnight, unique, ascending session labels")
    if as_of not in index:
        raise CostUnavailable("as_of_missing", f"no bar for {as_of.date()}")
    past = history.loc[:as_of]
    if len(past) < WINDOW + 1:
        raise CostUnavailable("warmup", f"{len(past)} of {WINDOW + 1} sessions through {as_of.date()}")
    window = past.iloc[-(WINDOW + 1):]
    expected = pd.DatetimeIndex(trading_days(window.index[0].date(), as_of.date()))
    if not window.index.equals(expected):
        raise CostUnavailable("missing_session", f"bars do not match NYSE sessions {window.index[0].date()}..{as_of.date()}")
    bars = window[["Open", "High", "Low", "Close", "Volume"]].to_numpy(dtype=float)
    o, h, l, c, v = bars.T
    if not np.isfinite(bars).all() or (bars[:, :4] <= 0).any() or (v < 0).any() \
            or (l > np.minimum(o, c)).any() or (h < np.maximum(o, c)).any():
        raise CostUnavailable("malformed_bar", "OHLC must be positive and finite with L <= O, C <= H; volume finite >= 0")
    return window


def estimate_fill_cost(history: pd.DataFrame, *, as_of, quantity: float, config: CostConfig,
                       split_sessions) -> CostEstimate:
    """Cost fractions for a fill after session `as_of`, from bars at or before it only.

    `split_sessions` is required: a split in the window would mix share bases, so it refuses.
    Raises `CostUnavailable` with a specific `reason` instead of returning a zero or stale estimate.
    """
    basis = history.attrs.get("volume_basis")
    if basis not in PERMITTED_VOLUME_BASES:
        raise CostUnavailable("volume_basis", f"{basis!r} is not one of {sorted(PERMITTED_VOLUME_BASES)}")
    if isinstance(quantity, bool) or not (isinstance(quantity, (int, float)) and math.isfinite(quantity) and quantity > 0):
        raise CostUnavailable("invalid_quantity", f"{quantity!r}")
    as_of = pd.Timestamp(as_of)
    window = _window(history, as_of)
    recent = window.iloc[1:]
    if any(recent.index[0] <= pd.Timestamp(s).normalize() <= as_of for s in split_sessions):
        raise CostUnavailable("split_in_window", "share bases of Q and ADV are not verified comparable")
    s2 = edge_squared(recent["Open"], recent["High"], recent["Low"], recent["Close"])
    if not math.isfinite(s2):
        raise CostUnavailable("spread_undefined", "EDGE is undefined on this window")
    adv = float(recent["Volume"].mean())
    if adv <= 0:
        raise CostUnavailable("zero_adv", "no traded volume in the window")
    sigma = float(np.std(np.diff(np.log(window["Close"].to_numpy(dtype=float))), ddof=1))
    half = math.sqrt(abs(s2)) / 2.
    impact = config.impact_coef * sigma * math.sqrt(quantity / adv)
    if not half + impact < 1.:
        raise CostUnavailable("nonpositive_fill_price", f"adverse fraction {half + impact:.6g} >= 1")
    return CostEstimate(half, impact, half + impact, s2, "negative_abs" if s2 < 0 else "positive",
                        sigma, adv, float(quantity), as_of, recent.index[0], basis)
