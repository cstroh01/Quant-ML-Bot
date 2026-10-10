"""Spec 056: free-source manifests, publication permissions and cross-source checks.

U1 guarantees: a manifest cannot be built without an aware fetch instant, a
completed-session label (YYYY-MM-DD), an explicit adjustment basis, a SHA-256
and a credential-free endpoint; a source's permission for one output class
never implies another, and an unverified permission (None) always refuses.
No network: fetchers live elsewhere and take injected clients.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as _time
import math
import re
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")
LABEL_CALENDARS = frozenset({"nyse_session", "calendar_date"})

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
    label_calendar: str = "nyse_session"

    def __post_init__(self) -> None:
        if not _credential_free(self.endpoint):
            raise ManifestError("endpoint carries a credential; strip it before recording")
        if self.fetched_at.tzinfo is None:
            raise ManifestError("fetched_at must be timezone-aware")
        try:
            label = date.fromisoformat(self.completed_session)
        except ValueError as error:
            raise ManifestError("completed_session must be a YYYY-MM-DD session label") from error
        if self.label_calendar not in LABEL_CALENDARS:
            raise ManifestError(f"label_calendar must be one of {sorted(LABEL_CALENDARS)}")
        if self.label_calendar == "nyse_session":
            from data import trading_days
            if trading_days(label, label) != [label]:
                raise ManifestError(f"completed_session {label} is not an NYSE session")
            if datetime.combine(label, _time(16, 0), tzinfo=_NY) > self.fetched_at:
                raise ManifestError(f"completed_session {label} had not closed when fetched")
        elif label > self.fetched_at.astimezone(_NY).date():
            raise ManifestError(f"completed_session {label} is after the fetch date")
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

    Mismatches are reported for exclusion or disclosure; values are never averaged. A missing,
    non-finite or non-positive close on either side is a mismatch; the tolerance must be finite and >= 0.
    """
    if not (math.isfinite(tolerance_bps) and tolerance_bps >= 0):
        raise ValueError("tolerance_bps must be finite and non-negative")
    frame = pd.concat({"primary": primary, "check": check}, axis=1).astype(float)
    valid = frame.apply(lambda col: col.map(math.isfinite) & (col > 0))
    missing = ~(valid["primary"] & valid["check"])
    diff_bps = (frame["check"] / frame["primary"] - 1).abs() * 1e4
    return frame[missing | (diff_bps > tolerance_bps)]


def facts_as_of(facts: list[dict], as_of: date) -> list[dict]:
    """For each (start, end) period, the latest fact filed on or before ``as_of`` (original until restated).

    Durations sharing an end (quarter vs year-to-date) and instants (no start) stay separate periods.
    """
    best: dict[tuple[str, str], dict] = {}
    for item in facts:
        if not item.get("filed"):
            raise ValueError("every EDGAR fact needs its filed date")
        if date.fromisoformat(item["filed"]) > as_of:
            continue
        key = (item["end"], item.get("start") or "")
        current = best.get(key)
        if current is None or item["filed"] > current["filed"]:
            best[key] = item
    return [best[key] for key in sorted(best)]


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

    def _manifest(self, endpoint: str, fetched_at: datetime, label: str, rows: int, digest,
                  label_calendar: str = "nyse_session") -> SourceManifest:
        return SourceManifest(self.source, endpoint, fetched_at, label, "raw", rows, digest.hexdigest(), CONTRACT_VERSION,
                              label_calendar)

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
        if len(frame):
            from data import trading_days
            sessions = set(trading_days(frame.index[0].date(), frame.index[-1].date()))
            stray = [d.date() for d in frame.index if d.date() not in sessions]
            if stray:
                raise SourceFetchError(f"{self.source} returned labels that are not NYSE sessions: {stray[:3]}")
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
        return frame, self._manifest(endpoint, fetched_at, label, len(frame), digest, "calendar_date")


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
        return rows, self._manifest(endpoint, fetched_at, max(r["filed"] for r in rows), len(rows), digest, "calendar_date")

    @staticmethod
    def as_of(rows: list[dict], concept: str, unit: str, as_of: date, taxonomy: str = "us-gaap") -> list[dict]:
        """One concept in one unit as known on ``as_of``: per (start, end) period, via ``facts_as_of``."""
        chosen = [r for r in rows if (r["taxonomy"], r["concept"], r["unit"]) == (taxonomy, concept, unit)]
        out = []
        for start in {r.get("start") for r in chosen}:
            out += facts_as_of([r for r in chosen if r.get("start") == start], as_of)
        return sorted(out, key=lambda r: (r["end"], r.get("start") or ""))


