"""Spec 044 P-1 registered rules: session labels, inputs, horizon and Q-P1..D-3.

Pure decision logic; no network, no writes. The CLI (`--self-check`, `--revision`)
is p1_probe.py beside this file, which imports this module. Split from the
original single-file probe for SC-007's 300-line cap (044 R10 / 043 review F6).
Imports pandas and the stdlib only, never scripts/.
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LEDGER = (REPO / "docs" / "trials" / "trials.jsonl", REPO / "docs" / "trials" / "trials.head.json")
OUT = HERE / "p1-determination.txt"
RAW = REPO / "data" / "cache" / "spec044_p1" / "p1-raw-rows.csv"
BASKET = ("AAPL", "AMZN", "GOOGL", "MSFT", "NVDA")
RANGES = ("p1-filed-ranges.csv",
          ["ticker", "quarter_start", "quarter_end", "low", "high", "form", "filed_date", "accession", "source_url"])
DECLARED = ("p1-declared-dividends.csv",
            ["ticker", "ex_date", "declared_amount", "share_basis", "declared_date", "form", "accession", "source_url"])
RANGE_BAND = 0.01  # Q-P1, registered
ADJ_CLOSE_TOL = 1e-4  # Q-P2, registered
DIVIDEND_TOL = 1e-3  # Q-P3, registered
VOLUME_WINDOW, VOLUME_MIN_RATIO = 60, 4.0  # Q-P4 diagnostic only (spec section 5, amended 2026-10-02)
NEW_YORK = ZoneInfo("America/New_York")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "ABSENT"


def positive(values) -> bool:
    """True only if there is at least one value and every value is finite and > 0."""
    series = pd.Series(values, dtype="float64").reset_index(drop=True)
    return len(series) > 0 and bool((series.map(math.isfinite) & (series > 0)).all())


def later_split_factor(history: pd.DataFrame) -> pd.Series:
    """F(t): product of this response's split ratios strictly after t."""
    ratios = history["Stock Splits"].where(history["Stock Splits"] > 0, 1.0)
    return ratios[::-1].cumprod()[::-1] / ratios


def splits(history: pd.DataFrame) -> pd.Series:
    return history["Stock Splits"][history["Stock Splits"] > 0]


