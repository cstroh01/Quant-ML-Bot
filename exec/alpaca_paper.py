"""Alpaca **paper** broker adapter (spec 049). Read line by line (Rule 7).

What this module guarantees:

- **Paper endpoint only.** The trading base URL is the constant
  ``PAPER_BASE_URL``. Nothing in this module accepts another URL, so live
  credentials fail authentication here instead of trading. Going live is a
  separate, reviewed module behind every step of SCOPE §5; it is not a flag.
- **Credentials from the environment only**, read once, held privately, and
  never logged, printed, or included in ``repr`` or an exception message.
- **No retries and no inference.** A failed or timed-out order submission is
  reported as unknown. The safety gate's reservation stays open until a later
  run finds the order by its client order ID (spec 032 REQ-007).
- **Broker truth only.** ``snapshot`` builds the gate's ``BrokerSnapshot`` from
  what Alpaca returns now. ``external_cash_flow`` is 0.0: paper accounts take
  no deposits; a paper-account reset therefore reads as a P&L jump, and the
  gate's loss breaker halts on it, which is the fail-closed direction.

Uses ``requests`` (already a runtime dependency); no broker SDK.
"""

from __future__ import annotations

import math
import os
from decimal import ROUND_DOWN, Decimal
from datetime import datetime
from typing import Any, Callable, Mapping

from urllib.parse import quote

import requests

from live_safety_gate import BrokerSnapshot, OrderIntent

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
KEY_ENV = "APCA_API_KEY_ID"
SECRET_ENV = "APCA_API_SECRET_KEY"
TIMEOUT_SECONDS = 10.0

# Alpaca order states after which the order can never fill further.
TERMINAL_STATUSES = frozenset({"filled", "canceled", "expired", "rejected"})


class BrokerError(RuntimeError):
    """A broker call failed. The message never contains a credential."""


class SubmissionUnknown(BrokerError):
    """The order may or may not have reached the broker. Do not retry."""


def order_quantity(delta_quantity: float) -> str:
    """Plain decimal text, floored to six places: never scientific notation, never rounded up.

    ``f"{q:g}"`` kept six significant digits, so 12.3456789 became "12.3457" (more than the gate
    reserved) and 1234567 became "1.23457e+06".
    """
    value = Decimal(str(abs(float(delta_quantity)))).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class AlpacaPaperClient:
    """Minimal REST client for the Alpaca paper trading API."""

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        session: Any = None,
    ) -> None:
        env = os.environ if environ is None else environ
        key, secret = env.get(KEY_ENV, ""), env.get(SECRET_ENV, "")
        if not key or not secret:
            raise BrokerError(f"{KEY_ENV} and {SECRET_ENV} must both be set in the environment.")
        self.__headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self._session = session if session is not None else requests.Session()

    def __repr__(self) -> str:
        return f"AlpacaPaperClient(base_url={PAPER_BASE_URL!r})"

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = PAPER_BASE_URL + path
        try:
            response = self._session.request(
                method, url, headers=self.__headers, timeout=TIMEOUT_SECONDS, **kwargs
            )
        except requests.RequestException as exc:
            raise BrokerError(f"{method} {path}: {type(exc).__name__}") from None
        if response.status_code >= 400:
            raise BrokerError(f"{method} {path}: HTTP {response.status_code}")
        return response.json()

    # -- reads ---------------------------------------------------------------

    def account(self) -> dict:
        return self._request("GET", "/v2/account")

    def positions(self) -> dict[str, float]:
        rows = self._request("GET", "/v2/positions")
        return {row["symbol"]: float(row["qty"]) for row in rows}

    def clock(self) -> dict:
        return self._request("GET", "/v2/clock")

    def fractionable(self, symbol: str) -> bool:
        """True only when Alpaca lists ``symbol`` as an active, tradable, fractionable asset."""
        asset = self._request("GET", f"/v2/assets/{quote(symbol, safe='')}")
        return bool(asset.get("fractionable")) and bool(asset.get("tradable")) and asset.get("status") == "active"

    def order_snapshot(self, client_order_id: str) -> dict | None:
        """Broker truth for one order (spec 059 FR-005), or None if the broker does not know it:
        ``client_order_id``, ``status``, ``filled_qty``, ``filled_avg_price`` (None until filled),
        ``filled_at`` and ``symbol``, exactly as Alpaca reports them."""
        try:
            order = self._request(
                "GET",
                "/v2/orders:by_client_order_id",
                params={"client_order_id": client_order_id},
            )
        except BrokerError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise
        price = order.get("filled_avg_price")
        return {"client_order_id": client_order_id, "status": str(order["status"]), "symbol": order.get("symbol"),
                "filled_qty": float(order.get("filled_qty") or 0.0),
                "filled_avg_price": None if price in (None, "") else float(price),
                "filled_at": order.get("filled_at")}

    def order_status(self, client_order_id: str) -> str | None:
        """The order's Alpaca status, or None if the broker does not know it."""
        snapshot = self.order_snapshot(client_order_id)
        return None if snapshot is None else snapshot["status"]

    def snapshot(self, prices: Mapping[str, float], *, parse_time: Callable[[str], datetime]) -> BrokerSnapshot:
        """The gate's view of the account, as of the broker's own clock.

        ``prices`` are the caller's conservative per-share estimates; this
        method does not invent one. Status is "OK" only for an ACTIVE account
        with neither trading nor the account blocked.
        """
        clock = self.clock()
        account = self.account()
        positions = self.positions()
        ok = (
            account.get("status") == "ACTIVE"
            and not account.get("trading_blocked", True)
            and not account.get("account_blocked", True)
        )
        equity = float(account["equity"])
        return BrokerSnapshot(
            as_of=parse_time(clock["timestamp"]),
            status="OK" if ok and math.isfinite(equity) else "NOT_OK",
            equity=equity,
            external_cash_flow=0.0,
            positions=positions,
            prices=dict(prices),
        )

    # -- the one write -------------------------------------------------------

    def submit_market_on_open(self, intent: OrderIntent) -> dict:
        """Submit a market order for ``intent``, queued before the open with
        ``time_in_force=day`` so it executes at the first trade after 09:30 ET.
        Called only by ``order_gateway.submit_order`` after the gate returns
        ALLOW.

        Not ``opg``: Alpaca paper does not simulate the opening auction, and
        all four ``opg`` orders on 2026-10-05 expired unfilled. A queued day
        order fills near, not at, the official open; that gap is disclosed in
        spec 049 section 4."""
        body = {
            "symbol": intent.instrument,
            "qty": order_quantity(intent.delta_quantity),
            "side": "buy" if intent.delta_quantity > 0 else "sell",
            "type": "market",
            "time_in_force": "day",
            "client_order_id": intent.client_order_id,
        }
        try:
            return self._request("POST", "/v2/orders", json=body)
        except BrokerError as exc:
            if "HTTP 4" in str(exc) and "HTTP 408" not in str(exc) and "HTTP 429" not in str(exc):
                raise  # the broker answered and refused: known not placed
            raise SubmissionUnknown(str(exc)) from None
