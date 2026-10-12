"""Spec 046 U1 contracts: EDGE half-spread plus square-root impact, point in time.
Synthetic frames only (EXAMPLE — NOT A RESULT). The spread oracle is `bidask==2.1.0` (T001)."""
from datetime import date

import bidask
import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401
from cost_model import CostConfig, CostUnavailable, estimate_fill_cost, robustness_configs
from data import trading_days
from trial_registry import canonical_json, digest

SESSIONS = pd.DatetimeIndex(trading_days(date(2024, 1, 2), date(2024, 4, 30)))  # spans MLK, Presidents' Day, Good Friday


def bars(seed=20261009, n=40, spread=0.01, basis="provider_nominal"):
    """Trades alternate at bid/ask around a log random walk. EXAMPLE — NOT A RESULT."""
    rng = np.random.default_rng(seed)
    mid = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n * 50)))
    px = (mid * (1 + rng.choice([-1, 1], n * 50) * spread / 2)).reshape(n, 50)
    frame = pd.DataFrame({"Open": px[:, 0], "High": px.max(1), "Low": px.min(1), "Close": px[:, -1],
                          "Volume": rng.integers(100_000, 1_000_000, n).astype(float)}, index=SESSIONS[:n])
    frame.attrs["volume_basis"] = basis
    return frame


def cost(frame, t=30, q=1_000.0, split_sessions=()):
    return estimate_fill_cost(frame, as_of=frame.index[t], quantity=q, config=CostConfig(), split_sessions=split_sessions)


def refusal(reason, frame, **kw):
    with pytest.raises(CostUnavailable) as caught:
        cost(frame, **kw)
    assert caught.value.reason == reason, f"refused for {caught.value.reason!r}, expected {reason!r}"


@pytest.mark.parametrize("seed, spread, negative", [(20261009, 0.01, False), (7, 0.002, False), (11, 0.03, False),
                                                    (1, 0.0005, True)])
def test_half_spread_matches_bidask_oracle(seed, spread, negative):
    window = bars(seed, spread=spread).iloc[10:31]
    signed = bidask.edge(window.Open, window.High, window.Low, window.Close, sign=True)
    assert (signed < 0) == negative, "fixture must keep exercising both signs of S^2"
    est = cost(bars(seed, spread=spread))
    assert est.half_spread == pytest.approx(abs(signed) / 2, abs=1e-12), "S/2 per fill; negative S^2 -> sqrt|S^2|"
    assert est.spread_handling == ("negative_abs" if negative else "positive") and est.half_spread > 0


def test_impact_is_square_root_in_quantity_with_spread_unchanged():
    frame = bars()
    small, large = cost(frame, q=1_000.0), cost(frame, q=4_000.0)
    assert large.impact == pytest.approx(2 * small.impact, rel=1e-12), "4x Q must give 2x impact"
    assert large.half_spread == small.half_spread
    assert large.total == pytest.approx(large.half_spread + large.impact, rel=1e-15)


def test_sigma_and_adv_follow_the_recorded_conventions():
    frame, t = bars(), 30
    est = cost(frame, t=t)
    closes = frame.Close.iloc[t - 21:t + 1].to_numpy()
    assert est.sigma == pytest.approx(np.std(np.diff(np.log(closes)), ddof=1), rel=1e-12)
    assert est.adv == pytest.approx(frame.Volume.iloc[t - 20:t + 1].mean(), rel=1e-12)
    assert est.impact == pytest.approx(est.sigma * np.sqrt(1_000.0 / est.adv), rel=1e-12)
    assert (est.window_start, est.as_of) == (frame.index[t - 20], frame.index[t])


@pytest.mark.parametrize("basis", ["nominal_reconstructed", "provider_nominal", None, "adjusted", "provider_unverified"])
def test_only_verified_volume_bases_are_accepted(basis):
    if basis in ("nominal_reconstructed", "provider_nominal"):
        assert cost(bars(basis=basis)).volume_basis == basis
    else:
        refusal("volume_basis", bars(basis=basis))


def test_warmup_refuses_until_the_first_complete_window_and_the_last_row_is_usable():
    frame = bars()
    refusal("warmup", frame, t=20)
    first = cost(frame, t=21)
    assert first.window_start == frame.index[1] and first.half_spread > 0 and first.impact > 0
    assert cost(frame, t=39).as_of == frame.index[-1]


@pytest.mark.parametrize("column", ["Open", "High", "Low", "Close", "Volume"])
def test_future_bars_cannot_move_the_estimate(column):
    frame, t = bars(), 30
    clean = cost(frame, t=t)
    for start in (t + 1, t + 2):
        moved = frame.copy()
        moved.iloc[start:, moved.columns.get_loc(column)] *= 3.0
        if column != "Volume":
            moved.loc[moved.index[start:], "High"] = moved.iloc[start:, :4].max(axis=1)
            moved.loc[moved.index[start:], "Low"] = moved.iloc[start:, :4].min(axis=1)
        assert cost(moved, t=t) == clean, f"{column} from t+{start - t} leaked into the estimate"