def sessions(history: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Naive midnight labels (zone dropped, wall date kept, never UTC); split events validated, none discarded."""
    if history.empty:
        raise ValueError(f"{ticker}: provider returned no rows")
    index = pd.DatetimeIndex(history.index)
    history = history.copy()
    history.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    if history.index.duplicated().any() or not history.index.is_monotonic_increasing:
        raise ValueError(f"{ticker}: session labels are not unique and ascending")
    ratios = history["Stock Splits"]
    if not (ratios.map(math.isfinite).all() and (ratios >= 0).all()):
        raise ValueError(f"{ticker}: a split value is missing, infinite or negative (0 alone means no split)")
    if not positive(later_split_factor(history)):
        raise ValueError(f"{ticker}: cumulative split factor is not finite and positive")
    return history


def keep(raw: list, question: str, ticker: str, frame: pd.DataFrame, factor=None) -> None:
    rows = frame.assign(question=question, ticker=ticker, factor=math.nan if factor is None else factor)
    raw.append(rows.rename_axis("session").reset_index())


def read_inputs(spec: tuple, dates: list[str]):
    name, columns = spec
    path = HERE / name
    if not path.exists():
        return None, f"{name} missing"
    frame = pd.read_csv(path, dtype=str)
    if list(frame.columns) != columns:
        return None, f"{name} header is not {columns}"
    if frame.empty:
        return None, f"{name} has no rows"
    for column in dates:
        frame[column] = pd.to_datetime(frame[column], format="%Y-%m-%d")
    return frame, ""


def horizon(histories: dict, now_utc: datetime):
    """Coverage: every response ends on one session within 1 completed weekday of the as-of instant."""
    lasts = {ticker: history.index[-1] for ticker, history in histories.items()}
    if len(set(lasts.values())) != 1:
        return "STOP", f"responses end on different sessions: {lasts}"
    now = now_utc.astimezone(NEW_YORK)  # an instant crossing into session space, explicitly
    completed = pd.Timestamp(now.date())
    if now.weekday() >= 5 or now.time() < time(16, 0):
        completed -= pd.offsets.BDay(1)
    last = next(iter(lasts.values()))
    lag = len(pd.bdate_range(last + pd.Timedelta(days=1), completed))
    verdict = "PASS" if lag <= 1 else "STOP"
    return verdict, f"responses end {last.date()}; last completed weekday {completed.date()}; lag {lag} (max 1)"


def q_p1(histories, lines, raw):
    ranges, why = read_inputs(RANGES, ["quarter_start", "quarter_end", "filed_date"])
    if ranges is None:
        return "STOP", why
    cumulative = False
    for row in ranges.itertuples(index=False):
        label = f"{row.ticker} {row.quarter_start.date()}..{row.quarter_end.date()}"
        low, high = float(row.low), float(row.high)
        if row.form not in ("10-K", "10-Q") or not positive([low, high]) or low > high:
            return "STOP", f"{label}: form or filed range invalid"
        history = histories[row.ticker]
        later = splits(history).loc[row.quarter_end + pd.Timedelta(days=1):]
        if later.empty:
            return "STOP", f"{label}: no later split, so the row cannot discriminate"
        if row.filed_date >= later.index[0]:
            return "STOP", (f"{label}: filed {row.filed_date.date()}, not before the split on "
                            f"{later.index[0].date()}; a later filing restates ranges for splits")
        quarter = history.loc[row.quarter_start:row.quarter_end]
        factor = later_split_factor(history).loc[quarter.index]
        keep(raw, "Q-P1", row.ticker, quarter, factor)
        rebuilt = quarter["Close"] * factor
        if not (positive(quarter["Close"]) and positive(rebuilt)):
            return "STOP", f"{label}: missing or non-positive observation"
        band = (low * (1 - RANGE_BAND), high * (1 + RANGE_BAND))
        inside, outside = rebuilt.between(*band).all(), not quarter["Close"].between(*band).any()
        lines.append(f"{label} {row.form} {row.accession}: filed [{low}, {high}] rebuilt [{rebuilt.min():.6f}, "
                     f"{rebuilt.max():.6f}] provider [{quarter['Close'].min():.6f}, {quarter['Close'].max():.6f}]")
        if not (inside and outside):
            return "STOP", f"{label}: rebuilt inside={inside}, provider outside={outside}"
        cumulative |= len(later) >= 2
    if not cumulative:
        return "STOP", "no filed quarter precedes two splits; the cumulative product is untested"
    return "PASS", "rebuilt closes lie inside every pre-split filed range; provider closes do not"


def q_p2(histories, lines, raw):
    cases, missing = [], []
    for ticker, history in histories.items():
        paid = history.index[history["Dividends"] > 0]
        for ex in paid[paid >= pd.Timestamp("2016-01-01")]:
            position = history.index.get_loc(ex)
            if position == 0:
                missing.append(f"{ticker} {ex.date()} (no prior session)")
                continue
            pair = history.iloc[position - 1:position + 1]
            keep(raw, "Q-P2", ticker, pair)
            prior, current = pair.iloc[0], pair.iloc[1]
            observed = (prior["Adj Close"] / prior["Close"]) / (current["Adj Close"] / current["Close"])
            expected = 1 - current["Dividends"] / prior["Close"]
            if not positive([prior["Close"], prior["Adj Close"], current["Close"], current["Adj Close"],
                             observed, expected]):
                missing.append(f"{ticker} {ex.date()}")
                continue
            cases.append((ticker, ex.date(), observed, expected, prior["Close"] == prior["Adj Close"]))
    if missing:
        return "STOP", f"missing or non-positive observation at {missing[:5]}"
    if not cases:
        return "STOP", "no dividend ex-dates from 2016 on"
    if all(case[4] for case in cases):
        return "STOP", "Close equals Adj Close before every dividend: Close is dividend-adjusted"
    worst = max(cases, key=lambda case: abs(case[2] - case[3]))
    lines.append(f"{len(cases)} ex-dates; worst |observed-expected| {abs(worst[2] - worst[3]):.3e} at {worst[:2]}")
    bad = [case for case in cases if abs(case[2] - case[3]) > ADJ_CLOSE_TOL]
    if bad:
        return "STOP", f"{len(bad)} ex-dates deviate from 1 - D/prior Close by more than {ADJ_CLOSE_TOL}"
    return "PASS", "Close differs from Adj Close by the dividend factor: Close is not dividend-adjusted"


def required_dividend_cases(histories) -> set:
    """Registered coverage: last dividend before each split from 2016, and any dividend on a split ex-date."""
    required = set()
    for ticker, history in histories.items():
        paid = history.index[history["Dividends"] > 0]
        for day in splits(history).loc["2016-01-01":].index:
            if len(paid[paid < day]):
                required.add((ticker, paid[paid < day][-1]))
            if day in paid:
                required.add((ticker, day))
    return required


def q_p3(histories, lines, raw):
    declared, why = read_inputs(DECLARED, ["ex_date", "declared_date"])
    if declared is None:
        return "STOP", why
    rows = {(row.ticker, row.ex_date): row for row in declared.itertuples(index=False)}
    absent = sorted(f"{t} {d.date()}" for t, d in required_dividend_cases(histories) - rows.keys())
    if absent:
        return "STOP", f"required cases have no declared row: {absent}"
    verdicts, same_day = set(), []
    for (ticker, ex), row in sorted(rows.items()):
        history, label = histories[ticker], f"{ticker} {ex.date()}"
        on_split, amount = ex in splits(history).index, float(row.declared_amount)
        if row.share_basis not in (("pre_split", "post_split") if on_split else ("not_applicable",)):
            return "STOP", f"{label}: share_basis {row.share_basis!r} invalid for this ex-date"
        if row.declared_date > ex or not positive([amount]):
            return "STOP", f"{label}: declared after the ex-date, or amount invalid"
        if ex not in history.index or not positive([history.at[ex, "Dividends"]]):
            return "STOP", f"{label}: provider has no usable dividend on this ex-date"
        factor = later_split_factor(history)
        keep(raw, "Q-P3", ticker, history.loc[[ex]], factor.loc[[ex]])
        provider, f = float(history.at[ex, "Dividends"]), float(factor.at[ex])
        if row.share_basis == "pre_split":
            amount /= float(history.at[ex, "Stock Splits"])  # declared per pre-split share -> post-split share
        adjusted = abs(provider * f / amount - 1) <= DIVIDEND_TOL
        nominal = abs(provider / amount - 1) <= DIVIDEND_TOL
        lines.append(f"{label} {row.accession}: provider {provider} F {f:g} declared {row.declared_amount} "
                     f"({row.share_basis}) adjusted={adjusted} nominal={nominal}")
        if on_split:
            same_day.append((label, adjusted, nominal))
        if f != 1.0:
            verdicts.add("adjusted" if adjusted and not nominal else "nominal" if nominal and not adjusted
                         else "neither")
    if verdicts not in ({"adjusted"}, {"nominal"}):
        return "STOP", f"verdicts {sorted(verdicts) or 'none informative'}"
    verdict = verdicts.pop()
    resolved = [label for label, adjusted, nominal in same_day if (adjusted if verdict == "adjusted" else nominal)]
    unresolved = [label for label, *_ in same_day if label not in resolved]
    if unresolved:
        return "STOP", f"dividends {verdict}, but same-day cases disagree: {unresolved}"
    state = f"resolved by {resolved}" if resolved else "UNRESOLVED (no dividend on a split ex-date): FR-012 refuses"
    return "PASS", f"dividends are {verdict} (FR-004); same-day convention {state}"


def volume_step_label(step: float, ratio: float) -> str:
    """Diagnostic label for one post/pre median step. It never selects a volume_basis.

    Medians from different sessions confound share basis with trading activity
    (044 R2 / 043 review F1), so this label is recorded as evidence only.
    """
    if not (math.isfinite(step) and step > 0):
        return "inconclusive"
    if 0.5 <= step <= 2.0:
        return "adjusted"
    return "nominal" if abs(step / ratio - 1) <= 0.25 else "inconclusive"


def q_p4(histories, lines, raw):
    """Always inconclusive: FR-005's provider_unverified branch, with median steps kept as diagnostics.

    No same-observation or primary-source contract identifies the provider's
    Volume share basis, so no verified branch is selectable here, however
    unanimous the diagnostics are (spec section 5 Q-P4, amended 2026-10-02).
    """
    labels, w = [], VOLUME_WINDOW
    for ticker, history in histories.items():
        for ex, ratio in splits(history).loc["2016-01-01":].items():
            if ratio < VOLUME_MIN_RATIO:
                continue
            position, label = history.index.get_loc(ex), f"{ticker} {ex.date()} {ratio:g}:1"
            window = history.iloc[max(position - w, 0):position + w]
            keep(raw, "Q-P4", ticker, window)
            volume = window["Volume"]
            usable = volume.map(math.isfinite).all() and (volume >= 0).all()
            if position < w or position + w > len(history) or not usable:
                step = "inconclusive"
            else:
                pre = history["Volume"].iloc[position - w:position].median()
                post = history["Volume"].iloc[position:position + w].median()
                step = volume_step_label(post / pre if pre > 0 else math.nan, ratio)
                label += f": median pre {pre:.0f} post {post:.0f}"
            lines.append(f"{label} -> diagnostic {step}")
            labels.append(step)
    return "STOP", (f"inconclusive: {len(labels)} splits >= 4:1 from 2016, diagnostic steps {labels}. Medians across "
                    "different sessions cannot identify the share basis. volume_basis provider_unverified: Volume "
                    "passes through and is blocked from the cost model (FR-005); this STOP does not halt the spec")


def d3_googl(histories, lines, raw):
    early = splits(histories["GOOGL"]).loc[:"2015-12-31"]
    lines.append(f"GOOGL provider splits before 2016: {[(d.date().isoformat(), r) for d, r in early.items()]}")
    if early.empty:
        return "STOP", "no GOOGL split before 2016 in the provider table; windows from 2016 are unaffected"
    unclean = [r for r in early if not any(abs(r * q - round(r * q)) <= 1e-9 for q in range(1, 11))]
    if unclean:
        return "STOP", f"ratios {unclean} are not clean; GOOGL windows before them are refused (D-3)"
    return "PASS", "clean ratios; windows from 2016 never use them"


QUESTIONS = (("Q-P1", q_p1), ("Q-P2", q_p2), ("Q-P3", q_p3), ("Q-P4", q_p4), ("D-3", d3_googl))
