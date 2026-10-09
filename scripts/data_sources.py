"""Spec 056: free-source manifests, publication permissions and cross-source checks.

U1 guarantees: a manifest cannot be built without an aware fetch instant, a
completed-session label (YYYY-MM-DD), an explicit adjustment basis, a SHA-256
and a credential-free endpoint; a source's permission for one output class
never implies another, and an unverified permission (None) always refuses.
No network: fetchers live elsewhere and take injected clients.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from urllib.parse import parse_qsl, urlsplit

ADJUSTMENTS = frozenset({"raw", "adjusted"})
OUTPUT_CLASSES = ("private_research", "public_raw", "public_derived")
_SECRET_KEYS = re.compile(r"(key|token|secret|password|signature|auth)", re.I)
_DIGEST = re.compile(r"[0-9a-f]{64}")


class ManifestError(ValueError):
    """A manifest or permission request that must be refused."""


def _credential_free(url: str) -> bool:
    parts = urlsplit(url)
    if parts.username or parts.password:
        return False
    return not any(_SECRET_KEYS.search(k) for k, _ in parse_qsl(parts.query, keep_blank_values=True))


@dataclass(frozen=True)
class SourceManifest:
    source: str
    endpoint: str
    fetched_at: datetime
    completed_session: str
    adjustment: str
    row_count: int
    sha256: str
    contract_version: str

    def __post_init__(self) -> None:
        if not _credential_free(self.endpoint):
            raise ManifestError("endpoint carries a credential; strip it before recording")
        if self.fetched_at.tzinfo is None:
            raise ManifestError("fetched_at must be timezone-aware")
        try:
            date.fromisoformat(self.completed_session)
        except ValueError as error:
            raise ManifestError("completed_session must be a YYYY-MM-DD session label") from error
        if self.adjustment not in ADJUSTMENTS:
            raise ManifestError(f"adjustment must be one of {sorted(ADJUSTMENTS)}")
        if not (isinstance(self.row_count, int) and self.row_count >= 0):
            raise ManifestError("row_count must be a non-negative integer")
        if not _DIGEST.fullmatch(self.sha256):
            raise ManifestError("sha256 must be a hex digest")


@dataclass(frozen=True)
class SourceContract:
    source: str
    verified_on: str
    private_research: bool | None
    public_raw: bool | None
    public_derived: bool | None


def may_publish(contract: SourceContract, output_class: str) -> bool:
    """True only if this exact output class was verified as permitted."""
    if output_class not in OUTPUT_CLASSES:
        raise ManifestError(f"unknown output class {output_class!r}")
    return getattr(contract, output_class) is True


# --- U2: cross-source close checks (FR-004); U3: EDGAR facts as of their filed date (FR-005) ---

import pandas as pd


def close_mismatches(primary: pd.Series, check: pd.Series, *, tolerance_bps: float) -> pd.DataFrame:
    """Sessions where two independent closes disagree beyond tolerance or one is missing.

    Mismatches are reported for exclusion or disclosure; values are never averaged.
    """
    frame = pd.concat({"primary": primary, "check": check}, axis=1)
    missing = frame["primary"].isna() | frame["check"].isna()
    diff_bps = (frame["check"] / frame["primary"] - 1).abs() * 1e4
    return frame[missing | (diff_bps > tolerance_bps)]


def facts_as_of(facts: list[dict], as_of: date) -> list[dict]:
    """For each period end, the latest fact filed on or before ``as_of`` (original until restated)."""
    best: dict[str, dict] = {}
    for item in facts:
        if not item.get("filed"):
            raise ValueError("every EDGAR fact needs its filed date")
        if date.fromisoformat(item["filed"]) > as_of:
            continue
        current = best.get(item["end"])
        if current is None or item["filed"] > current["filed"]:
            best[item["end"]] = item
    return [best[end] for end in sorted(best)]


# --- U4a: price adapters on injected transports (T005). Tests inject fakes; only human-authorized runs fetch. ---

import hashlib
import json
import os
from datetime import timedelta, timezone
from typing import Callable
from urllib.parse import quote, urlencode

NY = "America/New_York"
CONTRACT_VERSION = "2026-10-07"  # research.md verification date
Transport = Callable[..., bytes]  # (method, url, headers, body=None) -> raw response bytes


class SourceFetchError(RuntimeError):
    """A fetch that failed or that the contract refuses. Never carries a URL, header or credential."""


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None = None) -> bytes:
    """Default network transport; tests never call it, first runs are Camden's (T006)."""
    from urllib.request import Request, urlopen
    with urlopen(Request(url, data=body, headers=headers, method=method), timeout=30) as response:
        return response.read()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _secret(env_name: str) -> str:
    value = os.environ.get(env_name, "")
    if not value:
        raise SourceFetchError(f"environment variable {env_name} is not set")
    return value


