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
`push`, or `checkout` — with two narrow, permanent exceptions below. Camden
performs every other version-control operation himself in GitKraken.

**Exception — the GitHub Actions lane.** An agent invoked from a GitHub issue
or PR comment, running in the repository's GitHub Actions workflow, may run
`git add`, `git commit`, and `git push` — and only those three — to the
branch it was invoked on. `merge`, `rebase`, `reset`, `checkout` of another
branch, force-push, tag, any push to `main`, and any history rewrite remain
forbidden in every lane, including this one. An agent working outside these
two lanes — a local session, a worktree, a terminal — runs no `git` at all.

**Exception — the authorized cloud-session lane.** An agent running in Anthropic-managed cloud as a Claude scheduled task configured by Camden, or in a Claude cloud session explicitly started by Camden through the browser, Claude app, or cloud CLI launch, or in an OpenAI-managed Codex cloud task explicitly started by Camden, may clone and fetch the repository; create exactly one new feature branch for that session or task; stage explicit paths; commit; and push without force to that branch only. Claude branches must begin `claude/`; Codex branches must begin `codex/`. Provider-managed checkout and branch creation count toward this same single-branch allowance; they do not authorize a second branch. The task may open one draft PR to `main` and update that same PR from its own branch while the same session or task continues.

No push to a branch created by another session or task, no merge, rebase, reset, force-push, tag, history rewrite, checkout of another branch after branch creation, or push to `main` is permitted. Agents never approve PRs, merge them, or mark them ready for review. No edit to this file, `CLAUDE.md`, `docs/SCOPE-V1.md`, `docs/autonomy/`, `.github/`, `docs/trials/`, or anything in `exec/` is permitted in this lane. All other repository protections and human gates remain binding. Local sessions, terminals, worktrees, and cloud sessions continued locally gain no Git permission from this exception.

This is a comprehension rule, continuous with Rule 9. The exception lets a session place its work on a feature branch for review; it does not let the session make the work permanent on `main`. Camden must still explain what the change does, why it is correct, and what would break if it were wrong before he merges it.

_Amended 2026-09-06, Camden's confirmation: this exception was previously a
documented carve-out in `CLAUDE.md` ("Rule 10 and the GitHub Actions lane"),
pending a dedicated amendment here per this file's own Amendment clause. That
CLAUDE.md section now records history rather than an open question — this
rule's text is the current authority._

_Amended 2026-10-01, Camden's confirmation: added the cloud scheduled-session
lane so unattended cloud runs can put commits where review already is. Same
argument as the Actions lane — the push lands on a `claude/*` branch inside a
draft PR, never `main`, and Rule 9 still gates every merge._

_Amended 2026-10-05, with Camden's explicit approval: extended the cloud lane to Camden-started Claude cloud sessions and Codex cloud tasks so bounded queue work can use eligible cloud credit and independent providers. One session-owned provider-prefixed branch and draft PR only; protected paths, local Git prohibition, and Camden's comprehension and merge gates remain intact._

## Rule 11 — No unsourced figures in any UI, report, or document

Every number rendered to a human — terminal output, `reports/`, a tearsheet, a
README table, a spec's results section — carries provenance: the artifact it
was computed from, the commit or run id that produced it, and the date. A
figure that cannot name its source is deleted, not footnoted.

Illustrative or placeholder numbers are forbidden outright in any surface a
reader could mistake for results. If an example value is genuinely needed, it
is labelled `EXAMPLE — NOT A RESULT` on the same line.

A figure whose source artifact no longer exists in the tree is stale by
definition and must be regenerated or removed before the PR that touches that
surface can merge.

_Added 2026-09-14. Findings 45, 46 and 47 of the 2026-09-12 audit all trace to
the absence of this rule._

## Rule 12 — No green signal without proof it can go red

Every gate needs a test that deliberately breaks the gated thing and confirms
the gate fires. A gate that has never been observed failing is not evidence
that the property it guards holds — it is an untested claim that happens to be
printing the word `passed`.

"Gate" means anything whose passing is read as permission: an anti-lookahead
assertion, a collection guard, a purge/embargo check, a leakage or determinism
test, a CI step, a schema or bounds validation. The proof obligation falls on
whoever adds or changes the gate, in the same PR.

`tests/test_collection_guards.py` is the reference shape. It does not describe
its own reliability; it plants each defect it claims to catch — a test file
outside `tests/`, a module collecting zero cases, a module hidden by
`collect_ignore` — runs the real gate against that planted defect in an
isolated tree, and asserts both the failure **and** the specific message
naming the offending path. It carries a `control` scenario that must pass
clean, so a gate stuck in the failing position is caught too. Red evidence
without a green control proves only that something is broken.

The planted defect must be plausible: the bug a tired reviewer would actually
ship, not a strawman any assertion would catch. A guard proven only against an
obviously broken input has been proven against nothing. The defect is planted
in a copy or an isolated tree and never committed to the module it mimics.

