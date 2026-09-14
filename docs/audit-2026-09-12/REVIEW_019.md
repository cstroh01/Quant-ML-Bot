# Review — spec 019, funded ledger and timing

Reviewer: Claude Code (Opus 5), read-only lane. Reviewed 2026-09-14.
Subject: `.specify/specs/019-funded-ledger-and-timing/` as implemented by Codex in six review units,
uncommitted on top of `4023aa54`. Spec 018's uncommitted work in the same tree is out of scope and
was not reviewed.

Authority: `AUDIT.md` for every finding. `REMEDIATION_PLAN.md` is not cited as evidence anywhere below.

## Provenance of figures in this document (Rule 11)

The tree under review is uncommitted, so no figure here can name a commit beyond "base `4023aa54` +
working tree as found on 2026-09-14". Every figure is tagged:

- **[O]** observed output of a command in Appendix A, run 2026-09-14 against that tree.
- **[D]** derived in closed form in this document; the derivation is shown.
- **[A]** quoted from `AUDIT.md` at the cited line.
- **[H]** quoted from `CODEX_LANE_HANDOFF.md` at the cited line. That file carries no commit and no
  date (see R-21).

A seeded Monte-Carlo cross-check of R-05 agreed with the closed form. Its script is not in the tree,
so its figure is not reported (constitution:223-225). Each unit PR must re-run Appendix A and cite
its own head SHA.

Severity: **P0** blocks merge of the named unit. **P1** must be fixed before Stage 3.3 begins.
**P2** is an improvement.

---

## Summary

| Priority | Answer |
|---|---|
| 1. Unit 5 guard | **(b).** The guard is correct and ships unflagged. Merge order is **019 → 020 → Stage 3.3**. Spec 020 cannot land before 019, because 020's own acceptance test calls 019's code. |
| 2. HAC bandwidth | **Confirmed:** unit 6 never ties the bandwidth to h. **Not confirmed:** that a reported t-stat is inflated today. The only HAC call runs on non-overlapping daily account returns, and no t-stat exists. The defect is latent, plus a fixed L=5 at the live call. Fix in R-05. |
| 3. Closures | **Agree:** 10, 22, 24 (closed); 03, 04, 12, 13 (partial); 25 (open). **Qualified:** 01 and 23 are closed at the library only. **Downgrade to partial:** 02 (fails open when attrs are lost) and 11 (its ID and quote checks are untested). |
| 4. Mutation | **22 of 22** candidate mutants on unit 5/6 guards survive all 65 tests [O]. The 019 helper structurally cannot express "a guard was removed". |
| 5. Finding 25 | **Constrain the policy to fixed-horizon explicitly.** Hysteresis stays legal only at h = 1. Optimal stopping is deferred to work order 5 as its own spec. |
| 6. Harnesses | **Converge on the 018 runner's out-of-process shape**, with one driver and per-spec registries. Adopt 019's "expected killer" idea. Delete the 019 helper after 16/16 parity. |
| 7. Constitution | **P0:** under the canonical test command the 65 tests are not discovered and their modules raise 6 import errors [O]. The suite on this tree has **168** failing tests [O]. **P1:** Rule 3 cost defaults, Rule 5 gap case, Rule 11 figures, Rule 4 exception. |

---

# Part 1 — Unit 5 and merge order

## R-01 — Decision (b): the guard is correct, ships unflagged, and 020 precedes Stage 3.3

**Claim.** `run_backtest` refusing anything but declared unadjusted dollars
(`scripts/backtest_harness.py:37-38`) is the right invariant, and it must not sit behind a flag.
Spec 020 is a hard prerequisite for Stage 3.3 and for any funded figure on real data. It is not a
prerequisite for merging 019.

**Evidence that the guard is correct — not (c).**

1. **The audit requires it.** Finding 13 (`AUDIT.md:71`) requires "unadjusted prices and explicit
   split/dividend events for the ledger".
2. **Adjusted prices violate Rule 1 inside the ledger itself.**
   - An adjusted `Open[t]` equals the raw `Open[t]` times the adjustment factor of every ex-date
     *after* `t`, up to the download date.
   - The harness buys a fixed integer quantity (`backtest_harness.py:22`, `:132`) and tests
     affordability in absolute dollars (`:135`). That decision therefore depends on dividends and
     splits that had not happened at `t`: constitution:15-16's per-row test fails on the rejection
     event.
   - The audit's concession that ratio features are rescaling-invariant (`AUDIT.md:71`) does not
     cover absolute-dollar affordability, fixed `$` commissions, or `total_pnl / capital_base`
     (`scripts/metrics.py:351`). A later re-download also changes past results.
3. **It fails closed.** A frame whose `attrs` are dropped is rejected, the safe direction. Contrast R-07.

**Evidence against a flag — not (a).**

1. **A flag is Rule 3's banned pattern moved to prices.** "No `costs=False` flag"
   (constitution:73-75) exists because a flagged figure gets quoted as real. The figure a
   price-basis flag would re-enable is the one the audit rejected: "not reliable funded-account
   results" (`AUDIT.md:41` [A]).
2. **A flag would not make anything runnable.**
   - No production caller passes `starting_capital`, and unit 6 raises for that at
     `backtest_harness.py:68-69`. The callers are `ma_crossover_backtest.py:81,92,186`,
     `logistic_baseline.py:314`, `multi_ticker_comparison.py:134,142,266` and
     `reports/api/routes/backtest.py:53-57`.
   - Both ML runners fail even earlier, at `scripts/estimators.py:278-280`, because
     `EMBARGO_BARS = 1` is below the returned span of 2 (`multi_ticker_comparison.py:77-78`,
     `feature_set_comparison.py:106-107`). The flag would buy the defect and nothing else.

