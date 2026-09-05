"""Tests for the gap report wired into the Phase 0 sanity check.

The reporting itself is `data.find_missing_bars`, covered in `test_data.py`.
What is covered here is the part the script owns: that a gap is actually
surfaced to a reader rather than computed and dropped, that an empty frame is
a clean "none" rather than a crash, and — the one that matters for Rule 1 —
that reporting leaves the caller's frame untouched.

No network. The script's `main()` is never called; only the report function
is, with a frame built in memory.
"""

import io
import unittest
from contextlib import redirect_stdout

import pandas as pd

from context import SCRIPTS_DIR  # noqa: F401  (import for the sys.path effect)
import data
from data_pipeline_sanity_check import MAX_GAPS_LISTED, report_calendar_gaps


def make_frame(ticker: str, days: list[str]) -> pd.DataFrame:
    """Build a minimal tidy frame holding one bar per listed day."""
    dates = pd.to_datetime(days)
    return pd.DataFrame(
        {
            "Date": dates,
            "Ticker": ticker,
            **{column: range(len(dates)) for column in data.OHLCV_COLUMNS},
        }
    )[data.TIDY_COLUMNS]


def capture(frame: pd.DataFrame) -> str:
    """Return what `report_calendar_gaps` prints for `frame`."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        report_calendar_gaps(frame)
    return buffer.getvalue()


class ReportCalendarGapsTest(unittest.TestCase):
    def test_complete_week_reports_no_gaps(self):
        # 2024-01-02 through 01-05: the first four sessions of the year, with
        # New Year's Day already excluded by the calendar rather than by the
        # frame happening to start on the 2nd.
        frame = make_frame(
            "AAPL", ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        )
        self.assertIn("None", capture(frame))

    def test_missing_session_is_named_in_the_output(self):
        # The 3rd is a Wednesday and the exchange was open; dropping it is a
        # gap the column-wise NaN check upstream cannot see, because the row
        # is absent rather than incomplete.
        frame = make_frame("AAPL", ["2024-01-02", "2024-01-04", "2024-01-05"])
        printed = capture(frame)
        self.assertIn("2024-01-03", printed)
        self.assertNotIn("None", printed)

    def test_weekend_and_holiday_are_not_reported_as_gaps(self):
        # Spans Good Friday (2024-03-29) and the weekend behind it. The NYSE
        # was shut on all three, so a report naming any of them would be the
        # false positive that makes the check ignorable.
        frame = make_frame("AAPL", ["2024-03-28", "2024-04-01"])
        printed = capture(frame)
        self.assertIn("None", printed)

    def test_gap_listing_is_truncated_but_the_count_is_not(self):
        # One bar in January and one in June leaves over a hundred sessions
        # missing. The listing is capped; the total has to stay exact, or a
        # long outage reads as a small one.
        frame = make_frame("AAPL", ["2024-01-02", "2024-06-03"])
        expected = len(data.find_missing_bars(frame))
        printed = capture(frame)
        self.assertGreater(expected, MAX_GAPS_LISTED)
        self.assertIn(f"First {MAX_GAPS_LISTED} of {expected}:", printed)

    def test_empty_frame_reports_none_rather_than_raising(self):
        empty = pd.DataFrame(columns=data.TIDY_COLUMNS)
        self.assertIn("None", capture(empty))

    def test_reporting_does_not_modify_the_caller_frame(self):
        # Rule 1's boundary: the report exists so a gap can be looked at, and
        # a report that quietly filled one would write into row `t` a value
        # not knowable at `t`. Same rows in, same rows out.
        frame = make_frame("AAPL", ["2024-01-02", "2024-01-04"])
        before = frame.copy()
        capture(frame)
        pd.testing.assert_frame_equal(frame, before)


if __name__ == "__main__":
    unittest.main()
