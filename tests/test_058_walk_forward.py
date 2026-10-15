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
    for cut in ("2021-06-01", "2022-11-01"):  # decision rows: the only book rows a one-bar shift could reach
        moved = closes.copy()
        later = closes.index > cut
        moved.loc[later] *= np.linspace(0.5, 3.0, later.sum())[:, None]
        assert cut in base.index and wf.target_book("H9", moved).loc[:cut].equals(base.loc[:cut]), \
            f"T014 LOOKAHEAD book {cut}"


def test_embargo_covers_the_longest_signal_lookback():
    _, closes = panel(5)
    first = hypothesis_selection("H1-12", closes).any(axis=1).to_numpy().argmax()
    assert first >= wf.LONGEST_LOOKBACK - 1, "precondition: H1-12 needs the stated lookback"
    assert wf.EMBARGO >= wf.LONGEST_LOOKBACK >= first + 1, "T014 EMBARGO"
    assert (pd.Timestamp("2019-01-02") + pd.DateOffset(months=wf.INITIAL_TRAIN_MONTHS)) > S[wf.LONGEST_LOOKBACK], \
        "T014 EMBARGO warmup"


@pytest.mark.parametrize("case", ["holdout session", "unknown H11", "unknown H3-4", "flat bps costs"])
def test_refusals_happen_before_any_ledger_event(ledger, case):
    opens, closes = panel(6)
    costs, config, error = COSTS, "H4", ValueError
    if case == "holdout session":
        opens, closes = panel(6, pd.bdate_range("2019-01-02", "2023-10-02"))
        error = HoldoutSealError
    elif case.startswith("unknown"):
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


SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]


def wide_panel(seed=21):
    """Sector ETFs and SHY beside the core four, so H3, H6, H7 and H8 all select something."""
    tickers = [*T, "SHY", *SECTORS]
    rng = np.random.default_rng(seed)
    scale = np.array([0.012, 0.004, 0.009, 0.008, 0.001, *np.linspace(0.008, 0.016, len(SECTORS))])
    steps = rng.normal(0.0002, 1, (len(S), len(tickers))) * scale
    closes = pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=S, columns=tickers)
    opens = closes.shift(1) * np.exp(rng.normal(0, 0.002, closes.shape))
    return opens.fillna(closes), closes


@pytest.mark.parametrize("config_id", ["H3-3", "H3-5", "H6-6", "H6-12", "H7", "H8"])
def test_equal_leg_configurations_follow_d8_sizing_and_their_cadence(config_id):
    from portfolio_risk import equal_weight_vol_target_book
    _, closes = wide_panel()
    book = wf.target_book(config_id, closes)
    full = equal_weight_vol_target_book(hypothesis_selection(config_id, closes), closes, span=60,
                                        target_volatility=0.10, max_gross=1.0)
    cadence = "weekly" if config_id == "H8" else "monthly"
    expected = full.loc[decision_sessions(full.index, cadence=cadence)]
    pd.testing.assert_frame_equal(book, expected, obj=f"T014 D8 {config_id}")
    assert (book.sum(axis=1) <= 1 + 1e-12).all() and (book > 0).any().any(), f"T014 D8 {config_id} gross/empty"
    held = book[book.sum(axis=1) > 0]
    assert all(np.allclose(r[r > 0], r[r > 0].iloc[0]) for _, r in held.iterrows()), f"T014 D8 {config_id} equal legs"
    assert len(book) > 3 * len(wf.target_book("H7", closes)) if config_id == "H8" else True, "T014 CADENCE weekly"


def test_an_equal_leg_configuration_records_one_completed_trial(ledger):
    opens, closes = wide_panel(22)
    receipt = run("H8", opens, closes)
    events = ledger.verify()["events"]
    assert [e["event_type"] for e in events] == ["started", "completed"], "T014 D8 trial"
    assert events[0]["config"]["model"]["params"]["sizing"] == "equal_legs_scaled_down", "T014 D8 sizing recorded"
    assert receipt["event_type"] == "completed", "T014 D8 receipt"


