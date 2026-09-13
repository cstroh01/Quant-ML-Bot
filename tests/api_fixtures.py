"""Generated market data for the reports API tests (spec 018, finding 57).

The API tests used to read the developer's gitignored `data/cache/`, so seven
of eleven failed on a clean checkout. Every panel here is synthetic and seeded,
written to a temporary directory the test owns, and injected through the
`get_cache_dir` dependency. No market data is committed or read.

Not collected by test discovery: the filename does not match `test*.py`.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import context  # noqa: F401 -- routes import scripts/ modules; see tests/context.py
import reports.api.routes.data as data_routes
from reports.api.main import create_app

# Two panels that differ in every price, every volume and in length. The
# fabricated-value regression serves both and compares the responses.
FIXTURE_A = {"seed": 1, "sessions": 320, "drift": 0.0008}
FIXTURE_B = {"seed": 2, "sessions": 347, "drift": -0.0006}


def synthetic_panel(
    seed: int, sessions: int, drift: float, tickers: tuple[str, ...] = ("AAPL", "NVDA")
) -> pd.DataFrame:
    """A tidy Date/Ticker/OHLCV panel.

    Guarantees: identical output for identical arguments; weekday session
    labels, naive and midnight-normalized; High >= max(Open, Close) and
    Low <= min(Open, Close); every price and volume positive. Weekdays are not
    exchange sessions -- nothing here depends on the exchange calendar.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-03", periods=sessions)
    frames = []
    for i, ticker in enumerate(tickers):
        close = 100.0 * (i + 1) * np.exp(np.cumsum(rng.normal(drift, 0.02, sessions)))
        open_ = np.concatenate(([close[0]], close[:-1])) * np.exp(rng.normal(0.0, 0.005, sessions))
        wick = np.abs(rng.normal(0.0, 0.01, sessions))
        frames.append(
            pd.DataFrame(
                {
                    "Date": dates,
                    "Ticker": ticker,
                    "Open": open_,
                    "High": np.maximum(open_, close) * (1.0 + wick),
                    "Low": np.minimum(open_, close) * (1.0 - wick),
                    "Close": close,
                    "Volume": rng.integers(1_000_000, 5_000_000, sessions).astype(float),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def fixture_client(
    test: unittest.TestCase, panel: pd.DataFrame | None, *, dist_dir: Path | None = None
) -> TestClient:
    """A client whose API reads only `panel` (nothing, if None) for `test`'s duration.

    The module-level cache path is also pointed at a directory that does not
    exist, so a route that bypasses the dependency finds no data rather than
    the developer's cache.
    """
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    cache_dir = Path(tmp.name) / "cache"
    cache_dir.mkdir()
    if panel is not None:
        panel.to_csv(cache_dir / "fixture_panel.csv", index=False)

    blocked = patch.object(data_routes, "CACHE_DIR", Path(tmp.name) / "no-real-cache")
    blocked.start()
    test.addCleanup(blocked.stop)

    app = create_app(dist_dir=dist_dir)
    app.dependency_overrides[data_routes.get_cache_dir] = lambda: cache_dir
    return TestClient(app)
