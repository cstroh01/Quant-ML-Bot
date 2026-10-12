"""Spec 058 T013 remainder (queue Q105): the B-RND seeded random-signal baseline selection.

EXAMPLE — NOT A RESULT. Seeded synthetic panels; no figure here is a result.
Declaration rule (B-RND): "seeded random long/flat per asset, monthly, same sizing and costs".
Rule 4: matched trade frequency (entries and exits, not only exposure), several seeds;
Rule 1: row t reads nothing after t.
"""

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401 -- existing repository import bootstrap
import signals
from mutation_support_019 import killed

TICKERS = ["SPY", "IEF", "GLD", "XLK", "XLE", "SHY"]


def panel(n=260, seed=0, late=None):
    """Synthetic closes on business days; ``late`` maps ticker -> first listed row."""
    index = pd.bdate_range("2019-01-02", periods=n)
    values = 100 * np.exp(np.cumsum(np.random.default_rng(seed).normal(0, 0.01, (n, len(TICKERS))), axis=0))
    closes = pd.DataFrame(values, index=index, columns=TICKERS)
    for ticker, row in (late or {}).items():
        closes.iloc[:row, closes.columns.get_loc(ticker)] = np.nan
    return closes


def monthly(closes):
    return signals.decision_sessions(closes.index, cadence="monthly")


def coin(p):
    """Enter p, exit 1 - p, start p: the Markov chain that is an independent p-coin each decision."""
    return {"enter_probability": p, "exit_probability": 1 - p, "initial_probability": p}


def draw(closes, p=0.5, seed=7, **activity):
    return signals.random_selection(closes, decision_mask=monthly(closes), seed=seed, **(activity or coin(p)))


def changes(selection, mask):
    """Position changes between consecutive decision rows, over all tickers."""
    rows = selection.to_numpy()[mask]
    return int((rows[1:] != rows[:-1]).sum())


def test_same_seed_same_selection_and_different_seeds_differ():
    closes = panel()
    first = draw(closes, seed=7)
    pd.testing.assert_frame_equal(first, draw(closes, seed=7))
    assert not first.equals(draw(closes, seed=8))
    assert first.shape == closes.shape and (first.dtypes == bool).all()


def test_selection_changes_only_on_decision_rows_and_nothing_before_the_first():
    closes = panel()
    mask = monthly(closes)
    out = draw(closes)
    assert not out.iloc[:int(np.argmax(mask))].to_numpy().any()  # flat before the first decision
    changed = (out != out.shift(1, fill_value=False)).any(axis=1).to_numpy()
    assert not (changed & ~mask).any()  # complete panel: holdings move only on decision rows


def test_never_selects_a_ticker_without_a_close_at_t():
    closes = panel(late={"XLE": 120})
    closes.iloc[200:205, closes.columns.get_loc("GLD")] = np.nan  # a halt inside the panel
    out = draw(closes, p=1.0)
    assert not (out & closes.isna()).to_numpy().any()
    assert not out["XLE"].iloc[:120].any() and out["XLE"].iloc[120:].any()


def test_row_t_reads_nothing_after_t():
    """Rule 1: perturb every value and the missing-row pattern after t; rows <= t are unchanged."""
    closes = panel()
    t = 150
    future = closes.copy()
    future.iloc[t + 1:] = future.iloc[t + 1:] * 3.0
    future.iloc[t + 1:t + 40, 0] = np.nan
    for p in (0.5, 1.0):  # p = 1 holds every eligible name, so any read of t+1's close shows at t
        pd.testing.assert_frame_equal(draw(closes, p=p).iloc[:t + 1], draw(future, p=p).iloc[:t + 1])


def test_a_ticker_stream_does_not_depend_on_the_other_columns():
    closes = panel()
    alone = draw(closes[["SPY"]])["SPY"]
    pd.testing.assert_series_equal(draw(closes)["SPY"], alone)


@pytest.mark.parametrize("p", [0.0, 1.0])
def test_probability_bounds(p):
    closes = panel()
    out = draw(closes, p=p)
    mask = monthly(closes)
    started = np.cumsum(mask) > 0
    expected = closes.notna() & (p == 1.0) & started[:, None]
    pd.testing.assert_frame_equal(out, pd.DataFrame(expected, index=closes.index, columns=closes.columns))


def test_hold_rate_matches_the_requested_probability():
    closes = panel(n=2600)
    mask = monthly(closes)
    out = draw(closes, p=0.3, seed=11)
    realized = out.loc[mask].to_numpy().sum() / closes.loc[mask].notna().to_numpy().sum()
    assert realized == pytest.approx(0.3, abs=0.03)


