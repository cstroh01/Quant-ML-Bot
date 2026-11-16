"""Read-only daily health check for Quant-ML-Bot's unattended operation.

Guarantees: only issues read-only ``gh`` calls (``gh api`` GETs, ``gh run``,
``gh issue``/``gh pr`` list/view, ``gh variable list``); writes nothing to
either repository or to docs/trials; never prints account numbers,
fingerprints, keys or tokens (any JSON key matching those words is redacted).

Usage: python .claude/skills/daily-check/check.py [--hours N]
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

PUBLIC = "cstroh01/Quant-ML-Bot"
PRIVATE = "cstroh01/Quant-ML-Bot-private"
STATE_REF = "ops-state"
PREVIEW_TARGET = 5
SECRET_KEY = re.compile(r"account|fingerprint|acct|key|secret|token|password", re.I)


def gh(*args: str, check: bool = True) -> str:
    """Run gh and return stdout as text; on failure return '' unless check."""
    proc = subprocess.run(["gh", *args], capture_output=True)
    if proc.returncode != 0:
        if check:
            raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
        return ""
    return proc.stdout.decode("utf-8", "replace")


def gh_json(*args: str, check: bool = True):
    out = gh(*args, check=check)
    return json.loads(out) if out.strip() else None


def state_file(path: str) -> str | None:
    """Text of an ops-state file, decoded from .content (avoids CR mangling)."""
    meta = gh_json("api", f"repos/{PRIVATE}/contents/{path}?ref={STATE_REF}", check=False)
    if not meta or "content" not in meta:
        return None
    return base64.b64decode(meta["content"]).decode("utf-8", "replace")


def jsonl(path: str) -> list[dict]:
    text = state_file(path) or ""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def redact(obj):
    if isinstance(obj, dict):
        return {k: "<redacted>" if SECRET_KEY.search(k) else redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def et_today() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:  # no tzdata on this Python; EST is close enough for a date label
        return (datetime.now(timezone.utc) - timedelta(hours=5)).date().isoformat()


def section(title: str) -> None:
    print(f"\n## {title}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=30, help="look-back window for runs/issues")
    hours = ap.parse_args().hours
    sys.stdout.reconfigure(encoding="utf-8")
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    today = et_today()
    attention: list[str] = []

    print(f"# Daily check — {datetime.now(timezone.utc):%Y-%m-%d %H:%MZ} (ET session {today}, window {hours}h)")

    # --- pins -------------------------------------------------------------
    section("Pins")
    main_head = gh_json("api", f"repos/{PUBLIC}/commits/main")
    main_sha = main_head["sha"]
    print(f"public main      {main_sha[:7]}  {main_head['commit']['message'].splitlines()[0][:80]}")
    pins = {}
    for line in gh("variable", "list", "--repo", PRIVATE).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] in ("QMB_PINNED_SHA", "QMB_FIDELITY_PIN", "QMB_FIDELITY_PREVIEW_ENABLED",
                                            "QMB_FIDELITY_LIVE_ENABLED"):
            pins[parts[0]] = parts[1]
            print(f"{parts[0]:<29} {parts[1][:12]}  (set {parts[2][:10] if len(parts) > 2 else '?'})")
    fid_pin = pins.get("QMB_FIDELITY_PIN", "")
    if pins.get("QMB_PINNED_SHA") != fid_pin:
        attention.append("QMB_PINNED_SHA and QMB_FIDELITY_PIN differ")
    checks = gh_json("api", f"repos/{PUBLIC}/commits/{main_sha}/check-runs?per_page=100", check=False) or {}
    concl = Counter((c.get("conclusion") or c.get("status")) for c in checks.get("check_runs", []))
    print(f"public main CI   {dict(concl)}")
    if any(k in concl for k in ("failure", "cancelled", "timed_out")):
        attention.append(f"public main CI not green: {dict(concl)}")

    # --- halts --------------------------------------------------------------
    section("Halts")
    tree = gh_json("api", f"repos/{PRIVATE}/git/trees/{STATE_REF}?recursive=1")
    paths = [t["path"] for t in tree["tree"] if t["type"] == "blob"]
    halts = [p for p in paths if p.rsplit("/", 1)[-1] in ("HALTED", "KILL") and not p.startswith("drills/")]
    if halts:
        for p in halts:
            print(f"PRESENT: {p}")
            attention.append(f"halt file present: {p}")
    else:
        print("no HALTED or KILL in any namespace")

    # --- private runs -----------------------------------------------------
    section(f"Private runs (last {hours}h)")
    runs = gh_json("run", "list", "--repo", PRIVATE, "--limit", "100", "--json",
                   "databaseId,workflowName,conclusion,status,createdAt,event") or []
    recent = [r for r in runs if datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00")) >= since]
    by_wf: dict[str, Counter] = {}
    for r in recent:
        by_wf.setdefault(r["workflowName"], Counter())[r["conclusion"] or r["status"]] += 1
    for wf, c in sorted(by_wf.items()):
        print(f"{wf:<22} {dict(c)}")
    for r in recent:
        if r["conclusion"] not in ("success", "skipped", None, ""):
            print(f"  NOT OK: {r['databaseId']} {r['createdAt']} {r['workflowName']} {r['conclusion']}")
            attention.append(f"{r['workflowName']} run {r['databaseId']} {r['conclusion']}")
    if not any(r["workflowName"] == "paper-loop" for r in recent):
        attention.append("no paper-loop run in window")

    # --- issues -------------------------------------------------------------
    section("Issues")
    issues = gh_json("issue", "list", "--repo", PRIVATE, "--state", "open", "--limit", "100",
                     "--json", "number,title,createdAt") or []
    new = [i for i in issues if datetime.fromisoformat(i["createdAt"].replace("Z", "+00:00")) >= since]
    print(f"private open {len(issues)} (newest #{issues[0]['number'] if issues else '-'}), new in window {len(new)}")
    for i in new:
        print(f"  NEW #{i['number']} {i['title']}")
        attention.append(f"new private issue #{i['number']}: {i['title']}")
    prs = gh_json("pr", "list", "--repo", PUBLIC, "--state", "open", "--json", "number,title,author") or []
    print(f"public open PRs {len(prs)}: " + ", ".join(f"#{p['number']}" for p in prs))

    # --- Fidelity -------------------------------------------------------------
    section("Fidelity (live_fidelity)")
    sessions = sorted(p.rsplit("/", 1)[-1][:-5] for p in paths
                      if p.startswith("live_fidelity/preview-sessions/") and p.endswith(".json"))
    clean_at_pin = []
    for s in sessions:
        rec = json.loads(state_file(f"live_fidelity/preview-sessions/{s}.json") or "{}")
        ok = rec.get("clean") is True and not rec.get("challenge") and rec.get("place_calls", 0) == 0
        if ok and rec.get("pin_sha") == fid_pin:
            clean_at_pin.append(s)
        if s == today:
            print(f"today {s}: mode={rec.get('mode')} clean={rec.get('clean')} challenge={rec.get('challenge')} "
                  f"place_calls={rec.get('place_calls')} pin={str(rec.get('pin_sha'))[:7]}")
    if today not in sessions:
        print(f"today {today}: no preview-session record (yet)")
    print(f"clean preview sessions at current pin: {len(clean_at_pin)}/{PREVIEW_TARGET} {clean_at_pin}")
    manifest = state_file("live_fidelity/evidence/docs/implementation/spec-061/fidelity-preview/manifest.json")
    names: list[str] = []
    if manifest:
        names = [x["artifact"].rsplit("/", 1)[-1] for x in json.loads(manifest).get("sessions", [])]
        print(f"evidence manifest: {len(names)} sessions {names}")
    attempts_today = f"live_fidelity/attempts/{today}.json" in paths
    print(f"attempt marker today: {attempts_today}")
    fid_runs = [r for r in recent if r["workflowName"] == "fidelity-preview" and r["conclusion"] == "success"]
    for r in sorted(fid_runs, key=lambda r: r["createdAt"]):
        log = gh("run", "view", str(r["databaseId"]), "--repo", PRIVATE, "--log", check=False)
        line = next((l for l in log.splitlines() if "item 6: " in l and "print(" not in l), None)
        if line:
            print(f"run {r['databaseId']}: {line.split('item 6: ', 1)[1].strip()}")
    last = (jsonl("live_fidelity/runs.jsonl") or [None])[-1]
    if last:
        outcomes = Counter(a.get("outcome") for a in last.get("actions", []))
        print(f"last runs.jsonl: session={last.get('session')} mode={last.get('mode')} budget={last.get('budget')} "
              f"place_calls={last.get('place_calls')} outcomes={dict(outcomes)}")
        if last.get("aborted"):
            failure = last.get("failure") or {}
            print(f"  ABORTED: stage={failure.get('stage')} kind={failure.get('kind')} detail={failure.get('detail')}")
        if any(o not in ("PREVIEW", None) for o in outcomes) and last.get("mode") == "preview":
            attention.append(f"preview run had non-PREVIEW outcomes {dict(outcomes)}")
        if last.get("mode") == "submit":
            # LIVE (057 T011): only SUBMITTED and BUDGET_REFUSED are expected; every SUBMITTED is one placement.
            odd = {o: n for o, n in outcomes.items() if o not in ("SUBMITTED", "BUDGET_REFUSED")}
            if odd:
                attention.append(f"LIVE run had unexpected outcomes {odd}")
            if last.get("place_calls") != outcomes.get("SUBMITTED", 0):
                attention.append(f"LIVE place_calls {last.get('place_calls')} != SUBMITTED {outcomes.get('SUBMITTED', 0)}")
            for a in last.get("actions", []):
                print(f"  {str(a.get('outcome')):<15} {str(a.get('ticker')):<4} qty={a.get('delta_quantity')} "
                      f"notional=${float(a.get('notional') or 0):.2f} {a.get('reason') or ''}")
    book = json.loads(state_file("live_fidelity/bot-positions.json") or "{}")
    if book.get("orders") or book.get("positions"):
        unapplied = [o.get("symbol") for o in book.get("orders", {}).values() if not o.get("applied")]
        print(f"bot ledger: positions {book.get('positions')}; orders {len(book.get('orders', {}))}, "
              f"awaiting broker confirmation {unapplied or 'none'}")

    # --- PAPER -----------------------------------------------------------------
    for prof in ("paper_small", "paper_large"):
        section(f"PAPER {prof}")
        prs_runs = jsonl(f"{prof}/ops/runs.jsonl")
        if prs_runs:
            r = prs_runs[-1]
            print(f"last run: session={r.get('session')} status={r.get('status')} exit={r.get('exit_code')} "
                  f"version={str(r.get('strategy_version'))[:7]}")
            if r.get("exit_code") not in (0, None):
                attention.append(f"{prof} last run exit {r.get('exit_code')}")
            if r.get("session") != today:
                print(f"  (no run recorded for {today} yet)")
        incidents = jsonl(f"{prof}/ops/incidents.jsonl")
        print(f"incidents total {len(incidents)}; latest: {redact(incidents[-1]) if incidents else '-'}")
        fills = jsonl(f"{prof}/live_safety/{prof}/fills.jsonl")
        intents = jsonl(f"{prof}/live_safety/{prof}/intents.jsonl")
        todays = [i["intent"] for i in intents if i.get("intent", {}).get("session") == today]
        print(f"fills total {len(fills)}; latest: " + (
            f"{fills[-1].get('symbol')} {fills[-1].get('filled_qty')} @ {fills[-1].get('filled_avg_price')} "
            f"({fills[-1].get('filled_at', '')[:10]})" if fills else "-"))
        print(f"intents for {today}: " + (", ".join(
            f"{i.get('side')} {i.get('qty')} {i.get('ticker')} (${i.get('notional')})" for i in todays) or "none"))
        # A fill is recorded by the next session's run, so only earlier sessions can be overdue.
        filled = {f.get("client_order_id") for f in fills}
        overdue = [i["client_order_id"] for i in intents
                   if i.get("intent", {}).get("session", today) < today and i["client_order_id"] not in filled]
        if overdue:
            print(f"  UNFILLED from earlier sessions: {overdue}")
            attention.append(f"{prof}: {len(overdue)} earlier intent(s) with no recorded fill")

    # --- phase + attention ---------------------------------------------------
    section("Phase")
    gate = gh_json("api", f"repos/{PUBLIC}/contents/docs/implementation/spec-059/gate-manifest.json?ref={main_sha}",
                   check=False) or {}
    gate_items = set(json.loads(base64.b64decode(gate["content"])).get("items", {})) if gate.get("content") else set()
    live_on = pins.get("QMB_FIDELITY_LIVE_ENABLED") == "true" and pins.get("QMB_FIDELITY_PREVIEW_ENABLED") != "true"
    evidenced = len(names) if manifest else 0
    if live_on:
        print("C: LIVE armed; report outcomes, orders and positions only (no edge claim)")
    elif gate_items >= {str(i) for i in range(1, 8)}:
        print("B2: all 7 gate items on main; next per FINISH-RUNBOOK: repin, clear HALTED, install, arm")
    elif max(len(clean_at_pin), evidenced) >= PREVIEW_TARGET:
        print("B+: preview target reached; next is the final gate PR (items 1 and 7)")
    else:
        print(f"A: collecting Fidelity previews ({len(clean_at_pin)}/{PREVIEW_TARGET}); no repin, no merge needing one")
    section("Needs attention")
    print("\n".join(f"- {a}" for a in attention) if attention else "nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