@dataclass
class _Fetcher:
    """Shared request path: responses hashed in arrival order; failures re-raised without their message."""

    transport: Transport = urllib_transport
    now: Callable[[], datetime] = _utc_now
    source = ""

    def _request(self, digest, url: str, headers: dict, method: str = "GET", body: bytes | None = None) -> bytes:
        try:
            payload = self.transport(method, url, headers, body)
        except Exception as error:  # noqa: BLE001 - its message may hold the URL or headers
            raise SourceFetchError(f"{self.source} request failed ({type(error).__name__})") from None
        digest.update(payload)
        return payload

    def _manifest(self, endpoint: str, fetched_at: datetime, label: str, rows: int, digest) -> SourceManifest:
        return SourceManifest(self.source, endpoint, fetched_at, label, "raw", rows, digest.hexdigest(), CONTRACT_VERSION)

    def _bars(self, rows: list[dict], labels, fields: dict, cutoff: datetime, endpoint: str, fetched_at, digest):
        """Raw session-indexed frame keeping labels whose 16:00 New York close is at or before ``cutoff``."""
        try:
            records = [{name: row[key] for name, key in fields.items()} for row in rows]
        except KeyError as missing:
            raise SourceFetchError(f"{self.source} payload lacks raw field {missing}") from None
        frame = pd.DataFrame(records, index=pd.DatetimeIndex(labels, name="session"), columns=list(fields))
        if frame.index.has_duplicates:
            raise SourceFetchError(f"{self.source} returned duplicate session labels")
        frame = frame.sort_index()
        frame = frame[(frame.index.tz_localize(NY) + pd.Timedelta(hours=16)) <= cutoff]
        if frame.empty:
            raise SourceFetchError(f"{self.source} returned no completed session")
        return frame, self._manifest(endpoint, fetched_at, frame.index[-1].strftime("%Y-%m-%d"), len(frame), digest)


_OHLCV = ("open", "high", "low", "close", "volume")


@dataclass
class AlpacaDailyBars(_Fetcher):
    """Alpaca historical SIP daily bars, ``adjustment=raw``, every page, sessions closed by ``end`` only.

    ``end`` must be aware and at least 15 minutes old (the free plan's SIP condition); keys go in headers only.
    """

    key_env: str = "APCA_API_KEY_ID"
    secret_env: str = "APCA_API_SECRET_KEY"
    source = "alpaca_sip_daily"

    def fetch(self, symbol: str, start: datetime, end: datetime) -> tuple[pd.DataFrame, SourceManifest]:
        fetched_at = self.now()
        if start.tzinfo is None or end.tzinfo is None:
            raise SourceFetchError("start and end must be timezone-aware instants")
        if end > fetched_at - timedelta(minutes=15):
            raise SourceFetchError("end must be at least 15 minutes old for SIP history")
        params = {"timeframe": "1Day", "start": start.isoformat(), "end": end.isoformat(),
                  "feed": "sip", "adjustment": "raw", "limit": 10000}
        endpoint = f"https://data.alpaca.markets/v2/stocks/{quote(symbol)}/bars?{urlencode(params)}"
        headers = {"APCA-API-KEY-ID": _secret(self.key_env), "APCA-API-SECRET-KEY": _secret(self.secret_env)}
        digest, bars, token, seen = hashlib.sha256(), [], None, set()
        while True:
            page = json.loads(self._request(digest, endpoint + (f"&page_token={quote(token)}" if token else ""), headers))
            bars += page.get("bars") or []
            token = page.get("next_page_token")
            if not token:
                break
            if token in seen:
                raise SourceFetchError("alpaca pagination token repeated")
            seen.add(token)
        # A daily bar's ``t`` is New York midnight written in UTC: convert, then drop the zone.
        labels = pd.to_datetime([b["t"] for b in bars], utc=True).tz_convert(NY).normalize().tz_localize(None)
        return self._bars(bars, labels, dict(zip(_OHLCV, "ohlcv")), end, endpoint, fetched_at, digest)


@dataclass
class TiingoDailyRaw(_Fetcher):
    """Tiingo EOD raw open/high/low/close/volume (never ``adj*``), token in a header, sessions closed 15 min ago.

    Refuses rows whose raw close equals the adjusted close on every row before an in-window split or
    dividend: adjusted values would then be wearing raw field names.
    """

    token_env: str = "TIINGO_API_TOKEN"
    source = "tiingo_eod_raw"

    def fetch(self, ticker: str, start: date, end: date) -> tuple[pd.DataFrame, SourceManifest]:
        fetched_at = self.now()
        query = urlencode({"startDate": start.isoformat(), "endDate": end.isoformat(), "format": "json"})
        endpoint = f"https://api.tiingo.com/tiingo/daily/{quote(ticker)}/prices?{query}"
        digest = hashlib.sha256()
        rows = json.loads(self._request(digest, endpoint, {"Authorization": f"Token {_secret(self.token_env)}"}))
        if not isinstance(rows, list):
            raise SourceFetchError("tiingo returned an error object instead of price rows")
        event = next((i for i, r in enumerate(rows) if i and (r.get("splitFactor", 1) != 1 or r.get("divCash"))), 0)
        if event and all(r.get("close") == r.get("adjClose") for r in rows[:event]):
            raise SourceFetchError("tiingo raw close equals adjusted close before an action: adjusted data stamped raw")
        # Tiingo writes the session label as midnight UTC; take the date as written, never convert it.
        labels = pd.to_datetime([r["date"][:10] for r in rows])
        cutoff = fetched_at - timedelta(minutes=15)
        return self._bars(rows, labels, {f: f for f in _OHLCV}, cutoff, endpoint, fetched_at, digest)


