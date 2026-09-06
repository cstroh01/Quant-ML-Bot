# Quant-ML-Bot Constitution

Non-negotiable rules. Every agent working in this repository — Claude Code,
Antigravity, Copilot, CI — obeys these regardless of which spec it is
implementing. A pull request that violates any rule is rejected on sight, no
matter how good its results look.

These rules exist because every one of them guards a failure that is **silent**.
A backtest that leaks the future does not crash. It prints a Sharpe ratio.

---

## Rule 1 — Point-in-time correctness

**For every row timestamped `t`, every value in that row must be computable
using only data that existed at or before `t`.**

This is judged per row, against that row's own timestamp — not per dataset, and
not per train/test split. A correct chronological split does not make a row
legal. A single feature computed with a full-sample statistic contaminates every
row it touches.

Concretely, this forbids:

- Any `.mean()`, `.std()`, `.min()`, `.max()`, `.quantile()`, or fit statistic
  computed over the full sample and then applied to earlier rows. Use expanding
  or trailing windows.
- `fillna(method='bfill')`, `interpolate()` in any backward-looking mode, or any
  imputation that reads forward.
- Scalers, encoders, or normalizers fit on all data and then applied to the
  training window. Fit inside the fold, on the fold's past only.
- Labels or targets computed at `t` that are only observable after `t` being
  used as *features*. (They are legal as *targets*; never as inputs.)
- Trading at the same bar's close that produced the signal. Signals shift
  forward; fills happen at the next bar's open.

**Worked case, for calibration.** A z-score of a price series on Jan 2 computed
point-in-time reads `+1.00`. The same z-score computed with a full-sample
`.mean()` and `.std()` reads `-0.77`. Same day, same price, opposite sign. The
train/test split was correct in both. Only the feature was poisoned.

**How it is enforced.** Anything that computes a feature, a label, or a
timestamp alignment ships with a test that would fail if the computation could
see past `t`. Review alone does not satisfy this rule.

---

## Rule 2 — Purged, embargoed walk-forward cross-validation only

**Random k-fold is banned. Plain chronological k-fold without purging is banned.**

Every evaluation uses walk-forward splits in which:

- Training data strictly precedes validation data in time.
- Observations whose label horizon overlaps the validation window are **purged**
  from training.
- An **embargo** gap is applied after each validation window before training
  resumes, sized to at least the label horizon.

Financial observations are serially correlated and their labels span time. A
label at `t` computed over the next `h` bars overlaps every training sample
within `h` bars of it. Without purging, the model is graded on data it
effectively memorized.

Any PR reporting a cross-validated metric states its **fold count, purge length,
and embargo length** in the PR description. A metric without those three numbers
is not a metric.

---

## Rule 3 — Costs and slippage are mandatory

**No backtest reports a return, Sharpe, or P&L figure without commission and
slippage applied.** There is no "gross" mode, no `costs=False` flag, no
"we'll add them later."

Minimum model, until replaced by something better justified:

- Commission per trade, explicitly parameterized.
- Slippage applied against the trade direction, expressed in basis points of
  notional or as a fraction of the bid-ask spread.
- Both values recorded in the results artifact alongside the metrics they
  produced.

Strategies that survive costs are a small subset of strategies that look
profitable without them. Reporting a costless result — even internally, even as
an intermediate — creates a number that will later be quoted as if it were real.

---

## Rule 4 — Two baselines per strategy PR

**Every PR that proposes or modifies a strategy reports its metrics beside two
baselines, computed over the identical period, with identical costs:**

1. **Buy and hold** the same instrument.
2. **A random signal** with matched trade frequency, averaged over multiple
   seeds.

Baseline 1 answers "is this better than doing nothing." Baseline 2 answers "is
this better than luck at the same activity level." A strategy that beats neither
is not a finding, and a strategy that beats only the random baseline is a
transaction-cost story, not an edge.

