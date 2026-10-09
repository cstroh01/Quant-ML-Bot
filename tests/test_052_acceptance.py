"""Spec 052 T006: one synthetic dated panel exercising spec §5 end to end.

EXAMPLE — NOT A RESULT. Every ticker, price, volume and date below is invented to
exercise the registry; nothing here is market data or evidence of any return.
"""
from datetime import date, datetime, time
import hashlib
import statistics

import pandas as pd

import context  # noqa: F401
from asset_registry import (NY, EligibilityLimits, ExecutableQuote, Fact, Registry, causal_membership,
                            executable_eligibility, fold_local_cross_section, research_eligibility)
from mode_config import ModeProfile

S = [d.date() for d in pd.bdate_range("2026-03-02", periods=20)]  # 20 synthetic sessions, no holidays
OLD = date(2020, 1, 2)
LIM = EligibilityLimits(min_sessions=15, min_price=5.0, min_median_dollar_volume=3_500_000.0,
                        max_spread_bps=50.0, max_participation=0.01)
RESEARCH_REASONS = {"insufficient_history", "price_below_floor", "illiquid",
                    "corporate_actions_unreconciled", "price_basis_unknown"}
EXEC_REASONS = {"not_tradable", "halted", "stale_bar", "class_not_permitted", "spread_too_wide",
                "participation_too_high", "below_broker_minimum"}


def at(session: date) -> datetime:
    """An aware instant after that session's close."""
    return datetime.combine(session, time(16, 30), tzinfo=NY)


def fact(iid, field, value, effective, observed=None):
    return Fact(iid, field, value, effective, at(observed or effective), f"synthetic:{iid}")


def panel_facts() -> list[Fact]:
    facts = []
    for iid, sym in [("AAA", "AAA"), ("DLST", "DLST"), ("REN", "OLDN"), ("SPLT", "SPLT"),
                     ("HALT", "HLT"), ("STAL", "STL"), ("OPTN", "OPTX")]:
        facts += [fact(iid, "symbol", sym, OLD), fact(iid, "listed", "NYSE", OLD)]
    return facts + [
        fact("DLST", "delisted", "acquired", S[12]),
        fact("REN", "symbol", "NEWN", S[8], observed=S[6]),  # rename announced two sessions early
        fact("SPLT", "corporate_action", "split 2:1", S[10], observed=S[7]),
        fact("FUT", "symbol", "IPOX", S[15], observed=S[3]),  # future listing, known in advance
        fact("FUT", "listed", "NYSE", S[15], observed=S[3]),
        fact("LATE", "symbol", "LATE", S[5], observed=S[9]),  # effective S[5], first observed S[9]
        fact("LATE", "listed", "NYSE", S[5], observed=S[9]),
    ]


REG = Registry(panel_facts())


def expected_members(i: int) -> set[str]:
    out = {"AAA", "REN", "SPLT", "HALT", "STAL", "OPTN"}
    return out | ({"DLST"} if i < 12 else set()) | ({"LATE"} if i >= 9 else set()) | ({"FUT"} if i >= 15 else set())


def test_causal_membership_uses_each_sessions_own_snapshot():
    assert causal_membership(REG, S) == {s: expected_members(i) for i, s in enumerate(S)}


def test_delisted_name_stays_in_every_snapshot_with_its_reason():
    for i, s in enumerate(S):
        entry = REG.snapshot(s)["DLST"]
        assert entry["symbol"] == "DLST" and entry["active"] is (i < 12)
        assert entry.get("delisted") == ("acquired" if i >= 12 else None)


def test_rename_keeps_identity_and_past_snapshots_keep_the_old_symbol():
    for i, s in enumerate(S):
        snap = REG.snapshot(s)
        symbols = {e["symbol"] for e in snap.values()}
        assert snap["REN"]["symbol"] == ("NEWN" if i >= 8 else "OLDN")
        assert ("OLDN" in symbols) is (i < 8) and ("NEWN" in symbols) is (i >= 8)


def test_future_dated_and_late_observed_facts_are_invisible_earlier():
    for i, s in enumerate(S):
        snap = REG.snapshot(s)
        assert ("FUT" in snap) is (i >= 15)
        assert ("LATE" in snap) is (i >= 9)
        assert ("corporate_action" in snap["SPLT"]) is (i >= 10)


def test_snapshot_hash_is_reproducible_and_moves_only_with_a_visible_fact():
    for s in S:
        assert REG.snapshot_hash(s) == Registry(list(reversed(panel_facts()))).snapshot_hash(s)
    changed = Registry([fact("DLST", "delisted", "bankrupt", S[12]) if f.field == "delisted" else f
                        for f in panel_facts()])
    assert changed.snapshot_hash(S[11]) == REG.snapshot_hash(S[11])
    assert changed.snapshot_hash(S[12]) != REG.snapshot_hash(S[12])


def bars(close, volume) -> pd.DataFrame:
    """Session-labelled Close/Volume over the panel; scalars or per-session lists."""
    return pd.DataFrame({"Close": close, "Volume": volume}, index=pd.DatetimeIndex(S), dtype=float)


NOMINAL = bars([40.0] * 10 + [20.0] * 10, [100_000] * 10 + [200_000] * 10)  # as traded; 2:1 split at S[10]
ADJUSTED = bars(20.0, 200_000)  # back-adjusted to the post-split basis
PENNY = bars(3.0, 100_000).iloc[9:]  # LATE: bars from first observation only