**What (b) costs, and why it is acceptable.** Stage 3.3 waits on 020. That is the audit's own order:
work order 2 carries 13 (`AUDIT.md:230`), and work order 3 persists baselines, which are funded runs
(`AUDIT.md:231`). Prediction-quality research (`feature_set_comparison.py`) never calls
`run_backtest`; it is blocked only by the embargo constant (R-02).

**Severity.** P0 — this decision fixes the merge order.

**Recommended action — merge order.**

1. **019, as six unit PRs in the handoff's order.** Each PR carries the reconciliation of every test
   and consumer it breaks (R-02), `unittest` conversion of its tests (R-17), and tests that kill its
   surviving guard mutants (R-13). Until 020 merges, production entry points fail with a named "no
   verified unadjusted dataset" reason. They are not deleted, and they do not fail with a stack trace.
2. **020, amended per R-03, R-04 and R-21.** It cannot precede 019: its acceptance Test 5
   (`.specify/specs/020-unadjusted-price-data/spec.md:154-156`) runs 019's `execution_price_frame`
   and `run_backtest`.
3. **Stage 3.3 (work order 3).**

## R-02 — The merge blocker is consumer breakage, not the guard: 168 failing tests

**Claim.** The handoff says older tests and integrations "were neither modified nor run"
(`CODEX_LANE_HANDOFF.md:162-164`). On this tree the canonical suite fails badly, and nearly all of
it traces to 019 error messages.

**Evidence.** `unittest discover -s tests`: **553 run, 40 failures, 128 errors** [O]. Grouped by
message [O]:

| Count | Message | Source |
|---:|---|---|
| 58 | funded ledger requires declared unadjusted dollar prices | `backtest_harness.py:38` |
| 27 | Input X contains NaN | unit 4: `features.py:185-188` no longer drops rows |
| 25 | purge/embargo shorter than label availability horizon | `estimators.py:280` |
| 6 | No module named 'pytest' | R-17 |
| 4 | prices must contain executable 'Open' prices | `targets.py:56` |

That is 120 of 168. The rest are assertion failures in modules only 019 changed, encoding pre-019
behaviour: `test_targets` expects h rather than h+1, and `test_ml_signal` expects the terminal
flatten. One `test_reports_api` failure is not attributed.

By module [O]: `test_feature_scaling` 39, `test_metrics` 23, `test_targets` 23, `test_ml_signal` 15,
`test_backtest_harness` 12, `test_ma_crossover_backtest` 11, `test_model_cv` 11,
`test_multi_ticker_comparison` 8, `test_estimators` 8, `test_signals` 5,
`test_feature_set_comparison` 5, loader (pytest import) 6, `test_logistic_baseline` 1,
`test_reports_api` 1.

**A note on the h+1 purge.** It is one row more conservative than required. `walk_forward_cv.py:98`
keeps `t < test_start - label_horizon`. With a purge of h, the last kept label ends at
`Open[test_start]`, which is known before the decision at that session's close. h+1 is therefore a
choice, not a derivation. It is still defensible, but it is what breaks every `EMBARGO_BARS = 1`
configuration.

**Severity.** P0 for each unit that introduces a listed message.

**Recommended action.**

- Reverse "no seventh review unit" (`CODEX_LANE_HANDOFF.md:169`) in effect: each unit PR leaves
  `python -m unittest discover -s tests` green on its own. A unit merged onto a red main cannot
  pass Rule 9, because "what would break if it were wrong" is unanswerable when 168 things already are.
- Legacy tests that encode a defect the audit named are rewritten, not deleted, and the PR names
  the finding.
- `EMBARGO_BARS` becomes the returned span, not a literal. Record in the contract that h+1 is
  chosen (R-23).

## R-03 — Spec 020 as written would leave 019 unrunnable for every dividend payer

**Claim.** 019 rejects any positive dividend without a payment session
(`backtest_harness.py:45-48`, `data.py:418-420`). Spec 020 concedes the vendor usually lacks
historical payment dates (020 `spec.md:162-166`). Landing 020 unamended does not unblock Stage 3.3
for any dividend-paying ticker in its universe.

**Evidence.** `Equity = Cash + Quantity×Price + Receivable` (`backtest_harness.py:84-88`). A payment
moves Receivable to Cash (`:110-111`, `:124-125`), leaving Equity unchanged. A pay date therefore
changes **only** `Buying_Power`, never equity, returns or drawdown.

**Severity.** P0 for Stage 3.3; P1 for 019.

**Recommended action.**

- Add to 019's contract: if a payment session is not sourced, use a declared upper-bound session,
  and record `Pay_Date_Basis ∈ {sourced, bound}` on the dividend event.
- A later pay date can only reject more orders, never admit an unaffordable one, so this is
  Rule 1-safe. Spec 020 supplies the bound per ticker from primary filings.
- Kill M4 (R-13) first, because a bound date may fall on a non-session.

## R-04 — The price-basis tag is a declaration with two divergent validators

**Claim.** The tag has no non-test writer, and its two consumers validate different rule sets.

**Evidence.**

- `execution_price_frame` requires the tag (`data.py:401-402`) but never sets it. The only writer in
  `scripts/` stamps `research_adjusted` (`data.py:302`). Tests stamp `unadjusted_dollars` by hand
  (`tests/test_019_ledger.py:13`, `tests/test_019_conventions.py:129`).
- `run_backtest` does not require `execution_price_frame`'s output. It re-validates a different
  subset: no OHLC bounds, no volume, no ticker check when `Ticker` is absent
  (`backtest_harness.py:45-62` vs `data.py:408-420`).
- Both basis checks are exact string compares, yet an allowlist→denylist mutant survives (M1), as
  does deleting the second check outright (M2).

**Severity.** P1.

**Recommended action.**

- State in the contract that the tag is a declaration against accident, not a proof against
  forgery. Its only non-test writer will be 020's single loader (020 `spec.md:115`).