The random baseline's seed count and dispersion are reported, not just its mean.

---

## Rule 5 — Tests required on anything touching time

**Any code that indexes, shifts, resamples, joins, aligns, or windows on a
timestamp ships with tests in the same PR.** Not a follow-up issue. Not the next
PR.

At minimum the tests cover:

- The off-by-one case — does the value at `t` depend on the bar at `t+1`?
- The boundary case — first row, last row, and the fold edges.
- The gap case — missing bars, holidays, halts, and irregular spacing.

Time-alignment bugs do not raise exceptions. They shift a column by one and
improve the results.

---

## Rule 6 — Dependencies require justification

**No dependency is added without a one-line justification in the PR description
naming what it does that the standard library and the existing dependencies
cannot.**

Every dependency is a permanent maintenance and supply-chain liability accepted
in exchange for saved time. That trade is often worth making, and it is never
made silently.

---

## Rule 7 — Execution code is never autonomous

**Once real broker credentials exist, `exec/` is excluded from every autonomous
agent lane and from CI-driven modification.**

- No autonomous agent modifies code that can place an order.
- Changes to `exec/` come through the reviewed lane only, read line by line.
- Credentials live in a gitignored `.env`. They never appear in the repository,
  in an agent's context window, in CI logs, or in a spec.

The blast radius of every other module is a wrong number. The blast radius of
this one is money leaving the account.

---

## Rule 8 — Layer separation

**Data, signal, and execution/accounting remain independently correct and
independently testable.**

The backtest harness knows nothing about how a signal was produced. The signal
layer knows nothing about fills, position sizing, or P&L. This is what allows a
model to later replace a rule without touching execution — and what allows a bug
to be localized instead of hunted.

A PR that reaches across these boundaries states why in its description.

---

## Rule 9 — The merge gate

**No PR merges that Camden cannot explain.**

Explain means: what the change does, why it is correct, and what would break if
it were wrong. Not a summary of the diff — an account of the mechanism.

Agents write code faster than it can be understood, and the gap compounds
silently until the repository is a black box its owner nominally maintains. This
rule is the only thing preventing that, and it binds even when the code is
obviously fine and the queue is backed up.

A PR blocked on this gate is not blocked on the code. It is blocked on an
explanation, and the explanation is the deliverable.

---

## Rule 10 — Version control is human-owned

**Agents do not run `git`.** No `add`, `commit`, `branch`, `merge`, `rebase`,
`push`, or `checkout` — with one narrow, permanent exception below. Camden
performs every other version-control operation himself in GitKraken.

**Exception — the GitHub Actions lane.** An agent invoked from a GitHub issue
or PR comment, running in the repository's GitHub Actions workflow, may run
`git add`, `git commit`, and `git push` — and only those three — to the
branch it was invoked on. `merge`, `rebase`, `reset`, `checkout` of another
branch, force-push, tag, any push to `main`, and any history rewrite remain
forbidden in every lane, including this one. An agent working outside the
Actions lane — a local session, a worktree, a terminal — runs no `git` at
all.

This is not a safety rule. It is a comprehension rule — the same one as
Rule 9, enforced at the point where changes become permanent. The exception
does not defeat it: a push in this lane lands on a feature branch inside an
open PR, never `main`, and Rule 9 still gates the merge on Camden being able
to explain the change. What it grants is the ability to put a commit where
the review already is — not the ability to make anything permanent.

_Amended 2026-09-06, Camden's confirmation: this exception was previously a
documented carve-out in `CLAUDE.md` ("Rule 10 and the GitHub Actions lane"),
pending a dedicated amendment here per this file's own Amendment clause. That
CLAUDE.md section now records history rather than an open question — this
rule's text is the current authority._

---

## Amendment

Rules change by editing this file in a dedicated commit that changes nothing
else, with the reason stated in the commit message. A rule loosened to let a
specific PR through is a rule that was never binding.
