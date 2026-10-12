"""Spec 058 T014: the purged, embargoed walk-forward runner (Rules 1, 2, 3, 5, 13).

EXAMPLE — NOT A RESULT. Seeded synthetic random walks and a synthetic ledger root; the real
docs/trials/ ledger is never written and its bytes are checked unchanged.
"""
import hashlib
import json
import shutil

import numpy as np
import pandas as pd
import pytest
from context import SCRIPTS_DIR

import edge_walk_forward as wf
from data_sources import HoldoutSealError, RESEARCH_END
from portfolio_backtest import run_portfolio_backtest
from portfolio_risk import fixed_allocation_book, volatility_target_book
from selection_bias import _eligible
from signals import decision_sessions, hypothesis_selection
from trial_registry import DECLARED_FAMILIES, TrialLedger, declare_family
from trial_runner import injected_ledger

ROOT = SCRIPTS_DIR.parent
S = pd.bdate_range("2019-01-02", str(RESEARCH_END))
T = ["SPY", "IEF", "GLD", "TLT"]
COSTS = {"commission": 1.0, "slippage": {"model": "spread_plus_sqrt_impact", "source": "synthetic fixture"}}
DATA = {"sha256": "d" * 64, "price_basis": "unadjusted_dollars", "corporate_actions_verified": True}
FILL = lambda ticker, as_of, quantity: 5e-4  # noqa: E731


def panel(seed=1, index=S):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0002, 1, (len(index), len(T))) * np.array([0.012, 0.004, 0.009, 0.008])
    closes = pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=index, columns=T)
    opens = closes.shift(1) * np.exp(rng.normal(0, 0.002, closes.shape))
    return opens.fillna(closes), closes


def real_ledger_digest():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "docs/trials").rglob("*")) if p.is_file()}


@pytest.fixture
def ledger(tmp_path):
    source = tmp_path / DECLARED_FAMILIES[wf.FAMILY]
    source.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / DECLARED_FAMILIES[wf.FAMILY], source)
    declare_family(wf.FAMILY, root=tmp_path, synthetic=True)
    log = TrialLedger(tmp_path, synthetic=True)
    with injected_ledger(log):
        yield log


def run(config_id, opens, closes, **changes):
    return wf.run_configuration(config_id, opens, closes, fill_cost=FILL, costs=changes.get("costs", COSTS), data=DATA)


def test_one_configuration_is_one_completed_trial_with_oos_returns_and_cv(ledger):
    before = real_ledger_digest()
    opens, closes = panel()
    receipt = run("H4", opens, closes)
    events = ledger.verify()["events"]
    assert [(e["event_type"], e["family"]) for e in events] == [("started", wf.FAMILY), ("completed", wf.FAMILY)], \
        "T014 RECORD"
    meta = receipt["sidecar"]["metadata"]
    assert meta["oos"] is True and meta["net_costs"] is True and meta["costs"] == COSTS, "T014 RECORD metadata"
    assert meta["cv"]["folds"] == 4 and meta["cv"]["purge"] == 1 and meta["cv"]["embargo"] >= wf.LONGEST_LOOKBACK, \
        "T014 RECORD cv"
    rows = [json.loads(line) for line in (ledger.root / receipt["sidecar"]["path"]).read_text().splitlines()]
    assert rows[0]["session"] >= "2020-02-03" and rows[-1]["session"] == str(RESEARCH_END), "T014 TRAIN"
    assert real_ledger_digest() == before, "T014 REAL LEDGER"
    # Spec 033's matrix must accept it: roles are synthetic here and the copy has no git metadata.
    trial = receipt | {"role": "candidate", "returns": rows, "source": {"git_sha": "a" * 40, "workspace_state": "clean"}}
    assert _eligible(trial) is None, f"T014 ELIGIBLE {_eligible(trial)}"


def test_oos_rows_are_costed_equity_returns_on_test_sessions_only():
    opens, closes = panel(2)
    rows, cv = wf.oos_returns("H10", opens, closes, fill_cost=FILL, commission_per_fill=1.0, starting_capital=1e5)
    book = fixed_allocation_book(closes, wf.H10)
    book = book.loc[decision_sessions(book.index, cadence="monthly")]
    equity = run_portfolio_backtest(opens, closes, book, starting_capital=1e5, commission_per_fill=1.0,
                                    fill_cost=FILL).equity
    expected = np.log(equity / equity.shift(1)).loc["2020-02-03":]
    assert [r["session"] for r in rows] == [d.strftime("%Y-%m-%d") for d in expected.index], "T014 TRAIN sessions"
    assert np.allclose([r["log_return"] for r in rows], expected.to_numpy(), rtol=0, atol=1e-15), "T014 OOS"
    gross = np.log(run_portfolio_backtest(opens, closes, book, starting_capital=1e5, commission_per_fill=0.0,
                                          fill_cost=lambda *_: 0.0).equity)
    assert not np.allclose(gross.diff().loc["2020-02-03":], expected), "precondition: costs move the returns"