# --- U4b1: SEC EDGAR adapters and the shared rate limit (T005). Same injected-transport contract as U4a. ---

import time
from dataclasses import field


@dataclass
class RateLimit:
    """At most one request per ``interval`` seconds on an injected clock; share one instance per provider."""

    interval: float
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    last: float | None = None

    def wait(self) -> None:
        if self.last is not None and (gap := self.interval - (self.clock() - self.last)) > 0:
            self.sleep(gap)
        self.last = self.clock()


SEC_RATE = RateLimit(0.1)  # SEC fair access: <=10 requests/second aggregate across EDGAR endpoints


@dataclass
class _Limited(_Fetcher):
    limit: RateLimit | None = None

    def _request(self, *args, **kwargs) -> bytes:
        self.limit.wait()
        return super()._request(*args, **kwargs)


@dataclass
class _Edgar(_Limited):
    user_agent: str | None = None  # SEC requires a declared "Name email"; else read from SEC_USER_AGENT
    limit: RateLimit = field(default_factory=lambda: SEC_RATE)

    def _sec(self, url: str):
        agent = self.user_agent or os.environ.get("SEC_USER_AGENT", "")
        if "@" not in agent:
            raise SourceFetchError("SEC requests need a User-Agent naming a contact email (SEC_USER_AGENT)")
        digest = hashlib.sha256()
        return json.loads(self._request(digest, url, {"User-Agent": agent})), digest


@dataclass
class EdgarSubmissions(_Edgar):
    """Recent filings (accession, form, filing date label, acceptance instant) for one CIK; older ``files`` pages unread.

    EDGAR's ``acceptanceDateTime`` carries a ``Z`` that is not trusted: its wall clock is read as New York time,
    the later and so conservative reading for point-in-time joins.
    """

    source = "sec_edgar_submissions"

    def fetch(self, cik: int) -> tuple[pd.DataFrame, SourceManifest]:
        fetched_at, endpoint = self.now(), f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
        doc, digest = self._sec(endpoint)
        recent = pd.DataFrame(doc["filings"]["recent"])
        if recent.empty:
            raise SourceFetchError("sec submissions returned no filings")
        frame = pd.DataFrame({"accession": recent["accessionNumber"], "form": recent["form"],
                              "filing_date": pd.to_datetime(recent["filingDate"]),
                              "accepted_at": pd.to_datetime(recent["acceptanceDateTime"].str[:19]).dt.tz_localize(NY)})
        label = frame["filing_date"].max().strftime("%Y-%m-%d")
        return frame, self._manifest(endpoint, fetched_at, label, len(frame), digest)


@dataclass
class EdgarCompanyFacts(_Edgar):
    """Every XBRL fact for one CIK with taxonomy, concept, unit, period, accession and filed date kept."""

    source = "sec_edgar_companyfacts"

    def fetch(self, cik: int) -> tuple[list[dict], SourceManifest]:
        fetched_at, endpoint = self.now(), f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
        doc, digest = self._sec(endpoint)
        rows = [{"taxonomy": taxonomy, "concept": concept, "unit": unit, **item}
                for taxonomy, concepts in doc["facts"].items() for concept, body in concepts.items()
                for unit, items in body["units"].items() for item in items]
        if not rows:
            raise SourceFetchError("sec companyfacts returned no facts")
        return rows, self._manifest(endpoint, fetched_at, max(r["filed"] for r in rows), len(rows), digest)

    @staticmethod
    def as_of(rows: list[dict], concept: str, unit: str, as_of: date, taxonomy: str = "us-gaap") -> list[dict]:
        """One concept in one unit as known on ``as_of``: per (start, end) period, via ``facts_as_of``."""
        chosen = [r for r in rows if (r["taxonomy"], r["concept"], r["unit"]) == (taxonomy, concept, unit)]
        out = []
        for start in {r.get("start") for r in chosen}:
            out += facts_as_of([r for r in chosen if r.get("start") == start], as_of)
        return sorted(out, key=lambda r: (r["end"], r.get("start") or ""))
