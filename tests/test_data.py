"""Tests for the data layer, with timestamp handling as the headline concern.

Rule 5 requires the off-by-one, boundary, and gap cases on anything that
indexes, sorts, or aligns on a timestamp. This module had zero tests before
this file; the three cases are marked in the test names below.

No network. The download path is exercised through `download_market_data`'s
`downloader` parameter, and every cache test redirects `data.CACHE_DIR` into a
temporary directory so the real cache is never read or written.
"""

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from context import SCRIPTS_DIR  # noqa: F401  (import for the sys.path effect)
import data
from data import (
    download_market_data,
    find_missing_bars,
    is_market_holiday,
    market_holidays,
    trading_days,
)


def make_yfinance_frame(tickers: list[str], dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Build a frame shaped the way yfinance returns `group_by="ticker"`.

    A MultiIndex on the columns, ticker at the outer level, with the bar date
    on the index. Prices differ per ticker so a test can tell whose row it is
    looking at after the sort.
    """
    blocks = {}
    for offset, ticker in enumerate(tickers):
        base = 100 * (offset + 1)
        for field_offset, field in enumerate(data.OHLCV_COLUMNS):
            blocks[(ticker, field)] = [
                base + field_offset + row for row in range(len(dates))
            ]
    frame = pd.DataFrame(blocks, index=dates)
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    frame.index.name = "Date"
    return frame


def make_tidy_frame(tickers: list[str], dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Build a tidy OHLCV frame of the shape download_market_data returns."""
    rows = []
    for offset, ticker in enumerate(tickers):
        base = 100 * (offset + 1)
        for row, day in enumerate(dates):
            rows.append(
                {
                    "Date": day,
                    "Ticker": ticker,
                    **{
                        field: base + field_offset + row
                        for field_offset, field in enumerate(data.OHLCV_COLUMNS)
                    },
                }
            )
    return pd.DataFrame(rows)


class CacheDirTestCase(unittest.TestCase):
    """Point data.CACHE_DIR at a temp directory for the duration of a test."""

    def setUp(self):
        self._tempdir = TemporaryDirectory()
        self._original_cache_dir = data.CACHE_DIR
        data.CACHE_DIR = Path(self._tempdir.name)
        self.addCleanup(self._restore)

    def _restore(self):
        data.CACHE_DIR = self._original_cache_dir
        self._tempdir.cleanup()

    def downloader_returning(self, tickers, dates):
        """A stand-in downloader that serves one fixed frame."""

        def downloader(_requested, **_kwargs):
            return make_yfinance_frame(tickers, dates)

        return downloader

    def forbidden_downloader(self, *_args, **_kwargs):
        """A downloader whose only job is to fail the test if it is called."""
        self.fail("Network path was taken when the cache should have served.")


# ---------------------------------------------------------------------------
# Trading calendar  (Rule 5: off-by-one — every assertion here pins an exact
# date, because a calendar that is one day out excuses the wrong bar)
# ---------------------------------------------------------------------------


class TradingCalendarTests(unittest.TestCase):
    def test_fixed_and_floating_holidays_land_on_the_right_day(self):
        # Real NYSE closures. A floating holiday computed with an off-by-one
        # in the nth-weekday arithmetic lands a week early or late, which no
        # count-based assertion would catch.
        for day, name in [
            (date(2024, 1, 1), "New Year's Day"),
            (date(2024, 1, 15), "MLK Day (3rd Monday)"),
            (date(2024, 2, 19), "Washington's Birthday (3rd Monday)"),
            (date(2024, 3, 29), "Good Friday"),
            (date(2024, 5, 27), "Memorial Day (last Monday)"),
            (date(2024, 6, 19), "Juneteenth"),
            (date(2024, 7, 4), "Independence Day"),
            (date(2024, 9, 2), "Labor Day (1st Monday)"),
            (date(2024, 11, 28), "Thanksgiving (4th Thursday)"),
            (date(2024, 12, 25), "Christmas"),
        ]:
            with self.subTest(holiday=name):
                self.assertTrue(is_market_holiday(day))

    def test_good_friday_is_a_holiday_across_several_years(self):
        # Good Friday is the holiday pandas' USFederalHolidayCalendar omits,
        # and the reason this calendar is hand-rolled. It moves every year, so
        # one year passing proves little.
        for day in [
            date(2021, 4, 2),
            date(2022, 4, 15),
            date(2023, 4, 7),
            date(2024, 3, 29),
            date(2025, 4, 18),
            date(2026, 4, 3),
        ]:
            with self.subTest(good_friday=day):
                self.assertTrue(is_market_holiday(day))

    def test_federal_holidays_the_nyse_trades_through_are_not_holidays(self):
        # The other half of the reason for a hand-rolled calendar. If these
        # were treated as closures, a genuinely missing bar on one of them
        # would be silently excused — a false negative, the failure direction
        # that actually hurts.
        for day, name in [
            (date(2024, 10, 14), "Columbus Day"),
            (date(2024, 11, 11), "Veterans Day"),
            (date(2024, 11, 29), "day after Thanksgiving (half day, open)"),
        ]:
            with self.subTest(open_day=name):
                self.assertFalse(is_market_holiday(day))

    def test_saturday_holiday_is_observed_on_the_preceding_friday(self):
        # July 4th 2020 fell on a Saturday; the NYSE closed Friday the 3rd.
        self.assertTrue(is_market_holiday(date(2020, 7, 3)))
        self.assertFalse(is_market_holiday(date(2020, 7, 4)))

    def test_sunday_holiday_is_observed_on_the_following_monday(self):
        # Christmas 2022 fell on a Sunday; the NYSE closed Monday the 26th.
        self.assertTrue(is_market_holiday(date(2022, 12, 26)))
        self.assertFalse(is_market_holiday(date(2022, 12, 25)))

    def test_new_years_on_a_saturday_does_not_close_the_preceding_friday(self):
        # The documented exception to the observation rule: January 1st 2022
        # was a Saturday and the NYSE traded normally on Friday December 31st,
        # 2021. Applying the generic Saturday rule here would wrongly excuse a
        # missing bar on a real session.
        self.assertFalse(is_market_holiday(date(2021, 12, 31)))
        self.assertTrue(is_market_holiday(date(2023, 1, 2)))  # Sunday case still holds

    def test_juneteenth_only_counts_from_2022(self):
        # It became a market holiday in 2022. Backdating it would excuse a
        # missing June 19th bar in every earlier year.
        self.assertFalse(is_market_holiday(date(2021, 6, 18)))
        self.assertFalse(is_market_holiday(date(2019, 6, 19)))
        self.assertTrue(is_market_holiday(date(2022, 6, 20)))  # 19th was a Sunday
        self.assertTrue(is_market_holiday(date(2023, 6, 19)))

    def test_weekends_are_not_holidays(self):
        # is_market_holiday answers "is this a closure", not "was the market
        # open". Conflating them would make trading_days double-count.
        self.assertFalse(is_market_holiday(date(2024, 3, 30)))  # Saturday
        self.assertFalse(is_market_holiday(date(2024, 3, 31)))  # Sunday

    def test_a_full_year_has_the_expected_number_of_sessions(self):
        # 2024 had 252 NYSE sessions. This is the aggregate check that would
        # fail if the calendar gained or lost a holiday anywhere in the year.
        sessions = trading_days(date(2024, 1, 1), date(2024, 12, 31))
        self.assertEqual(len(sessions), 252)
        self.assertEqual(len(market_holidays(2024)), 10)

    def test_session_counts_match_the_published_nyse_totals(self):
        # The aggregate cross-check on the whole calendar. These are the
        # published NYSE session counts; a single holiday wrong in either
        # direction moves one of these numbers by one. 2020 is high because no
        # holiday fell on a weekend, and 2025 is low because of the Carter
        # day of mourning.
        for year, expected in [
            (2018, 251),
            (2019, 252),
            (2020, 253),
            (2021, 252),
            (2022, 251),
            (2023, 250),
            (2024, 252),
            (2025, 250),
        ]:
            with self.subTest(year=year):
                sessions = trading_days(date(year, 1, 1), date(year, 12, 31))
                self.assertEqual(len(sessions), expected)

    def test_trading_days_is_inclusive_at_both_ends(self):
        # Rule 5, boundary case: an exclusive end would silently drop the last
        # session of every window, and a range that starts on a session must
        # include it.
        sessions = trading_days(date(2024, 3, 4), date(2024, 3, 8))
        self.assertEqual(sessions[0], date(2024, 3, 4))
        self.assertEqual(sessions[-1], date(2024, 3, 8))
        self.assertEqual(len(sessions), 5)

    def test_trading_days_on_a_single_closed_day_is_empty(self):
        self.assertEqual(trading_days(date(2024, 3, 29), date(2024, 3, 29)), [])
        self.assertEqual(trading_days(date(2024, 3, 4), date(2024, 3, 4)), [date(2024, 3, 4)])

    def test_reversed_range_is_empty_rather_than_raising(self):
        self.assertEqual(trading_days(date(2024, 3, 8), date(2024, 3, 4)), [])

    def test_range_spanning_a_year_boundary_uses_both_years_holidays(self):
        # A year-cache bug shows up here: December's holidays come from one
        # year's set and January's from the next.
        sessions = trading_days(date(2023, 12, 22), date(2024, 1, 3))
        self.assertNotIn(date(2023, 12, 25), sessions)
        self.assertNotIn(date(2024, 1, 1), sessions)
        self.assertIn(date(2024, 1, 2), sessions)

    def test_ad_hoc_closures_are_not_reported_as_sessions(self):
        # Hurricane Sandy shut the exchange for two weekdays. Nothing computes
        # these; they are listed, and the list has to actually be consulted.
        sessions = trading_days(date(2012, 10, 26), date(2012, 10, 31))
        self.assertNotIn(date(2012, 10, 29), sessions)
        self.assertNotIn(date(2012, 10, 30), sessions)
        self.assertIn(date(2012, 10, 31), sessions)


# ---------------------------------------------------------------------------
# Gap detection  (Rule 5: gap case)
# ---------------------------------------------------------------------------


class FindMissingBarsTests(unittest.TestCase):
    def test_a_complete_run_of_sessions_reports_no_gaps(self):
        dates = pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 15)))
        gaps = find_missing_bars(make_tidy_frame(["AAPL"], dates))
        self.assertTrue(gaps.empty)

    def test_weekends_are_not_reported_as_gaps(self):
        # The frame below skips Saturday and Sunday, as real data does. If
        # weekends counted, every week would report two false gaps and the
        # report would be worthless.
        dates = pd.to_datetime(["2024-03-08", "2024-03-11"])  # Friday, Monday
        gaps = find_missing_bars(make_tidy_frame(["AAPL"], dates))
        self.assertTrue(gaps.empty)

    def test_a_holiday_is_not_reported_as_a_gap(self):
        # Good Friday 2024 (March 29). This is FR-009's literal requirement:
        # a market holiday explains the missing bar, so it must not surface.
        dates = pd.to_datetime(["2024-03-28", "2024-04-01"])
        gaps = find_missing_bars(make_tidy_frame(["AAPL"], dates))
        self.assertTrue(gaps.empty)

    def test_a_missing_midweek_session_is_reported_as_exactly_that_day(self):
        # Rule 5, off-by-one: the report must name the day that is missing,
        # not the one before or after it. A report shifted by one is worse
        # than no report — it sends the reader to a bar that is present.
        dates = pd.to_datetime(["2024-03-05", "2024-03-06", "2024-03-08"])
        gaps = find_missing_bars(make_tidy_frame(["AAPL"], dates))

        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps.loc[0, "Date"], pd.Timestamp("2024-03-07"))
        self.assertEqual(gaps.loc[0, "Ticker"], "AAPL")

    def test_a_multi_day_gap_reports_every_missing_session(self):
        dates = pd.to_datetime(["2024-03-04", "2024-03-08"])
        gaps = find_missing_bars(make_tidy_frame(["AAPL"], dates))

        self.assertEqual(
            list(gaps["Date"]),
            [pd.Timestamp("2024-03-05"), pd.Timestamp("2024-03-06"), pd.Timestamp("2024-03-07")],
        )

    def test_gaps_are_bounded_by_each_tickers_own_history(self):
        # The IPO / delisting case from the spec's Edge Cases. AAPL spans the
        # whole window and MSFT starts late; bounding by the frame's range
        # instead of each ticker's would invent a gap for every session before
        # MSFT's first bar.
        aapl = make_tidy_frame(["AAPL"], pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 15))))
        msft = make_tidy_frame(["MSFT"], pd.to_datetime(trading_days(date(2024, 3, 11), date(2024, 3, 15))))
        gaps = find_missing_bars(pd.concat([aapl, msft], ignore_index=True))

        self.assertTrue(gaps.empty)

    def test_a_gap_at_the_very_first_or_last_session_is_outside_the_window(self):
        # Rule 5, boundary: the window is the ticker's observed first and last
        # bar, so an absence at the edge is indistinguishable from the history
        # simply starting later. Asserting it rather than leaving it implied.
        dates = pd.to_datetime(["2024-03-05", "2024-03-06", "2024-03-07"])
        gaps = find_missing_bars(make_tidy_frame(["AAPL"], dates))

        self.assertTrue(gaps.empty)
        self.assertNotIn(pd.Timestamp("2024-03-04"), list(gaps.get("Date", [])))

    def test_gaps_are_reported_per_ticker(self):
        aapl = make_tidy_frame(["AAPL"], pd.to_datetime(["2024-03-05", "2024-03-07"]))
        msft = make_tidy_frame(["MSFT"], pd.to_datetime(trading_days(date(2024, 3, 5), date(2024, 3, 7))))
        gaps = find_missing_bars(pd.concat([aapl, msft], ignore_index=True))

        self.assertEqual(list(gaps["Ticker"]), ["AAPL"])
        self.assertEqual(list(gaps["Date"]), [pd.Timestamp("2024-03-06")])

    def test_report_is_sorted_by_ticker_then_date_with_a_clean_index(self):
        aapl = make_tidy_frame(["AAPL"], pd.to_datetime(["2024-03-04", "2024-03-08"]))
        msft = make_tidy_frame(["MSFT"], pd.to_datetime(["2024-03-04", "2024-03-06"]))
        gaps = find_missing_bars(pd.concat([msft, aapl], ignore_index=True))

        self.assertEqual(list(gaps["Ticker"]), ["AAPL", "AAPL", "AAPL", "MSFT"])
        self.assertEqual(list(gaps.index), [0, 1, 2, 3])

    def test_single_row_frame_reports_no_gaps(self):
        gaps = find_missing_bars(make_tidy_frame(["AAPL"], pd.to_datetime(["2024-03-05"])))
        self.assertTrue(gaps.empty)

    def test_empty_frame_returns_an_empty_report_rather_than_raising(self):
        gaps = find_missing_bars(make_tidy_frame([], pd.to_datetime([])))
        self.assertTrue(gaps.empty)
        self.assertEqual(list(gaps.columns), ["Ticker", "Date"])

    def test_the_report_does_not_modify_the_frame_it_inspects(self):
        # FR-009 is inspection only. Nothing is filled, and in particular no
        # row is invented for the missing session — a fill would have to be
        # checked against Rule 1 before it could exist at all.
        prices = make_tidy_frame(["AAPL"], pd.to_datetime(["2024-03-05", "2024-03-07"]))
        before = prices.copy()

        gaps = find_missing_bars(prices)

        self.assertFalse(gaps.empty)
        pd.testing.assert_frame_equal(prices, before)