def test_holidays_pass_but_a_missing_session_refuses():
    frame = bars()
    assert frame.index[0] < pd.Timestamp("2024-01-15") < frame.index[21]  # MLK Day closure inside the t=21 window
    cost(frame, t=21)
    refusal("missing_session", frame.drop(frame.index[20]))
    refusal("missing_session", frame.drop(frame.index[9]), t=29)  # the extra close sigma needs


@pytest.mark.parametrize("column, value", [("High", 50.0), ("Close", -1.0), ("Volume", np.nan), ("Open", np.inf)])
def test_malformed_bars_refuse(column, value):
    frame = bars()
    frame.iloc[25, frame.columns.get_loc(column)] = value
    refusal("malformed_bar", frame)


@pytest.mark.parametrize("q", [0, -10.0, float("nan"), float("inf"), True])
def test_invalid_quantity_refuses(q):
    refusal("invalid_quantity", bars(), q=q)


def test_split_inside_the_window_refuses_and_before_it_does_not():
    frame = bars()
    refusal("split_in_window", frame, split_sessions=[frame.index[10]])  # t-20: its return enters sigma
    refusal("split_in_window", frame, split_sessions=[frame.index[30] + pd.Timedelta(hours=9)])
    cost(frame, split_sessions=[frame.index[9], frame.index[31]])


def test_primary_config_is_fixed():
    assert (CostConfig().impact_coef, CostConfig().spread_window, CostConfig().adv_window) == (1.0, 21, 21)
    for bad in ({"impact_coef": 0.5}, {"impact_coef": 2.0}, {"spread_window": 20}, {"sigma_window": 22},
                {"model": "flat_bps"}):
        with pytest.raises(ValueError):
            CostConfig(**bad)


def test_unusable_inputs_refuse_rather_than_trade_free():
    flat = bars()
    flat[["Open", "High", "Low"]] = np.repeat(flat[["Close"]].to_numpy(), 3, axis=1)
    refusal("spread_undefined", flat)
    idle = bars()
    idle["Volume"] = 0.0
    refusal("zero_adv", idle)
    refusal("nonpositive_fill_price", bars(), q=1e15)
    aware = bars()
    aware.index = aware.index.tz_localize("UTC")
    refusal("malformed_history", aware)
    with pytest.raises(CostUnavailable, match="as_of_missing"):
        estimate_fill_cost(bars(), as_of="2024-01-15", quantity=1.0, config=CostConfig(), split_sessions=())


# Plan §3's slippage fields, written out here rather than read from the module under test.
CONVENTION_FIELDS = {"estimator_version", "sigma_convention", "volume_convention", "window_policy",
                     "spread_handling", "warmup_policy", "liquidation_cost_policy"}
CANONICAL_FIELDS = {"model", "role", "impact_coef", "spread_window", "sigma_window", "adv_window", "source",
                    *CONVENTION_FIELDS}


def test_robustness_rows_are_labelled_and_cannot_stand_in_for_primary():
    primary, rows = CostConfig(), robustness_configs()
    assert (primary.role, primary.impact_coef) == ("primary", 1.0), "M10: primary must stay Y=1.0"
    assert [(r.role, r.impact_coef) for r in rows] == [("robustness", 0.5), ("robustness", 2.0)], "M10: rows"
    for bad in ({"role": "robustness", "impact_coef": 1.0}, {"role": "robustness", "impact_coef": 0.7},
                {"role": "primary", "impact_coef": 2.0}, {"role": "best"}, {"impact_coef": True}, {"adv_window": 21.0}):
        with pytest.raises(ValueError):
            CostConfig(**bad)
    base = cost(bars())
    for row in rows:
        est = estimate_fill_cost(bars(), as_of=bars().index[30], quantity=1_000.0, config=row, split_sessions=())
        assert est.half_spread == base.half_spread, "robustness Y must leave the spread alone"
        assert est.impact == pytest.approx(row.impact_coef * base.impact, rel=1e-12), "M10: row Y not applied"


def test_canonical_config_records_every_convention_and_refuses_altered_ones():
    mapping = CostConfig().as_mapping()
    assert set(mapping) == CANONICAL_FIELDS, f"M10: canonical config fields {sorted(set(mapping) ^ CANONICAL_FIELDS)}"
    canonical_json(mapping)  # finite JSON values only, as trial_registry requires
    assert CostConfig(**mapping) == CostConfig(), "the serialized config must rebuild the same config"
    identities = {digest(c.as_mapping()) for c in (CostConfig(), *robustness_configs())}
    assert len(identities) == 3, "M10: each labelled row needs its own config identity"
    for field in CONVENTION_FIELDS:
        assert mapping[field], f"M10: {field} recorded empty"
        with pytest.raises(ValueError, match=field):  # M10: a label may not describe other arithmetic
            CostConfig(**{**mapping, field: mapping[field] + " (altered)"})