def research(frame, s, **kw):
    flags = {"actions_reconciled": True, "basis_known": True} | kw
    return research_eligibility(frame, as_of=s, limits=LIM, **flags)


def test_split_dollar_volume_is_basis_consistent_and_basis_must_be_known():
    # Dollar volume is 4M every session on either consistent basis; pricing nominal
    # shares at the adjusted price would give a 3M median and a false "illiquid".
    assert research(NOMINAL, S[19]) == research(ADJUSTED, S[19]) == []
    assert research(NOMINAL, S[19], basis_known=False) == ["price_basis_unknown"]
    assert research(NOMINAL, S[19], actions_reconciled=False) == ["corporate_actions_unreconciled"]


def test_every_research_failure_is_reported_not_just_the_first():
    assert research(PENNY, S[19]) == ["insufficient_history", "price_below_floor", "illiquid"]


def test_research_eligibility_reads_only_rows_at_or_before_as_of():
    for frame in (bars(50.0, 200_000), NOMINAL):
        for s in S:
            assert research(frame, s) == research(frame.loc[:pd.Timestamp(s)], s)
    assert research(bars(50.0, 200_000), S[13]) == ["insufficient_history"]  # 14 sessions < 15


PROFILE = ModeProfile(name="paper_small", mode="PAPER", broker="alpaca_paper",
                      account_fingerprint=hashlib.sha256(b"synthetic").hexdigest(),
                      credential_refs=("SYNTHETIC_KEY_REF",), state_dir="state/paper", log_namespace="paper",
                      bot_budget_usd=5_000.0, daily_deploy_fraction=0.2, instruments=("us_equity", "etf"),
                      fractional=True, safety_config_version="synthetic-v1")


def quote(**extra) -> ExecutableQuote:
    base = dict(tradable=True, halted=False, last_bar_session=S[18], instrument_class="us_equity",
                spread_bps=8.0, adv_shares=200_000.0, min_notional_usd=1.0)
    return ExecutableQuote(**(base | extra))


# Injected read-only broker snapshot for an order on S[19]; last completed session is S[18].
ORDERS = {
    "AAA": (quote(), 100, 5_000.0),
    "HALT": (quote(halted=True), 100, 5_000.0),
    "STAL": (quote(last_bar_session=S[16]), 100, 5_000.0),
    "OPTN": (quote(instrument_class="option"), 100, 5_000.0),
    "SPLT": (quote(), 5_000, 100_000.0),  # 2.5% of 20-session ADV
    "REN": (quote(), 0.01, 0.50),  # below the $1 broker minimum
}


def executable() -> dict[str, list[str]]:
    return {iid: executable_eligibility(q, previous_session=S[18], allowed_classes=PROFILE.instruments,
                                        order_qty=qty, order_notional=notional, limits=LIM)
            for iid, (q, qty, notional) in ORDERS.items()}


def test_executable_refusals_name_their_reason_and_honor_the_051_profile():
    assert set(ORDERS) <= causal_membership(REG, [S[19]])[S[19]]
    assert executable() == {"AAA": [], "HALT": ["halted"], "STAL": ["stale_bar"],
                            "OPTN": ["class_not_permitted"], "SPLT": ["participation_too_high"],
                            "REN": ["below_broker_minimum"]}


def test_every_exclusion_on_the_panel_carries_a_named_reason():
    snap, members = REG.snapshot(S[19]), causal_membership(REG, [S[19]])[S[19]]
    ledger = {iid: [e.get("delisted", "")] for iid, e in snap.items() if iid not in members}
    ledger |= {"LATE": research(PENNY, S[19])} | {iid: r for iid, r in executable().items() if r}
    assert set(ledger) == {"DLST", "LATE", "HALT", "STAL", "OPTN", "SPLT", "REN"}
    for iid, reasons in ledger.items():
        assert reasons and all(r.strip() for r in reasons), iid
        assert iid == "DLST" or set(reasons) <= RESEARCH_REASONS | EXEC_REASONS, iid


def test_fold_local_cross_section_fits_on_causal_train_rows_only():
    membership = causal_membership(REG, S)
    rows = [(s, iid) for s in S for iid in sorted(membership[s])]
    frame = pd.DataFrame({"f": [float((7 * k) % 11) for k in range(len(rows))]},
                         index=pd.MultiIndex.from_tuples(rows, names=["session", "instrument_id"]))
    train = [r for r in rows if r[0] <= S[9]]
    assert all(iid != "FUT" and (iid != "DLST" or s < S[12]) for s, iid in train)
    scores, params = fold_local_cross_section(frame, "f", train)
    values = frame.loc[train, "f"].tolist()
    assert abs(params["mean"] - statistics.fmean(values)) < 1e-12
    assert abs(params["std"] - statistics.pstdev(values)) < 1e-12
    shocked = frame.copy()
    shocked.loc[shocked.index.get_level_values("session") > S[9], "f"] = 1e6
    shocked_scores, shocked_params = fold_local_cross_section(shocked, "f", train)
    assert shocked_params == params
    pd.testing.assert_series_equal(scores.loc[train], shocked_scores.loc[train])
