"""EXAMPLE — NOT A RESULT. Synthetic candidate inventory; no strategy evaluation."""
import hashlib
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import context  # noqa: F401
import research_universe as ru
from data import trading_days
from mutation_support_019 import killed

DAY = date(2026, 10, 16)
DATES = pd.DatetimeIndex(trading_days(date(2026, 7, 1), DAY))
POLICY = dict(min_sessions=30, min_price=2., min_median_dollar_volume=1000., liquidity_window=20)


def reference(i="one", **changes):
    return dict(instrument_id=i, symbol=i.upper(), asset_type="common_stock", exchange="XNYS",
                listed_on="2020-01-02", delisted_on="", leveraged=False, inverse=False,
                observed_at="2026-06-30T12:00:00Z", effective_date="2020-01-02",
                source="synthetic-reference") | changes


def bars(*ids):
    return pd.concat([pd.DataFrame(dict(instrument_id=i, Date=DATES, Close=10., Volume=1000.))
                      for i in ids], ignore_index=True)


def screen(refs=None, prices=None, **kwargs):
    return ru.build_candidates(pd.DataFrame(refs or [reference()]),
                               bars("one") if prices is None else prices,
                               as_of=DAY, price_basis="raw", **(POLICY | kwargs))


def test_common_stocks_and_etfs_have_no_size_or_symbol_count_cutoff():
    refs = [reference(str(i), asset_type="etf" if i % 2 else "common_stock") for i in range(125)]
    result = screen(refs, bars(*(str(i) for i in range(125))))
    assert len(result) == 125 and result["candidate"].all()
    assert set(result.asset_type) == {"common_stock", "etf"}


@pytest.mark.parametrize("mic", ["XNAS", "XNGS", "XNCM", "XNMS"])
def test_nasdaq_operating_and_segment_mics_are_eligible(mic):
    assert screen([reference(exchange=mic)]).iloc[0].candidate


@pytest.mark.parametrize("mic", ["XNGS", "XNCM", "XNMS"])
def test_nasdaq_segment_mapping_has_semantic_red_controls(mic):
    killed(ru, '"' + mic + '"', '"ZZZZ"', lambda: test_nasdaq_operating_and_segment_mics_are_eligible(mic))


@pytest.mark.parametrize("change,reason", [
    ({"exchange": "OTC"}, "venue_not_permitted"),
    ({"exchange": "XLON"}, "venue_not_permitted"),
    ({"exchange": "XNDQ"}, "venue_not_permitted"),
    ({"asset_type": "warrant"}, "security_type_not_permitted"),
    ({"leveraged": True}, "leveraged_or_inverse_or_unknown"),
    ({"inverse": True}, "leveraged_or_inverse_or_unknown"),
    ({"inverse": None}, "leveraged_or_inverse_or_unknown"),
    ({"listed_on": "2026-10-19"}, "not_listed"),
    ({"delisted_on": str(DAY)}, "delisted"),
])
def test_exclusion_is_explicit(change, reason):
    result = screen([reference(**change)])
    assert not result.iloc[0].candidate and reason in result.iloc[0].reasons.split(";")


def test_reference_changes_after_decision_and_future_bars_do_not_change_inventory():
    base = screen()
    future = bars("one").tail(1).assign(Date=pd.Timestamp("2026-10-19"), Close=1e20, Volume=-1)
    late = reference(symbol="CHANGED", observed_at="2026-10-16T20:00:01Z")
    future_effect = reference(symbol="CHANGED", effective_date="2026-10-19")
    pd.testing.assert_frame_equal(base, screen([reference(), late, future_effect],
                                              pd.concat([bars("one"), future])))
    unseen = reference("new", observed_at="2026-10-16T20:00:01Z")
    assert screen([reference(), unseen]).instrument_id.tolist() == ["one"]


def test_future_reference_contents_cannot_change_the_as_of_result():
    late = reference(instrument_id=None, symbol="", source="", exchange=None,
                     listed_on="malformed", observed_at="2026-10-16T20:00:01Z")
    future = late | {"observed_at": "2026-06-30T12:00:00Z", "effective_date": "2026-10-19"}
    pd.testing.assert_frame_equal(screen(), screen([reference(), late, future]))
    assert screen([late, future]).empty