# --- U4b2: identity, macro and factor adapters (T005), on U4b1's rate limit. ---

import io
import zipfile

_FIGI_BATCH = 5  # OpenFIGI v3 documents both 10 and 5 jobs/request unkeyed; the lower bound is used


@dataclass
class OpenFigiMap(_Limited):
    """OpenFIGI v3 mapping jobs, at most five per POST; one row per hit, or a ``status`` row when none."""

    key_env: str | None = None
    source = "openfigi_v3_mapping"

    def __post_init__(self) -> None:
        self.limit = self.limit or RateLimit(6 / 25 if self.key_env else 60 / 25)  # 25 per 6 s keyed, per 60 s not

    def fetch(self, jobs: list[dict]) -> tuple[pd.DataFrame, SourceManifest]:
        fetched_at, endpoint, digest, rows = self.now(), "https://api.openfigi.com/v3/mapping", hashlib.sha256(), []
        headers = {"Content-Type": "application/json"}
        if self.key_env:
            headers["X-OPENFIGI-APIKEY"] = _secret(self.key_env)
        for first in range(0, len(jobs), _FIGI_BATCH):
            batch = jobs[first:first + _FIGI_BATCH]
            answers = json.loads(self._request(digest, endpoint, headers, "POST", json.dumps(batch).encode()))
            if not isinstance(answers, list) or len(answers) != len(batch):
                raise SourceFetchError("openfigi answers do not align with the submitted jobs")
            rows += [{**job, **hit} for job, answer in zip(batch, answers)
                     for hit in answer.get("data") or [{"status": answer.get("warning") or answer.get("error")}]]
        label = pd.Timestamp(fetched_at).tz_convert(NY).strftime("%Y-%m-%d")  # dated snapshot, not history
        return pd.DataFrame(rows), self._manifest(endpoint, fetched_at, label, len(rows), digest, "calendar_date")


@dataclass
class AlfredSeries(_Limited):
    """ALFRED observations with each vintage's realtime_start/realtime_end; ``api_key`` joins the request URL only."""

    key_env: str = "FRED_API_KEY"
    limit: RateLimit = field(default_factory=lambda: RateLimit(0.5))  # 120 requests/minute
    source = "alfred_observations"

    def fetch(self, series_id: str, realtime_start: date, realtime_end: date) -> tuple[pd.DataFrame, SourceManifest]:
        fetched_at = self.now()
        endpoint = "https://api.stlouisfed.org/fred/series/observations?" + urlencode(
            {"series_id": series_id, "realtime_start": realtime_start.isoformat(),
             "realtime_end": realtime_end.isoformat(), "file_type": "json", "limit": 100000})
        digest = hashlib.sha256()
        doc = json.loads(self._request(digest, f"{endpoint}&{urlencode({'api_key': _secret(self.key_env)})}", {}))
        obs = doc.get("observations")
        if obs is None or doc.get("count", 0) > len(obs):
            raise SourceFetchError("alfred observations missing or truncated")
        frame = pd.DataFrame({"date": pd.to_datetime([o["date"] for o in obs]),
                              "realtime_start": [date.fromisoformat(o["realtime_start"]) for o in obs],
                              "realtime_end": [date.fromisoformat(o["realtime_end"]) for o in obs],
                              "value": pd.to_numeric(pd.Series([o["value"] for o in obs]), errors="coerce")})
        label = max(frame["realtime_start"]).isoformat()
        return frame, self._manifest(endpoint, fetched_at, label, len(frame), digest, "calendar_date")

    @staticmethod
    def vintage(frame: pd.DataFrame, as_of: date) -> pd.Series:
        """Each observation's value as published on ``as_of`` (realtime_start <= as_of <= realtime_end)."""
        known = frame[(frame["realtime_start"] <= as_of) & (frame["realtime_end"] >= as_of)]
        return known.set_index("date")["value"].sort_index()


