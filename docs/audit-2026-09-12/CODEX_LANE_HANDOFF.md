# Core Python lane handoff — spec 019

Core implementation and focused verification are complete for the bounded
cash-account profile below. **65 tests pass; 16 semantic mutants are killed.**
No git command, Spec Kit command, cache write/download, package installation,
API/UI/CI edit, portfolio-risk edit, or external message was performed.

**Publication limitation:** no branches or PRs were created. The explicit git
ban and human-owned version control leave publication to Camden. The six
sequential review units below are the PR assembly boundaries, not claims of
six published PRs. Do not submit the combined working-tree change as one PR.

## Changed-file inventory and review boundaries

Counts are added + removed production/test lines against in-memory snapshots
after each unit, using line-sequence comparison (no git). Final GitKraken
hunk grouping can differ. Every unit has substantial room below 400 lines.
Keep spec documents with unit 1 and append each unit's handoff evidence with
that unit rather than placing this entire handoff in the last PR.

| Unit / proposed PR title | Files and exact responsibility | Code + tests |
|---|---|---:|
| 1 — Fund orders from cash | `scripts/backtest_harness.py`: funded `run_backtest`, validation, closed-trade summary; `tests/test_019_ledger.py`; `tests/test_019_mutation_support.py` | 272 |
| 2 — Anchor account metrics before fills | `scripts/metrics.py`: ledger-backed `equity_curve`, initial-capital log returns/drawdown; `tests/test_019_metrics.py` | 236 |
| 3 — Predict executable open-to-open returns | `scripts/targets.py`: endpoint masking and h+1 availability; `tests/test_019_targets.py` | 126 |
| 4 — Preserve inference sessions through CV | `scripts/features.py`: eligibility instead of deletion; `scripts/estimators.py`: `model_row_masks`, fit/inference filtering; `scripts/model_cv.py`: inner/outer masks; `scripts/ml_signal.py`: remove terminal flatten; `tests/test_019_calendar.py`; mutation helper namespace repair | 200 |
| 5 — Separate dollar prices and corporate actions | `scripts/data.py`: adjusted-cache tag, `execution_price_frame`; harness split/dividend/payment events; metrics receivable reconciliation; features causal research series; targets action-spanning abstention; `tests/test_019_prices.py` | 200 |
| 6 — Validate accounting conventions and metadata | `scripts/metrics.py`: shared costs, event/trade validation, log hurdle, HAC mean SE and growth conventions; harness imports shared validator, requires capital, adds trade IDs; `scripts/ml_signal.py`: shared finite costs/thresholds and audit-25 limitation; `tests/test_019_conventions.py`; ledger tests pass capital explicitly | 323 |

Also created, by hand: `.specify/specs/019-funded-ledger-and-timing/spec.md`,
`plan.md`, `tasks.md`, and this handoff. These and the table enumerate **every
file touched**. All eight production modules were confirmed under `scripts/`
before editing. No original test file was modified.

## Findings and authority disagreements

- **Closed within the declared single-asset cash profile:** 01, 02, 10, 11,
  22, 23, 24. Event IDs, trade IDs, quantities, fees, phases, source quotes,
  cash, receivables, closed-trade metadata and cumulative P&L reconcile.
- **03 closed at the core boundary:** invalid prices/signals/costs fail;
  nonfinite trade P&L cannot become a successful zero-P&L summary.
- **04 core work complete, HTTP closure belongs to the other lane.** Shared
  `metrics.validate_costs` is used by harness, metrics and signal costs.
  Zero-cost fixture defaults remain; production callers must supply costs.
- **12 partial:** effective annual hurdle converted to log units; mean log
  return separated from 252-session CAGR; zero cash interest and fixed hurdle
  labeled; Bartlett HAC mean uncertainty with recorded bandwidth added.
  Expected-session validation, historical cash rates, robust Sharpe/CAGR
  uncertainty and bandwidth sensitivity remain open. No significance badge.
- **13 partial:** adjusted/undeclared prices cannot fund an account; explicit
  raw-dollar/action input boundary and causal research series implemented.
  Verified vendor raw snapshots, archival provenance and migration remain
  open. This run was forbidden to regenerate or overwrite the cache.
- **25 remains open:** E[log return] is not E[dollar payoff], and hysteresis
  need not hold for the label's h sessions. Timing is repaired; utility
  calibration, conditional payoff distributions and policy selection are not.

