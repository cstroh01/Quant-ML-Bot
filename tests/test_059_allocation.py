"""Spec 059 T002 / FR-002: the preregistered LIVE allocation's weights (Rules 1, 5).

EXAMPLE — NOT A RESULT. ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED. Seeded synthetic random walks
only; no figure here is a result.
"""
import numpy as np
import pandas as pd

from portfolio_risk import allocation_weights
from signals import ALLOCATION_SLEEVES, allocation_selection, decision_sessions

S = pd.bdate_range("2010-01-04", periods=420)
VOL = {"SPY": 0.011, "EFA": 0.012, "EEM": 0.015, "IEF": 0.004, "TLT": 0.009, "TIP": 0.003, "GLD": 0.010,
       "DBC": 0.012, "QQQ": 0.013}


def walk(seed, tickers, scale=1.0):
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 1, (len(S), 1))
    noise = rng.normal(0, 1, (len(S), len(tickers)))
    steps = (0.5 * common + 0.85 * noise) * np.array([VOL[t] for t in tickers]) * scale
    return pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=S, columns=list(tickers))


def weights(closes):
    return allocation_weights(allocation_selection(closes), closes, decision_sessions(closes.index, cadence="monthly"))


def ewma_cov(x, y, span=60):
    w = (1 - 2 / (span + 1)) ** np.arange(len(x))[::-1]
    mx, my = (w * x).sum() / w.sum(), (w * y).sum() / w.sum()
    return (w * (x - mx) * (y - my)).sum() / w.sum() * w.sum() ** 2 / (w.sum() ** 2 - (w ** 2).sum())


def oracle(closes, session):
    """Spec 059 §3 by hand: normalized inverse vol, scaled by min(1, 0.10 / portfolio vol)."""
    returns = np.log(closes.loc[:session]).diff().iloc[1:].to_numpy()
    k = returns.shape[1]
    cov = np.array([[ewma_cov(returns[:, i], returns[:, j]) for j in range(k)] for i in range(k)]) * 252
    raw = 1 / np.sqrt(np.diag(cov))
    w = raw / raw.sum()
    return w * min(1.0, 0.10 / np.sqrt(w @ cov @ w))


def test_two_and_three_sleeve_weights_match_the_hand_oracle():
    for tickers, scale in ((("SPY", "IEF"), 1.0), (("EEM", "TLT", "GLD"), 2.0), (("IEF", "TIP"), 0.5)):
        closes = walk(len(tickers), tickers, scale)
        book = weights(closes)
        for session in book.index[book.sum(axis=1) > 0][[0, -1]]:
            assert np.allclose(book.loc[session].to_numpy(), oracle(closes, session), rtol=1e-9, atol=0), \
                f"Q108 ORACLE {tickers} {session.date()}"


def test_gross_is_capped_at_one_and_the_remainder_is_cash():
    calm, wild = weights(walk(1, ("IEF", "TIP"), 0.5)), weights(walk(1, ("EEM", "GLD"), 3.0))
    live_calm, live_wild = calm[calm.sum(axis=1) > 0], wild[wild.sum(axis=1) > 0]
    assert len(live_calm) > 5 and np.allclose(live_calm.sum(axis=1), 1.0, rtol=1e-12, atol=0), "Q108 CAP"
    assert (live_wild.sum(axis=1) < 0.9).all() and (live_wild >= 0).all().all(), "Q108 CASH"


def test_a_sleeve_enters_after_its_listing_close_plus_sixty_sessions_on_the_next_decision():
    closes = walk(3, ALLOCATION_SLEEVES)
    closes.iloc[:150, ALLOCATION_SLEEVES.index("DBC")] = np.nan  # DBC lists at S[150]
    held = allocation_selection(closes)["DBC"]
    assert not held.iloc[:210].any() and held.iloc[210:].all(), "Q108 ENTRY selection"
    book = weights(closes)
    entered = book.index[book["DBC"] > 0]
    first_decision = book.index[book.index >= S[210]][0]
    assert entered[0] == first_decision and (book.loc[: S[209], "DBC"] == 0).all(), "Q108 ENTRY weights"


def test_only_the_eight_sleeves_are_ever_held():
    closes = walk(4, (*ALLOCATION_SLEEVES, "QQQ"))
    book = weights(closes)
    assert (book["QQQ"] == 0).all() and (book[list(ALLOCATION_SLEEVES)].sum(axis=1) > 0).any(), "Q108 SLEEVES"


def test_weights_change_only_on_monthly_decision_rows():
    closes = walk(5, ALLOCATION_SLEEVES)
    book = weights(closes)
    firsts = S.to_series().groupby(S.to_period("M")).first().iloc[1:]
    assert list(book.index) == list(firsts), "Q108 CADENCE"


def test_future_closes_never_change_an_earlier_decision():
    closes = walk(6, ALLOCATION_SLEEVES)
    base = weights(closes)
    for cut in base.index[[4, 10]]:  # decision rows: the rows a one-session shift could reach
        moved = closes.copy()
        later = closes.index > cut
        moved.loc[later] *= np.linspace(0.4, 2.5, later.sum())[:, None]
        assert weights(moved).loc[:cut].equals(base.loc[:cut]), f"Q108 LOOKAHEAD {cut.date()}"
        assert not weights(moved).loc[cut:].iloc[1:].equals(base.loc[cut:].iloc[1:]), "precondition: later rows move"
