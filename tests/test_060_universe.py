"""EXAMPLE — NOT A RESULT. Spec 060 T002 (queue Q113): offline ETF universe builder and v1 list format.

Every figure below is a synthetic fixture value, not market data. The real list
(`docs/universe/etf_universe_v1.csv`) is built by spec 060 T007's bounded fetch.
"""

import socket
from datetime import date

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401 -- existing repository import bootstrap
import asset_registry as ar
from mutation_support_019 import killed

AS_OF = date(2026, 10, 1)
SESSIONS = pd.bdate_range("2022-01-03", "2027-06-30")  # weekdays; ~190 sessions after AS_OF
LIQUID = 30e6  # synthetic dollar volume per session, above the $20M floor


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def deny_network(*args, **kwargs):
        pytest.fail("Spec 060 tests must not access the network")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(socket.socket, "connect", deny_network)


def cand(symbol, asset_class="us_equity_broad", *, name=None, etf=True, test_issue=False,
         category="", listed="2010-01-04"):
    return {"symbol": symbol, "name": name or f"{symbol} Index Fund", "etf_flag": etf,
            "test_issue": test_issue, "issuer_category": category, "asset_class": asset_class,
            "listing_date": pd.Timestamp(listed)}


def panel(spec):
    """``spec`` maps symbol -> (first session, dollar volume per session, or a callable of Date)."""
    rows = []
    for symbol, (first, dollar) in spec.items():
        dates = SESSIONS[SESSIONS >= pd.Timestamp(first)]
        values = dollar(dates) if callable(dollar) else np.full(len(dates), dollar)
        rows.append(pd.DataFrame({"Date": dates, "Ticker": symbol, "Close": 100.0,
                                  "Volume": np.asarray(values) / 100.0}))
    return pd.concat(rows, ignore_index=True)


def build(candidates, bars, **kw):
    kw.setdefault("size", 100)
    return ar.build_etf_universe(pd.DataFrame(candidates), bars, as_of=AS_OF, **kw)


def row(result, symbol):
    hit = result.loc[result["symbol"].eq(symbol)]
    assert len(hit) == 1, symbol
    return hit.iloc[0]


def test_taxonomy_is_spec_060_section_3():
    assert len(ar.ETF_ASSET_CLASSES) == 14 and len(set(ar.ETF_ASSET_CLASSES)) == 14
    assert ar.MIN_MEDIAN_DOLLAR_VOLUME == 20e6 and ar.DOLLAR_VOLUME_SESSIONS == 252
    assert ar.HISTORY_YEARS == 3 and ar.CLASS_CAP == 12


def test_every_candidate_gets_one_row_and_every_exclusion_a_reason():
    cands = [cand("AAA"), cand("BBB", etf=False), cand("CCC", test_issue=True),
             cand("DDD", "not_a_class"), cand("EEE")]
    bars = panel({s: ("2022-01-03", LIQUID) for s in "AAA BBB CCC DDD".split()})
    result = build(cands, bars)
    assert list(result.columns) == list(ar.UNIVERSE_COLUMNS)
    assert sorted(result["symbol"]) == ["AAA", "BBB", "CCC", "DDD", "EEE"]
    assert row(result, "AAA")["selected"] and row(result, "AAA")["exclusion_reason"] == ""
    assert row(result, "BBB")["exclusion_reason"] == "not_etf"
    assert row(result, "CCC")["exclusion_reason"] == "test_issue"
    assert row(result, "DDD")["exclusion_reason"] == "unknown_asset_class"
    assert row(result, "EEE")["exclusion_reason"] == "insufficient_history"  # no bars at all
    assert (result.loc[~result["selected"], "exclusion_reason"] != "").all()
    ar.validate_universe(result, require_all_classes=False)


@pytest.mark.parametrize("name, category", [
    ("ProShares Ultra QQQ", ""), ("Direxion Daily Semiconductor Bull 3X", ""),
    ("ProShares Short S&P500", ""), ("iPath S&P 500 VIX Short-Term Futures ETN", ""),
    ("Plain Name Fund", "leveraged"), ("Plain Name Fund", "Inverse"),
    ("Plain Name Fund", "volatility"), ("ProShares UltraShort 20+ Year Treasury", ""),
    ("ProShares Short 20+ Year Treasury", ""), ("ProShares Short High Yield", ""),
    ("Invesco DB US Dollar Index Bearish Fund", ""),
])
def test_leveraged_inverse_and_volatility_products_are_screened(name, category):
    result = build([cand("LEV", name=name, category=category)], panel({"LEV": ("2022-01-03", LIQUID)}))
    assert row(result, "LEV")["exclusion_reason"] == "leveraged_inverse_or_volatility"


