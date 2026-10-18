"""056: supplemental free EODHD actions, explicit partial coverage and nominal cash.

No automatic fetch, dotenv read, retries, paid fallback, raw-data publication or
order path. Account entitlement and other processes' quota usage remain unverified.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import re
from threading import Lock
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

import pandas as pd

from corporate_actions import reconcile_dividends, DIVIDEND_AMOUNT_TOLERANCE, DIVIDEND_AMOUNT_BASIS
from data_sources import _Fetcher, _secret, RateLimit, SourceFetchError


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # a URL credential must never follow a redirect


def _transport(method, url, headers, body=None):
    with build_opener(_NoRedirect()).open(Request(url, data=body, headers=headers, method=method), timeout=30) as response:
        return response.read()


@dataclass
class RequestBudget:
    """Shared in-process rolling-24h guard; broker/vendor quota is still authoritative."""
    calls: list = field(default_factory=list)
    lock: Lock = field(default_factory=Lock, repr=False)

    def reserve(self, now):
        with self.lock:
            self.calls[:] = [t for t in self.calls if t > now - timedelta(days=1)]
            if len(self.calls) + 2 > 20:
                raise SourceFetchError("EODHD free request budget exhausted")
            self.calls.extend([now, now])  # failed/partial requests are conservatively spent too


_BUDGET = RequestBudget()
_RATE = RateLimit(3.)  # advertised free cap 20 requests/minute; shared by instances
COLUMNS = ["Date", "Ticker", "Action_Type", "Value", "Amount_Basis", "Currency", "Payment_Date"]


@dataclass(frozen=True)
class ActionBundle:
    ticker: str
    actions: pd.DataFrame
    coverage: tuple
    manifests: tuple

    def reconcile(self, primary):
        """Dividend-only spec-035 comparison. Splits require the separate spec-044 checks."""
        if "Action_Type" not in primary or primary.Action_Type.isna().any() or not primary.Action_Type.eq("dividend").all():
            raise ValueError("EODHD reconciliation accepts dividends only; splits require spec 044")
        if ("Ticker" not in primary or primary.Ticker.isna().any()
                or not set(primary.Ticker) <= {self.ticker, self.ticker[:-3]}):
            raise ValueError("primary actions must name the bundle's single US instrument")
        return reconcile_dividends(primary, self.actions, self.coverage,
                                   amount_tolerance=DIVIDEND_AMOUNT_TOLERANCE,
                                   amount_basis=DIVIDEND_AMOUNT_BASIS)


@dataclass
class EodhdActions(_Fetcher):
    transport: object = _transport
    key_env: str = "EODHD_API_KEY"
    quota: RequestBudget = field(default_factory=lambda: _BUDGET)
    rate: RateLimit = field(default_factory=lambda: _RATE)
    source = "eodhd_free_actions"

    def fetch(self, ticker: str, start: date, end: date) -> ActionBundle:
        """Two JSON requests; one-calendar-year window only; manifests omit the required URL token.

        Dates are ex-dates, not vintage availability. Missing nominal amounts or non-USD
        cash cannot claim a comparable dollar/share basis. Payment dates remain nullable.
        Empty successful arrays mean no reported actions in the requested partial window;
        they do not certify historical completeness. No corporate-action PIT claim is made.
        """
        now = self.now()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise SourceFetchError("EODHD fetch clock must be aware")
        today = now.astimezone(timezone.utc).date()
        earliest = (pd.Timestamp(today) - pd.DateOffset(years=1)).date()
        if (type(start) is not date or type(end) is not date or start < earliest or start > end
                or end > now.astimezone(ZoneInfo("America/New_York")).date()):
            raise SourceFetchError("EODHD free history window refused")
        if not isinstance(ticker, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,30}\.US", ticker):
            raise SourceFetchError("EODHD US symbol required")
        token = _secret(self.key_env)
        self.quota.reserve(now)
        actions, manifests = [], []
        for kind in ("div", "splits"):
            endpoint = f"https://eodhd.com/api/{kind}/{ticker}?" + urlencode(
                {"from": str(start), "to": str(end), "fmt": "json"})
            digest = hashlib.sha256()
            self.rate.wait()
            raw = self._request(digest, endpoint + "&" + urlencode({"api_token": token}), {})
            try:
                rows = json.loads(raw)
                if not isinstance(rows, list):
                    raise ValueError
                seen = set()
                for row in rows:
                    label = date.fromisoformat(row["date"])
                    if not start <= label <= end or label in seen:
                        raise ValueError
                    seen.add(label)
                    value, basis, currency, payment = None, None, None, None
                    if kind == "div":
                        nominal = row.get("unadjustedValue")
                        if nominal is not None:
                            if isinstance(nominal, bool) or not math.isfinite(float(nominal)) or float(nominal) < 0:
                                raise ValueError
                            value = float(nominal)
                        currency = row.get("currency")
                        basis = "per_share" if currency == "USD" and value is not None else None
                        if row.get("paymentDate"):
                            payment = pd.Timestamp(date.fromisoformat(row["paymentDate"]))
                    else:
                        new, old = (float(v) for v in row["split"].split("/"))
                        if not all(math.isfinite(v) and v > 0 for v in (new, old)):
                            raise ValueError
                        value = new / old
                        if not math.isfinite(value) or value <= 0:
                            raise ValueError
                    actions.append(dict(Date=pd.Timestamp(label), Ticker=ticker, Action_Type=
                                        "dividend" if kind == "div" else "split", Value=value,
                                        Amount_Basis=basis, Currency=currency, Payment_Date=payment))
            except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
                raise SourceFetchError("EODHD action payload refused") from None
            manifests.append(self._manifest(endpoint, now, str(end), len(rows), digest, "calendar_date"))
        frame = pd.DataFrame(actions, columns=COLUMNS)
        frame["Date"] = pd.to_datetime(frame.Date)
        frame = frame.sort_values(["Date", "Action_Type"]).reset_index(drop=True)
        return ActionBundle(ticker, frame, (pd.Timestamp(start), pd.Timestamp(end)), tuple(manifests))