@pytest.mark.parametrize("change", [{"symbol": None}, {"source": ""}, {"instrument_id": 1},
                                    {"observed_at": "2026-10-16"}, {"effective_date": "malformed"}])
def test_visible_reference_schema_is_still_enforced(change):
    with pytest.raises(ValueError):
        screen([reference(**change)])


def test_visible_content_guard_has_a_semantic_red_control():
    def oracle():
        try: screen([reference(source="")])
        except ValueError: return
        raise AssertionError("visible reference without source accepted")
    killed(ru, 'if not ref[field].map(lambda value: isinstance(value, str) and bool(value.strip())).all():', 'if False:', oracle)


def test_observation_cutoff_and_delisting_boundaries():
    before = reference(delisted_on="2026-10-19", observed_at="2026-10-16T20:00:00Z", effective_date=str(DAY))
    assert screen([before]).iloc[0].candidate
    assert not screen([reference(observed_at="2026-10-16T20:00:01Z")]).shape[0]


def test_new_york_decision_cutoff_tracks_the_dst_boundary():
    day = date(2026, 11, 2)  # first session after US DST ends
    dates = pd.DatetimeIndex(trading_days(date(2026, 7, 1), day))
    prices = pd.DataFrame(dict(instrument_id="one", Date=dates, Close=10., Volume=1000.))
    for stamp, count in (("2026-11-02T21:00:00Z", 1), ("2026-11-02T21:00:01Z", 0)):
        result = ru.build_candidates(pd.DataFrame([reference(observed_at=stamp)]), prices,
                                     as_of=day, price_basis="raw", **POLICY)
        assert len(result) == count


def test_identity_join_never_inherits_another_instruments_history():
    result = screen([reference("new", symbol="ONE", listed_on="2026-10-15")], bars("one"))
    assert not result.iloc[0].candidate
    assert "insufficient_history" in result.iloc[0].reasons
    result = screen([reference("one", listed_on="2026-10-15")])
    assert "insufficient_history" in result.iloc[0].reasons


@pytest.mark.parametrize("edit,reason", [
    (lambda f: f.iloc[:-1], "stale_bar"),
    (lambda f: f.drop(index=len(f) - 5), "missing_sessions"),
    (lambda f: f.assign(Volume=-1), "invalid_bars"),
    (lambda f: f.assign(Close=float("nan")), "invalid_bars"),
    (lambda f: f.assign(Close=1e308, Volume=1e308), "invalid_bars"),
    (lambda f: f.assign(Close=1e154, Volume=1e154), "invalid_bars"),
    (lambda f: f.assign(Close=1.), "price_below_floor"),
    (lambda f: f.assign(Volume=1.), "illiquid"),
])
def test_missing_or_bad_data_is_excluded(edit, reason):
    result = screen(prices=edit(bars("one")))
    assert not result.iloc[0].candidate and reason in result.iloc[0].reasons.split(";")


def test_invalid_bar_cannot_hide_outside_the_liquidity_tail():
    for position in (-25, -31, -40):
        for field, value in [("Volume", -1.), ("Close", -1.), ("Close", 0.), ("Close", float("nan"))]:
            bad = bars("one")
            bad.loc[bad.index[position], field] = value
            result = screen(prices=bad).iloc[0]
            assert not result.candidate and "invalid_bars" in result.reasons.split(";")
        test_missing_or_bad_data_is_excluded(lambda f: f.drop(index=f.index[position]), "missing_sessions")


def test_holiday_gap_is_not_a_missing_bar():
    # The exchange calendar excludes Labor Day, rather than expecting a weekday bar.
    assert pd.Timestamp("2026-09-07") not in DATES
    assert screen().iloc[0].candidate


def test_raw_basis_aware_dates_and_duplicate_bars_are_refused():
    with pytest.raises(ValueError, match="raw"):
        ru.build_candidates(pd.DataFrame([reference()]), bars("one"), as_of=DAY,
                            price_basis="adjusted", **POLICY)
    with pytest.raises(ValueError, match="naive"):
        screen(prices=bars("one").assign(Date=DATES.tz_localize("UTC")))
    with pytest.raises(ValueError, match="duplicate"):
        screen(prices=pd.concat([bars("one"), bars("one").tail(1)]))