**Actual plan/audit disagreement:** audit work order 2 includes 22–25, while
the derived plan's Stage 3.2 omits 25 and places it only in Stage 3.5. Audit
wins: 25 was assessed here and remains an explicit blocker, not silently
deferred out of scope. Audit also lists 25 in work order 5; that is not a
reason to omit its work-order-2 assessment.

**User overrides of the plan, not audit disagreements:** the plan proposes
022–025 and targets/data before ledger; this run requires handwritten 019
and ledger-first order. The plan labels those spec numbers proposed. The
audit imposes neither those numbers nor that internal sequence. 03–04 are
work-order-1 prerequisites used here; their Stage 3.1 assignment agrees with
the audit. No other Stage-3.2/work-order-2 disagreement was found.

## Frozen timing and price contract

- `feature_available_at` and `decision_at`: after session t's close.
- `entry_at`: Open[t+1]. `exit_at`: Open[t+h+1], for an h-session forecast.
- Target: log(Open[t+h+1]/Open[t+1]); `label_available_at`: exit open.
  Both endpoints must be finite and positive. Final h+1 labels are missing.
  Labels crossing a split/dividend are unavailable, not misleading price
  ratios. A total-payoff target across actions is future work.
- Purge/embargo span is h+1. `build_target`/`build_features` return that
  availability span. CV refuses a shorter span than feature-frame metadata.
- Preserve source sessions and index. Filter training and validation after
  calendar splitting; inference does not require a known outcome. Multi-asset
  callers must split by ticker; these CV/target paths reject mixed tickers.
- No final-row flatten. Default accounting marks open positions; optional
  `liquidate=True` records a terminal-close liquidation and charges its fee.
- Capital must be explicit before the first open. Entry notional plus fee is
  consumed atomically; rejected orders incur no fee. Buying power is cash;
  Reserved_Cash is zero because there are no outstanding orders or financing.
- `price_basis='unadjusted_dollars'` means verified historical dollar prices.
  Never apply this tag to old adjusted caches to bypass the boundary.
  `execution_price_frame` validates OHLCV/actions and derives Research_Close
  and Research_Volume forward without rewriting earlier research values.
- Split is new shares per old share, 1 for no action, before the open.
  Dividend is dollars per post-split share: entitlement before ex-date opening
  trades; cash only on the stated payment session (or first observed session
  thereafter). Receivables contribute equity but never buying power.
- Dates are naive session labels. Phase distinguishes initial/open/close;
  these are not broker execution timestamps. Initial peak position is -1,
  with no invented previous trading day. Split fractions are retained;
  broker cash-in-lieu, withholding and settlement restrictions are unmodeled.

## Red evidence, mutation evidence, lookahead answers

Each unit's new tests was run before implementation. These are excerpts of
actual failures, not reconstructed examples or import failures. Commands used
`python -B -m pytest -p no:cacheprovider tests/test_019_<unit>.py -q`.

| Unit | Actual red output | Mutants killed | First-principles lookahead answer |
|---|---|---|---|
| 1 (`ledger`) | `AssertionError: A $100 account accepted a $201.10 entry`; original trade entry `200.1`, net P&L `-2.2`; **10 failed** | affordability disabled; entry fee omitted; forced liquidation | Already-shifted decisions consume only that open's price; marks use that close. Prefix events do not change when rows are appended. Unit 6 removes the legacy capital fallback so the first close cannot determine funding at the first open. |
| 2 (`metrics`) | `Obtained: -0.052631578947368474`, `Expected: -0.1`; open-position P&L `assert 0.0 == 5.0`; **4 failed, 1 passed** | initial peak omitted; initial return omitted | Initial capital predates every fill. Fees belong to their actual event; a future exit cannot change earlier close equity. |
| 3 (`targets`) | `AssertionError: overnight gain occurred before executable entry`; `assert np.float64(0.6931471805599453) == 0.0`; **13 failed** | entry moved to current open; purge shortened; null made class zero | Future opens are outcomes only. Their availability is t+h+1; no outcome can enter features or training before that point. |
| 4 (`calendar`) | `AssertionError: feature construction compressed the session calendar`; `assert [True, False] == [True, True]`; `AssertionError: warmup/gap reached estimator fit`; **5 failed** | label-row deletion; terminal flatten; training mask bypass | Trailing features are prefix-invariant. Both CV paths pass full future-price perturbation tests; folds split the intact source calendar before masks. Missing inference never moves the next open. |
| 5 (`prices`) | `Failed: DID NOT RAISE ValueError` for adjusted data; `assert [1.0, 1.0, 1.0, 0.0] == [1.0, 2.0, 2.0, 0.0]`; **6 failed** | split omitted; dividend credited immediately; research chain omitted | Actions occur only on/after their supplied dates. Research adjustments chain forward. Payment information cannot make an ex-date receivable spendable early. |
| 6 (`conventions`) | Sharpe `6.515810180854346` vs expected `6.5351506733716604`; `missing autocovariance-aware uncertainty`; **7 failed, 2 passed** initially | effective hurdle treated as log; autocovariance dropped | These are retrospective descriptive statistics, not decision inputs. Fixed annualization and bandwidth are explicit assumptions, never fitted to improve a decision. |

