"""SCOPE §11.3 capital-gate checklist (spec 059 T008 / FR-007). Offline; prints, never arms.

Reads one evidence manifest (JSON) that names, for each §11.3 item, the artifact that evidences it
(a path inside the repository), that artifact's SHA-256, the commit it was produced at and its UTC
date (Rule 11: every figure carries its source). Prints every item with that evidence, and prints
``ARMABLE`` only when every item has evidence whose file exists and whose bytes hash to the recorded
digest. It never arms anything: LIVE arming stays Camden's action (spec 059 T010; Rule 7a).

Guarantees: items are the fixed list below, in §11.3's order; an item missing from the manifest, a
missing file, a digest mismatch, a malformed commit or date, or a path outside the repository makes
that item ``MISSING`` and the verdict ``NOT ARMABLE``. Exit status 0 only for ``ARMABLE``.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import sys

from _project import project_root

ROOT = project_root()
ITEMS = (
    ("1", "Full suite and mutation suites green on main (specs 012, 017, 019, 032, 033)"),
    ("2", "Spec 061 buffered allocation declared before its fresh costed trial; both baselines published"),
    ("3", "Safety layer in the PAPER and LIVE order paths; kill-switch and reset drills passed (spec 055)"),
    ("4", "PAPER evidence: >= 10 sessions on both profiles, every order reconciled, cost compared per order"),
    ("5", "Historical replay 2020-02-03..2020-04-30 and calendar 2022 without error or unshown breach"),
    ("6", "Fidelity: 5 clean preview-only sessions; holdings reconcile with spec 054"),
    ("7", "LIVE budget $200 of settled cash, deposits never raise it"),
)
SHA = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{7,40}")


def check_item(entry: dict | None, root: Path) -> tuple[bool, str]:
    """(has evidence, one-line reason). ``entry`` is the manifest's object for one item, or None."""
    if not isinstance(entry, dict):
        return False, "no evidence recorded"
    artifact, digest = entry.get("artifact"), entry.get("sha256")
    commit, when = entry.get("commit"), entry.get("date_utc")
    if not isinstance(artifact, str) or not artifact:
        return False, "no artifact path"
    path = (root / artifact).resolve()
    if root.resolve() not in path.parents:
        return False, f"artifact {artifact!r} is outside the repository"
    if not path.is_file():
        return False, f"artifact {artifact} does not exist"
    if not isinstance(digest, str) or not SHA.fullmatch(digest):
        return False, "sha256 missing or malformed"
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        return False, f"artifact {artifact} does not hash to the recorded sha256"
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        return False, "commit missing or malformed"
    try:
        stamp = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
    except ValueError:
        return False, "date_utc missing or malformed"
    if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
        return False, "date_utc must be a UTC instant"
    return True, f"{artifact} sha256 {digest[:12]}… @ {commit[:12]} {stamp.date().isoformat()}"


def checklist(manifest: dict, root: Path = ROOT) -> tuple[bool, list[str]]:
    """(armable, printed lines) for one manifest ``{"items": {"1": {...}, ...}}``."""
    items = manifest.get("items") if isinstance(manifest, dict) else None
    items = items if isinstance(items, dict) else {}
    lines, armable = [], True
    for number, title in ITEMS:
        ok, reason = check_item(items.get(number), root)
        if ok and number in TYPED:
            typed, detail = TYPED[number](items.get(number), root)
            ok = typed
            reason += '; ' + detail
        armable &= ok
        lines.append(f"[{'EVIDENCED' if ok else 'MISSING  '}] §11.3.{number} {title} — {reason}")
    lines.append("ARMABLE — Camden may arm LIVE (spec 059 T010); this command arms nothing."
                 if armable else "NOT ARMABLE — every item above needs evidence first.")
    return armable, lines


