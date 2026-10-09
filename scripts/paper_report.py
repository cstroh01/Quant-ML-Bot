"""049 T011: render existing paper-run JSONL as a daily Markdown report.

Reads the supplied log only. No broker, strategy evaluation, ledger write,
or inferred performance: no return, Sharpe or equity change is ever computed.
Every report names its source line and recorded run date; normal records
retain their disclosure verbatim. Abort records produced by the prototype lack
a disclosure and are explicitly marked as such. The daily report carries the
Rule 16 block (run disclosures plus ``LIMITATIONS``) at its top and bottom, and
lists every malformed line instead of skipping it.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from _project import project_root

NY = ZoneInfo("America/New_York")
ABORT_DISCLOSURE = "Disclosure: not recorded in the aborted input. No performance result."
LIMITATIONS = (
    "Paper mechanics prototype. Not a performance result. Limitations (SCOPE-V1 §6, Rule 16): "
    "static survivor basket with no delisted names; free-tier corporate-action data; "
    "no point-in-time fundamentals; daily bars only; modeled, not fill-calibrated, costs."
)
CLEAN_OUTCOMES = ("SUBMITTED", "DRY_RUN")


def _label(record: dict) -> str:
    """Offline or placeholder-equity records are examples, never results."""
    example_label = "EXAMPLE \u2014 NOT A RESULT"
    placeholder = "placeholder" in str(record.get("equity_source", "")).lower()
    return example_label if record.get("mode") == "offline_example" or placeholder else ""


def log_path(profile: str | None) -> Path:
    """Default run log, or a profile namespace's log; the name is never a path."""
    base = project_root() / "data" / "live_safety"
    if profile is None:
        return base / "paper-runs" / "runs.jsonl"
    if profile in ("", ".", "..") or any(sep in profile for sep in "/\\:"):
        raise ValueError(f"profile must be a plain namespace name, got {profile!r}")
    return base / profile / "paper-runs" / "runs.jsonl"