def test_ordinary_names_pass_the_screen():
    for name in ("Vanguard Short-Term Bond ETF", "iShares 1-3 Year Treasury Bond ETF",
                 "SPDR Gold Shares", "Invesco DB US Dollar Index Bullish Fund",
                 "Invesco S&P 500 Low Volatility ETF", "JPMorgan Ultra-Short Income ETF",
                 "iShares Short Treasury Bond ETF", "iShares Short Maturity Bond ETF",
                 "PIMCO Enhanced Short Maturity Active ETF", "BlackRock Ultra Short-Term Bond ETF",
                 "Invesco Ultra Short Duration ETF"):
        result = build([cand("OK", name=name)], panel({"OK": ("2022-01-03", LIQUID)}))
        assert row(result, "OK")["selected"], name


def test_three_year_history_boundary():
    # as_of - 3 years is Sun 2023-10-01: a first bar on Fri 2023-09-29 passes, Mon 10-02 fails.
    bars = panel({"EDGE": ("2023-09-29", LIQUID), "LATE": ("2023-10-02", LIQUID)})
    result = build([cand("EDGE"), cand("LATE")], bars)
    assert row(result, "EDGE")["selected"]
    assert row(result, "LATE")["exclusion_reason"] == "insufficient_history"


def test_dollar_volume_floor_is_inclusive_and_uses_the_median():
    spiky = lambda d: np.where(np.arange(len(d)) % 3 == 0, 1e9, 10e6)  # median below, mean above
    bars = panel({"FLOOR": ("2022-01-03", 20e6), "THIN": ("2022-01-03", 19.99e6),
                  "SPIKY": ("2022-01-03", spiky)})
    result = build([cand("FLOOR"), cand("THIN"), cand("SPIKY")], bars)
    assert row(result, "FLOOR")["selected"]
    assert row(result, "THIN")["exclusion_reason"] == "illiquid"
    assert row(result, "SPIKY")["exclusion_reason"] == "illiquid"


def test_dollar_volume_reads_only_sessions_at_or_before_as_of():
    """Rule 1: a liquidity burst after as_of must not admit a thin ETF, nor a drought evict a liquid one."""
    burst = lambda d: np.where(d > pd.Timestamp(AS_OF), 1e10, 5e6)
    drought = lambda d: np.where(d > pd.Timestamp(AS_OF), 0.0, LIQUID)
    result = build([cand("BURST"), cand("DRY")],
                   panel({"BURST": ("2022-01-03", burst), "DRY": ("2022-01-03", drought)}))
    assert row(result, "BURST")["exclusion_reason"] == "illiquid"
    assert row(result, "DRY")["selected"]
    assert row(result, "DRY")["median_dollar_volume_252"] == pytest.approx(LIQUID)


def test_window_is_the_trailing_252_sessions():
    # Thin for all but the last 126 sessions: the 252-session median sits on the boundary.
    late = lambda d: np.where(np.arange(len(d)) >= len(d) - 126 - (d > pd.Timestamp(AS_OF)).sum(),
                              1e9, 1e6)
    result = build([cand("LATE")], panel({"LATE": ("2022-01-03", late)}))
    assert row(result, "LATE")["median_dollar_volume_252"] == pytest.approx((1e6 + 1e9) / 2)


def test_missing_sessions_extend_the_window_to_252_bars():
    """Rule 5 gap case: the window is the last 252 bars on or before as_of; a missing session
    (halt, holiday, absent bar) is not imputed, so the window reaches one bar further back."""
    late = lambda d: np.where(np.arange(len(d)) >= len(d) - 126 - (d > pd.Timestamp(AS_OF)).sum(),
                              1e9, 1e6)
    bars = panel({"GAP": ("2022-01-03", late), "FULL": ("2022-01-03", late)})
    halted = pd.Timestamp("2026-09-15")  # inside the 126 high-volume sessions
    bars = bars.loc[~(bars["Ticker"].eq("GAP") & bars["Date"].eq(halted))]
    result = build([cand("GAP"), cand("FULL")], bars)
    assert row(result, "FULL")["median_dollar_volume_252"] == pytest.approx((1e6 + 1e9) / 2)
    assert row(result, "GAP")["median_dollar_volume_252"] == pytest.approx(1e6)  # 125 high, 127 low
    assert row(result, "GAP")["exclusion_reason"] == "illiquid"
    assert row(result, "GAP")["first_bar"] == "2022-01-03"


