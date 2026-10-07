"""049 T011: render existing paper-run JSONL as Markdown on stdout.

Reads the supplied log only. No broker, strategy evaluation, ledger write,
or inferred performance. Every report names its source line and recorded run
date; normal records retain their disclosure verbatim. Abort records produced
by the prototype lack a disclosure and are explicitly marked as such.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


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
        disclosure = "Disclosure: not recorded in the aborted input. No performance result."
    if not isinstance(disclosure, str):
        raise ValueError("disclosure must be text")

    decision = record.get("decision", {})
    actions = record.get("actions", [])
    reconciliation = record.get("reconciliation", [])
    if not isinstance(decision, dict) or any(not isinstance(row, dict) for row in decision.values()):
        raise ValueError("decision must map tickers to objects")
    if not isinstance(actions, list) or not isinstance(reconciliation, list):
        raise ValueError("actions and reconciliation must be lists")
    example_label = "EXAMPLE \u2014 NOT A RESULT"
    placeholder = "placeholder" in str(record.get("equity_source", "")).lower()
    label = example_label if record.get("mode") == "offline_example" or placeholder else ""
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


def render_log(path: Path) -> str:
    """Return one ordered report per nonblank JSONL line; name invalid lines."""
    path = path.resolve()
    reports = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            source = f"{path}:{number}"
            try:
                reports.append(render_run(json.loads(line), source=source))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{source}: {exc}") from exc
    return "\n---\n\n".join(reports)


def main(argv: list[str] | None = None) -> int:
    """Read an explicit log path and print Markdown; never create output files."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log", type=Path, help="existing paper-run JSONL path")
    args = parser.parse_args(argv)
    try:
        report = render_log(args.log)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