def test_h9_blends_its_three_inverse_vol_books_on_monthly_rows():
    _, closes = panel(3)
    parts = [volatility_target_book(hypothesis_selection(p, closes), closes, span=60, target_volatility=0.10,
                                    max_gross=1.0) for p in ("H1-12", "H2-200", "H4")]  # declaration H9
    expected = sum(parts) / 3
    book = wf.target_book("H9", closes)
    assert book.index.equals(closes.index[decision_sessions(closes.index, cadence="monthly")]), "T014 CADENCE"
    assert np.allclose(book, expected.loc[book.index], rtol=0, atol=1e-15), "T014 H9"


def test_future_rows_never_change_earlier_oos_returns():
    opens, closes = panel(4)
    base, _ = wf.oos_returns("H9", opens, closes, fill_cost=FILL, commission_per_fill=1.0, starting_capital=1e5)
    for cut in ("2021-06-15", "2022-11-30"):
        moved_opens, moved_closes = opens.copy(), closes.copy()
        later = closes.index > cut
        moved_closes.loc[later] *= np.linspace(0.5, 3.0, later.sum())[:, None]
        moved_opens.loc[later] *= np.linspace(0.5, 3.0, later.sum())[:, None]
        moved, _ = wf.oos_returns("H9", moved_opens, moved_closes, fill_cost=FILL, commission_per_fill=1.0,
                                  starting_capital=1e5)
        upto = [r for r in base if r["session"] <= cut]
        assert [r for r in moved if r["session"] <= cut] == upto, f"T014 LOOKAHEAD {cut}"
        assert moved[len(upto):] != base[len(upto):], "precondition: the perturbation reaches later rows"


def test_future_closes_never_change_earlier_book_rows():
    _, closes = panel(8)
    base = wf.target_book("H9", closes)
    for cut in ("2021-06-15", "2022-11-30"):
        moved = closes.copy()
        later = closes.index > cut
        moved.loc[later] *= np.linspace(0.5, 3.0, later.sum())[:, None]
        assert wf.target_book("H9", moved).loc[:cut].equals(base.loc[:cut]), f"T014 LOOKAHEAD book {cut}"


def test_embargo_covers_the_longest_signal_lookback():
    _, closes = panel(5)
    first = hypothesis_selection("H1-12", closes).any(axis=1).to_numpy().argmax()
    assert first >= wf.LONGEST_LOOKBACK - 1, "precondition: H1-12 needs the stated lookback"
    assert wf.EMBARGO >= wf.LONGEST_LOOKBACK >= first + 1, "T014 EMBARGO"
    assert (pd.Timestamp("2019-01-02") + pd.DateOffset(months=wf.INITIAL_TRAIN_MONTHS)) > S[wf.LONGEST_LOOKBACK], \
        "T014 EMBARGO warmup"


@pytest.mark.parametrize("case", ["holdout session", "undecided H3-3", "undecided H7", "unknown H11", "flat bps costs"])
def test_refusals_happen_before_any_ledger_event(ledger, case):
    opens, closes = panel(6)
    costs, config, error = COSTS, "H4", ValueError
    if case == "holdout session":
        opens, closes = panel(6, pd.bdate_range("2019-01-02", "2023-10-02"))
        error = HoldoutSealError
    elif case.startswith(("undecided", "unknown")):
        config = case.split()[1]
    else:
        costs = {"commission": 1.0, "slippage": {"model": "flat_bps", "bps": 5}}
    try:
        run(config, opens, closes, costs=costs)
        refused = False
    except error:
        refused = True
    assert refused and ledger.verify()["events"] == [], f"T014 REFUSE {case}"


def test_holdout_is_refused_by_the_returns_function_too():
    opens, closes = panel(7, pd.bdate_range("2019-01-02", "2023-10-02"))
    refusal = ""
    try:
        wf.oos_returns("H4", opens, closes, fill_cost=FILL, commission_per_fill=1.0, starting_capital=1e5)
    except HoldoutSealError as error:
        refusal = str(error)
    assert "sealed" in refusal, "T014 SEAL"
