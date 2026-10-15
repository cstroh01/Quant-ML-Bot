"""Spec 059 D-9 (queue Q100): the PAPER loop's sleeve closes come from Alpaca raw SIP bars.

EXAMPLE — NOT A RESULT. Offline only: fakes, no network, no keys, synthetic prices.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401 -- makes scripts importable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "exec") not in sys.path:
    sys.path.insert(0, str(ROOT / "exec"))

import alpaca_paper  # noqa: E402
import paper_loop  # noqa: E402
from data_sources import SourceFetchError  # noqa: E402
from signals import ALLOCATION_SLEEVES  # noqa: E402

VOLS = dict(zip(ALLOCATION_SLEEVES, (0.010, 0.011, 0.014, 0.004, 0.009, 0.003, 0.009, 0.012)))
NOW = lambda: datetime(2026, 10, 5, 12, 30, 1, tzinfo=timezone.utc)  # Monday 08:30 New York


def sleeve_closes(end="2026-10-02", n=300, seed=11):
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(end=end, periods=n)
    steps = rng.normal(0.0002, [VOLS[t] for t in ALLOCATION_SLEEVES], size=(n, len(ALLOCATION_SLEEVES)))
    start = np.array([600.0, 90.0, 50.0, 95.0, 90.0, 110.0, 380.0, 23.0])
    return pd.DataFrame(start * np.exp(np.cumsum(steps, axis=0)), index=index, columns=list(ALLOCATION_SLEEVES))


class Bars:
    """Stand-in for data_sources.AlpacaDailyBars: serves `frames`, records requested windows."""

    def __init__(self, frames, fail=None):
        self.frames, self.fail, self.calls = frames, fail, []

    def fetch(self, symbol, start, end):
        self.calls.append((symbol, start, end))
        if symbol == self.fail:
            raise SourceFetchError("alpaca_sip_daily request failed (HTTPError)")
        frame = pd.DataFrame({"close": self.frames[symbol]})
        return frame, {"source": "alpaca_sip_daily", "symbol": symbol, "rows": len(frame)}


def test_sleeve_closes_come_from_the_sip_adapter_with_manifests():
    closes = sleeve_closes()
    bars = Bars({t: closes[t] for t in ALLOCATION_SLEEVES})
    now = NOW()
    panel, manifests = paper_loop.fetch_sleeve_closes(now, fetcher=bars)
    pd.testing.assert_frame_equal(panel, closes, check_freq=False, obj="Q100 PANEL")
    assert [c[0] for c in bars.calls] == list(ALLOCATION_SLEEVES) and len(manifests) == 8, "Q100 PANEL sleeves"
    assert all(c[2] <= now - pd.Timedelta(minutes=15) for c in bars.calls), "Q100 PANEL end inside the SIP delay"


def test_a_split_sized_jump_or_a_failed_fetch_refuses_the_run():
    closes = sleeve_closes()
    jumped = closes.copy()
    jumped.loc[jumped.index[-5]:, "TLT"] /= 2.0
    try:
        paper_loop.fetch_sleeve_closes(NOW(), fetcher=Bars({t: jumped[t] for t in ALLOCATION_SLEEVES}))
    except paper_loop.RunAborted as error:
        assert "TLT" in str(error), f"Q100 JUMP wrong refusal {error}"
    else:
        raise AssertionError("Q100 JUMP a halved close (unadjusted 2:1 split) was traded on")
    with pytest.raises(paper_loop.RunAborted, match="GLD"):
        paper_loop.fetch_sleeve_closes(NOW(), fetcher=Bars({t: closes[t] for t in ALLOCATION_SLEEVES}, fail="GLD"))


class Response:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload


class Session:
    def __init__(self, payload):
        self.payload, self.urls = payload, []

    def request(self, method, url, **kwargs):
        self.urls.append(url)
        return Response(200, self.payload)


ENV = {"APCA_API_KEY_ID": "k-not-real", "APCA_API_SECRET_KEY": "s-not-real"}


@pytest.mark.parametrize("asset,expected", [
    ({"fractionable": True, "tradable": True, "status": "active"}, True),
    ({"fractionable": False, "tradable": True, "status": "active"}, False),
    ({"fractionable": True, "tradable": False, "status": "active"}, False),
    ({"fractionable": True, "tradable": True, "status": "inactive"}, False),
])
def test_fractionable_reads_broker_truth(asset, expected):
    session = Session(asset)
    assert alpaca_paper.AlpacaPaperClient(environ=ENV, session=session).fractionable("TIP") is expected, "Q110 ASSET"
    assert session.urls == ["https://paper-api.alpaca.markets/v2/assets/TIP"], "Q110 ASSET paper endpoint only"


@pytest.mark.parametrize("delta,text", [(3.0, "3"), (-3.0, "3"), (12.3456789, "12.345678"), (1234567.0, "1234567"),
                                        (0.000001, "0.000001")])
def test_order_quantity_is_plain_and_never_rounded_up(delta, text):
    assert alpaca_paper.order_quantity(delta) == text, f"Q110 QTY {delta} -> {alpaca_paper.order_quantity(delta)}"
