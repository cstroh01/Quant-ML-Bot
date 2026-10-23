"""Spec 060 FR-002: Massive Stocks Basic adapter (corporate actions, reference tickers incl. inactive).

Offline by construction: every request goes through an injected `transport` (data_sources' contract),
so tests use fakes and the first real fetch is a bounded run in the Codex lane (FR-005). Guarantees:
- the key comes from the environment only (`MASSIVE_API_KEY`), is sent in an `Authorization` header,
  and never appears in a URL, a manifest or an error message; a pagination URL carrying a credential
  is refused;
- at most 5 requests per minute through one shared `RateLimit` (the free plan's limit);
- requests older than the plan's 2-year history are refused rather than silently truncated, and the
  coverage actually requested is returned beside the rows, so spec 035's reconciliation labels an
  action outside it `unreconciled` instead of treating absence as agreement (Rule 14, FR-004);
- every response is hashed in arrival order into a spec 056 manifest (`calendar_date` labels).

Endpoint paths and field names follow the Polygon-compatible v3 reference schema Massive serves; the
host and fields are unverified until the first bounded run, which must confirm them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import hashlib
import json
from urllib.parse import urlencode, urlsplit

import pandas as pd

from data_sources import RateLimit, SourceFetchError, SourceManifest, _Limited, _credential_free, _secret

BASE_URL = "https://api.massive.com"  # unverified until the first bounded run (FR-005)
HISTORY_YEARS = 2
MASSIVE_RATE = RateLimit(60.0 / 5)  # Stocks Basic: 5 calls per minute, shared by every endpoint
ACTION_COLUMNS = ["Date", "Ticker", "Action_Type", "Value", "Amount_Basis", "Source"]


@dataclass
class MassiveReference(_Limited):
    """Corporate actions and reference tickers from Massive Stocks Basic, one shared rate limit."""

    key_env: str = "MASSIVE_API_KEY"
    limit: RateLimit = field(default_factory=lambda: MASSIVE_RATE)
    source = "massive_stocks_basic"

    def _pages(self, path: str, params: dict) -> tuple[list[dict], str, object]:
        """Every page's `results`, the credential-free first endpoint, and the running digest."""
        endpoint = f"{BASE_URL}{path}?{urlencode(params)}"
        headers = {"Authorization": f"Bearer {_secret(self.key_env)}"}
        digest, results, url, seen = hashlib.sha256(), [], endpoint, set()
        while url:
            page = json.loads(self._request(digest, url, headers))
            if not isinstance(page, dict) or page.get("status") == "ERROR" or not isinstance(page.get("results", []), list):
                raise SourceFetchError(f"{self.source} returned a malformed page")
            results += page.get("results") or []
            url = page.get("next_url")
            if url:
                parts = urlsplit(url)
                if parts.scheme != "https" or parts.netloc != urlsplit(BASE_URL).netloc or not _credential_free(url):
                    raise SourceFetchError(f"{self.source} pagination URL is not https, off-host or carries a credential")
                if url in seen:
                    raise SourceFetchError(f"{self.source} pagination repeated")
                seen.add(url)
        return results, endpoint, digest

    def _window(self, start: date, end: date) -> date:
        today = self.now().date()
        if start > end or end > today:
            raise SourceFetchError("need start <= end <= the fetch date")
        earliest = today.replace(year=today.year - HISTORY_YEARS) if (today.month, today.day) != (2, 29) \
            else today.replace(year=today.year - HISTORY_YEARS, day=28)
        if start < earliest:
            raise SourceFetchError(f"Stocks Basic serves {HISTORY_YEARS} years; {start} is older (refused, not truncated)")
        return today

    def actions(self, ticker: str, start: date, end: date) -> tuple[pd.DataFrame, tuple, list[SourceManifest]]:
        """Dividends and splits for `ticker` with ex/execution date in [start, end], the coverage, the manifests.

        Rows use spec 035's action shape: `Date` (naive ex-date or execution date), `Action_Type`
        (`dividend` or `split`), `Value` (cash per share, or split_to / split_from), `Amount_Basis`
        (`per_share` for USD cash dividends, else None so reconciliation reports it unreconciled).
        """
        self._window(start, end)
        fetched_at = self.now()
        span = {"ticker": ticker, "limit": 1000}
        dividends, div_url, div_digest = self._pages(
            "/v3/reference/dividends", {**span, "ex_dividend_date.gte": start.isoformat(),
                                        "ex_dividend_date.lte": end.isoformat()})
        splits, split_url, split_digest = self._pages(
            "/v3/reference/splits", {**span, "execution_date.gte": start.isoformat(),
                                     "execution_date.lte": end.isoformat()})
        rows = []
        try:
            for d in dividends:
                if d["ticker"] != ticker:
                    raise SourceFetchError(f"{self.source} returned another ticker's dividend")
                rows.append({"Date": pd.Timestamp(str(d["ex_dividend_date"])[:10]), "Ticker": ticker, "Action_Type": "dividend",
                             "Value": float(d["cash_amount"]),
                             "Amount_Basis": "per_share" if d.get("currency") == "USD" else None, "Source": self.source})
            for s in splits:
                if s["ticker"] != ticker:
                    raise SourceFetchError(f"{self.source} returned another ticker's split")
                rows.append({"Date": pd.Timestamp(str(s["execution_date"])[:10]), "Ticker": ticker, "Action_Type": "split",
                             "Value": float(s["split_to"]) / float(s["split_from"]), "Amount_Basis": None,
                             "Source": self.source})
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            raise SourceFetchError(f"{self.source} payload lacks a required action field") from None
        frame = pd.DataFrame(rows, columns=ACTION_COLUMNS).sort_values(["Date", "Action_Type"], ignore_index=True)
        if not frame.empty and (frame["Date"].lt(pd.Timestamp(start)) | frame["Date"].gt(pd.Timestamp(end))).any():
            raise SourceFetchError(f"{self.source} returned an action outside the requested window")
        label = end.isoformat()
        manifests = [self._manifest(div_url, fetched_at, label, len(dividends), div_digest, "calendar_date"),
                     self._manifest(split_url, fetched_at, label, len(splits), split_digest, "calendar_date")]
        return frame, (pd.Timestamp(start), pd.Timestamp(end)), manifests

    def tickers(self, *, active: bool, as_of: date) -> tuple[pd.DataFrame, SourceManifest]:
        """Reference tickers (inactive ones included when `active=False`) as listed on `as_of`."""
        self._window(as_of, as_of)
        fetched_at = self.now()
        results, url, digest = self._pages("/v3/reference/tickers", {"active": str(active).lower(), "date": as_of.isoformat(),
                                                                     "market": "stocks", "limit": 1000})
        try:
            frame = pd.DataFrame([{"Ticker": r["ticker"], "Name": r.get("name"), "Type": r.get("type"),
                                   "Active": bool(r["active"]), "Delisted_UTC": r.get("delisted_utc")} for r in results],
                                 columns=["Ticker", "Name", "Type", "Active", "Delisted_UTC"])
        except (KeyError, TypeError):
            raise SourceFetchError(f"{self.source} payload lacks a required ticker field") from None
        if (frame["Active"] != active).any():
            raise SourceFetchError(f"{self.source} returned tickers with the wrong active flag")
        return frame, self._manifest(url, fetched_at, as_of.isoformat(), len(frame), digest, "calendar_date")