- Put the frame rules in one function that both call sites use.
- Add negative tests with an arbitrary third tag (kills M1) and an adjusted tag into
  `execution_price_frame` (kills M2).

---

# Part 2 — HAC bandwidth

## R-05 — Bandwidth untied to h: latent for overlapping series; fixed L=5 at the live call

**Claim as posed.** Labels are overlapping h-period returns, so Bartlett bandwidth must be at least
h−1. Unit 6 never ties it to h.

**Verification.**

1. **True that nothing ties L to h.** `performance_summary` hardcodes `min(5, len(returns)-1)`,
   computed twice: once for the SE and once for the recorded `hac_lags` (`scripts/metrics.py:343-344`).
   `performance_summary` has no horizon parameter. `mean_log_return_se` (`:256-273`) has no overlap
   parameter and accepts any `lags ≥ 0`.
2. **Not true today that a t-stat is inflated.** The only call runs on
   `equity_log_returns(curve["Equity"])` (`:333`): one account return per session,
   non-overlapping. The MA(h−1) structure belongs to per-decision h-period series, not to this one.
   No t-statistic is computed anywhere in `scripts/`; the only inferential outputs are the ADF
   p-value (`stationarity_check.py:22`) and McNemar and Wilcoxon (`feature_set_comparison.py:391`,
   `:442-443`).
3. **Where overlap is real.** `compare_regression` ranks per-decision squared-error differences on
   labels (`feature_set_comparison.py:423-426`). At h=1 the new labels share only an endpoint; at
   h>1 they overlap, which is finding 28 (`AUDIT.md:103`). That is the first place anyone will
   substitute a HAC SE, and this function would be wrong there.

**Why "at least h−1" is necessary but not sufficient [D].** Let y_t be the sum of h iid
unit-variance returns, sampled every period. Then γ_j = h−j for j < h, and the long-run variance is
h². Bartlett with L ≥ h−1 estimates h + 2Σ_{j<h}(1−j/(L+1))(h−j) = **h² − h(h²−1)/(3(L+1))**.

At the floor L = h−1 the recovered variance ratio is **(2h²+1)/(3h²)**:

| h | Variance ratio | SE ratio | t inflated by |
|---:|---|---|---|
| 5 | 51/75 = 0.68 | 0.825 | 1.21× |
| 2 | 0.75 | 0.866 | 1.15× |
| → ∞ | 2/3 | 0.816 | 1.22× |

- **L = 0** recovers 1/h, so t is inflated by √h.
- **The current fixed L = 5 at h = 10** recovers (10 + 2·Σ_{j=1..5}(1−j/6)(10−j))/100 =
  (10 + 115/3)/100 = 0.483, so t is inflated about 1.44×.
- **Staying within 5% variance understatement** needs L+1 ≥ (h²−1)/(0.15h), about 6.7h.

**Live-call convention [D].** Newey–West (1994) gives floor(4(n/100)^(2/9)). At n = 2,514 sessions
(`AUDIT.md:23` [A]) that is floor(8.19) = 8. The fixed 5 is tied to nothing.

**Severity.** P1, latent. It becomes P0 the moment finding 25 or 28 work passes a label-indexed
series. The fixed L at the live call is P2.

**Recommended action.**

1. **Signature — `metrics.py:256`.**
   `mean_log_return_se(returns, *, overlap: int, lags: int | None = None)`. `overlap` is required:
   the periods each observation spans. Use 1 for daily account returns. For per-decision label
   series use **h, the label horizon** — not the h+1 span `targets.py:127` returns (R-10).
2. **Validation.** Reject `overlap < 1` and `lags < overlap−1` with `ValueError`. Reject
   `bool`/non-int `lags` (M19 currently survives).
3. **Default bandwidth.** When `lags is None` and `overlap == 1`, use
   `lags = min(n−1, floor(4·(n/100)**(2/9)))`.
4. **Overlapping series.** When `overlap > 1`, raise `NotImplementedError` for now; no such caller
   exists. Finding 28's spec picks the estimator and validates it on simulated nulls, as
   `AUDIT.md:103` requires: non-overlapping subsamples (every h-th decision, exact) or a block
   bootstrap with block ≥ h. Do not ship Bartlett at L = h−1 for label series — the table shows it
   still understates.
5. **Call site — `metrics.py:343-344`.** Compute `lags` once via rule 3 and pass the same variable
   to the SE and to `hac_lags` (M15 currently survives).
6. **Nonpositive variance — `metrics.py:273`.** Return `nan` when variance ≤ 0 instead of
   `max(0., variance)`. A zero SE is an infinite t-stat, and this file already refuses `inf` for
   Sharpe (`:237-241`). Bartlett with /n is PSD, so this is unreachable today; a kernel change makes
   it reachable.
7. **Tests.** Add a hand oracle at `lags ≥ 2` — the only oracle is at `lags=1`
   (`tests/test_019_conventions.py:17-22`), where Bartlett's 1−1/2 equals the wrong 1−1/(2L), so
   M14b survives. Test that `hac_lags` equals the lags used, and that `lags < overlap−1` raises.

---

# Part 3 — Claimed closures against AUDIT.md

## R-06 — Closure table

