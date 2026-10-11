"""Spec 058 T010 (D-6): portfolio accounting, weights at close t -> fills at open t+1.

EXAMPLE — NOT A RESULT. Synthetic panels and a constant stand-in cost; no figure here is a result.
"""
import numpy as np
import pandas as pd
import pytest
from cost_model import CostUnavailable
from portfolio_backtest import run_portfolio_backtest

S = pd.DatetimeIndex(pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]))


def panel(a, b):
    return pd.DataFrame({"A": a, "B": b}, index=S, dtype=float)


OPENS, CLOSES = panel([10, 10, 12, 11], [20, 20, 22, 21]), panel([10, 11, 12, 12], [20, 22, 21, 22])
WEIGHTS = pd.DataFrame({"A": [0.5, 0.0], "B": [0.25, 0.5]}, index=S[:2])


flat = lambda ticker, as_of, quantity: 0.01  # noqa: E731 - constant stand-in cost


def run(opens=OPENS, closes=CLOSES, weights=WEIGHTS, cost=flat, capital=1000.0):
    return run_portfolio_backtest(opens, closes, weights, starting_capital=capital,
                                  commission_per_fill=1.0, fill_cost=cost)


def test_hand_two_asset_oracle():
    result = run()
    # d0 close: equity 1000 -> 50 A (0.5*1000/10) and 12.5 B (0.25*1000/20), filled at d1's open.
    cash = 1000 - (50 * 10 * 1.01 + 1) - (12.5 * 20 * 1.01 + 1)
    e1 = cash + 50 * 11 + 12.5 * 22
    b = 0.5 * e1 / 22  # d1 decision: A -> 0, B -> half of e1 at d1's close
    cash += 50 * 12 * 0.99 - 1 - ((b - 12.5) * 22 * 1.01 + 1)  # sells first, then the buy, at d2's open
    expected = [1000.0, e1, cash + b * 21, cash + b * 22]
    assert np.allclose(result.equity, expected, rtol=0, atol=1e-9), f"T010 ORACLE {list(result.equity)}"
    assert np.allclose(result.holdings.loc[S[3]], [0, b]), "T010 ORACLE holdings"
    price = result.fills.set_index(["Session", "Ticker"]).Price
    assert price[(S[1], "A")] == pytest.approx(10.1) and price[(S[2], "A")] == pytest.approx(11.88), "T010 ORACLE"
    assert result.fills.Commission.sum() == 4 and result.skipped.empty, "T010 ORACLE commission"


def test_fill_quote_is_the_next_sessions_open():
    fills = run().fills
    for row in fills.itertuples():
        assert row.Session == S[S.get_loc(row.Decision) + 1], "T010 NEXT_OPEN session"
        assert row.Quote == OPENS.loc[row.Session, row.Ticker], f"T010 NEXT_OPEN quote {row}"


def test_future_rows_do_not_move_decisions_fills_or_marks():
    base = run()
    for k in range(len(S)):
        later = S > S[k]
        opens, closes = OPENS.copy(), CLOSES.copy()
        closes.loc[later] *= 3.0  # sizing must read the decision close, never a later one
        opens.loc[S > S[min(k + 1, 3)]] *= 0.5
        moved = run(opens, closes)
        assert np.allclose(moved.equity[:k + 1], base.equity[:k + 1]), f"T010 LOOKAHEAD equity through {k}"
        old, new = (r.fills[r.fills.Session <= S[min(k + 1, 3)]] for r in (base, moved))
        assert np.allclose(old.Quantity, new.Quantity), f"T010 LOOKAHEAD fill quantity after {k}"


def test_cost_is_read_as_of_the_decision_session():
    calls = []
    run(cost=lambda ticker, as_of, quantity: calls.append((ticker, as_of, quantity)) or 0.0)
    assert [c[:2] for c in calls] == [("A", S[0]), ("B", S[0]), ("A", S[1]), ("B", S[1])], f"T010 COST_ASOF {calls}"
    assert calls[0][2] == 50 and calls[2][2] == 50, "T010 COST_ASOF quantity is the absolute share delta"


def test_a_ticker_without_a_row_is_not_tradable_and_marks_use_the_last_close():
    opens, closes = OPENS.copy(), CLOSES.copy()
    opens.loc[S[1], "B"] = np.nan  # B has no bar on the fill session
    closes.loc[S[2], "A"] = np.nan  # A held but unpriced at d2's close
    result = run(opens, closes, WEIGHTS.iloc[:1])
    assert list(result.fills.Ticker) == ["A"], f"T010 NO_ROW fills {list(result.fills.Ticker)}"
    assert list(result.skipped.Reason) == ["no_row"] and result.holdings.B.eq(0).all(), "T010 NO_ROW skip"
    cash = 1000 - (50 * 10 * 1.01 + 1)
    assert result.equity[S[2]] == pytest.approx(cash + 50 * 11), "T010 MARK last observed close"
    closes.loc[S[0], "B"] = np.nan
    skipped = run(OPENS, closes, WEIGHTS.iloc[:1]).skipped
    assert list(skipped.Reason) == ["no_close_at_decision"], "T010 NO_ROW decision close"


def test_cost_unavailable_skips_the_order_instead_of_filling_free():
    def cost(ticker, as_of, quantity):
        if ticker == "B":
            raise CostUnavailable("warmup", "short history")
        return 0.01
    result = run(cost=cost)
    assert "B" not in set(result.fills.Ticker), "T010 COST unavailable must not fill"
    assert set(result.skipped.Reason) == {"cost_unavailable:warmup"}, "T010 COST reason"


def test_buys_are_scaled_to_cash_and_never_borrow():
    opens = OPENS.copy()
    opens.loc[S[1]] = [15, 30]  # gap up after a gross-1 decision
    weights = pd.DataFrame({"A": [0.5], "B": [0.5]}, index=S[:1])
    result = run(opens, CLOSES, weights)
    held = result.holdings.loc[S[1]]
    cash = result.equity[S[1]] - float((held * CLOSES.loc[S[1]]).sum())
    assert cash == pytest.approx(0, abs=1e-9) and (held < [50, 25]).all(), f"T010 CASH {cash} {list(held)}"


def test_decision_on_the_last_session_has_no_fill():
    result = run(weights=pd.DataFrame({"A": [1.0]}, index=S[3:]))
    assert result.fills.empty and list(result.skipped.Reason) == ["no_next_session"]


@pytest.mark.parametrize("weights", [
    pd.DataFrame({"A": [0.7], "B": [0.4]}, index=S[:1]),
    pd.DataFrame({"A": [-0.1]}, index=S[:1]),
    pd.DataFrame({"A": [np.nan]}, index=S[:1]),
    pd.DataFrame({"C": [0.1]}, index=S[:1]),
    pd.DataFrame({"A": [0.1]}, index=S[:1].tz_localize("UTC")),
])
def test_invalid_weights_are_refused(weights):
    with pytest.raises(ValueError):
        run(weights=weights)


def test_costs_and_capital_must_be_explicit_and_valid():
    with pytest.raises(TypeError):
        run_portfolio_backtest(OPENS, CLOSES, WEIGHTS, starting_capital=1000.0, commission_per_fill=None, fill_cost=flat)
    for bad in ({"capital": 0.0}, {"cost": lambda *args: 1.0}):
        with pytest.raises(ValueError):
            run(**bad)