def fidelity_preview(entry, root):
    """Typed item 6: hashed, distinct NYSE days; clean sessions, each reconciled against broker-API
    holdings. Camden, 2026-10-22: "API holdings count." A CSV is optional; a supplied one must match."""
    from data import trading_days
    from zoneinfo import ZoneInfo
    import math
    try:
        if entry.get('type') != 'fidelity_preview': raise ValueError
        fingerprint=entry['account_fingerprint']
        if not SHA.fullmatch(fingerprint): raise ValueError
        manifest=json.loads((root/entry['artifact']).read_text(encoding='utf-8'))
        days, csv_days = set(), set()
        for item in manifest['sessions']:
            path=(root/item['artifact']).resolve()
            if root.resolve() not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
                raise ValueError
            row=json.loads(path.read_text(encoding='utf-8'))
            if row['account_fingerprint']!=fingerprint: raise ValueError
            day=date.fromisoformat(row['session'])
            if day in days or trading_days(day,day)!=[day]: raise ValueError
            if row['clean'] is not True or row['challenge'] is not False or row['place_calls']!=0: raise ValueError
            if row.get('profile') != 'live_fidelity' or type(row.get('totp_step')) is not bool: raise ValueError
            if not re.fullmatch('[0-9a-f]{40}',row['pin_sha']): raise ValueError
            if not row['pin_sha'].startswith(entry.get('commit',row['pin_sha'])): raise ValueError
            if row['library']!={'version':'0.2.2','sha256':'f5a94056bd9a055ba88482ffcc7dc17013de9871b852b4d9b0dc55352506dd15'}: raise ValueError
            cash=row['settled_cash']; stamp=datetime.fromisoformat(cash['as_of'])
            if stamp.utcoffset() is None or stamp.astimezone(ZoneInfo('America/New_York')).date()!=day: raise ValueError
            if isinstance(cash['amount'],bool) or not math.isfinite(cash['amount']) or cash['amount']<0: raise ValueError
            if not any(p['qty']==1.0 and p['conf_num'] for p in row['previews']): raise ValueError
            if row['holdings_match'] not in (None,True) or row['api_holdings_reconciled'] is not True: raise ValueError
            if row['holdings_match'] is True and not SHA.fullmatch(row.get('csv_sha256','')): raise ValueError
            if row['holdings_match'] is True: csv_days.add(day)
            days.add(day)
        csv=bool(days) and max(days) in csv_days
        return len(days)>=5, f'{len(days)} distinct clean API-reconciled sessions; latest CSV match {csv} (optional)'
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return False,'invalid fidelity_preview evidence'


def paper_evidence_report(entry, root):
    """Typed item 4: the artifact is a ``scripts/paper_evidence.py`` report that says PASS with at
    least ``MIN_SESSIONS`` completed submit sessions for every required PAPER profile. A hashed file
    that is not such a report (or says NOT PASSED) does not evidence item 4."""
    from paper_evidence import MIN_SESSIONS, REQUIRED_PROFILES
    try:
        lines = (root / entry['artifact']).read_text(encoding='utf-8').splitlines()
        if not lines or not lines[0].startswith('# PAPER evidence'):
            return False, 'not a paper_evidence.py report'
        if 'PAPER EVIDENCE: PASS' not in lines or 'PAPER EVIDENCE: NOT PASSED' in lines:
            return False, 'report verdict is not PASS'
        counts = {}
        for line in lines[lines.index('completed submit sessions:') + 1:]:
            m = re.fullmatch(r'- (\w+): (\d+)', line)
            if not m:
                break
            counts[m.group(1)] = int(m.group(2))
        short = [p for p in REQUIRED_PROFILES if counts.get(p, 0) < MIN_SESSIONS]
        if short:
            return False, f'sessions below {MIN_SESSIONS}: {", ".join(short)}'
        return True, ', '.join(f'{p} {counts[p]} sessions' for p in REQUIRED_PROFILES)
    except (OSError, ValueError, KeyError, TypeError):
        return False, 'invalid paper evidence report'


TYPED = {'4': paper_evidence_report, '6': fidelity_preview}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SCOPE §11.3 capital-gate checklist (offline; never arms)")
    parser.add_argument("manifest", type=Path, help="evidence manifest JSON")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"NOT ARMABLE — manifest unreadable ({type(exc).__name__})")
        return 1
    armable, lines = checklist(manifest)
    print("\n".join(lines))
    return 0 if armable else 1


if __name__ == "__main__":
    sys.exit(main())