| Finding (AUDIT.md) | Claimed | Evidence | Verdict |
|---|---|---|---|
| 01 (`:45`) funded ledger | closed | `backtest_harness.py:81-144`; `metrics.py:101-171`; hand oracles `test_019_ledger.py:23-34`, `test_019_prices.py:28-41` | **Closed at library only** (R-08). M3, M4, M11–M13 show the reconciliation holds only on the happy path. |
| 02 (`:47`) initial capital | closed | `metrics.py:212-214`, `:290-305`; `test_019_metrics.py:17-40` | **Downgrade to partial** (R-07). |
| 03 (`:49`) invalid fills | partial | `backtest_harness.py:57-64`, `:170-171` | Agree. The tearsheet half belongs to 018. |
| 04 (`:51`) cost domains | partial | `metrics.py:27-32` used at `backtest_harness.py:36`, `ml_signal.py:61` | Agree, with a correction: "production runs must carry an explicit cost configuration" is unmet (R-18). |
| 10 (`:63`) marking vs liquidation | closed | `backtest_harness.py:143-144`; `metrics.py:348`; `ml_signal.py:181-182`; `test_019_calendar.py:38-46` | **Agree.** |
| 11 (`:65`) ledger validation | closed | `metrics.py:97-189` | **Downgrade to partial** (R-09). |
| 12 (`:67`) Sharpe/CAGR/cash | partial | `metrics.py:243-253`, `:339-347` | Agree; add R-05. |
| 13 (`:71`) adjusted vs executable | partial | `data.py:392-426`; `backtest_harness.py:37` | Agree; add R-03 and R-04. |
| 22 (`:91`) executable target | closed | `targets.py:52-63`, `:77-96`; `test_019_targets.py:15-21` | **Agree**, with R-10 fixed before merge. |
| 23 (`:93`) calendar-preserving features | closed | `features.py:185-188`; `estimators.py:275-285`, `:349-350`; `model_cv.py:300-313`, `:439-450`; `test_019_calendar.py:24-35`, `:94-110` | **Closed at core only** (R-08). Callers that skip the masks now fit on NaN rows (27 errors, R-02). |
| 24 (`:95`) NaN endpoints | closed | `targets.py:71-74`, `:84-88`; `test_019_targets.py:24-30` | **Agree.** |
| 25 (`:97`) prediction-to-utility | open | `ml_signal.py:161-163`; `spec.md:34-35` | Agree (R-15). |

## R-07 — Finding 02's fix is carried by `attrs` and silently reverts when they are lost

**Claim.** Pre-trade anchoring is chosen by sniffing `attrs`. Without them the metrics return the
exact pre-audit figure, with no error.

**Evidence.**

- `equity_log_returns` anchors only if `equity.attrs.get("capital_base")` exists
  (`metrics.py:212-214`); `max_drawdown` does the same (`:290-292`).
- On the audit's own fixture [O], `max_drawdown(curve["Equity"])` gives −0.10.
  `pd.Series(curve["Equity"].to_numpy())` and a CSV round trip both give −0.0526 — the defective
  value the audit reported (`AUDIT.md:47` [A]: −5.263%).
- Mutant M21 shows no test pins the anchor at `performance_summary` level, the level consumers read.
- The same pattern makes the purge guard fail open. `model_row_masks` defaults the required span to
  the caller's own value when `attrs` are absent (`estimators.py:278`). A caller passing
  `label_horizon=1` for an h=2 label then passes the very check `test_019_calendar.py:86-91`
  enforces. Compare R-01, where the price-basis guard fails closed.

**Severity.** P1.

**Recommended action.**

- Make `capital_base` an explicit required keyword of `equity_log_returns` and `max_drawdown`, with
  explicit `capital_base=None` to opt out.
- Make the required span an explicit argument of `model_row_masks`, taken from the value
  `build_features` returns. Keep `attrs` as an echo, never as the switch.
- Add a summary-level drawdown test (kills M21).

## R-08 — 01 and 23 are library closures; record them that way

**Claim.** The handoff's "closed" (`CODEX_LANE_HANDOFF.md:37-39` [H]) is accurate only at the library
boundary.

**Evidence.**

- Finding 01's subject is "the source of account returns". The tearsheet route that rendered that
  number (`reports/api/routes/backtest.py:53-57`) now raises instead of being replaced.
- Finding 23's cited symptom (the API rundown turning September 4 into September 3,
  `AUDIT.md:93`) is untouched.

**Severity.** P2 as wording; the consumer work itself is tracked elsewhere.

**Recommended action.** Mark both "library-closed; consumer open (018 T024; API rundown)" in the
contract section (R-23). Do not mark them closed in any status surface until a consumer test passes.

## R-09 — Finding 11: IDs are row numbers, and the checks guarding them are untested

**Claim.** Finding 11 names "trade/fill IDs" and "per-event balances". The IDs exist but link
nothing, and three named validations survive deletion.

**Evidence.**

- `Trade_ID` is `np.arange(len(log))` (`backtest_harness.py:146`). Ledger events carry no
  `Trade_ID`, and trades carry no entry or exit `Event_ID`, so fills and trades are linked only by
  chronology.
- Deleting the `Trade_ID` check (M17), the `Event_ID` check (M20) or the source-quote check (M11)
  passes all 65 tests [O].
- M11 matters most. The replay prices fills from the ledger's own `Price` (`metrics.py:135`,
  `:142`), so a tampered fill quote with consistent cash is caught only by the untested line `:121`.

**Severity.** P1.

**Recommended action.** Add `Entry_Event_ID` and `Exit_Event_ID` to trade records, validated against
the ledger; finding 08's order lifecycle will need a join key regardless. Add tamper tests that kill
M11, M17 and M20.

## R-10 — `build_target` documents a horizon but returns a span

**Claim.** The docstrings say the third return value is "the horizon that was used". The code
returns `horizon + 1`.

**Evidence.**

- `targets.py:109-111` and module docstring `:3-6` versus `:127`. `features.py:125-129` repeats the
  claim, and `:187` stores the span under the key `label_horizon`.
- A caller who follows the docstring and passes the value back as `horizon=` builds an
  (h+1)-session label. The 23 `test_targets` failures ("2 != 1", "3 != 2" [O]) are that confusion
  in executable form.

**Severity.** P1; fix before the unit 3 PR merges.

**Recommended action.** Rename the documented value, and the `attrs` key, to
`label_availability_span`. State "span = h + 1; never pass it as `horizon`". Add a test that
`build_target(..., horizon=span)` differs from the original label.

