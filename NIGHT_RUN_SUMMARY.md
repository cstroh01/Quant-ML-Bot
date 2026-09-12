# Night Run Summary — Spec 017, Position Sizing and Portfolio Risk Layer

_Run: 2026-09-11 → 2026-09-12. Agent lane, local session. No `git` run._
_Resumed and closed out: 2026-09-12, second session. No `git` run._

## TL;DR

- Full Spec Kit lifecycle run: specify → clarify → plan → tasks → implement.
- New module `scripts/portfolio_risk.py`, new tests `tests/test_portfolio_risk.py`.
- **Final test count: 541 passed** (baseline 416 + 125 new). No network, no new dependency.
  Re-run on resumption: 541, `OK`, 160.9 s.
- Mutation check: **21 of 21** injected defects caught; unmutated control clean.
  Rebuilt and re-run on resumption: 21 of 21 again.
- **Not through the Merge Gate (Rule 9).** Nothing is committed — that's yours.

---

## Resumption — where the night run stopped, and what closed it out

**Where it stopped.** The night run ended immediately after writing this file
(12:02:47 AM), one minute after adding the spec 017 section to
`docs/PROJECT_CONTEXT.md` (12:02:02 AM). Every deliverable was on disk; only the
bookkeeping was missing — T033 and T034 were still unticked in `tasks.md`. No
transcript of the night run survives on this machine, so this was
reconstructed from file contents and modification times, not from a log.

**What the second session did.**