# ---------------------------------------------------------------------------
# Tidy contract and the timestamp round-trip  (Rule 5: off-by-one + boundary)
# ---------------------------------------------------------------------------


class TidyContractTests(CacheDirTestCase):
    def test_download_returns_the_tidy_contract_shape(self):
        dates = pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 8)))
        prices = download_market_data(
            ["AAPL", "MSFT"], "1y", downloader=self.downloader_returning(["AAPL", "MSFT"], dates)
        )

        self.assertEqual(list(prices.columns), data.TIDY_COLUMNS)
        self.assertEqual(list(prices.index), list(range(len(prices))))
        self.assertEqual(len(prices), 10)
        self.assertFalse(prices.isnull().to_numpy().any())

    def test_rows_are_sorted_by_ticker_then_date(self):
        dates = pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 8)))
        prices = download_market_data(
            ["MSFT", "AAPL"], "1y", downloader=self.downloader_returning(["MSFT", "AAPL"], dates)
        )

        self.assertEqual(prices["Ticker"].tolist(), ["AAPL"] * 5 + ["MSFT"] * 5)
        for _, group in prices.groupby("Ticker"):
            self.assertTrue(group["Date"].is_monotonic_increasing)

    def test_first_and_last_rows_survive_the_sort(self):
        # Rule 5, boundary: a sort that drops or duplicates an edge row is the
        # kind of thing a length check alone misses.
        dates = pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 8)))
        prices = download_market_data(
            ["AAPL"], "1y", downloader=self.downloader_returning(["AAPL"], dates)
        )

        self.assertEqual(prices.iloc[0]["Date"], pd.Timestamp("2024-03-04"))
        self.assertEqual(prices.iloc[-1]["Date"], pd.Timestamp("2024-03-08"))

    def test_dates_are_timezone_naive_and_midnight_normalized(self):
        # The module's stated convention. A Date carrying a zone or a
        # non-midnight time makes downstream joins compare a naive to an aware
        # timestamp, which either raises or shifts a bar across a day.
        dates = pd.to_datetime(["2024-03-04", "2024-03-05"]).tz_localize("America/New_York")
        prices = download_market_data(
            ["AAPL"], "1y", downloader=self.downloader_returning(["AAPL"], dates)
        )

        self.assertIsNone(prices["Date"].dt.tz)
        self.assertEqual(list(prices["Date"]), [pd.Timestamp("2024-03-04"), pd.Timestamp("2024-03-05")])

    def test_cache_round_trip_does_not_shift_any_date(self):
        # Rule 5, off-by-one, and the most load-bearing test in this file. The
        # returned frame comes from two different code paths — a fresh
        # download and a CSV read-back — and a caller must not be able to tell
        # which. A one-day drift here would move every bar in the system.
        dates = pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 15)))
        downloaded = download_market_data(
            ["AAPL", "MSFT"], "1y", downloader=self.downloader_returning(["AAPL", "MSFT"], dates)
        )
        from_cache = download_market_data(
            ["AAPL", "MSFT"], "1y", downloader=self.forbidden_downloader
        )

        pd.testing.assert_frame_equal(downloaded, from_cache)

        # The dtype is pinned separately because it is the part that actually
        # broke: pandas infers datetime resolution from the source, so these
        # two paths produced datetime64[s] and datetime64[us] respectively.
        # Same instants, different dtype — assert_frame_equal catches it here,
        # but a downstream join would only fail later and less legibly.
        self.assertEqual(downloaded["Date"].dtype, "datetime64[ns]")
        self.assertEqual(from_cache["Date"].dtype, "datetime64[ns]")

    def test_the_callers_ticker_list_is_not_mutated(self):
        dates = pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 8)))
        tickers = ["MSFT", "AAPL"]
        download_market_data(
            tickers, "1y", downloader=self.downloader_returning(["MSFT", "AAPL"], dates)
        )

        self.assertEqual(tickers, ["MSFT", "AAPL"])


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------