def _cell(value: Any) -> str:
    if value is None:
        return "not recorded"
    return html.escape(str(value)).replace("\\", "\\\\").replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def _table(rows: list[dict], columns: list[str], *, label: str = "") -> list[str]:
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("table rows must be objects")
    if not rows:
        return ["No rows recorded."]
    if label:
        rows = [{**row, "Disclosure": label} for row in rows]
        columns = columns + ["Disclosure"]
    return ["| " + " | ".join(_cell(key) for key in columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
            *("| " + " | ".join(_cell(row.get(key)) for key in columns) + " |" for row in rows)]


def render_run(record: dict, *, source: str) -> str:
    """Render recorded fields only, without mutating the record.

    ``source`` identifies the input artifact and JSONL line. Missing values
    are labelled, never turned into a zero or a successful outcome.
    """
    if not isinstance(record, dict):
        raise ValueError("run record must be an object")
    if not source or not record.get("run_at_utc"):
        raise ValueError("source and run_at_utc are required")
    aborted = "aborted" in record
    disclosure = record.get("disclosure")
    if not aborted:
        for field in ("session", "mode", "safety_config_version", "decision", "actions", "reconciliation", "disclosure"):
            if field not in record:
                raise ValueError(f"missing {field}")
        if not isinstance(disclosure, str) or not disclosure.strip():
            raise ValueError("disclosure must be nonempty text")
    elif disclosure is None:
        disclosure = ABORT_DISCLOSURE
    if not isinstance(disclosure, str):
        raise ValueError("disclosure must be text")

    decision = record.get("decision", {})
    actions = record.get("actions", [])
    reconciliation = record.get("reconciliation", [])
    if not isinstance(decision, dict) or any(not isinstance(row, dict) for row in decision.values()):
        raise ValueError("decision must map tickers to objects")
    if not isinstance(actions, list) or not isinstance(reconciliation, list):
        raise ValueError("actions and reconciliation must be lists")
    label = _label(record)
    lines = ["# Paper run", "", f"Source: <code>{html.escape(source)}</code>",
             f"Run at UTC: {_cell(record['run_at_utc'])}",
             f"Session: {_cell(record.get('session'))}",
             f"Mode: {_cell(record.get('mode'))}",
             f"Equity source: {_cell(record.get('equity_source'))}",
             f"Safety configuration: {_cell(record.get('safety_config_version'))}", ""]
    if label:
        lines.append(label)
    lines.append(disclosure)
    if aborted:
        lines.extend(["", "## Aborted", "", _cell(record["aborted"])])
    lines.extend(["", "## Decisions", ""])
    rows = [{**values, "Ticker": ticker} for ticker, values in decision.items()]
    lines.extend(_table(rows, ["Ticker", "Confidence", "Volatility", "Target"], label=label))
    for title, entries, preferred in (
        ("Actions", actions, ["ticker", "delta_quantity", "target_weight", "outcome"]),
        ("Reconciliation", reconciliation, ["client_order_id", "broker_status"]),
    ):
        if any(not isinstance(row, dict) for row in entries):
            raise ValueError(f"{title} rows must be objects")
        columns = preferred + sorted({key for row in entries for key in row} - set(preferred))
        lines.extend(["", f"## {title}", "", *_table(entries, columns, label=label)])
    return "\n".join(lines) + "\n"


def read_log(path: Path) -> tuple[list[tuple[str, str, dict]], list[dict]]:
    """(source, New York run date, record) per valid line, and every invalid line.

    A line is valid only if ``render_run`` accepts it and its ``run_at_utc``
    carries a zone. Invalid lines are returned with their error, never dropped.
    """
    runs, malformed = [], []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            source = f"{path}:{number}"
            try:
                record = json.loads(line)
                render_run(record, source=source)
                stamp = datetime.fromisoformat(str(record["run_at_utc"]).replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("run_at_utc has no zone")
            except (ValueError, TypeError) as exc:
                malformed.append({"Line": source, "Error": str(exc)})
                continue
            runs.append((source, stamp.astimezone(NY).date().isoformat(), record))
    return runs, malformed


def _day_section(day: str, runs: list[tuple[str, dict]]) -> list[str]:
    summary, aborted, recon, groups, refusals = [], [], [], {}, []
    for source, record in runs:
        if "aborted" in record:
            aborted.append({"Source": source, "Run at UTC": record["run_at_utc"], "Reason": record["aborted"]})
            continue
        label = _label(record)
        summary.append({"Source": source, "Run at UTC": record["run_at_utc"], "Session": record["session"],
                        "Mode": record["mode"], "Profile": record.get("profile"), "Equity": record.get("equity"),
                        "Equity source": record.get("equity_source"),
                        "Safety config": record["safety_config_version"], "Label": label})
        recon.extend({"Source": source, **row} for row in record["reconciliation"])
        for action in record["actions"]:
            outcome = str(action.get("outcome") or "not recorded")
            entry = {"Source": source, **action, "outcome": outcome, "Label": label}
            groups.setdefault(outcome, []).append(entry)
            if outcome not in CLEAN_OUTCOMES:
                refusals.append(entry)
    action_cols = ["Source", "ticker", "delta_quantity", "target_weight", "client_order_id", "reason", "Label"]
    lines = ["", f"## {day} (New York run date)", "", "### Runs", "",
             *_table(summary, ["Source", "Run at UTC", "Session", "Mode", "Profile", "Equity",
                               "Equity source", "Safety config", "Label"]),
             "", "### Aborted runs", "", *_table(aborted, ["Source", "Run at UTC", "Reason"]),
             "", f"### Reconciliation ({len(recon)} rows)", "",
             *_table(recon, ["Source", "client_order_id", "broker_status"]), "", "### Actions by outcome"]
    for outcome in sorted(groups):
        lines.extend(["", f"#### {outcome} ({len(groups[outcome])})", "", *_table(groups[outcome], action_cols)])
    lines.extend(["", "### Refusals and unknown outcomes", "",
                  *_table(refusals, ["Source", "ticker", "outcome", "reason", "Label"])])
    return lines


def render_daily(path: Path, *, day: str | None = None) -> tuple[str, int]:
    """Markdown report per New York run date and the malformed-line count.

    The Rule 16 block (every distinct run disclosure plus ``LIMITATIONS``) is
    printed before the first and after the last section.
    """
    path = path.resolve()
    runs, malformed = read_log(path)
    if day is not None:
        runs = [run for run in runs if run[1] == day]
    disclosures = dict.fromkeys(r.get("disclosure") or ABORT_DISCLOSURE for _, _, r in runs)
    block = [f"> {LIMITATIONS}", *(f">\n> {text}" for text in disclosures)]
    lines = ["# Paper daily report", "", f"Source: <code>{html.escape(str(path))}</code>", "", *block]
    if malformed:
        lines.extend(["", f"## Malformed lines ({len(malformed)}, not rendered)", "",
                      *_table(malformed, ["Line", "Error"])])
    if not runs:
        lines.extend(["", "No run records" + (f" for {day}." if day else ".")])
    for current in sorted({run[1] for run in runs}):
        lines.extend(_day_section(current, [(s, r) for s, d, r in runs if d == current]))
    lines.extend(["", *block])
    return "\n".join(lines) + "\n", len(malformed)


def main(argv: list[str] | None = None) -> int:
    """Print (or write with ``--out``) the daily report. Exit 1 if any line is malformed."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log", type=Path, nargs="?", help="paper-run JSONL (default: the paper loop's log)")
    parser.add_argument("--profile", help="namespace: data/live_safety/<profile>/paper-runs/runs.jsonl")
    parser.add_argument("--date", help="New York run date YYYY-MM-DD (default: every date)")
    parser.add_argument("--out", type=Path, help="write the report here instead of stdout")
    args = parser.parse_args(argv)
    if args.log is not None and args.profile is not None:
        parser.error("give a log path or --profile, not both")
    try:
        path = (args.log or log_path(args.profile)).resolve()
        if args.date is not None:
            date.fromisoformat(args.date)
        if args.out is not None and args.out.resolve() == path:
            raise ValueError("--out must not overwrite the input log")
        report, malformed = render_daily(path, day=args.date)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.out is not None:
        args.out.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 1 if malformed else 0


if __name__ == "__main__":
    raise SystemExit(main())