| Step | Result |
|---|---|
| Re-ran the full suite | **541 collected, `OK`, 160.9 s** — matches the night's figure |
| Rebuilt the mutation runner (the night's lived in a scratchpad that no longer exists) and re-ran all 21 mutants against copies | Control 125 run / 0 failed. **21 of 21 caught.** Module SHA-256 `a6b9818d…0914` before and after — the same hash the night run recorded. The same eight mutants are caught by exactly one test. |
| Ticked T033, T034; added T035 with the evidence above | `tasks.md` |
| Fixed stale text | Checklist note (said FR-011 and "three markers remain"; now FR-013 and resolved). Plan said "twelve mutants"; now twenty-one. Spec status Draft → Implemented, not through the Merge Gate. |
| Reproduced two audit findings that touch this module | Open questions 11 and 12 below; two flags added to `PROJECT_CONTEXT.md` |

The rebuilt mutants were re-implemented from T030's descriptions, not copied,
so they are an independent check rather than a replay. Their "caught by"
counts differ from T030 for the multi-test mutants because the second runner
counted failing test IDs including subtests.

**Not touched:** `docs/audit-2026-09-12/`. It is a separate, project-wide audit
written by another session at 12:30 PM on 2026-09-12 (probes only, no report).
It is not part of this spec's run.

---

## What was built

### Spec artifacts — `.specify/specs/017-position-sizing-risk/`

| File | What it holds |
|---|---|
| `spec.md` | 3 user stories, 18 FRs, 9 SCs, and a **Clarifications** section with 5 self-resolved questions and their reasoning |
| `research.md` | R1–R8: each decision, why, and the rejected alternatives |
| `plan.md` | Constitution check (Rules 1–10), design, test map, size flag |
| `data-model.md` | Every input/output shape and the guard's state machine |
| `contracts/portfolio-risk-module.md` | Public API and what each function guarantees |
| `quickstart.md` | How to verify: tests, one decision by hand, one halt by hand |
| `tasks.md` | 35 tasks, all checked, with evidence recorded inline |
| `checklists/requirements.md` | Spec quality checklist, 16/16 |

`.specify/feature.json` now points at 017 (it pointed at 013). Switch it back
if 013 is next.

### Code

`scripts/portfolio_risk.py` — the layer between signal and execution.

| Requirement | How it's met |
|---|---|
| **(1) Sizing** off confidence and volatility, never full Kelly | `volatility_target_weights`: `confidence × target_vol / realized_vol`, capped per name. **Volatility targeting only; no Kelly code path at all** (AST test enforces it). |
| **(2) Correlation-aware** across AAPL, MSFT, GOOGL, NVDA, AMZN | `correlation_adjusted_weights`: each held weight ÷ its *overlap* = Σ over held names of `max(ρ, 0)`. `k` identical names → one bet; uncorrelated → untouched; hedges earn nothing extra. Tested on exactly spec 013's `TICKER_UNIVERSE`. |
| **(3) Daily/weekly loss and drawdown cap** that halts entries automatically | `LossCapGuard.observe(session, equity)`: daily loss, weekly loss, weekly drawdown from the week's high. Daily breach halts that close's decision; weekly breach latches to the end of the ISO week. `apply_entry_halt`: `min(target, current)` — no opens, no adds; exits allowed. |
| One call, every step visible | `target_weights(...)` returns a per-ticker frame: `Confidence, Volatility, Standalone, Capped, Overlap, Adjusted, Gross_Scaled, Current, Target`. |

**Fixed step order:** standalone → per-name cap → overlap → gross cap → halt.
Cap-before-overlap matters: three identical names at standalone 1.0 end at
0.25 combined (one bet) this way, 0.75 (three bets) the other way.

**Recommended config** (`RECOMMENDED_CONFIG`, nothing defaults to it):
10% target vol · 25% max per name · 100% max gross (no leverage) · 63-session
windows · −2% daily · −4% weekly loss · −5% weekly drawdown.

### Module boundary (Rule 8)

- Imports exactly `__future__, dataclasses, numpy, pandas, constants` — AST-tested.
- Does **not** import `backtest_harness`, `metrics`, `signals`, `ml_signal`,
  `estimators`, `data`, or any runner.
- Reads equity and holdings as inputs; never computes a fill, trade, or P&L.
- The integration test does its own toy mark-to-market *in the test*, the same
  way `test_ml_signal.py` imports the harness while `ml_signal.py` doesn't.

---

## Evidence

### Tests

| | Count | Time |
|---|---|---|
| Baseline, before any change | 416, OK | 138.6 s |
| `test_portfolio_risk.py` alone | 125, OK | 1.6 s |
| **Full suite, final** | **541, OK** | 160.8 s |
| **Full suite, re-run on resumption** | **541, OK** | 160.9 s |

Rule 5 coverage on every time-indexed function: off-by-one (perturb the
future, assert bit-identical, plus a control that perturbing `t` does
change `t`), boundary (first row, exactly one window, ISO year boundary),
gap (missing bar, Good Friday week, missing week).

### Mutation check (SC-008)

Mutants were copies placed ahead of `scripts/` on `sys.path`. The repo file
was never edited, and its SHA-256 matched before and after.

- 14 defects named in SC-008 + 7 extras (incl. two Rule 1 leaks) = **21, all caught**.
- **8 caught by exactly one test** — the three strict-vs-inclusive boundaries
  (one-test by construction), plus missing-confidence, zero-vol,
  anchor-in-high-water-mark, gross-cap-clipping, aware-labels. Full table in
  `tasks.md` T030.
- **Independently rebuilt and re-run on resumption** (T035): 21 of 21, the
  same eight at one test, same module hash.

### Real data (cached 10y, 2016-09-06 → 2026-09-04) — no P&L

Full conviction on all five, `RECOMMENDED_CONFIG`, 2,451 sized sessions:

| Measure | p10 | median | p90 |
|---|---|---|---|
| Overlap per held name | 2.20 | **3.24** | 4.02 |
| Gross after overlap step | 0.27 | **0.38** | 0.57 |
| Exposure removed by overlap step | — | **69%** | 75% |

- Peak overlap 4.48 (2020-05-20); 4.44 around the March 2020 crash; 3.71 around 2025-04-08.
- Gross cap never bound.
- Speed: 3.5 ms per `target_weights` call on the full panel.

_This diagnostic was not re-run on resumption; it computes no metric that
anything downstream depends on._

---

## Decisions made without you (overturn by editing spec.md → Clarifications)

| Q | Decision | One-line why |
|---|---|---|
| 1 | Vol targeting, **no Kelly** | Half Kelly on 52.99% accuracy = 1.65× leverage from an unproven edge |
| 2 | ISO calendar week; weekly halt latches to week end | A rolling window never resets, so "when do we resume" has no answer |
| 3 | Halt blocks **adding**, not just opening; exits allowed | Otherwise scale a 0.1% stub to the cap mid-halt |
| 4 | Confidence ∈ [0,1]; realized vol, 63 sessions | Estimator-agnostic; a quarter balances noise against turnover |
| 5 | Cap → overlap → gross → halt; inclusive limits; no leverage | Any other cap order undoes the correlation step |

---

## Open questions and flags

**Raised, not resolved** (per CLAUDE.md):

1. **The request cited "the constitution's Rule on adversarial coverage." No rule by that name exists.**
   - Nearest: Rule 1's enforcement clause and Rule 5.
   - The mutation check follows specs 012/013's precedent.
   - Either the prompt misremembers, or it's a rule you meant to add.
   - I did not edit the constitution.
2. **Out of declared sequence.** `PROJECT_CONTEXT.md` has spec 013's real multi-ticker run as next. 017 was built ahead of it, the same shape of drift the doc already flags for 016.
3. **PR size.** 745 module + 1,391 test lines, ~2.6× spec 012's module. CLAUDE.md says split when line-by-line review is impractical. Split seams are in `plan.md` → *Complexity Tracking*. Not split unilaterally.
4. **Is the overlap step too aggressive?** It removes a median 69% of full-conviction exposure on real data. The rule is doing what it says (five names ≈ 1.5 independent bets). Whether to soften it, e.g. toward portfolio-vol scaling, needs a costed backtest to judge.
5. **Kelly.** If you want a fractional-Kelly path, it needs a calibrated probability or return forecast first. Best as its own spec after 013, with a ceiling ≤ ½.
6. **No wiring yet.** `run_backtest` is one share, one ticker. The next spec is a weight-based multi-asset execution path. It's an execution-layer change, and it brings Rule 3 costs plus both Rule 4 baselines.
7. **Where confidence comes from** is undecided. Mapping a classifier's probability, a regression prediction, or 012's entry mask onto [0,1] is a signal-layer choice for the wiring spec.
8. **No all-time max-drawdown kill switch** (needs a human reset). This is a common pre-live control; it wasn't requested, so it wasn't added.
9. **Loss limits (2/4/5%) are reasoned in σ units, not calibrated.** No real equity curve exists yet to test them against.
10. **CLAUDE.md's module table** doesn't list `portfolio_risk.py`. Worth a row ("owns sizing, correlation budget, entry halts / must not know fills, P&L, signal origin"). Left for you.
11. **A dust-size position halves its correlated neighbours.** _(Added on resumption; from `docs/audit-2026-09-12` probe `tiny_correlated_position`, reproduced.)*
    - Overlap counts a held name by *presence*, not size.
    - Name A at 0.25 beside name B at 1e-12, ρ = 1: A becomes **0.125**. With B at exactly 0, A stays **0.25**.
    - So one name's confidence moving from 0 to 1e-9 can halve another name's position. That discontinuity is turnover Rule 3 will charge for once costs exist.
    - This is FR-005 working as written, not an implementation bug. Fixing it — a size-aware overlap, or a minimum weight before a name counts as held — changes the spec, the SC-004/SC-005 arithmetic, and several mutants. Your call; best settled alongside item 4.
12. **The weekly halt latch lives only in memory.** _(Added on resumption; from probe `restart_resets_loss_latch`, reproduced.)_
    - A guard latched on Tuesday, replaced by a freshly constructed guard on Wednesday, reports **not halted**.
    - Irrelevant inside a backtest. It matters the moment paper trading runs as a process that can restart mid-week.
    - Mitigation already exists and was checked: replaying the week's equity through `loss_cap_history` rebuilds the latch correctly (halted on Wednesday).
    - The wiring or paper-trading spec should *require* the guard to be rebuilt by replay (or its state persisted), never constructed empty mid-week.

**Disclosures about this run:**

- **T003 (TDD red) was invalid as run.** I invoked `python -m unittest tests.test_portfolio_risk`. It failed on `import context`, before reaching the missing module. The mutation check is the real evidence the tests bite. The same wrong command was in `quickstart.md` and is fixed.
- **One vacuous assertion was caught before the first run and corrected.** It compared a sum against 3× its own mean.
- **Two claims in the plan were checked and corrected.** The size estimate was wrong (fixed in `plan.md`). The speed goal held (3.5 ms against a 50 ms goal).
- **The night run ended before its own bookkeeping.** T033/T034 were done but unticked; closed on resumption, with both headline claims re-verified rather than trusted.
- **No transcript of the night run exists locally.** The resumption account above is reconstructed from files and timestamps.
- **Rule 10:** no `git` command of any kind, in either session. File-unchanged checks used SHA-256 hashes.

---

## Files touched

| New | Modified |
|---|---|
| `scripts/portfolio_risk.py` | `.specify/feature.json` (013 → 017) |
| `tests/test_portfolio_risk.py` | `docs/PROJECT_CONTEXT.md` (new spec 017 section at top; two flags added on resumption) |
| `.specify/specs/017-position-sizing-risk/` (8 docs + checklist) | `.specify/specs/017-position-sizing-risk/{tasks,plan,spec}.md`, `checklists/requirements.md` (resumption: ticks, T035, stale text) |
| `NIGHT_RUN_SUMMARY.md` | |

Scratchpad only (outside the repo): mutation runners and results (both
sessions), real-data diagnostic, test logs.

## Suggested next steps (pick one)

1. **Merge Gate on 017.** Explain the step order and the halt's `min(target, current)` in your own words; split the PR first if it's too big to read.
2. **Run spec 013 for real**, which puts the declared sequence back in order before building on 017.
3. **Spec 018: weight-based execution path.** It wires 017 into a costed backtest with both baselines, and it's where items 4 and 11 above (overlap aggressiveness, dust positions) get answered — and where item 12's replay requirement belongs.
