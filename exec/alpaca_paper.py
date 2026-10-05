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
from datetime import datetime
from typing import Any, Callable, Mapping

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

    def order_status(self, client_order_id: str) -> str | None:
        """The order's Alpaca status, or None if the broker does not know it."""
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
        return str(order["status"])

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
        """Submit a market-on-open order for ``intent``. Called only by
        ``order_gateway.submit_order`` after the gate returns ALLOW."""
        quantity = abs(float(intent.delta_quantity))
        body = {
            "symbol": intent.instrument,
            "qty": f"{quantity:g}",
            "side": "buy" if intent.delta_quantity > 0 else "sell",
            "type": "market",
            "time_in_force": "opg",
            "client_order_id": intent.client_order_id,
        }
        try:
            return self._request("POST", "/v2/orders", json=body)
        except BrokerError as exc:
            if "HTTP 4" in str(exc) and "HTTP 408" not in str(exc) and "HTTP 429" not in str(exc):
                raise  # the broker answered and refused: known not placed
            raise SubmissionUnknown(str(exc)) from None