# --- Spec 058 T013 B-RND (queue Q132). EXAMPLE — NOT A RESULT: synthetic panels and ledger only. ---
from portfolio_risk import equal_weight_book, equal_weight_vol_target_book
from signals import random_selection


def test_brnd_seeds_are_the_twenty_preregistered_constants():
    assert wf.BRND_SEEDS == tuple(range(20261015, 20261035)) and len(wf.BRND_SEEDS) == 20, "Q132 SEEDS"
    assert wf.require_brnd_seeds(wf.BRND_SEEDS) == wf.BRND_SEEDS
    for bad in (wf.BRND_SEEDS[:1], wf.BRND_SEEDS[:19], wf.BRND_SEEDS[::-1], tuple(range(1, 21))):
        with pytest.raises(ValueError):
            wf.require_brnd_seeds(bad)


def test_brnd_matches_each_candidates_sizing_class_and_cadence():
    for c in wf.CANDIDATES:
        expected = ("equal_legs_vol_target" if c in wf.EQUAL_LEGS else
                    "equal_weight_unscaled" if c == "H10" else "inverse_vol_vol_target")
        assert wf.sizing_class(c) == expected, f"Q132 SIZING {c}"
        assert wf.cadence(c) == ("weekly" if c == "H8" else "monthly"), f"Q132 CADENCE {c}"
    assert len(wf.CANDIDATES) == 15
    with pytest.raises(ValueError):
        wf.sizing_class("B-BH")


def test_inverse_vol_brnd_book_is_the_hand_built_vol_target_book():
    _, closes = panel(3)
    activity = wf.brnd_activity("H4", closes)
    mask = decision_sessions(closes.index, cadence="monthly")
    selection = random_selection(closes, decision_mask=mask, seed=wf.BRND_SEEDS[0], **activity)
    oracle = volatility_target_book(selection, closes, span=wf.VOL_SPAN, target_volatility=wf.TARGET_VOLATILITY,
                                    max_gross=wf.MAX_GROSS).loc[mask]
    book = wf.brnd_book("H4", closes, seed=wf.BRND_SEEDS[0], activity=activity)
    pd.testing.assert_frame_equal(book, oracle)
    wrong = equal_weight_vol_target_book(selection, closes, span=wf.VOL_SPAN, target_volatility=wf.TARGET_VOLATILITY,
                                         max_gross=wf.MAX_GROSS).loc[mask]
    assert not np.allclose(book.to_numpy(), wrong.to_numpy()), "Q132 SIZING CLASS"


def test_h10_brnd_is_unscaled_equal_weight():
    _, closes = panel(4)
    activity = wf.brnd_activity("H10", closes)
    mask = decision_sessions(closes.index, cadence="monthly")
    selection = random_selection(closes, decision_mask=mask, seed=wf.BRND_SEEDS[1], **activity)
    book = wf.brnd_book("H10", closes, seed=wf.BRND_SEEDS[1], activity=activity)
    pd.testing.assert_frame_equal(book, equal_weight_book(selection, max_gross=1.0).loc[mask])


def test_h8_brnd_decides_on_iso_week_starts():
    _, closes = wide_panel(5)
    book = wf.brnd_book("H8", closes, seed=wf.BRND_SEEDS[2], activity=wf.brnd_activity("H8", closes))
    weekly = closes.index[decision_sessions(closes.index, cadence="weekly")]
    assert book.index.equals(weekly) and len(book) > 200, "Q132 CADENCE H8"


def test_brnd_activity_is_matched_and_fitted_inside_the_research_window(monkeypatch):
    _, closes = panel(6)
    activity = wf.brnd_activity("H1-12", closes)
    assert set(activity) == {"enter_probability", "exit_probability", "initial_probability"}
    assert 0 < activity["initial_probability"] < 1, "Q132 MATCHED"
    late = pd.bdate_range(closes.index[-1] + pd.Timedelta(days=1), periods=5)
    extended = pd.concat([closes, pd.DataFrame(100.0, index=late, columns=closes.columns)])
    monkeypatch.setattr(wf, "matched_activity", lambda *a, **k: pytest.fail("fitted on a sealed panel"))
    with pytest.raises(HoldoutSealError):
        wf.brnd_activity("H1-12", extended)