---

# Part 4 — Mutation attack on units 5 and 6

## R-11 — The 019 helper cannot express "a guard was removed"

**Claim.** "16 semantic mutants killed" (`CODEX_LANE_HANDOFF.md:4` [H]) is a count over the one class
of defect the helper can express.

**Evidence.**

- `killed()` counts a kill only on `AssertionError` (`tests/test_019_mutation_support.py:16-19`).
  When `pytest.raises` sees no exception it raises `Failed`, whose MRO is
  `Failed → OutcomeException → BaseException` [O], and that escapes the `except`.
- A guard-removal mutant on `data.py:401` with a `pytest.raises` oracle did not register as a kill;
  it escaped as `Failed: DID NOT RAISE ValueError` [O].
- Consequently **0 of the 16** existing mutants target a `raise`. All of them alter arithmetic,
  assignments or value conditions (`test_019_ledger.py:71-77`, `test_019_metrics.py:58-63`,
  `test_019_targets.py:50-57`, `test_019_calendar.py:113-122`, `test_019_prices.py:74-80`,
  `test_019_conventions.py:115-121`).
- **Mutants collide.** A mutant whose edit rewrites another mutant's find string "kills" via that
  test's own `count(old) == 1` assertion. Observed as M14 [O].
- **Encoding is locale-dependent.** `read_text()` without an encoding reads cp1252 on this Windows
  host (`test_019_mutation_support.py:9`).

**Severity.** P1; the evidence claim is overstated.

**Recommended action.** Restate the handoff figure as "16 of 16 value mutants; 0 guard mutants
attempted". Resolve the tooling through R-16, not by patching this helper.

## R-12 — Vacuous negative tests: the error arrives from an unrelated guard

**Claim.** Two negative tests pass even when the guard they name is deleted.

**Evidence.**

- `test_missing_pay_date_and_invalid_split_fail` (`tests/test_019_prices.py:68-71`) calls
  `run_backtest(p)` without `starting_capital`. With the action validation at
  `backtest_harness.py:45-48` deleted, the same `ValueError` type still arrives from `:68-69`, so M3
  survives [O].
- `test_adjusted_and_undeclared_prices_cannot_fund_account` (`:20-25`) omits capital too, and is
  rescued only by `match='unadjusted'`.

**Severity.** P1.

**Recommended action.** Every negative test passes otherwise-valid arguments, so the only defect is
the one under test, and pins the message with `assertRaisesRegex` after R-17's conversion.

## R-13 — 22 of 22 candidate mutants on unit 5/6 guards survive the 65 tests

**Method.** Each row replaces an exact find string, occurring exactly once, in a scratch copy of
`scripts/`. It runs the six 019 test files with Appendix A's command, then restores.
Control: 65 passed [O]. Every row finished "65 passed" [O].

M14 as first written (`1 - lag / (2 * lags)` on `metrics.py:272`) failed only
`test_metric_convention_mutants`, through the collision in R-11. M14b applies the same weight change
on `:271`, leaving the find string intact, and survives.

| # | Unit | Location | Change | Behaviour broken |
|---|---|---|---|---|
| M1 | 5 | `backtest_harness.py:37` | `!= "unadjusted_dollars"` → `in (None, "research_adjusted")` | Allowlist becomes denylist; any other tag funds an account |
| M2 | 5 | `data.py:401` | basis check → `if False:` | Adjusted frames produce a `Research_Close` |
| M3 | 5 | `backtest_harness.py:45` | action validation → `if False and (...)` | Split 0 wipes holdings; NaT pay date leaves the receivable unpaid forever |
| M4 | 5 | `backtest_harness.py:108` | `date <= row.Date` → `==` | Pay date on a non-session never pays, contradicting `CODEX_LANE_HANDOFF.md:95-96` |
| M5 | 5 | `targets.py:91` | split term → `pd.Series(False, ...)` | A split-spanning price ratio (e.g. log(½) for 2:1 [D]) is emitted as a label |
| M6 | 5 | `targets.py:93` | `range(2, h+2)` → `range(h+1, h+2)` | h≥2: an action inside the interval is undetected |
| M7 | 5 | `data.py:421` | `Split*(Close+Div)` → `(Split*Close+Div)` | Same-day split and dividend: dividend treated as per pre-split share |
| M8 | 5 | `data.py:424` | `Volume / Split.cumprod()` → `Volume` | `Rel_Volume` jumps at every split (`features.py:155`) |
| M9 | 5 | `data.py:415` | High bound → `False` | Invalid OHLC accepted |
| M10 | 5 | `data.py:419` | pay-date check → `if False:` | `execution_price_frame` accepts what `run_backtest` rejects |
| M11 | 6 | `metrics.py:121` | drop source-quote clause | Tampered fill quote with consistent cash reconciles |
| M12 | 5 | `metrics.py:148` | drop split-vs-source clause | Tampered split ratio with consistent quantity reconciles |
| M13 | 5 | `metrics.py:127` | duplicate-action check → `if False:` | Duplicated corporate action reconciles |
| M14b | 6 | `metrics.py:271` | covariance × (1−j/2L)/(1−j/(L+1)) | Non-Bartlett weights for L≥2, the range `performance_summary` uses |
| M15 | 6 | `metrics.py:343` | SE `lags=min(5,n−1)` → `lags=0` | Reported SE ignores autocovariance while `hac_lags` still says 5 |
| M16 | 6 | `metrics.py:342` | drop CAGR finite guard | Insolvent account reports finite CAGR |
| M17 | 6 | `metrics.py:172` | `Trade_ID` check → `if False:` | Renumbered trades reconcile |
| M18 | 6 | `metrics.py:243` | risk-free domain check → `if False:` | Hurdle −1 gives `log1p(−1) = −inf` [D]; Sharpe `+inf` |
| M19 | 6 | `metrics.py:264` | lags validation → `if False:` | `lags=-1` silently means 0; `lags=True` means 1 |
| M20 | 6 | `metrics.py:98` | drop `Event_ID` clause | Renumbered events reconcile |
| M21 | 6 | `metrics.py:334` | drawdown on `pd.Series(values)` | Summary drawdown un-anchored: finding 02 returns (R-07) |
| M22 | 6 | `backtest_harness.py:71` | `cash <= 0` → `cash < 0` | Zero-capital account accepted |

