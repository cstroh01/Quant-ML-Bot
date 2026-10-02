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
import math
import sys
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from p1_rules import (DECLARED, HERE, LEDGER, NEW_YORK, OUT, QUESTIONS, RANGES, RAW, REPO, BASKET,
                      VOLUME_WINDOW, horizon, keep, later_split_factor, q_p2, q_p4, sessions, sha256,
                      splits, volume_step_label)


def run(revision: str) -> None:
    before = {path.name: sha256(path) for path in LEDGER}
    inputs = {name: sha256(HERE / name) for name in (RANGES[0], DECLARED[0])}
    started = datetime.now(timezone.utc)
    lines, raw, summary = ["--- Provider split tables (this response) ---"], [], []
    try:
        histories = {ticker: sessions(yf.Ticker(ticker).history(
            period="max", interval="1d", auto_adjust=False, actions=True), ticker) for ticker in BASKET}
        coverage = horizon(histories, started)
    except Exception as error:  # fail closed: a bad response is a recorded STOP
        histories, coverage = {}, ("STOP", f"{type(error).__name__}: {error}")
    summary.append(f"Horizon: {coverage[0]} - {coverage[1]}")
    for ticker, history in histories.items():
        lines.append(f"{ticker}: splits {[(d.date().isoformat(), r) for d, r in splits(history).items()]}")
        keep(raw, "splits", ticker, history.loc[splits(history).index])
    for name, question in QUESTIONS:
        lines.append(f"--- {name} ---")
        if coverage[0] != "PASS":
            status, reason = "STOP", "response horizon or coverage not established"
        else:
            try:
                status, reason = question(histories, lines, raw)
            except Exception as error:  # fail closed: an error is a STOP, never a pass
                status, reason = "STOP", f"{type(error).__name__}: {error}"
        summary.append(f"{name}: {status} - {reason}")
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


def self_check() -> int:
    """Each planted defect must STOP or raise; each control must PASS. Offline; writes nothing."""
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
    for name, got, expected in cases:
        print(f"{'ok  ' if got == expected else 'FAIL'} {name}: got {got!r}, expected {expected!r}")
    return 1 if any(got != expected for _, got, expected in cases) else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Spec 044 P-1 determination probe")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--revision", help="full commit sha of the tree run from")
    mode.add_argument("--self-check", action="store_true", help="offline proof of the probe's own gates")
    args = parser.parse_args()
    if args.self_check:
        sys.exit(self_check())
    run(args.revision)


if __name__ == "__main__":
    main()