def test_seeds_give_different_baselines_and_a_positive_dispersion():
    opens, closes = panel(7)
    activity = wf.brnd_activity("H1-12", closes)  # a switching candidate; an always-invested one matches itself
    returns = {}
    for seed in wf.BRND_SEEDS[:3]:
        rows, _ = wf._oos_from_book(wf.brnd_book("H1-12", closes, seed=seed, activity=activity), opens, closes,
                                    fill_cost=FILL, commission_per_fill=1.0, starting_capital=100_000.0)
        returns[seed] = rows
    spread = wf.brnd_dispersion(returns)
    assert spread["annual_log_return"]["sd"] > 0 and spread["sharpe"]["n_seeds"] == 3, "Q132 SEED STREAMS"


def test_dispersion_matches_hand_computation():
    a, b = [0.01, -0.02, 0.03], [0.0, 0.01, 0.01]
    out = wf.brnd_dispersion({1: a, 2: b})
    sa, sb = np.std(a, ddof=1), np.std(b, ddof=1)
    sharpe = [np.mean(a) / sa * np.sqrt(252), np.mean(b) / sb * np.sqrt(252)]
    assert out["sharpe"]["mean"] == pytest.approx(np.mean(sharpe))
    assert out["max_drawdown"]["min"] == pytest.approx(np.exp(-0.02) - 1)
    assert out["max_drawdown"]["max"] == pytest.approx(0.0)
    with pytest.raises(ValueError):
        wf.brnd_dispersion({1: a})


def test_brnd_is_recorded_as_a_random_signal_baseline_never_a_candidate(ledger, monkeypatch):
    before = real_ledger_digest()
    roles, original = [], wf.research_attempt

    def spy(config, *, role, family):
        roles.append((role, family, config["model"]["name"], config["seed"]))
        return original(config, role=role, family=family)

    monkeypatch.setattr(wf, "research_attempt", spy)
    opens, closes = panel(8)
    receipt = wf.run_brnd("H3-3", wf.BRND_SEEDS[0], opens, closes, fill_cost=FILL, costs=COSTS, data=DATA)
    assert roles == [("random_signal_baseline", wf.FAMILY, "B-RND", wf.BRND_SEEDS[0])], "Q132 ROLE"
    events = ledger.verify()["events"]
    assert [e["event_type"] for e in events] == ["started", "completed"]
    params = events[0]["config"]["model"]["params"] if "config" in events[0] else None
    assert receipt["sidecar"]["metadata"]["oos"] is True
    assert params is None or (params["candidate"] == "H3-3" and params["sizing"] == "equal_legs_vol_target")
    assert real_ledger_digest() == before, "Q132 REAL LEDGER"


def test_brnd_refuses_unregistered_seeds_and_sealed_panels_before_any_ledger_event(ledger):
    opens, closes = panel(9)
    with pytest.raises(ValueError):
        wf.run_brnd("H4", 7, opens, closes, fill_cost=FILL, costs=COSTS, data=DATA)
    with pytest.raises(ValueError):
        wf.run_brnd_family("H4", opens, closes, seeds=wf.BRND_SEEDS[:1], fill_cost=FILL, costs=COSTS, data=DATA)
    late = pd.bdate_range(closes.index[-1] + pd.Timedelta(days=1), periods=3)
    grow = lambda f: pd.concat([f, pd.DataFrame(100.0, index=late, columns=f.columns)])  # noqa: E731
    with pytest.raises(HoldoutSealError):
        wf.run_brnd("H4", wf.BRND_SEEDS[0], grow(opens), grow(closes), fill_cost=FILL, costs=COSTS, data=DATA)
    assert ledger.verify()["events"] == [], "Q132 PRE-LEDGER REFUSAL"