class CacheBehaviorTests(CacheDirTestCase):
    def setUp(self):
        super().setUp()
        self.dates = pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 8)))

    def test_a_warm_cache_makes_no_network_call(self):
        # SC-002. forbidden_downloader fails the test if it is reached, which
        # is a stronger assertion than checking a call counter after the fact.
        download_market_data(
            ["AAPL"], "1y", downloader=self.downloader_returning(["AAPL"], self.dates)
        )
        prices = download_market_data(["AAPL"], "1y", downloader=self.forbidden_downloader)

        self.assertEqual(len(prices), 5)

    def test_ticker_order_hits_the_same_cache_entry(self):
        # The cache key is built from the sorted set, so these are one request
        # and not two. Before this, the second call re-downloaded and wrote a
        # second file that could never serve the first.
        download_market_data(
            ["AAPL", "MSFT"], "1y", downloader=self.downloader_returning(["AAPL", "MSFT"], self.dates)
        )
        prices = download_market_data(["MSFT", "AAPL"], "1y", downloader=self.forbidden_downloader)

        self.assertEqual(sorted(prices["Ticker"].unique()), ["AAPL", "MSFT"])
        self.assertEqual(len(list(Path(data.CACHE_DIR).glob("*.csv"))), 1)

    def test_a_cache_missing_a_requested_ticker_is_treated_as_a_miss(self):
        # FR-003. The cache file for ["AAPL"] cannot serve ["AAPL", "MSFT"];
        # serving it would hand back a silently short frame.
        cached = make_tidy_frame(["AAPL"], self.dates)
        cached.to_csv(Path(data.CACHE_DIR) / "AAPL-MSFT_1y.csv", index=False)

        prices = download_market_data(
            ["AAPL", "MSFT"], "1y", downloader=self.downloader_returning(["AAPL", "MSFT"], self.dates)
        )

        self.assertEqual(sorted(prices["Ticker"].unique()), ["AAPL", "MSFT"])

    def test_a_superset_cache_is_filtered_to_the_requested_tickers(self):
        # SC-001: N tickers requested, exactly N returned. A superset file is
        # valid to read but must not leak its extra symbols to the caller.
        cached = make_tidy_frame(["AAPL", "MSFT"], self.dates)
        cached.to_csv(Path(data.CACHE_DIR) / "AAPL_1y.csv", index=False)

        prices = download_market_data(["AAPL"], "1y", downloader=self.forbidden_downloader)

        self.assertEqual(list(prices["Ticker"].unique()), ["AAPL"])

    def test_force_refresh_bypasses_a_valid_cache(self):
        # FR-007. The second downloader serves a longer window, so a stale
        # cache read would be visible as the wrong row count.
        download_market_data(
            ["AAPL"], "1y", downloader=self.downloader_returning(["AAPL"], self.dates)
        )
        longer = pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 15)))
        prices = download_market_data(
            ["AAPL"], "1y", force_refresh=True, downloader=self.downloader_returning(["AAPL"], longer)
        )

        self.assertEqual(len(prices), 10)

    def test_a_download_writes_a_cache_file(self):
        download_market_data(
            ["AAPL"], "1y", downloader=self.downloader_returning(["AAPL"], self.dates)
        )
        self.assertTrue((Path(data.CACHE_DIR) / "AAPL_1y.csv").exists())

    def test_different_periods_are_different_cache_entries(self):
        download_market_data(
            ["AAPL"], "1y", downloader=self.downloader_returning(["AAPL"], self.dates)
        )
        download_market_data(
            ["AAPL"], "2y", downloader=self.downloader_returning(["AAPL"], self.dates)
        )

        self.assertTrue((Path(data.CACHE_DIR) / "AAPL_1y.csv").exists())
        self.assertTrue((Path(data.CACHE_DIR) / "AAPL_2y.csv").exists())