**Severity.** P1 per row. Each unit PR must kill its rows before merge.

**Recommended action.** Add one test per row, written so the row turns from survivor to kill.
Register all 22 rows in the converged runner (R-16) as regression mutants.

## R-14 — Rule 9: guards outnumber the explanation of what they protect

**Claim.** `equity_curve` is a 140-line replay (`metrics.py:57-197`) with more than 20 distinct
`raise` sites. The 5.5 KB spec, plan and tasks do not say which defect each guard prevents, or which
test proves it.

**Evidence.** R-13: most guards in units 5 and 6 have no test that fails when they are removed.

**Severity.** P1.

**Recommended action.** Each unit PR carries a guard table with four columns: guard file:line, defect
prevented, killing test, killing mutant id. That table is Rule 9's "what would break if it were
wrong", in checkable form.

---

# Part 5 — Finding 25

## R-15 — Constrain the policy to fixed-horizon; do not restate it as optimal stopping yet

**Claim.** The policy re-decides every session with asymmetric thresholds
(`scripts/ml_signal.py:215-227`). Its own docstring concedes the h-session label does not fix the
holding period (`:161-163`; `spec.md:25-26`). For h>1, an entry justified by E[label_t] clearing the
round-trip hurdle can exit at t+1 on a new prediction. The realized trade's payoff is then not the
label whose forecast justified it, and nothing in the pipeline estimates that realized payoff.

**Recommendation: fixed-horizon, explicitly.** Four reasons.

1. **It is identified.** Under fixed-horizon, each trade's pre-cost log return is exactly its entry
   decision's label: entry `Open[t+1]`, exit `Open[t+h+1]` (`targets.py:63`,
   `backtest_harness.py:131`, `:92`). That is an exact, testable identity. An optimal-stopping
   payoff depends on future decisions and has no such identity.
2. **Optimal stopping needs what the audit orders later.** It needs a continuation value for every
   remaining k ≤ H — a family of labels or a distributional model — with the stopping rule selected
   inside training folds only (`AUDIT.md:97`). That is work order 5 (`AUDIT.md:233`) and research
   direction A (`AUDIT.md:201-207`), both sequenced after the ledger and dataset work. Building it
   now is the "model on a broken pipeline" CLAUDE.md warns against.
3. **It costs nothing today.** Both runners use h = 1 (`multi_ticker_comparison.py:77`,
   `feature_set_comparison.py:106`). At h = 1 the current hysteresis already is fixed-horizon: each
   held session is a one-session position whose payoff is that session's label. The looser exit
   threshold only reflects that continuing incurs no new round trip. The constraint forbids only
   h>1 hysteresis.
4. **It does not close 25.** E[log return] ≠ E[simple return] remains (`AUDIT.md:97`), so 25 stays
   open. Fixed-horizon removes the timing half of the mismatch, the half 019 is chartered to fix.

**Severity.** P1. It becomes P0 as soon as any caller uses h>1.

**Recommended action.**

- **Contract sentence (R-23):** "A decision at t with horizon h opens at `Open[t+1]` and closes at
  `Open[t+h+1]`; no early exit, no extension. Hysteresis is permitted only at h = 1."
- **Code.** `positions_from_predicted_return` gains a required `horizon: int` — the label horizon,
  not the span — and raises `ValueError` for h>1. A future h>1 scheduler is a separate function,
  not a mode flag.
- **Test.** In a zero-cost run, every closed trade's `log(Exit Price / Entry Price)` equals its entry
  row's label to 1e-12.
- **Deferral.** Optimal stopping gets its own spec under work order 5, with multi-horizon labels and
  in-fold policy selection.

---

# Part 6 — Mutation harness convergence

## R-16 — Converge on the 018 runner shape; take one idea from 019

**Claim.** Two harnesses built 24 hours apart disagree on isolation, kill criterion and dependencies.
A third will appear unless one is canonical.

**Evidence.**

| Property | `tests/mutation/run_spec_018_mutants.py` | `tests/test_019_mutation_support.py` |
|---|---|---|
| Isolation | copied tree, subprocess (`:88-104`) | `exec` into live module dict (`:14-15`) |
| Kill criterion | any test newly FAIL/ERROR vs control (`:131-133`) | designated oracle raises `AssertionError` only (`:18-19`) |
| Guard removal expressible | yes | no (R-11) |
| Non-Python targets (TSX) | yes (`:39-41`) | no |
| Stale cross-module names | none; the copy is re-imported | yes: `backtest_harness.py:6` keeps the unmutated `validate_costs` |
| Runner dependencies | stdlib + `unittest` | pytest (R-17) |
| Encoding | explicit UTF-8 (`:101`) | locale default (`:9`) |
| Registry | one data tuple with finding ids (`:32-77`) | calls scattered across six test files |
| Import error counted as a kill | **yes** (`:116-117`), a weakness | no, a strength |

**Severity.** P1.

**Recommended action.**

1. **One driver.** Generalize to `tests/mutation/run_mutants.py --spec {018,019,all}`. `COPIED` and
   `TEST_MODULES` become registry fields.
2. **Per-spec registries.** `tests/mutation/spec_018.py` and `tests/mutation/spec_019.py` each export
   `MUTANTS`. Each record holds `finding`, `file`, `find`, `replace`, `restored_defect` and
   `expected_killers` (test ids).