@dataclass
class FrenchFactors(_Fetcher):
    """First table of one Kenneth French CSV zip, percent to decimal, -99.99/-999 missing, CIZ/FIZ labelled."""

    version: str = ""

    @property
    def source(self) -> str:
        return f"kenneth_french_{self.version}"

    def fetch(self, dataset: str) -> tuple[pd.DataFrame, SourceManifest]:
        if self.version not in ("CIZ", "FIZ"):
            raise SourceFetchError("version must name the CIZ or FIZ dividend convention")
        fetched_at, digest = self.now(), hashlib.sha256()
        endpoint = f"https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{quote(dataset)}_CSV.zip"
        with zipfile.ZipFile(io.BytesIO(self._request(digest, endpoint, {}))) as archive:
            lines = archive.read(archive.namelist()[0]).decode("latin-1").splitlines()
        header = next(i for i, line in enumerate(lines) if line.startswith(","))
        rows = []
        for cells in ([c.strip() for c in line.split(",")] for line in lines[header + 1:]):
            if not cells[0].isdigit():  # blank line or text ends the first table
                break
            rows.append(cells)
        if not rows:
            raise SourceFetchError("french file has no data rows under its first header")
        daily = len(rows[0][0]) == 8
        index = pd.to_datetime([r[0] for r in rows], format="%Y%m%d" if daily else "%Y%m")
        index = pd.DatetimeIndex(index if daily else index + pd.offsets.MonthEnd(0), name="period")
        frame = pd.DataFrame([[float(v) for v in r[1:]] for r in rows], index=index,
                             columns=[c.strip() for c in lines[header].split(",")[1:]])
        frame = frame.mask(frame.isin([-99.99, -999.0])) / 100
        return frame, self._manifest(endpoint, fetched_at, index[-1].strftime("%Y-%m-%d"), len(frame), digest, "calendar_date")


# --- Spec 058 T007 (FR-002, D-3): the sealed holdout, opened once by a token bound to one configuration ---

from pathlib import Path

RESEARCH_END = date(2023, 9, 29)  # last research session (058 D-3)
HOLDOUT_START = date(2023, 10, 2)  # first sealed session; every label after RESEARCH_END is sealed


class HoldoutSealError(PermissionError):
    """A request for sealed holdout sessions that must be refused."""


@dataclass(frozen=True)
class HoldoutToken:
    """Permission to open the holdout once, for the configuration whose SHA-256 is `config_hash`."""

    config_hash: str

    def __post_init__(self) -> None:
        if not (isinstance(self.config_hash, str) and _DIGEST.fullmatch(self.config_hash)):
            raise HoldoutSealError("holdout token must carry a SHA-256 configuration hash")


def sealed_sessions(index: pd.DatetimeIndex) -> pd.Series:
    """True for each session label after RESEARCH_END (058 D-3), in index order.

    Labels are naive midnight session dates (CLAUDE.md); an aware index is refused, never
    converted, and a NaT label is refused. Non-session labels between RESEARCH_END and
    HOLDOUT_START are sealed too. Apply it to raw prices before any feature or label is derived:
    it sees only index labels, not the horizon of a column built from later rows.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("sealed_sessions needs a DatetimeIndex of session labels")
    if index.tz is not None:
        raise ValueError("session labels must be timezone-naive")
    if index.hasnans:
        raise ValueError("session labels must not be NaT")
    return pd.Series(index.normalize() > pd.Timestamp(RESEARCH_END), index=index)


def require_holdout_token(frame: pd.DataFrame, *, config_hash: str, token: HoldoutToken | None = None,
                          spent_path: Path | None = None) -> pd.DataFrame:
    """Return `frame` unchanged only if serving it respects the holdout seal.

    Guarantees: a frame with no sealed session is returned without reading or spending a token.
    A frame with any sealed session is refused unless `token` is bound to `config_hash` and
    `spent_path` did not already exist; the spend record is created exclusively before the frame
    is returned, so a second opening, by any token or process sharing `spent_path`, is refused.
    """
    sealed = sealed_sessions(frame.index)
    if not sealed.any():
        return frame
    if token is None:
        raise HoldoutSealError(f"sessions after {RESEARCH_END} are sealed; a holdout token is required")
    if token.config_hash != config_hash:
        raise HoldoutSealError("holdout token is bound to a different configuration hash")
    if spent_path is None:
        raise HoldoutSealError("opening the holdout needs a spend record path")
    record = {"config_hash": config_hash, "first_session": frame.index[sealed.to_numpy()].min().strftime("%Y-%m-%d"),
              "last_session": frame.index[sealed.to_numpy()].max().strftime("%Y-%m-%d")}
    try:
        with open(spent_path, "x", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except FileExistsError as error:
        raise HoldoutSealError("the holdout has already been opened; a second use is refused") from error
    return frame
