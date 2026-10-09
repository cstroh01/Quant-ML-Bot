"""Spec 044 P-1 determination probe. Camden-run, network, once. Not a test.

Imports yfinance, pandas, the stdlib and p1_rules.py beside it, never scripts/.
Applies spec 044 section 5's registered rules (p1_rules.py) mechanically and
prints PASS or STOP per question. Writes the summary to p1-determination.txt
beside this file, and the raw provider rows behind every decision to
data/cache/spec044_p1/ (gitignored market data; the summary records its
SHA-256). Reads docs/trials/ only to hash it.

Usage: python p1_probe.py --self-check           offline Rule 12 proof; no network, no writes
       python p1_probe.py --revision <full sha>  network, once
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import math
import re
import sys
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from p1_rules import (DECLARED, HERE, NEW_YORK, QUESTIONS, RANGES, BASKET, VOLUME_WINDOW, d3_googl, horizon,
                      keep, later_split_factor, q_p1, q_p2, q_p3, q_p4, read_inputs, sessions, splits,
                      volume_step_label)

REPO = HERE.parents[3]
LEDGER = (REPO / "docs" / "trials" / "trials.jsonl", REPO / "docs" / "trials" / "trials.head.json")
OUT = HERE / "p1-determination.txt"
RAW = REPO / "data" / "cache" / "spec044_p1" / "p1-raw-rows.csv"


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "ABSENT"


def full_sha(value: str) -> str:
    """The revision label must be a full 40-hex commit sha (043 review F7); anything else is refused."""
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise argparse.ArgumentTypeError(f"--revision needs a full 40-hex commit sha, got {value!r}")
    return value


def fetch(ticker: str) -> pd.DataFrame:
    return yf.Ticker(ticker).history(period="max", interval="1d", auto_adjust=False, actions=True)


def determine(source, started: datetime, questions=QUESTIONS):
    """Every decision run() records, with no network or writes of its own; `source(ticker)` is the only input."""
    lines, raw, summary = ["--- Provider split tables (this response) ---"], [], []
    try:
        histories = {ticker: sessions(source(ticker), ticker) for ticker in BASKET}
        coverage = horizon(histories, started)
    except Exception as error:  # fail closed: a bad response is a recorded STOP
        histories, coverage = {}, ("STOP", f"{type(error).__name__}: {error}")
    summary.append(f"Horizon: {coverage[0]} - {coverage[1]}")
    for ticker, history in histories.items():
        lines.append(f"{ticker}: splits {[(d.date().isoformat(), r) for d, r in splits(history).items()]}")
        keep(raw, "splits", ticker, history.loc[splits(history).index])
    for name, question in questions:
        lines.append(f"--- {name} ---")
        if coverage[0] != "PASS":
            status, reason = "STOP", "response horizon or coverage not established"
        else:
            try:
                status, reason = question(histories, lines, raw)
            except Exception as error:  # fail closed: an error is a STOP, never a pass
                status, reason = "STOP", f"{type(error).__name__}: {error}"
        summary.append(f"{name}: {status} - {reason}")
    return summary, lines, raw


def run(revision: str) -> None:
    before = {path.name: sha256(path) for path in LEDGER}
    inputs = {name: sha256(HERE / name) for name in (RANGES[0], DECLARED[0])}
    started = datetime.now(timezone.utc)
    summary, lines, raw = determine(fetch, started)
    RAW.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.concat(raw, ignore_index=True) if raw else pd.DataFrame()
    frame.to_csv(RAW, index=False)
    after = {path.name: sha256(path) for path in LEDGER}
    header = [
        "Spec 044 P-1 determination (spec.md section 5). No strategy result is produced or claimed here.",
        f"Run (UTC): {started.isoformat()}  revision: {revision}",
        f"yfinance {yf.__version__}  pandas {pd.__version__}  call: history(period=max, interval=1d, "
        "auto_adjust=False, actions=True)",
        *(f"input {name}: sha256 {digest}" for name, digest in inputs.items()),
        f"raw rows: {RAW.relative_to(REPO).as_posix()} ({len(frame)} rows, gitignored) sha256 {sha256(RAW)}",
        *(f"ledger {name}: before {before[name]} after {after[name]}" for name in before),
        f"ledger unchanged: {before == after}",
        "--- Summary ---", *summary,
    ]
    OUT.write_text("\n".join(header + lines) + "\n", encoding="utf-8")
    print("\n".join(summary) + f"\nwrote {OUT}")


def flat_volume_split(ticker: str) -> pd.DataFrame:
    """EXAMPLE — NOT A RESULT. One 4:1 split with flat volume either side of it."""
    w = VOLUME_WINDOW
    days = pd.bdate_range("2020-01-02", periods=2 * w + 1)
    frame = pd.DataFrame({"Volume": 1000.0, "Stock Splits": 0.0, "Dividends": 0.0}, index=days)
    frame.iloc[w, frame.columns.get_loc("Stock Splits")] = 4.0
    return sessions(frame, ticker)


def provider(days, close, stock_splits=None, dividends=None) -> pd.DataFrame:
    """EXAMPLE — NOT A RESULT. A minimal provider-shaped frame on the given session labels."""
    zeros = [0.0] * len(days)
    return sessions(pd.DataFrame({"Close": close, "Adj Close": close, "Dividends": dividends or zeros,
                                  "Stock Splits": stock_splits or zeros}, index=pd.to_datetime(days)), "SELF")


def csv(spec: tuple, *rows: str) -> io.StringIO:
    """EXAMPLE — NOT A RESULT. An in-memory input file with the registered header."""
    return io.StringIO("\n".join([",".join(spec[1]), *rows]) + "\n")


def self_check() -> int:
    """Each planted defect must STOP, raise or be refused; each control must PASS. Offline; writes nothing."""
    days = pd.to_datetime(["2024-03-07", "2024-03-08", "2024-03-11"])  # spans the 2024-03-10 DST change
    good = pd.DataFrame({"Close": [100.0, 100.0, 99.0], "Adj Close": [99.0, 99.0, 99.0],
                         "Dividends": [0.0, 0.0, 1.0], "Stock Splits": [0.0, 0.0, 0.0]}, index=days)
    nan_adj = good.copy()
    nan_adj.loc[days[1], "Adj Close"] = math.nan
    bad_split = good.copy()
    bad_split.loc[days[0], "Stock Splits"] = math.nan
    zoned = good.set_axis(days.tz_localize(NEW_YORK))
    four = pd.DataFrame({"Stock Splits": [0.0, 2.0, 0.0, 4.0]}, index=pd.date_range("2024-01-02", periods=4))

    def raises(frame):
        try:
            sessions(frame, "SELF")
        except ValueError:
            return True
        return False

    friday = {"X": good.iloc[:2]}
    # R2: five basket-sized splits whose median-step diagnostics agree unanimously.
    # The pre-amendment rule returned PASS ("adjusted") here; a verified basis must not.
    unanimous, diagnostics = {t: flat_volume_split(t) for t in "ABCDE"}, []
    q_p4_status, q_p4_reason = q_p4(unanimous, diagnostics, [])
    cases = [
        ("Q-P2 control", q_p2({"X": good}, [], [])[0], "PASS"),
        ("Q-P2 NaN Adj Close (R1)", q_p2({"X": nan_adj}, [], [])[0], "STOP"),
        ("split NaN refused (R4)", raises(bad_split), True),
        ("split control accepted", raises(good), False),
        ("zone dropped, date kept (R9)", list(sessions(zoned, "SELF").index) == list(days), True),
        ("F literal 8,4,4,1 (R8)", list(later_split_factor(four)), [8.0, 4.0, 4.0, 1.0]),
        ("volume step adjusted-looking", volume_step_label(1.0, 4.0), "adjusted"),
        ("volume step nominal-looking", volume_step_label(4.0, 4.0), "nominal"),
        ("volume step between bands", volume_step_label(2.5, 4.0), "inconclusive"),
        ("volume step NaN (R1)", volume_step_label(math.nan, 4.0), "inconclusive"),
        ("Q-P4 precondition: 5 unanimous diagnostics", [line.endswith("diagnostic adjusted")
                                                         for line in diagnostics], [True] * 5),
        ("Q-P4 unanimous diagnostics stay unverified (R2)", q_p4_status, "STOP"),
        ("Q-P4 names provider_unverified (R2)", "provider_unverified" in q_p4_reason, True),
        ("horizon weekend lag", horizon(friday, datetime(2024, 3, 11, 14, tzinfo=timezone.utc))[0], "PASS"),
        ("horizon stale", horizon(friday, datetime(2024, 3, 13, 22, tzinfo=timezone.utc))[0], "STOP"),
    ]
    # F3: Q-P1, Q-P3, D-3 and read_inputs on offline fixtures, each with a control.
    filed = provider(["2020-01-02", "2020-03-31", "2020-06-01", "2020-09-01"], [100.0] * 4, [0.0, 0.0, 2.0, 2.0])
    q1_row = "AAPL,2020-01-01,2020-03-31,390,410,10-Q,2020-04-30,0000000000-20-000001,https://example.invalid/q"
    paid = provider(["2024-01-02", "2024-06-10"], [100.0, 100.0], [0.0, 4.0], [0.01, 0.0])
    # The required case is 2024-03-05 (last dividend before the split); q3_row declares only 2024-01-02,
    # a row that alone would PASS, so only the required-case gate can stop it (T002a, Rule 12).
    two_paid = provider(["2024-01-02", "2024-03-05", "2024-06-10"], [100.0] * 3, [0.0, 0.0, 4.0], [0.01, 0.01, 0.0])
    q3_row = "NVDA,2024-01-02,0.04,not_applicable,2023-12-01,8-K,0000000000-23-000001,https://example.invalid/d"
    googl = {"GOOGL": provider(["2014-03-27", "2015-01-02"], [100.0, 100.0], [2.0, 0.0])}
    odd = {"GOOGL": provider(["2014-03-27", "2015-01-02"], [100.0, 100.0], [2.002, 0.0])}

    def rejects(*rows):
        return read_inputs(DECLARED, ["ex_date", "declared_date"], csv(DECLARED, *rows))[0] is None

    def refuses(revision):  # through the real CLI parser, so the type= wiring is covered too
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                parser().parse_args(["--revision", revision])
        except SystemExit:
            return True
        return False

    same_day = provider(["2024-01-02", "2024-06-10"], [100.0, 100.0], [0.0, 4.0], [0.01, 0.01])
    split_row = "NVDA,2024-06-10,0.04,pre_split,2024-05-22,8-K,0000000000-24-000001,https://example.invalid/s"

    def q3(history, *rows):
        return q_p3({"NVDA": history}, [], [], csv(DECLARED, *rows))[0]

    def q1(row):
        return q_p1({"AAPL": filed}, [], [], csv(RANGES, row))[0]

    # F3: run()'s decision core end to end, through determine() with an offline source.
    def boom(*_):
        raise RuntimeError("planted question error")

    probes = (("boom", boom), ("pass", lambda *_: ("PASS", "control")))
    nan_dividend = good.copy()
    nan_dividend.loc[days[0], "Dividends"] = math.nan

    def statuses(source, instant):
        return [line.split(" - ")[0] for line in determine(source, instant, probes)[0]]

    after_close = datetime(2024, 3, 11, 22, tzinfo=timezone.utc)
    cases += [
        ("horizon future-dated response (F2)", horizon({"X": good}, datetime(2024, 3, 11, 14, tzinfo=timezone.utc))[0],
         "STOP"),
        ("dividend NaN refused (F8)", raises(nan_dividend), True),
        ("dividend negative refused (F8)", raises(good.assign(Dividends=[0.0, -0.5, 0.0])), True),
        ("dividend infinite refused (F8)", raises(good.assign(Dividends=[0.0, math.inf, 0.0])), True),
        ("Q-P1 control", q_p1({"AAPL": filed}, [], [], csv(RANGES, q1_row))[0], "PASS"),
        # A wide filed range holds provider (100) and rebuilt (400) closes alike: it cannot discriminate.
        ("Q-P1 provider inside the range (F3)", q_p1({"AAPL": filed}, [], [], csv(RANGES, q1_row.replace(
            ",390,", ",99,")))[0], "STOP"),
        ("Q-P1 filed after the split (F3)", q_p1({"AAPL": filed}, [], [], csv(RANGES, q1_row.replace(
            "2020-04-30", "2020-06-01")))[0], "STOP"),
        ("Q-P3 control", q_p3({"NVDA": paid}, [], [], csv(DECLARED, q3_row))[0], "PASS"),
        ("Q-P3 required case missing (F3)", q_p3({"NVDA": two_paid}, [], [], csv(DECLARED, q3_row))[1].split(":")[0],
         "required cases have no declared row"),
        ("Q-P1 rebuilt outside the range (F3)", q1(q1_row.replace(",390,410,", ",490,510,")), "STOP"),
        ("Q-P1 low above high (F3)", q1(q1_row.replace(",390,410,", ",403,397,")), "STOP"),
        ("Q-P1 one later split only (F3)", q1("AAPL,2020-06-01,2020-08-31,195,205,10-Q,2020-07-30,"
                                             "0000000000-20-000002,https://example.invalid/q"), "STOP"),
        ("Q-P1 RANGES form 8-K refused (F7)", q1(q1_row.replace("10-Q", "8-K")), "STOP"),
        ("Q-P3 same-day control", q3(same_day, q3_row, split_row), "PASS"),
        ("Q-P3 same-day basis disagrees (F3)", q3(same_day, q3_row, split_row.replace("pre_split", "post_split")),
         "STOP"),
        ("Q-P3 declared after ex-date (F3)", q3(paid, q3_row.replace("2023-12-01", "2024-01-05")), "STOP"),
        ("Q-P3 amount fits neither basis (F3)", q3(paid, q3_row.replace("0.04", "0.02")), "STOP"),
        ("Q-P3 share_basis off a split day (F3)", q3(paid, q3_row.replace("not_applicable", "pre_split")), "STOP"),
        ("D-3 control", d3_googl(googl, [], [])[0], "PASS"),
        ("D-3 no pre-2016 split (F3)", d3_googl({"GOOGL": provider(["2016-01-04", "2016-01-05"], [1.0, 1.0])},
                                                [], [])[0], "STOP"),
        ("D-3 unclean ratio (F3)", d3_googl(odd, [], [])[0], "STOP"),
        ("read_inputs control", rejects(q3_row), False),
        ("read_inputs blank accession (F7)", rejects(q3_row.replace("0000000000-23-000001", " ")), True),
        ("read_inputs empty accession (F7)", rejects(q3_row.replace("0000000000-23-000001", "")), True),
        ("read_inputs duplicate key, unpadded date (F7)", rejects(q3_row, q3_row.replace("2024-01-02", "2024-1-2")),
         True),
        ("read_inputs invalid form (F7)", rejects(q3_row.replace("8-K", "S-1")), True),
        ("read_inputs duplicate key (F7)", rejects(q3_row, q3_row.replace("0.04", "0.05")), True),
        ("read_inputs off-basket ticker (F7)", rejects(q3_row.replace("NVDA", "TSLA")), True),
        ("revision full sha accepted", refuses("0123456789abcdef" * 2 + "01234567"), False),
        ("revision short sha refused (F7)", refuses("d8adac3"), True),
        ("revision sha with a suffix refused (F7)", refuses("0123456789abcdef" * 2 + "01234567-dirty"), True),
        ("run control", statuses(lambda _: good, after_close), ["Horizon: PASS", "boom: STOP", "pass: PASS"]),
        ("run future-dated response (F2)", statuses(lambda _: good, after_close.replace(hour=14)),
         ["Horizon: STOP", "boom: STOP", "pass: STOP"]),
        ("run NaN dividend (F8)", statuses(lambda t: nan_dividend if t == "MSFT" else good, after_close),
         ["Horizon: STOP", "boom: STOP", "pass: STOP"]),
    ]
    for name, got, expected in cases:
        print(f"{'ok  ' if got == expected else 'FAIL'} {name}: got {got!r}, expected {expected!r}")
    return 1 if any(got != expected for _, got, expected in cases) else 0


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Spec 044 P-1 determination probe")
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--revision", type=full_sha, help="full 40-hex commit sha of the tree run from")
    mode.add_argument("--self-check", action="store_true", help="offline proof of the probe's own gates")
    return cli


def main() -> None:
    args = parser().parse_args()
    if args.self_check:
        sys.exit(self_check())
    run(args.revision)


if __name__ == "__main__":
    main()