3. **Kill classes.** Report **killed-as-designed** (newly failing tests include an expected killer),
   **killed-incidentally** (counted, but the oracle is flagged as mis-aimed), and **survivor**. A
   mutant whose copy fails to import is **invalid**, not killed; take 019's rule over `:116-117`.
4. **Migrate before deleting.** Move 019's 16 mutants and R-13's 22. Delete
   `test_019_mutation_support.py` and the six `test_*_mutants` functions only after the migrated
   registry reproduces 16/16 kills.
5. **CI.** A separate job, not `unittest discover`, required on PRs touching `scripts/`.
6. **Convention.** Camden adds one sentence to CLAUDE.md "Tests.": mutation evidence lives only under
   `tests/mutation/` with one driver.

The driver runs `unittest`, so R-17 is a prerequisite.

---

# Part 7 — Constitution and CLAUDE.md compliance

## R-17 — The 65 tests do not run under the project's test command (P0)

**Claim.** CI and the canonical command never execute the new tests, and report 6 errors instead.

**Evidence.**

- CLAUDE.md:129-131 names `python -m unittest discover -s tests` and puts test-only libraries in
  `requirements-dev.txt`. That file has no pytest (`requirements-dev.txt:8-9`), and CI installs only
  it (`.github/workflows/test.yml:19-20`).
- Discovery on `test_019_*.py` gives 6 `ModuleNotFoundError: No module named 'pytest'` [O]. The venv
  lacks pytest too [O], as the handoff notes (`CODEX_LANE_HANDOFF.md:139-142` [H]).
- Even with pytest installed, `unittest` does not collect module-level `test_*` functions. The
  handoff's "65 passed" was obtained by injecting a system site-packages path (`:144` [H]).

**Severity.** P0 for every unit.

**Recommended action.** Convert all six modules to `unittest.TestCase`: `pytest.raises(match=)` →
`assertRaisesRegex`, `parametrize` → `subTest`, `pytest.approx` → `assertAlmostEqual` or
`np.testing`, and delete the `capsys` print (R-21). Do not add pytest; a second runner is the kind of
addition Rule 6 exists to question.

## R-18 — Rule 3: the funded harness still defaults costs to zero

**Claim.** Omitting costs silently produces a gross result.

**Evidence.**

- `run_backtest(commission_per_trade=0.0, slippage_bps=0.0)` (`backtest_harness.py:19-20`);
  `summarize_trades` does the same (`:157-158`). A zero default is a gross mode reached by omission
  (constitution:73-75).
- Audit 04: "production runs must carry an explicit cost configuration" (`AUDIT.md:51` [A]). The
  handoff acknowledges "zero-cost fixture defaults remain" (`CODEX_LANE_HANDOFF.md:44` [H]).
- The defaults predate 019, but 019 rewrote this signature.

**Severity.** P1; fix in unit 6.

**Recommended action.** Make both cost parameters required keyword-only, as `equity_curve` already
does (`metrics.py:61-62`). Unit 6 already breaks every call site by requiring capital, so the
marginal migration cost is zero. Zero-cost tests pass `0.0` explicitly.

## R-19 — Rule 5 gap case: a missing session changes the label without a trace

**Claim.** Rule 5 requires tests for "missing bars, holidays, halts" (constitution:117-120). The
positional shifts in 019 have none.

**Evidence.**

- Targets shift by row (`targets.py:63`). If the session after t is absent, `Open[t+1]` is the next
  *observed* open and the label silently spans more sessions.
- `test_019_calendar.py:26` injects a NaN value into a present row — a value gap, not a session gap.
- Harness payments on a non-session pay date are untested (M4).

**Severity.** P1.

**Recommended action.** Now: add missing-row tests that pin the positional behaviour, and state it
in the contract (R-23). Enforcing a complete calendar belongs to finding 16 (`AUDIT.md:77`), work
order 3.

## R-20 — Rule 8: the replay is a consistency check, not an independent oracle

**Claim.** The cross-module coupling is recorded, but one claim about it is overstated.

**Evidence.**

- `ml_signal.py:47` and `backtest_harness.py:6` import `metrics`. This is justified at
  `CODEX_LANE_HANDOFF.md:170-173`, which is acceptable as a recorded exception.
- The overstated part: `metrics.py:135-143` re-derives the fill model at `backtest_harness.py:92-93`
  and `:131-132`, from the same author and with the same formulas. A shared misconception, such as
  the slippage sign, passes both.
- The independent oracle the audit asks for (`AUDIT.md:169`) is the set of hand-computed literals in
  `test_019_ledger.py:29-33` and `test_019_prices.py:35-41`.

**Severity.** P2.

**Recommended action.** Describe the replay as "consistency", and cite the hand oracles as the
acceptance evidence. Move `validate_costs` to a pure `scripts/costs.py` in a later spec.

## R-21 — Rule 11: unsourced figures in the handoff, a test, and spec 020

**Claim.** Several rendered figures carry no artifact, commit and date, which Rule 11
(constitution:212-225) requires.

**Evidence.**

- **Handoff.** `CODEX_LANE_HANDOFF.md:4` ("65 … 16"), `:137` ("65 passed in 2.90s") and `:152-154`
  (policy, buy-and-hold and random figures) name no commit, and the file has no date.
- **The baseline figures' only artifact** is stdout from `tests/test_019_conventions.py:149-151`,
  which prints P&L figures under `capsys.disabled()` and persists nothing. Terminal output is in
  scope (constitution:214).
- **The "16 killed" count** omits its denominator (R-11).
- **Spec 020 `spec.md:111`** ("~$105", "~$25", "> $80.00") and **`:90`** (`created_at_utc` example)
  are unsourced and unlabelled. 020 is on 019's critical path (R-01).

**Severity.** P1: each surface must be fixed before the PR that touches it merges.

**Recommended action.**