def test_non_finite_volume_fails_closed():
    bad = lambda d: np.where(d == pd.Timestamp("2026-09-01"), np.nan, LIQUID)  # inside the window
    result = build([cand("NAN")], panel({"NAN": ("2022-01-03", bad)}))
    assert row(result, "NAN")["exclusion_reason"] == "illiquid"


def test_class_cap_and_size_cutoff_rank_by_dollar_volume():
    cands = [cand(f"E{i:02d}") for i in range(14)] + [cand("BND1", "treasuries")]
    bars = panel({**{f"E{i:02d}": ("2022-01-03", LIQUID + i * 1e6) for i in range(14)},
                  "BND1": ("2022-01-03", LIQUID + 50e6)})
    result = build(cands, bars, size=12)
    chosen = result.loc[result["selected"], "symbol"].tolist()
    assert len(chosen) == 12 and "E00" not in chosen and "E13" in chosen
    assert row(result, "E01")["exclusion_reason"] == "class_cap"
    assert row(result, "E00")["exclusion_reason"] == "class_cap"
    assert row(result, "E02")["exclusion_reason"] == "below_cutoff"  # 13th after the class cap
    assert row(result, "BND1")["selected"]
    assert list(result["rank"].dropna()) == list(range(1, 13))


def test_build_is_deterministic_and_does_not_mutate_inputs():
    cands = pd.DataFrame([cand("B"), cand("A")])
    bars = panel({"A": ("2022-01-03", LIQUID), "B": ("2022-01-03", LIQUID)})
    before = cands.copy(deep=True), bars.copy(deep=True)
    first = ar.build_etf_universe(cands, bars, as_of=AS_OF, size=1)
    pd.testing.assert_frame_equal(first, ar.build_etf_universe(cands, bars, as_of=AS_OF, size=1))
    pd.testing.assert_frame_equal(cands, before[0])
    pd.testing.assert_frame_equal(bars, before[1])
    assert row(first, "A")["selected"] and row(first, "B")["exclusion_reason"] == "below_cutoff"


def test_aware_dates_and_bad_inputs_are_refused():
    bars = panel({"A": ("2022-01-03", LIQUID)})
    with pytest.raises(ValueError, match="naive session labels"):
        build([cand("A")], bars.assign(Date=bars["Date"].dt.tz_localize("UTC")))
    with pytest.raises(ValueError, match="duplicate candidate"):
        build([cand("A"), cand("A")], bars)
    with pytest.raises(ValueError, match="duplicate bar"):
        build([cand("A")], pd.concat([bars, bars.tail(1)]))
    with pytest.raises(ValueError, match="size"):
        build([cand("A")], bars, size=0)


def full_universe():
    cands, spec = [], {}
    for k, cls in enumerate(ar.ETF_ASSET_CLASSES):
        symbol = f"C{k:02d}"
        cands.append(cand(symbol, cls))
        spec[symbol] = ("2022-01-03", LIQUID)
    return build(cands, panel(spec))


def test_validator_accepts_a_full_universe_and_round_trips_csv(tmp_path):
    result = full_universe()
    ar.validate_universe(result)
    path = tmp_path / "etf_universe_v1.csv"
    result.to_csv(path, index=False)
    ar.validate_universe(pd.read_csv(path, keep_default_na=False))


@pytest.mark.parametrize("break_it, message", [
    (lambda f: pd.concat([f, f.tail(1)]), "duplicate symbol"),
    (lambda f: f.assign(listing_date=f["listing_date"].where(f.index != 0, "")), "listing date"),
    (lambda f: f.loc[f["asset_class"] != "currency"], "class not covered: currency"),
    (lambda f: f.assign(exclusion_reason=f["exclusion_reason"].where(f.index != 0, "illiquid")),
     "selected row with an exclusion reason"),
    (lambda f: f.assign(selected=f["selected"].where(f.index != 0, False)),
     "excluded row without a reason"),
    (lambda f: f.drop(columns="as_of"), "missing columns"),
    (lambda f: f.assign(asset_class=f["asset_class"].where(f.index != 0, "crypto")), "unknown asset class"),
    (lambda f: f.assign(as_of=f["as_of"].where(f.index != 0, "2026-10-02")), "one as_of"),
])
def test_validator_refuses_each_format_defect(break_it, message):
    with pytest.raises(ValueError, match=message):
        ar.validate_universe(break_it(full_universe()))


@pytest.mark.parametrize("field, value, message", [
    ("median_dollar_volume_252", 1e6, "below the dollar-volume floor"),
    ("median_dollar_volume_252", "", "below the dollar-volume floor"),
    ("first_bar", "2024-01-02", "short of the history rule"),
    ("first_bar", "", "short of the history rule"),
    ("rank", 7, "rank must run 1"),
])
def test_validator_refuses_a_selected_row_that_breaks_the_rule(field, value, message):
    forged = full_universe().astype({field: object})
    forged.at[0, field] = value
    with pytest.raises(ValueError, match=message):
        ar.validate_universe(forged)