class AtomicWriteTests(CacheDirTestCase):
    def test_an_interrupted_write_leaves_the_previous_cache_intact(self):
        # FR-004 / SC-003. A half-written cache read as valid on the next run
        # is worse than no cache — it produces wrong data with no error. The
        # write is interrupted between the temp file and the rename, which is
        # exactly the window the atomic write exists to close.
        dates = pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 8)))
        good = download_market_data(
            ["AAPL"], "1y", downloader=self.downloader_returning(["AAPL"], dates)
        )
        path = Path(data.CACHE_DIR) / "AAPL_1y.csv"

        def interrupted_downloader(_requested, **_kwargs):
            # Simulate the crash: a temp file is left behind, and the rename
            # never happens.
            path.with_suffix(".csv.tmp").write_text("Date,Ticker,Open\n2024-03-0")
            raise KeyboardInterrupt("network dropped mid-write")

        with self.assertRaises(KeyboardInterrupt):
            download_market_data(
                ["AAPL"], "1y", force_refresh=True, downloader=interrupted_downloader
            )

        recovered = download_market_data(["AAPL"], "1y", downloader=self.forbidden_downloader)
        pd.testing.assert_frame_equal(recovered, good)

    def test_the_temp_file_is_not_mistaken_for_the_cache(self):
        # The temp path has to differ from the real one, or the "atomic" write
        # is writing straight over the file it is meant to protect.
        dates = pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 8)))
        download_market_data(
            ["AAPL"], "1y", downloader=self.downloader_returning(["AAPL"], dates)
        )

        self.assertFalse((Path(data.CACHE_DIR) / "AAPL_1y.csv.tmp").exists())


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class ErrorPathTests(CacheDirTestCase):
    def test_an_empty_ticker_list_raises(self):
        with self.assertRaises(ValueError):
            download_market_data([], "1y", downloader=self.forbidden_downloader)

    def test_an_empty_response_raises_rather_than_returning_a_bare_frame(self):
        # FR-006. Returning empty here would surface much later as a confusing
        # empty-slice bug in whichever script consumed it.
        def empty_downloader(_requested, **_kwargs):
            return pd.DataFrame()

        with self.assertRaises(RuntimeError):
            download_market_data(["AAPL"], "1y", downloader=empty_downloader)

    def test_a_silently_dropped_ticker_is_named_in_the_error(self):
        # FR-005. yfinance omits unknown symbols instead of raising, so the
        # default failure is a bare KeyError that does not say which symbol
        # was the problem.
        dates = pd.to_datetime(trading_days(date(2024, 3, 4), date(2024, 3, 8)))

        def partial_downloader(_requested, **_kwargs):
            return make_yfinance_frame(["AAPL"], dates)

        with self.assertRaises(RuntimeError) as caught:
            download_market_data(["AAPL", "NOTATICKER"], "1y", downloader=partial_downloader)

        self.assertIn("NOTATICKER", str(caught.exception))

    def test_a_failed_download_does_not_leave_a_cache_file_behind(self):
        def empty_downloader(_requested, **_kwargs):
            return pd.DataFrame()

        with self.assertRaises(RuntimeError):
            download_market_data(["AAPL"], "1y", downloader=empty_downloader)

        self.assertFalse((Path(data.CACHE_DIR) / "AAPL_1y.csv").exists())


if __name__ == "__main__":
    unittest.main()