- Delete the print and assert the invariants instead: equal bars, equal capital, one trade per seed.
- Move handoff figures into the unit PR descriptions with the PR head SHA and date.
- Cite `AUDIT.md:45` and `:47` on `spec.md:39-40`'s oracle values. Label or source spec 020's figures.
- **Out of 019 scope:** `performance_summary` returns cost and capital metadata but no dataset or run
  identity (`metrics.py:338-361`). Route that to finding 59 so Stage 3.3 closes it.

## R-22 — Rule 4 and CLAUDE.md:145: 019 changes every ML position series without a real baseline

**Claim.** 019 is a strategy change in the CLAUDE.md:145 sense, but a Rule 4 comparison on real data
is impossible until 020.

**Evidence.** Unit 3 moves the target from close-to-close to open-to-open, and unit 4 removes the
terminal flatten; together they change the positions of every ML strategy run. The only baseline
offered is a synthetic 8-session fixture (`test_019_conventions.py:124-151`;
`CODEX_LANE_HANDOFF.md:147-155` [H]), which the handoff itself calls "not a substitute for Rule 4".

**Severity.** P1.

**Recommended action.** Units 3 and 4 PR text states a Rule 4 exception explicitly: "no real-data
baseline possible until spec 020; historical ML results are non-comparable". Camden accepts or
rejects that exception at merge. The synthetic fixture must not be presented as compliance.

---

# Part 8 — Where the frozen contract belongs

## R-23 — Move "Frozen timing and price contract" into `spec.md` as its own normative section

**Claim.** The contract lives in an ephemeral handoff (`CODEX_LANE_HANDOFF.md:71-100`). Two partial
copies also live in `spec.md` (`:15-19` timing, `:29-33` prices). Three texts will drift.

**Recommended placement.** Insert a new section **`## Timing and price contract (normative)`** in
`.specify/specs/019-funded-ledger-and-timing/spec.md`, **after** `## Frozen decisions` (which ends at
`:35`) and **before** `## Acceptance` (`:37`). It belongs there because the Acceptance oracles at
`:39-43` test exactly these definitions, and a reader must meet the definitions first.

**Contents**, moved from the handoff and reorganized:

1. `### Instants`: one table of `feature_available_at`, `decision_at`, `entry_at`, `exit_at` and
   `label_available_at`.
2. `### Targets and cross-validation`.
3. `### Accounting`.
4. `### Prices and corporate actions`.
5. `### Session labels and phases`.

In the same edit, replace `spec.md:15-19` and `:29-33` each with a one-line pointer, and replace
handoff `:71-100` with a one-line pointer.

**Corrections to make while moving** — moving the text verbatim would freeze its errors:

- **Span, not horizon.** The third return value is `label_availability_span = h + 1`, never a
  horizon (R-10).
- **Purge.** h+1 is chosen, and is one row more conservative than `walk_forward_cv.py:98` requires
  (R-02).
- **Positional shifts.** A missing session lengthens a label (R-19).
- **Pay dates.** The sourced/bound policy, once decided (R-03).
- **Fixed-horizon.** The constraint, and hysteresis only at h = 1 (R-15).
- **The tag.** A declaration whose only non-test writer is spec 020's loader (R-04).
- **Closure status.** 01 and 23 are library-closed, consumer open (R-08).

**Why not a `contracts/` file.** Spec 018 uses `contracts/library-boundaries.md`, but this contract
and 019's Acceptance are one unit of meaning. Splitting them recreates the drift this move exists to
remove.

**Severity.** P1; do it with unit 1's PR, which already carries the spec documents
(`CODEX_LANE_HANDOFF.md:18-19`).

---

# Appendix A — Commands behind every [O] figure

All run 2026-09-14 on base `4023aa54` + working tree. `$SYS` is
`C:\Users\Owner\AppData\Local\Programs\Python\Python313\python.exe` (Python 3.13, pytest 9.1.1).
`venv\Scripts\python.exe` is Python 3.13.14 with pandas 3.0.5 and no pytest.

1. **019 tests:** `$SYS -B -m pytest -p no:cacheprovider -q tests/test_019_ledger.py tests/test_019_metrics.py tests/test_019_targets.py tests/test_019_calendar.py tests/test_019_prices.py tests/test_019_conventions.py`
   → `65 passed`.
2. **Canonical suite:** `venv\Scripts\python.exe -B -W ignore -m unittest discover -s tests`
   → `Ran 553 tests`, `FAILED (failures=40, errors=128)`. The R-02 groupings are regex counts over
   that command's stderr (`^(FAIL|ERROR): ` ids and exception lines).
3. **Canonical discovery of 019:** `venv\Scripts\python.exe -B -W ignore -m unittest discover -s tests -p "test_019_*.py"`
   → `Ran 6 tests`, 6 × `ModuleNotFoundError: No module named 'pytest'`.
4. **Mutants (R-13).** Copy `scripts/` plus `tests/context.py` and `tests/test_019_*.py` to a scratch
   directory. For each row, assert the find string occurs once, replace it in the copy, run
   command 1 in the copy, and restore. The repository was never edited.
5. **attrs fallback (R-07).** Build `test_019_metrics.loss_curve()`'s frame (Open/Close 50, capital
   100, $5 commission, buy at row 0, sell at row 2). Evaluate `max_drawdown` on `curve["Equity"]`,
   on `pd.Series(curve["Equity"].to_numpy())`, and on
   `pd.read_csv(StringIO(curve.to_csv(index=False)))["Equity"]`.
6. **Helper blind spot (R-11).** Import `pytest`, then call
   `killed(data, 'if frame.attrs.get("price_basis") != "unadjusted_dollars":', 'if False:', oracle)`,
   where `oracle` wraps `execution_price_frame` on a complete frame tagged `research_adjusted` in
   `pytest.raises(ValueError)`. Observe the escaping `Failed`.
