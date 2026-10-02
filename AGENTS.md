# AGENTS.md

A map for every coding agent (Codex, Copilot, Devin, Antigravity, Claude Code).
It points into the repo's system of record. It overrides nothing in it.

## Read first, in this order

1. `.specify/memory/constitution.md` — the non-negotiable rules. It wins every conflict.
2. `CLAUDE.md` — operating instructions, module boundaries, the test command.
3. `docs/SCOPE-V1.md` — scope, hard constraints, definition of done.
4. `docs/STATE.md` — the active spec and the human gates.
5. The spec you were given: `.specify/specs/NNN-*/spec.md`, `plan.md` and `tasks.md`.

## Ground rules

- **Work comes from a numbered spec task, never from a chat prompt.** A task that cannot be written as a spec is not ready.
- **Version control is human-owned (Rule 10).** Agents may not merge, rebase, reset, force-push, tag, or push to `main`. Only the lanes the constitution names may commit, and only to their own branch.
- **Only Camden merges (Rule 9).** Never approve, merge, or mark a PR ready for review.
- **Tests are contracts.** Never weaken an assertion to make code pass. If a spec and a test disagree, stop and report the conflict.
- **Never write to these paths:** `docs/trials/` (the trial ledger), `exec/`, `.env*`, or `data/cache/`.
- **Network:** pip and GitHub only. Market-data or vendor fetches are a human gate. Free data only.
- **Run the tests:** `python -m pytest tests` from the repo root. Python 3.12 matches CI.

## Review guidelines

Report only problems that would make a result wrong, a gate vacuous, or a boundary leak. Skip style.

**P0, block.** Any of these:

- **Lookahead (Rule 1).** A value in row `t` reads data after `t`. Watch for:
  - a full-sample `.mean()`, `.std()`, `.min()`, `.max()` or `.quantile()`;
  - `shift(-k)` on a feature;
  - `center=True` windows;
  - `bfill` or `interpolate()`;
  - a scaler fit outside its fold;
  - trading at the signal bar's own close instead of the next open.
- **Unpurged or unembargoed CV (Rule 2).** Random k-fold, or a CV metric reported without fold count, purge length and embargo length.
- **Costless results (Rules 3 and 13).** A return, Sharpe or P&L without costs, or with a flat-bps cost assumption.
- **Ledger writes.** A write to `docs/trials/` outside the trial-registry API, or a strategy evaluation that skips the ledger. Unrecorded trials deflate the Deflated Sharpe gate.
- **Credentials.** Any secret, token or broker credential in code, logs, specs or PR text.

**P1, fix before merge.** Any of these:

- **Vacuous test or gate (Rule 12).** It would still pass if the guarded property broke. It perturbs a field the code does not read. It has no planted defect proving it goes red.
- **Untested time code (Rule 5).** Code that touches time but has no off-by-one, boundary or gap test.
- **Module boundary crossed (`CLAUDE.md` table).** For example, signals knowing about fills, or the harness knowing how a signal was produced.
- **Naive and aware timestamps mixed.** Or a session label localized to UTC.
- **Missing provenance or limitations.** A figure shown to a reader without Rule 11 provenance or Rule 16 limitations.
- **Unjustified dependency (Rule 6).** A new dependency without a justification line.

## Module ownership

See the table in `CLAUDE.md`. Two agents must never edit the same file at the same time. One agent works per branch.
