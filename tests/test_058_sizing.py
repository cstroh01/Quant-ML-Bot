"""Spec 058 T012 (sizing) and T013 (H9/H10 combos, buy-and-hold baseline) as weight books (Rules 1, 4, 5).

EXAMPLE — NOT A RESULT. Seeded synthetic random walks; no figure here is a result.
"""
import numpy as np
import pandas as pd
import pytest
from portfolio_risk import blend_books, equal_weight_book, ewma_volatility, fixed_allocation_book, \
    volatility_target_book
from signals import hypothesis_selection

S = pd.bdate_range("2004-01-02", periods=300)
T = ["SPY", "IEF", "GLD", "TLT"]
H10 = {"SPY": 0.6, "IEF": 0.4}


def walk(seed, n=len(S)):
    steps = np.random.default_rng(seed).normal(0, 1, (n, len(T))) * np.array([0.02, 0.005, 0.01, 0.008])
    return pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=S[:n], columns=T)


def only(*tickers):
    selection = pd.DataFrame(False, index=S, columns=T)
    selection[list(tickers)] = True
    return selection


def vol_book(selection, closes):
    return volatility_target_book(selection, ewma_volatility(closes, span=60), target_volatility=0.10,
                                  max_gross=1.0)


def ewma_std_oracle(returns, span):
    """Bias-corrected exponentially weighted std (adjust=True), by hand rather than pandas ewm."""
    w = (1 - 2 / (span + 1)) ** np.arange(len(returns))[::-1]
    mean = (w * returns).sum() / w.sum()
    biased = (w * (returns - mean) ** 2).sum() / w.sum()
    return np.sqrt(biased * w.sum() ** 2 / (w.sum() ** 2 - (w ** 2).sum()))


def test_ewma_volatility_is_span_60_annualized_after_a_full_window():
    closes = walk(1)
    vol = ewma_volatility(closes, span=60)["SPY"]
    assert vol.iloc[:60].isna().all() and vol.iloc[60:].notna().all(), "T012 EWMA WARMUP"
    returns = np.log(closes["SPY"]).diff().to_numpy()
    for row in (60, 150, 299):
        expected = ewma_std_oracle(returns[1:row + 1], 60) * np.sqrt(252)
        assert vol.iloc[row] == pytest.approx(expected, rel=1e-9), f"T012 EWMA row {row}"


def test_a_selected_name_alone_carries_ten_percent_annualized_risk():
    closes = walk(2)
    book = vol_book(only("SPY"), closes)
    risk = book["SPY"] * ewma_volatility(closes, span=60)["SPY"]
    assert book.iloc[:60].eq(0).all().all() and book.drop(columns="SPY").eq(0).all().all(), "T012 TARGET flat"
    assert np.allclose(risk.iloc[60:], 0.10, rtol=1e-12, atol=0), "T012 TARGET"


def test_the_book_is_capped_at_gross_one_keeping_inverse_vol_ratios():
    closes = walk(3)
    vol = ewma_volatility(closes, span=60).iloc[60:]
    assert (0.10 / vol["IEF"] + 0.10 / vol["TLT"] > 1.05).all(), "precondition: uncapped book above 1"
    book = vol_book(only("IEF", "TLT"), closes).iloc[60:]
    assert np.allclose(book.sum(axis=1), 1.0, rtol=1e-12, atol=0), "T012 GROSS"
    assert np.allclose(book["IEF"] / book["TLT"], vol["TLT"] / vol["IEF"]), "T012 GROSS ratio"


def books(closes):
    vol = ewma_volatility(closes, span=60)
    size = lambda selection: volatility_target_book(selection, vol, target_volatility=0.10, max_gross=1.0)  # noqa: E731
    h4, h2 = size(hypothesis_selection("H4", closes)), size(hypothesis_selection("H2-100", closes))
    return {"vol": vol, "H4": h4, "H9": blend_books(h4, h2), "H10": fixed_allocation_book(closes, H10),
            "B-BH": equal_weight_book(closes.notna(), max_gross=1.0)}


def test_future_rows_never_change_volatility_or_any_book():
    base = walk(4)
    full = books(base)
    for cut in (120, 200, 280):
        future = base.copy()
        future.iloc[cut + 1:] = base.iloc[cut].to_numpy() * walk(cut, len(S) - cut - 1).to_numpy() ** 3 / 1e6
        future.iloc[cut + 1, T.index("IEF")] = np.nan
        moved = books(future)
        for name, frame in full.items():
            assert moved[name].iloc[:cut + 1].equals(frame.iloc[:cut + 1]), f"T012 LOOKAHEAD {name} cut {cut}"
        assert not moved["H4"].iloc[cut + 1:].equals(full["H4"].iloc[cut + 1:]), "T012 LOOKAHEAD vacuous"


def test_h9_is_the_equal_weight_average_of_its_three_books():
    rows = [[0.6, 0, 0, 0], [0, 0.9, 0, 0], [0.3, 0.3, 0.3, 0]]
    parts = [pd.DataFrame([row] * len(S), index=S, columns=T) for row in rows]
    assert np.allclose(blend_books(*parts).to_numpy(), [0.3, 0.4, 0.1, 0]), "T013 H9"
    with pytest.raises(ValueError, match="share sessions"):
        blend_books(parts[0], parts[1].iloc[1:])
    refusal = ""
    try:
        blend_books(parts[0], parts[0] * 2)  # gross 1.2: a levered input
    except ValueError as error:
        refusal = str(error)
    assert "gross" in refusal, "T013 H9 GROSS"


def test_h10_is_sixty_forty_only_once_both_legs_have_a_close():
    closes = walk(5)
    closes.iloc[:30, T.index("IEF")] = np.nan
    closes.iloc[100, T.index("SPY")] = np.nan
    book = fixed_allocation_book(closes, H10)
    assert book.iloc[:30].eq(0).all().all() and book.iloc[100].eq(0).all(), "T013 H10 LISTING"
    live = book.drop(index=[*S[:30], S[100]])
    assert (live["SPY"].eq(0.6) & live["IEF"].eq(0.4) & live[["GLD", "TLT"]].eq(0).all(axis=1)).all(), "T013 H10"
    with pytest.raises(ValueError, match="no leverage"):
        fixed_allocation_book(closes, {"SPY": 0.7, "IEF": 0.4})


def test_buy_and_hold_baseline_is_equal_weight_of_names_with_a_close():
    closes = walk(6)
    closes.iloc[:50, T.index("GLD")] = np.nan
    book = equal_weight_book(closes.notna(), max_gross=1.0)
    early = book.iloc[:50]
    assert np.allclose(early[["SPY", "IEF", "TLT"]], 1 / 3) and early["GLD"].eq(0).all(), "T013 B-BH listing"
    assert np.allclose(book.iloc[50:], 0.25), "T013 B-BH"
    assert equal_weight_book(only(), max_gross=1.0).eq(0).all().all(), "T013 B-BH empty"
    with pytest.raises(ValueError, match="boolean"):
        equal_weight_book(closes, max_gross=1.0)