def test_ambiguous_active_symbols_are_not_candidates():
    result = screen([reference("one"), reference("two", symbol=" one ")], bars("one", "two"))
    assert not result.candidate.any() and result.reasons.str.contains("ambiguous_symbol").all()


def test_reused_symbol_with_delisted_predecessor_has_independent_history():
    result = screen([reference("old", symbol="ONE", delisted_on="2025-01-02"), reference(listed_on="2025-01-03")],
                    pd.concat([bars("old").assign(Close=1.), bars("one")]))
    assert result.loc[result.instrument_id.eq("one"), "candidate"].item()
    assert "delisted" in result.loc[result.instrument_id.eq("old"), "reasons"].item().split(";")


def test_mature_successor_never_uses_predecessor_bars():
    result = screen([reference("old", symbol="ONE", delisted_on="2025-01-02"),
                     reference(listed_on="2025-01-03")], bars("old"))
    assert not result.loc[result.instrument_id.eq("one"), "candidate"].item()
    assert "insufficient_history" in result.loc[result.instrument_id.eq("one"), "reasons"].item()


@pytest.mark.parametrize("change", [{"min_price": float("nan")}, {"min_sessions": 0},
                                    {"liquidity_window": 31}, {"min_median_dollar_volume": -1}])
def test_invalid_policy_is_refused(change):
    with pytest.raises(ValueError):
        screen(**change)


def cli_args(tmp_path):
    refs, prices = tmp_path / "reference.csv", tmp_path / "bars.csv"
    pd.DataFrame([reference()]).to_csv(refs, index=False)
    bars("one").to_csv(prices, index=False)
    out = tmp_path / "out"
    args = ["--reference", str(refs), "--bars", str(prices), "--out", str(out),
            "--as-of", str(DAY), "--price-basis", "raw", "--min-sessions", "30",
            "--min-price", "2", "--min-dollar-volume", "1000"]
    return args


def test_cli_writes_private_hash_bound_inventory_and_refuses_overwrite(tmp_path, capsys):
    args = cli_args(tmp_path)
    refs, prices, out = (tmp_path / name for name in ("reference.csv", "bars.csv", "out"))
    assert ru.main(args) == 0
    receipt = json.loads((out / "receipt.json").read_text())
    assert receipt["label"] == ru.LABEL
    assert receipt["reference_sha256"] == hashlib.sha256(refs.read_bytes()).hexdigest()
    assert receipt["bars_sha256"] == hashlib.sha256(prices.read_bytes()).hexdigest()
    assert receipt["candidates_sha256"] == hashlib.sha256((out / "candidates.csv").read_bytes()).hexdigest()
    assert receipt["candidate_count"] == 1 and receipt["limitations"]
    shown = json.loads(capsys.readouterr().out)
    assert shown["receipt"] == str(out / "receipt.json")
    assert {k: shown[k] for k in receipt} == receipt
    saved = {p.name: p.read_bytes() for p in out.iterdir()}
    assert ru.main(args) != 0
    assert {p.name: p.read_bytes() for p in out.iterdir()} == saved
    assert "refused" in capsys.readouterr().err.lower()
    broken_out = tmp_path / "broken"
    bars("one").assign(Date="not-a-date").to_csv(prices, index=False)
    args[args.index("--out") + 1] = str(broken_out)
    assert ru.main(args) != 0 and not broken_out.exists()


@pytest.mark.parametrize("failure", ["csv", "receipt", "rename"])
def test_cli_failed_publication_leaves_no_inventory(tmp_path, monkeypatch, failure):
    args = cli_args(tmp_path)
    before = {p: p.read_bytes() if p.is_file() else None for p in tmp_path.rglob("*")}
    method = {"csv": "write_bytes", "receipt": "write_text", "rename": "rename"}[failure]
    original = getattr(Path, method)
    def fail(path, *a, **kw):
        if (failure == "csv" and path.name == "candidates.csv") or (
                failure == "receipt" and path.name == "receipt.json") or failure == "rename":
            raise OSError("synthetic publication failure")
        return original(path, *a, **kw)
    monkeypatch.setattr(Path, method, fail)
    assert ru.main(args) == 2
    assert {p: p.read_bytes() if p.is_file() else None for p in tmp_path.rglob("*")} == before