Additional unit-6 red checks exposed and then fixed: omitted-capital acceptance
(`DID NOT RAISE`); a total loss producing annualized log mean
`-6.147560685348439`; early payment and dividend-created shares (both
`DID NOT RAISE`); all five corrupted trade quantity/cost/income/cumulative-P&L
fields (`5 failed, 15 passed`). These were tested before their fixes too.

The original $100-price/$100-capital/$5-fee drawdown probe cannot legally
enter a funded account: $105 exceeds $100. The funded regression uses a
$50 share with the same $100 capital and $5 fees, reproducing the exact
equity path `[95,95,90]` and correct -10% drawdown without borrowing.

Mutation precedent was verified in 012 `tasks.md` T015 and 017 `plan.md`
SC-008. 003 and 007 contain no mutation suites. The committed helper executes
an in-memory source mutant, runs a passing original control first, requires
an assertion failure, restores module globals and verifies the source hash.
It neither edits production files nor counts an import error as a kill.
The unit-4 namespace repair ensures test mocks affect mutant globals too.

## Final verification and integration notes

Final result: **65 passed in 2.90s**, only the six new test modules, including
all 16 mutation cases. Python 3.13; pandas 3.0.5; sklearn 1.9.0; pytest 9.1.1.
The venv did not contain pytest (`No module named pytest`); that startup error
was not TDD evidence. System pytest was used for red/green runs, then the
existing pytest location was appended for the final venv-interpreter run:

```powershell
venv/Scripts/python.exe -B -c "import sys; sys.path.append(r'C:\Users\Owner\AppData\Local\Programs\Python\Python313\Lib\site-packages'); import pytest; raise SystemExit(pytest.main(['-p','no:cacheprovider','tests/test_019_ledger.py','tests/test_019_metrics.py','tests/test_019_targets.py','tests/test_019_calendar.py','tests/test_019_prices.py','tests/test_019_conventions.py','-q']))"
```

Synthetic baseline fixture: 2026-08-24 through 2026-09-02, 8 identical sessions,
$100 capital, $1 per fill, 5 bps slippage, explicit terminal liquidation.
Predetermined policy and every random seed make one two-session round trip;
buy-and-hold enters the next open and liquidates at the final close. No model
fit: fold count 0; purge/embargo not applicable to fixed fixture decisions.
Policy net P&L **-$0.0220**; buy-and-hold **$4.1759**; random across seeds 0–19
mean **-$0.0248**, sample SD **$0.00123969436**. These are mechanical oracles,
not historical strategy results, alpha claims, or a substitute for Rule 4's
real experiment before promoting a trading policy.

**Consumer changes required:** pass explicit capital and verified raw-dollar
prices; handle unavailable adjusted data; retain ledger attrs (CSV trade logs
alone cannot recover an account); accept mark-only open positions; propagate
the returned h+1 span; mask unknown outer labels when scoring predictions.
Predictions may exist on inference rows whose outcomes are not yet known.
Existing close-to-close results and callers that assumed dropped rows are
not interchangeable with this contract. The API/experiment integrations and
their older tests were neither modified nor run. Spec 013's real run stays held.

**Cuts/open work:** 12, 13 and 25 as described above; persistent dataset/run
manifests; corporate-action total-payoff labels; portfolio sizing/risk and
recovery; broker execution realism; full-session coverage validation. No
seventh review unit, cache migration, consumer rewrite or calibrated strategy
was added to conceal these limits. No new dependency was introduced. The
shared numeric cost validator lives in metrics because a new shared core
module is outside this lane; signals import that pure validator, never fills
or account state. This is the explicit Rule 8 boundary justification.