def ranked_universe():
    cands = [cand(f"E{i:02d}") for i in range(14)] + [cand("BND1", "treasuries"), cand("BND2", "treasuries")]
    bars = panel({**{f"E{i:02d}": ("2022-01-03", LIQUID + i * 1e6) for i in range(14)},
                  "BND1": ("2022-01-03", LIQUID + 50e6), "BND2": ("2022-01-03", LIQUID + 0.5e6)})
    return build(cands, bars, size=12)


def swap(frame, a, b):
    """Exchange two rows' selection outcome (selected, rank, reason): a forged hand edit."""
    forged = frame.copy()
    ia, ib = forged.index[forged["symbol"].eq(a)][0], forged.index[forged["symbol"].eq(b)][0]
    cols = ["selected", "rank", "exclusion_reason"]
    forged.loc[[ia, ib], cols] = forged.loc[[ib, ia], cols].to_numpy()
    return forged


@pytest.mark.parametrize("a, b", [
    ("E03", "E02"),   # a lower-volume row selected over a higher one marked below_cutoff
    ("E03", "E01"),   # a class_cap row swapped into the selection
    ("E13", "E12"),   # ranks out of dollar-volume order
])
def test_validator_refuses_a_selection_that_is_not_the_highest_volume(a, b):
    result = ranked_universe()
    ar.validate_universe(result, require_all_classes=False)
    with pytest.raises(ValueError, match="highest-dollar-volume selection"):
        ar.validate_universe(swap(result, a, b), require_all_classes=False)


def test_validator_refuses_an_unknown_exclusion_reason():
    result = build([cand("A"), cand("B", etf=False)], panel({"A": ("2022-01-03", LIQUID)}))
    ar.validate_universe(result, require_all_classes=False)
    forged = result.assign(exclusion_reason=result["exclusion_reason"].replace("not_etf", "vibes"))
    with pytest.raises(ValueError, match="unknown exclusion reason"):
        ar.validate_universe(forged, require_all_classes=False)


def test_validator_refuses_more_than_the_class_cap():
    cands = [cand(f"E{i:02d}") for i in range(13)]
    result = build(cands, panel({c["symbol"]: ("2022-01-03", LIQUID) for c in cands}))
    forged = result.assign(selected=True, exclusion_reason="")
    with pytest.raises(ValueError, match="over the class cap: us_equity_broad"):
        ar.validate_universe(forged, require_all_classes=False)


# --- Rule 12 planted defects (spec 060 §6), each with its control inside the oracle ---

def oracle_history():
    test_three_year_history_boundary()


def oracle_future_window():
    test_dollar_volume_reads_only_sessions_at_or_before_as_of()


def oracle_leveraged():
    result = build([cand("LEV", name="ProShares Ultra QQQ"), cand("OK")],
                   panel({"LEV": ("2022-01-03", LIQUID), "OK": ("2022-01-03", LIQUID)}))
    assert row(result, "OK")["selected"]
    assert row(result, "LEV")["exclusion_reason"] == "leveraged_inverse_or_volatility"


def oracle_duplicates():
    ar.validate_universe(full_universe())
    try:
        ar.validate_universe(pd.concat([full_universe(), full_universe().tail(1)]))
    except ValueError as error:
        assert "duplicate symbol" in str(error), str(error)
    else:
        raise AssertionError("validator accepted a duplicate symbol")


@pytest.mark.parametrize("old, new, oracle", [
    # An ETF admitted before 3 years of history (off by one year).
    ("cutoff - pd.DateOffset(years=HISTORY_YEARS)", "cutoff - pd.DateOffset(years=HISTORY_YEARS - 1)",
     oracle_history),
    # Dollar volume computed with a window that includes sessions after as_of.
    ("frame[\"Date\"] <= cutoff", "frame[\"Date\"] <= frame[\"Date\"].max()", oracle_future_window),
    # A leveraged ETF passing the screen (name screen dropped).
    ("if _LEVERAGED_NAME.search(", "if False and _LEVERAGED_NAME.search(", oracle_leveraged),
    # The validator stops checking duplicate symbols.
    ("if frame[\"symbol\"].duplicated().any():", "if False:", oracle_duplicates),
], ids=["history", "future-window", "leveraged", "duplicates"])
def test_planted_defects_are_killed(old, new, oracle):
    killed(ar, old, new, oracle)