A perturbation test states which field it perturbs and why that field is the
one the gated code reads. A gate aimed at a field its target no longer reads
passes vacuously, which is worse than no gate: it reports safety it is not
checking. The 2026-09-12 audit found exactly this in `TestOffByOne`, where the
spec 019 open-basis migration left an anti-lookahead guard perturbing `Close`
against a label built from `Open`. It would have passed against a label
reading arbitrarily far into the future.

_Added 2026-09-18. Rule 1 is only as good as the tests that detect its
violation; this rule is what keeps those tests honest._

## Rule 13 — Cost modeling requires spread and market impact

**Flat basis-point transaction cost assumptions are forbidden for any reported
backtest result.**

Slippage must be derived from a half-spread estimate calculated from daily OHLC
bars (following Ardia, Guidotti & Kroencke, JFE 2024) plus a square-root
market-impact term. Fixed or constant-basis-point slippage masks liquidity
dry-ups, execution capacity constraints, and the true cost of trading
non-megacap names. A backtest reported with flat basis-point costs is invalid.

Citation: `claude/research-solo-quant-edge-and-survival.md`, section "The 5-bullet plan", item 3 ("Fix data and costs, the two places a daily-bar backtest lies most").

_Added 2026-09-18, per report finding: flat basis-point transaction costs forbidden; slippage must derive from daily OHLC half-spread (Ardia, Guidotti & Kroencke 2024) plus square-root market impact._

## Rule 14 — Corporate action data verification

**Corporate action data (splits, dividends) sourced from yfinance must be
cross-checked against an independent second source before use in any backtest
whose results get reported.**

yfinance has documented defects including missed split adjustments, missed
dividend adjustments, and 100× currency/pricing errors. Backtests run on
unverified corporate action data produce phantom alpha or catastrophic
drawdowns from unadjusted price jumps. Any corporate action adjustments applied
to a traded universe must be reconciled against an independent second source
before results are reported.

_Amended 2026-09-25 (free-data-only scope, `docs/SCOPE-V1.md` §2)._ CRSP,
Compustat and Norgate are no longer acceptable reconciliation sources, because
they are out of scope as paid or licensed feeds. The second source must be free:
SEC EDGAR filings, exchange notices, or a free-tier reference feed whose
corporate-action coverage has been verified rather than assumed. Where a free
second source cannot cover an action, the action is **disclosed as
unreconciled** in every surface reporting a result derived from it, per Rule 16
— never silently accepted, and never used as grounds to skip the check.

Citation: `claude/research-solo-quant-edge-and-survival.md`, section "The 5-bullet plan", item 3 ("Fix data and costs, the two places a daily-bar backtest lies most").

_Added 2026-09-18, per report finding: yfinance corporate action data (splits, dividends) must be independently cross-checked before use in reported backtests due to documented defects._

## Rule 15 — Deflated Sharpe Ratio statistical gate

**No strategy variant's Sharpe ratio may be reported as a result unless it has
passed the Deflated Sharpe Ratio gate (DSR ≥ 0.95) once spec 033 exists.**

Until spec 033 exists and is operational, any reported Sharpe ratio must be
explicitly flagged as provisional and undeflated in the same surface where it is
shown (terminal output, reports, tearsheets, README tables, or specs), in
accordance with Rule 11's provenance requirement.

Unlogged backtest search, hyperparameter sweeps, and strategy iteration inflate
apparent Sharpe ratios purely through selection bias. A strategy variant
reporting an undeflated Sharpe provides no statistical evidence of edge over
luck.

Citation: `claude/research-solo-quant-edge-and-survival.md`, section "The 5-bullet plan", item 1 ("Build the false-discovery gate before any new alpha: a lifetime trial ledger, Deflated Sharpe and PBO").

_Added 2026-09-18, per report finding: strategy Sharpe ratios require Deflated Sharpe Ratio gating (DSR ≥ 0.95) once spec 033 exists, and must be flagged as provisional/undeflated until then._

## Rule 16 — Stated limitations travel with the results

**Every surface that reports a result also names the data limitations that
bound it.** A number is not honest merely because its arithmetic is correct and
its provenance is stamped; it is honest when a reader cannot mistake what it
does and does not evidence.

The limitations that must travel with any reported result from this project, for
as long as they hold, are listed in `docs/SCOPE-V1.md` §6: a static survivor
basket with no delisted names, free-tier corporate-action data, no
point-in-time fundamentals, daily bars only, and modeled rather than
fill-calibrated costs.

Concretely: a tearsheet, terminal panel, report, README table, or spec results
section carries the applicable limitation inline or by an unmissable reference
on the same surface. A footnote three documents away does not satisfy this.
Removing a limitation from the register requires evidence that it no longer
holds, in the PR that removes it.

Rule 11 makes a figure cite where it came from. This rule makes it admit what it
cannot show. A survivorship-biased Sharpe with perfect provenance is still a
number that will be quoted as if it generalized.

_Added 2026-09-25. The project's scope is now explicitly a free-data research
framework (`docs/SCOPE-V1.md`), which makes several limitations permanent rather
than temporary gaps awaiting a vendor — permanent limitations need a permanent
disclosure rule._

---

## Amendment

Rules change by editing this file in a dedicated commit that changes nothing
else, with the reason stated in the commit message. A rule loosened to let a
specific PR through is a rule that was never binding.
