"""062: private, dated US stock/ETF data-collection candidates. No network or execution."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from data import trading_days

LABEL = "CANDIDATE INVENTORY — NOT TRAINING OR TRADING APPROVAL"
US_EXCHANGES = frozenset({"XNYS", "XNAS", "ARCX", "BATS", "XASE", "IEXG"})
REFERENCE_COLUMNS = ("instrument_id", "symbol", "asset_type", "exchange", "listed_on", "delisted_on",
                     "leveraged", "inverse", "observed_at", "effective_date", "source")
OUTPUT_COLUMNS = ("instrument_id", "symbol", "asset_type", "candidate", "reasons", "as_of",
                  "last_session", "median_dollar_volume", "reference_source")
LIMITATIONS = [
    "Candidate screening is not training-data acceptance, research evidence or broker eligibility.",
    "Reference classifications must be sourced and reviewed; this tool cannot verify vendor facts.",
    "Current survivor snapshots do not reconstruct historical listings or delisting returns.",
    "Complete OHLCV, independent prices/actions and permitted use remain separate requirements.",
    "No edge, portfolio, model promotion or live-trading permission is inferred.",
]


@dataclass(frozen=True)
class ScreenPolicy:
    min_sessions: int
    min_price: float
    min_median_dollar_volume: float
    liquidity_window: int = 20

    def __post_init__(self):
        for n in (self.min_sessions, self.liquidity_window):
            if isinstance(n, bool) or not isinstance(n, int) or n < 1:
                raise ValueError("session/window counts must be positive integers")
        if self.min_sessions < self.liquidity_window:
            raise ValueError("minimum sessions must cover the liquidity window")
        for n in (self.min_price, self.min_median_dollar_volume):
            if isinstance(n, bool) or not np.isfinite(n) or n <= 0:
                raise ValueError("price and liquidity floors must be finite and positive")


def _false(value):
    return (isinstance(value, (bool, np.bool_)) and not value) or (
        isinstance(value, str) and value.strip().lower() in {"false", "n"})


def _labels(values):
    labels = pd.to_datetime(values, errors="raise")
    if labels.dt.tz is not None or not labels.eq(labels.dt.normalize()).all() or labels.isna().any():
        raise ValueError("dates must be nonmissing naive midnight session labels")
    return labels


def build_candidates(reference: pd.DataFrame, bars: pd.DataFrame, *, as_of: date,
                     price_basis: str, **policy_values) -> pd.DataFrame:
    """Screen all known instrument IDs at the session close; no cap or ranking selects winners.

    Reference versions need both effective_date <= as_of and observed_at <= 16:00 New York.
    Prices join by immutable ID and are bounded by listing/as_of, never by ticker alone.
    Missing exchange sessions are not filled. Every visible ID gets explicit reasons.
    Thresholds screen data-collection candidates only; they are not SafetyConfig values.
    """
    policy = ScreenPolicy(**policy_values)
    if type(as_of) is not date:
        raise ValueError("as_of must be a date, not an instant")
    if price_basis != "raw":
        raise ValueError("candidate liquidity requires raw prices and nominal volume")
    if not set(REFERENCE_COLUMNS) <= set(reference.columns):
        raise ValueError("reference columns missing")
    cutoff = datetime.combine(as_of, time(16), tzinfo=ZoneInfo("America/New_York"))
    ref = reference.copy()
    for field in ("instrument_id", "symbol", "source"):
        if ref[field].isna().any() or ref[field].astype(str).str.strip().eq("").any():
            raise ValueError("reference identity, symbol and source must be present")
    if not ref.instrument_id.map(lambda value: isinstance(value, str)).all():
        raise ValueError("instrument IDs must be strings")
    for field in ("symbol", "exchange"):
        ref[field] = ref[field].str.strip().str.upper()
    observed = ref.observed_at.map(pd.Timestamp)
    if any(pd.isna(t) or t.tz is None for t in observed):
        raise ValueError("observed_at must be aware instants")
    ref["observed_at"] = pd.to_datetime(observed, utc=True)
    ref["effective_date"] = _labels(ref.effective_date)
    ref = ref.loc[(observed <= cutoff) & (ref.effective_date <= pd.Timestamp(as_of))]
    if ref.duplicated(["instrument_id", "effective_date", "observed_at"]).any():
        raise ValueError("duplicate reference version")
    ref = ref.sort_values(["instrument_id", "effective_date", "observed_at"]).drop_duplicates(
        "instrument_id", keep="last")
    panel = bars[["instrument_id", "Date", "Close", "Volume"]].copy()
    panel["Date"] = _labels(panel.Date)
    panel = panel.loc[panel.Date <= pd.Timestamp(as_of)]
    if panel.duplicated(["instrument_id", "Date"]).any():
        raise ValueError("duplicate instrument/session bar")
    groups = dict(tuple(panel.groupby("instrument_id", sort=False)))
    recent = trading_days(as_of - pd.Timedelta(days=10), as_of)
    last = recent[-1]
    rows = []
    for item in ref.itertuples(index=False):
        reasons = []
        if item.exchange not in US_EXCHANGES:
            reasons.append("venue_not_permitted")
        if item.asset_type not in {"common_stock", "etf"}:
            reasons.append("security_type_not_permitted")
        if not (_false(item.leveraged) and _false(item.inverse)):
            reasons.append("leveraged_or_inverse_or_unknown")
        listed = _labels(pd.Series([item.listed_on])).iloc[0]
        if listed.date() > as_of:
            reasons.append("not_listed")
        if pd.notna(item.delisted_on) and str(item.delisted_on).strip():
            if _labels(pd.Series([item.delisted_on])).iloc[0].date() <= as_of:
                reasons.append("delisted")
        history = groups.get(item.instrument_id, panel.iloc[0:0])
        history = history.loc[history.Date >= listed].sort_values("Date")
        if len(history) < policy.min_sessions:
            reasons.append("insufficient_history")
        last_label = history.Date.iloc[-1].date() if len(history) else None
        if last_label != last:
            reasons.append("stale_bar")
        tail = history.tail(max(policy.min_sessions, policy.liquidity_window))
        if len(tail):
            expected = trading_days(tail.Date.iloc[0].date(), last)
            if tail.Date.dt.date.tolist() != expected:
                reasons.append("missing_sessions")
        values = tail[["Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
        valid = bool(len(values) and np.isfinite(values.to_numpy()).all()
                     and (values.Close > 0).all() and (values.Volume >= 0).all())
        with np.errstate(over="ignore", invalid="ignore"):
            dollar = values.Close * values.Volume
            valid = valid and bool(np.isfinite(dollar.to_numpy()).all())
            median = float(dollar.tail(policy.liquidity_window).median()) if valid else None
        if median is not None and not np.isfinite(median):
            valid, median = False, None
        if not valid:
            reasons.append("invalid_bars")
        elif values.Close.iloc[-1] < policy.min_price:
            reasons.append("price_below_floor")
        if median is None or median < policy.min_median_dollar_volume:
            reasons.append("illiquid")
        rows.append(dict(instrument_id=item.instrument_id, symbol=item.symbol, asset_type=item.asset_type,
                         candidate=not reasons, reasons=";".join(reasons), as_of=str(as_of),
                         last_session=str(last_label) if last_label else "", median_dollar_volume=median,
                         reference_source=item.source))
    result = pd.DataFrame(rows, columns=OUTPUT_COLUMNS).reset_index(drop=True)
    active = ~result.reasons.str.contains(r"(?:^|;)(?:delisted|not_listed)(?:;|$)")
    symbols = result.loc[active, "symbol"]
    for i in symbols.index[symbols.duplicated(keep=False)]:
        result.at[i, "candidate"] = False
        result.at[i, "reasons"] = (result.at[i, "reasons"] + ";ambiguous_symbol").lstrip(";")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=LABEL)
    for name in ("reference", "bars", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--price-basis", choices=["raw"], required=True)
    parser.add_argument("--min-sessions", type=int, required=True)
    parser.add_argument("--min-price", type=float, required=True)
    parser.add_argument("--min-dollar-volume", type=float, required=True)
    parser.add_argument("--liquidity-window", type=int, default=20)
    args = parser.parse_args(argv)
    policy = dict(min_sessions=args.min_sessions, min_price=args.min_price,
                  min_median_dollar_volume=args.min_dollar_volume, liquidity_window=args.liquidity_window)
    try:
        reference, prices = args.reference.read_bytes(), args.bars.read_bytes()
        from io import BytesIO
        frame = build_candidates(pd.read_csv(BytesIO(reference), dtype={"instrument_id": str}),
                                 pd.read_csv(BytesIO(prices), dtype={"instrument_id": str}),
                                 as_of=args.as_of, price_basis=args.price_basis, **policy)
        output = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
        receipt = dict(label=LABEL, as_of=str(args.as_of), policy=asdict(ScreenPolicy(**policy)),
                       price_basis=args.price_basis, reference_sha256=hashlib.sha256(reference).hexdigest(),
                       bars_sha256=hashlib.sha256(prices).hexdigest(),
                       candidates_sha256=hashlib.sha256(output).hexdigest(), candidate_count=int(frame.candidate.sum()),
                       known_instrument_count=len(frame), limitations=LIMITATIONS)
        receipt["implementation_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        receipt["run_id"] = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
        receipt["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
        target = args.out.absolute()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            raise FileExistsError(target)
        with TemporaryDirectory(prefix=".qmb-inventory-", dir=target.parent) as temporary:
            stage = Path(temporary)
            (stage / "candidates.csv").write_bytes(output)
            (stage / "receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8")
            if target.exists() or target.is_symlink():
                raise FileExistsError(target)
            stage.rename(target)
    except (OSError, ValueError, KeyError, TypeError):
        print("Candidate inventory refused; inspect input schema, policy and output location.", file=sys.stderr)
        return 2
    print(json.dumps(receipt | {"receipt": str(args.out / "receipt.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
