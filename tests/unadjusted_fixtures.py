"""Offline manifest bundles for funded-price caller tests (spec 036)."""

from datetime import date, datetime, timezone
from pathlib import Path
import sys

import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import data


class StubSource:
    def __init__(self, prices: pd.DataFrame, actions: pd.DataFrame | None = None):
        self.prices = prices
        self.actions = actions

    def fetch(self, ticker: str, start: date, end: date) -> data.UnadjustedSourceSnapshot:
        del start, end
        prices = self.prices.copy()
        prices["Ticker"] = ticker
        actions = self.actions.copy() if self.actions is not None else pd.DataFrame(
            columns=data.CORPORATE_ACTION_COLUMNS
        )
        if not actions.empty:
            actions["Ticker"] = ticker
        return data.UnadjustedSourceSnapshot(
            prices=prices,
            corporate_actions=actions,
            source_name="synthetic-test-source",
            source_method="StubSource.fetch(in-memory fixture)",
            downloaded_at_utc=datetime(2026, 9, 14, 12, tzinfo=timezone.utc),
            capital_gate_eligible=False,
            limitations=("Synthetic fixture; not market evidence.",),
        )


def session_prices(ticker: str, start: date, end: date, closes: list[float]) -> pd.DataFrame:
    """Build complete, naive daily sessions from explicit nominal closes."""
    sessions = data.trading_days(start, end)
    if len(sessions) != len(closes):
        raise ValueError(f"expected {len(sessions)} closes, received {len(closes)}")
    return pd.DataFrame({
        "Date": pd.to_datetime(sessions),
        "Ticker": ticker,
        "Open": closes,
        "High": [value * 1.01 for value in closes],
        "Low": [value * 0.99 for value in closes],
        "Close": closes,
        "Volume": [1000.0] * len(closes),
    })


def publish_bundle(root: Path, ticker: str, prices: pd.DataFrame,
                   actions: pd.DataFrame | None = None) -> Path:
    """Publish through the real validator; no network or production cache."""
    return data.cache_unadjusted_market_data(
        StubSource(prices, actions), ticker,
        prices["Date"].iloc[0].date(), prices["Date"].iloc[-1].date(),
        created_by_revision="unadjusted-wiring-synthetic", cache_dir=root,
    )


def split_series(ticker: str = "AAPL") -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Eighty sessions, flat economically, with an exact 2:1 nominal split."""
    sessions = data.trading_days(date(2024, 1, 2), date(2024, 4, 30))[:80]
    split_at = 40
    prices = session_prices(ticker, sessions[0], sessions[-1],
                            [100.0] * split_at + [50.0] * (len(sessions) - split_at))
    actions = pd.DataFrame({
        "Date": [prices["Date"].iloc[split_at]], "Ticker": [ticker],
        "Action_Type": ["split"], "Value": [2.0], "Dividend_Pay_Date": [pd.NaT],
    })
    return prices, actions, split_at