@pytest.mark.parametrize("old,new,oracle", [
    ('observed <= cutoff', 'observed <= cutoff + pd.Timedelta(days=1)',
     test_reference_changes_after_decision_and_future_bars_do_not_change_inventory),
    ('panel.Date <= pd.Timestamp(as_of)', 'panel.Date <= panel.Date.max()',
     test_reference_changes_after_decision_and_future_bars_do_not_change_inventory),
    ('if item.exchange not in US_EXCHANGES:', 'if False:',
     lambda: test_exclusion_is_explicit({"exchange": "OTC"}, "venue_not_permitted")),
    ('if not (_false(item.leveraged) and _false(item.inverse)):', 'if False:',
     lambda: test_exclusion_is_explicit({"inverse": True}, "leveraged_or_inverse_or_unknown")),
    ('if median is not None and not np.isfinite(median):', 'if False:',
     lambda: test_missing_or_bad_data_is_excluded(lambda f: f.assign(Close=1e154, Volume=1e154), "invalid_bars")),
    ('ref.effective_date <= pd.Timestamp(as_of)', 'ref.effective_date <= ref.effective_date.max()',
     test_reference_changes_after_decision_and_future_bars_do_not_change_inventory),
    ('if item.asset_type not in {"common_stock", "etf"}:', 'if False:',
     lambda: test_exclusion_is_explicit({"asset_type": "warrant"}, "security_type_not_permitted")),
    ('if listed.date() > as_of:', 'if False:',
     lambda: test_exclusion_is_explicit({"listed_on": "2026-10-19"}, "not_listed")),
    ('if _labels(pd.Series([item.delisted_on])).iloc[0].date() <= as_of:', 'if False:',
     lambda: test_exclusion_is_explicit({"delisted_on": str(DAY)}, "delisted")),
    ('if last_label != last:', 'if False:',
     lambda: test_missing_or_bad_data_is_excluded(lambda f: f.iloc[:-1], "stale_bar")),
    ('if history.Date.dt.date.tolist() != expected:', 'if False:',
     lambda: test_missing_or_bad_data_is_excluded(lambda f: f.drop(index=len(f) - 5), "missing_sessions")),
    ('elif values.Close.iloc[-1] < policy.min_price:', 'elif False:',
     lambda: test_missing_or_bad_data_is_excluded(lambda f: f.assign(Close=1.), "price_below_floor")),
    ('if median is None or median < policy.min_median_dollar_volume:', 'if False:',
     lambda: test_missing_or_bad_data_is_excluded(lambda f: f.assign(Volume=1.), "illiquid")),
    ('symbols.duplicated(keep=False)', 'symbols.duplicated(keep=False) & False',
     test_ambiguous_active_symbols_are_not_candidates),
    ('groups.get(item.instrument_id, panel.iloc[0:0])',
     'groups.get(ref.drop_duplicates("symbol").set_index("symbol").instrument_id[item.symbol], panel.iloc[0:0])',
     test_reused_symbol_with_delisted_predecessor_has_independent_history),
    ('groups.get(item.instrument_id, panel.iloc[0:0])',
     'groups.get(ref.drop_duplicates("symbol").set_index("symbol").instrument_id[item.symbol], panel.iloc[0:0])',
     test_mature_successor_never_uses_predecessor_bars),
    ('if len(history) < policy.min_sessions:', 'if False:',
     test_identity_join_never_inherits_another_instruments_history),
    ('valid = bool(len(values) and np.isfinite(values.to_numpy()).all()\n                     and (values.Close > 0).all() and (values.Volume >= 0).all())',
     'valid = bool(len(values))', test_invalid_bar_cannot_hide_outside_the_liquidity_tail),
    ('if not valid:', 'if False:', test_invalid_bar_cannot_hide_outside_the_liquidity_tail),
    ('history.loc[history.Date >= listed].sort_values("Date")',
     'history.loc[history.Date >= listed].sort_values("Date").tail(policy.min_sessions)', test_invalid_bar_cannot_hide_outside_the_liquidity_tail),
])
def test_planted_defects(old, new, oracle):
    killed(ru, old, new, oracle)
