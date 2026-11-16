---
name: daily-check
description: Camden's daily Quant-ML-Bot status check — pins, halts, private workflow runs, issues, Fidelity preview/live sessions, and PAPER small/large runs and fills, with what needs Camden. Use when Camden says "daily check", "/daily-check", "check it", "check the status", "how did day N go", or asks how the bot did today. Works in every phase, before and after the 5 Fidelity preview sessions.
---

# Daily check

Read-only. This skill never runs git, never writes to either repo, never repins, never merges.

## 1. Gather

From the repo root, run:

```
python -I .claude/skills/daily-check/check.py
```

Pass `--hours 72` after a weekend or a gap. The script prints these sections: Pins, Halts,
Private runs, Issues, Fidelity, PAPER small/large, Phase and Needs attention. It redacts
account, fingerprint, key and token fields. If you query anything by hand, decode `.content`
in Python (`gh` through bash adds CRs) and strip those same keys before printing.

If the script errors, fix the cause or fall back to the same `gh` calls by hand. Do not
report from memory.

## 2. Dig only where the output points

- **A failed run** (`NOT OK`): `gh run view <id> --repo cstroh01/Quant-ML-Bot-private --log-failed`.
  Quote the failing step and one key line.
- **A new private issue**: read its body.
- **A halt file**: report it first and loudly. Never clear it. Clearing a halt is Camden's
  call, made in the GitHub UI.
- **A fidelity-preview run that wasn't an attempt**: a run after the day's attempt prints
  "already attempted …; no retry". That is the design, not a failure.
- **`Host preflight refused; no child started`** on every dispatch while `live_fidelity/HALTED`
  (or KILL) exists: the host refuses before any login, and each refusal opens an issue. That is
  the latch working, not a new fault; the finding is the halt itself.
- **`latest CSV match False (optional)`**: optional. It doesn't count against item 6.
- **PAPER fills**: a fill is recorded by the *next* session's run, so today's intents having
  no fill yet is normal. Only `UNFILLED from earlier sessions` is a finding.

## 3. Phase-specific notes

The script's Phase line tells you the phase.

- **A — collecting previews (<5 clean at one pin):** remind Camden: no `postmerge-repin.ps1`
  and no merge that needs a repin until 5/5. A repin restarts the count. Project the date of
  the 5th clean session in trading days, skipping NYSE holidays.
- **B — 5/5 reached, evidence not yet public:** the next step is a Camden-reviewed public PR
  that copies the private evidence into `docs/implementation/spec-059/gate-manifest.json`
  (item 6) and `docs/implementation/spec-061/fidelity-preview/`. Check whether that PR is
  open and green. Explain the CSV-match line before it goes to review. After that comes the
  rest of the SCOPE §11.3 capital gate (constitution Rule 9b). Repins become allowed again,
  but never on weekdays from 08:00 to 12:00 ET.
- **B+ — evidence public, final gate PR (items 1 and 7) not yet merged:** check whether that PR
  is open and green; follow the orchestration folder's `FINISH-RUNBOOK-*.md`.
- **B2 — all 7 gate items on main, not yet armed:** follow `FINISH-RUNBOOK-*.md` (repin, clear
  HALTED, install `fidelity-live.yml`, arm). The clean-preview count at the new pin restarts at
  0; that is expected and does not affect item 6, which is recorded at its own pin.
- **C — LIVE armed** (`QMB_FIDELITY_LIVE_ENABLED=true`, previews off): the same sections still
  apply. The script flags:
  - any LIVE outcome other than SUBMITTED or BUDGET_REFUSED, and `place_calls` that differ from
    the SUBMITTED count;
  - an aborted record (it prints FR-013 stage, kind and detail);
  - orders in the bot ledger still awaiting broker confirmation (normal on the day they were
    placed; they are applied at the next run's reconciliation);
  - halt files in `live_fidelity`, and `budget` above the $200 cap (SCOPE §11.3 item 7).
  The workflow is `fidelity-live`; fidelity-preview runs stop (skipped) once armed.

  Report what LIVE did. Claim no edge: spec 059 is a preregistered allocation, not an
  edge claim. Any performance figure needs the buy-and-hold and random baselines and the
  costs (CLAUDE.md PR requirement 4). Otherwise give fills and positions only.

## 4. Report

Lead with one line: clean, or the single most important problem. Then give short sections:

- **Fidelity:** today's record, N/5 (or the live outcome), the item-6 log line.
- **Everything else:** run counts, halts, new issues, pins, PAPER last run and new fills.
- **Next:** what happens on the coming trading days, and any rule Camden must keep.
- **Needs you:** only real actions. Write "Nothing needs you today" when that is true.

Keep it short, and use they/them for Camden. Never print account numbers, fingerprints or
secrets.