def test_matched_activity_fits_exposure_entries_and_exits_on_decision_rows():
    closes = panel(late={"XLE": 100})
    mask = monthly(closes)
    rows = np.flatnonzero(mask)
    candidate = pd.DataFrame(False, index=closes.index, columns=closes.columns)
    candidate.loc[:, ["SPY", "IEF"]] = True            # held throughout: no exits
    candidate.iloc[rows[4]:, candidate.columns.get_loc("GLD")] = True  # one entry, never left
    fit = signals.matched_activity(candidate, closes, decision_mask=mask)
    eligible = closes.notna().to_numpy()[mask]
    held = candidate.to_numpy()[mask]
    both = eligible[1:] & eligible[:-1]
    assert fit["initial_probability"] == pytest.approx(held.sum() / eligible.sum())
    assert fit["exit_probability"] == 0.0
    assert fit["enter_probability"] == pytest.approx(1 / (both & ~held[:-1]).sum())
    candidate.loc[~mask] = ~candidate.loc[~mask]  # rows between decisions are not decisions
    assert signals.matched_activity(candidate, closes, decision_mask=mask) == fit


def test_baseline_matches_the_candidates_turnover_not_just_its_exposure():
    """Review P1 (#192): a persistent candidate must not face a churning baseline."""
    closes = panel(n=2600)
    mask = monthly(closes)
    persistent = pd.DataFrame(False, index=closes.index, columns=closes.columns)
    persistent.loc[:, ["SPY", "IEF"]] = True
    fit = signals.matched_activity(persistent, closes, decision_mask=mask)
    books = signals.random_selections(closes, decision_mask=mask, seeds=range(1, 21), **fit)
    assert all(changes(book, mask) == 0 for book in books.values())  # candidate makes 0 changes
    assert len({tuple(book.iloc[-1]) for book in books.values()}) > 1  # seeds still disperse
    active = draw(closes, seed=99, enter_probability=0.2, exit_probability=0.3, initial_probability=0.4)
    fit = signals.matched_activity(active, closes, decision_mask=mask)
    books = signals.random_selections(closes, decision_mask=mask, seeds=range(1, 21), **fit)
    mean = np.mean([changes(book, mask) for book in books.values()])
    assert mean == pytest.approx(changes(active, mask), rel=0.1)


def test_matched_activity_refuses_a_selection_without_a_close():
    closes = panel(late={"XLE": 100})
    candidate = pd.DataFrame(True, index=closes.index, columns=closes.columns)
    with pytest.raises(ValueError, match="no close"):
        signals.matched_activity(candidate, closes, decision_mask=monthly(closes))


def test_several_seeds_are_required_and_each_is_its_own_draw():
    closes = panel()
    mask = monthly(closes)
    books = signals.random_selections(closes, decision_mask=mask, seeds=[1, 2, 3], **coin(0.4))
    assert list(books) == [1, 2, 3]
    pd.testing.assert_frame_equal(books[2], signals.random_selection(
        closes, decision_mask=mask, seed=2, **coin(0.4)))
    for seeds in ([1], [1, 1], [1, 2.5], [True, 2]):
        with pytest.raises(ValueError, match="seeds"):
            signals.random_selections(closes, decision_mask=mask, seeds=seeds, **coin(0.4))


@pytest.mark.parametrize("p", [-0.1, 1.1, float("nan")])
def test_invalid_probability_and_mask_are_refused(p):
    closes = panel()
    for name in ("enter_probability", "exit_probability", "initial_probability"):
        with pytest.raises(ValueError, match=name):
            draw(closes, **{**coin(0.5), name: p})
    with pytest.raises(ValueError, match="decision_mask"):
        signals.random_selection(closes, decision_mask=monthly(closes)[1:], seed=1, **coin(0.5))


# --- Rule 12: planted defects, each killed by its own contract with a passing control ---

@pytest.mark.parametrize("old, new, oracle", [
    # Eligibility read one row ahead: the selection at t knows whether t+1 has a close.
    ("present = closes.notna().to_numpy()",
     "present = closes.notna().shift(-1, fill_value=True).to_numpy()",
     test_row_t_reads_nothing_after_t),
    # Exits drawn as a fair coin regardless of the candidate (the churn the review found).
    ("state = draws[k] >= exit_probability", "state = draws[k] >= 0.5",
     test_baseline_matches_the_candidates_turnover_not_just_its_exposure),
    # Entries ignore the fitted probability.
    ("state = draws[k] < enter_probability", "state = draws[k] < 0.5",
     test_hold_rate_matches_the_requested_probability),
    # The monthly holding not carried between decisions (flat between rebalances).
    ("held[row, col] = state and present[row, col]",
     "held[row, col] = state and present[row, col] and mask[row]",
     test_selection_changes_only_on_decision_rows_and_nothing_before_the_first),
], ids=["future-eligibility", "exit-ignored", "enter-ignored", "carry-dropped"])
def test_planted_defects_are_killed(old, new, oracle):
    killed(signals, old, new, oracle)
