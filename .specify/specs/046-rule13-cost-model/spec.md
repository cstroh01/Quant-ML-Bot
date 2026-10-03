# Feature Specification: Rule 13 cost model — OHLC half-spread and square-root impact

**Feature Branch**: `046-rule13-cost-model` (name only; version control is human-owned)
**Spec number**: 046. Directory inspection on 2026-10-03 found 045 as the highest
existing spec folder and no 046 folder. 035/038/039 remain reserved by the finish
plan; 042 remains reserved as recorded in spec 045's header.
**Created**: 2026-10-03
**Status**: Draft specification only. This writing task creates `spec.md`,
`plan.md`, and `tasks.md`; it authorizes no implementation or test edits.
**Input**: the owner's 2026-10-03 draft supplied with this task. D-1–D-3 and
placement are decided, reproduced in §7. The draft's external decision-note path
was not found in this checkout and is not used as a repository reference.
**Blocks**: S4's use of real Rule 13 cost evidence; does not alone complete
spec 033 or grant capital readiness.

## Hard precondition — sequencing

Place this work at **S3b, after S2 and before S4**, also dependent on S1/035's
unadjusted bundle and 044's nominal-price/volume provenance contract. Preserve
those dependencies even though some of the older finish-plan prose is historical.
No change to `docs/V1-FINISH-PLAN.md` is part of this drafting task.

Implementation waits for the upstream S1/S2/044 implementation prerequisites
and the published-paper verification gate in FR-001; document their completion
before starting U1. This drafting task does not claim those steps are complete.
Real-data acceptance additionally requires a bundle with an allowed, evidenced
`volume_basis`. Spec 044 §5's current Q-P4 amendment selects
`provider_unverified`; finishing 044 alone is not evidence that this prerequisite
is met. Synthetic, explicitly labelled fixtures can exercise the offline path;
they cannot authorize relabelling production volume. Existing ledger-write,
source-file pin, network, and merge gates remain in force.

## 1. Verified starting state and problem

The following citations were checked against the local tree on 2026-10-03,
without network access or Git commands. They describe this tree, not an asserted
checkout of the draft's historical `5840b62` revision.

| Evidence | Current finding |
|---|---|
| `.specify/memory/constitution.md:281` | Rule 13 requires daily-OHLC half-spread plus square-root impact and forbids flat-bps assumptions for reported backtests. |
| `scripts/backtest_harness.py:84` | One `slippage_bps / 10000.` rate is applied to sells at line 98 and buys at line 138; terminal liquidation uses the sell helper at line 151. |
| `reports/api/routes/backtest.py:44` | The tearsheet query defaults to 5.0 bps and passes it into the harness at line 64. |
| `scripts/selection_bias.py:41` | Eligibility compares the complete sidecar costs mapping against config commission and slippage, returning `cost_mismatch` on inequality. |
| `scripts/selection_bias.py:42` | After earlier eligibility checks pass, a model other than `spread_plus_sqrt_impact` returns `realistic_costs_missing`. This is a metadata check, not a numerical cost verifier. |
| `tests/spec033_support.py:14` | The only assignment of this model string found in current Python production/test sources is the synthetic fixture; the production occurrence is the eligibility comparison. |
| `scripts/trial_runner.py:115` | `Attempt.account` currently constructs flat-bps sidecar costs. Line 114 also declares `oos=False`; realistic costs must not flip that flag. |
| `scripts/metrics.py:128` | Equity reconciliation reconstructs a buy using flat bps, and line 135 does the same for an exit. Wiring only the harness would leave accounting inconsistent. |
| `.specify/specs/044-nominal-price-reconstruction/spec.md:147` | FR-005 permits only `nominal_reconstructed` or `provider_nominal` volume for cost-model consumers and assigns their refusal red proof to this spec. The Q-P4 caveat is at line 273. |
| `docs/SCOPE-V1.md:133` | The limitations register describes the intended Rule 13 model as modeled, not fill-calibrated; this is not implementation evidence. |
| `docs/V1-FINISH-PLAN.md:49` | S1 is the bundle step; S2 starts at line 74, S4 at line 91, and S7 at line 128. None of S1–S8 explicitly implements this model. |

Inspection of `scripts/` found no daily-OHLC spread/square-root-impact estimator.
`cost_utils.py` validates flat-cost inputs and converts the risk-free rate; it
does not supply that estimator. Existing real-run paths therefore do not establish
Rule 13 cost evidence. Cost compliance is necessary, not sufficient: OOS/CV,
corporate-action verification, source identity, ledger and backfill evidence
remain independent requirements of 033. No claim is made that changing one
string admits a real trial or makes Gate 3 pass.

## 2. Scope and module ownership

Add `scripts/cost_model.py`, owning a deterministic **per-fill cost estimate**.
It consumes validated market history and an externally supplied fill quantity;
it must not know signals, choose sizing, calculate P&L, download data, or write
the trial ledger. The harness consumes an injected cost function and remains
responsible for fills, affordability, cash, positions and accounting.

Include the minimal accounting, recorder, caller, API/schema and report changes
needed to carry the same actual cost evidence end to end. Reported strategy and
baseline runs share the same preregistered cost configuration and evaluation
period. Flat bps survives only as an explicit unit-test/unreported-diagnostic
mode labelled **`not reportable (Rule 13)`**, never as a fallback.

Free data only; standard library and existing pinned dependencies only. No
package, paid feed, broker path, signal redesign, sizing policy, calibration,
threshold tuning, ledger-history rewrite or relaxation of 033 is in scope.
Using an authors' reference implementation as a cited oracle is permitted after
verification; adopting it as a new dependency is not proposed or authorized.

## 3. User scenarios and testing

- **US1 (P1): a fill has reproducible modeled costs.** Given valid nominal
  OHLCV history through session t and an external quantity Q, a fill at t+1
  receives a half-spread and square-root-impact breakdown with source and as-of
  metadata; independent expected values match, and commission remains separate.
- **US2 (P1): unavailable evidence cannot become free trading.** Unverified
  volume, incomplete windows, invalid observations or undefined estimates refuse
  explicitly before a fill, with no zero-cost or flat-bps fallback.
- **US3 (P1): accounting and evidence describe the executed model.** The
  harness's actual fills reconcile to funded cash/returns, and the exact cost
  mapping reaches trial config, sidecar and reporting surfaces. A mismatched
  cost field is rejected by 033; a forged model label does not satisfy the
  numerical integration test.
- **US4 (P1): reported results disclose their limits.** Every Rule 13 result
  shows the model, provenance and the modeled-cost limitation. Diagnostic flat
  costs cannot appear as a reportable strategy or baseline result.

### Edge cases (Rules 1 and 5)

| Case | Required behavior |
|---|---|
| First row or incomplete trailing history | Explicit unavailable/refusal; no fill and no substituted zero. |
| First complete window, last row, fold boundary | Use only history available at the decision cutoff; a preceding history buffer is allowed, a future buffer is not. |
| Fill at next open | Estimate from bars ≤ t only. The t+1 execution quote converts the already determined fraction into fill dollars; t+1 OHLCV must not enter the estimator. |
| Weekend/holiday versus missing trading session | Count trading sessions, not calendar days. Expected closures are allowed; missing required observations refuse rather than fill/interpolate. |
| Future-row perturbation | With Q held fixed, independently perturb t+1 and later O/H/L/C/Volume; the cost fractions, window membership and as-of record stay unchanged. |
| Split within a window or before exit | Never compare Q and ADV on inconsistent share bases or treat a nominal split jump as ordinary volatility. Source-verified conventions or explicit refusal are required; no invented adjustment. |
| Zero/nonfinite ADV, invalid Q, malformed OHLCV | Refuse with a specific reason; never clamp to convenient liquidity or silently omit a row. |
| Terminal close liquidation | Charge the same model on the exit quantity using history strictly before the liquidation session; record phase/cutoff. No same-session completed bar enters its estimate. |
| Buy-and-hold/random baseline during warm-up | Apply the same declared usable-history/evaluation policy as the strategy; do not exempt baselines from costs. |

## 4. Functional requirements

- **FR-001 — Published half-spread source.** **HUMAN-VERIFICATION GATE:**
  **implement from the published paper; record the equation and page reference
  in research.md before coding**. Verify the Ardia–Guidotti–Kroencke JFE 2024
  published version, estimator identity, full-spread-to-half-spread conversion,
  units, required lags/observations, and the paper's negative/undefined handling.
  Cite any reference implementation used as an oracle. Record an independently
  checked numerical fixture and tolerance. No estimator formula is asserted
  here from memory. The reviewer must verify compatibility with D-2's fixed
  21-session choice before freezing the implementation; a conflict is a blocker,
  not permission to change that choice silently. Record handling/status in output.
- **FR-002 — Square-root impact.** The impact fraction is
  `Y * sigma_daily * sqrt(Q / ADV)`, with Q the absolute proposed fill quantity
  in shares and ADV mean daily volume in compatible share units. The total
  adverse slippage fraction is half-spread plus impact; commission is separate.
  Y is 1.0 for the primary run. Cite the square-root-law source and state that
  this Y is a preregistered assumption, not an empirical calibration. Record the
  daily-return convention, sigma estimator, sample count and split treatment
  before coding; no annualized sigma substitution. Robustness Y values 0.5 and
  2.0 are separate labelled rows, never searched or selected for performance.
- **FR-003 — Point-in-time windows.** Spread, sigma and ADV use 21 trading
  days trailing through t. A t+1 fill uses only bars ≤ t for every estimate;
  windows are never centered, backfilled or fitted over the full sample. Any
  additional lag needed to form 21 returns is declared and is also ≤ t. Dates
  are unique, sorted, timezone-naive midnight session labels, per `CLAUDE.md`.
  Tests cover independent future-field perturbations, first/last usable window,
  fold joins, holidays and missing trading sessions.
- **FR-004 — Verified volume.** Refuse any frame whose `volume_basis` is not
  exactly `nominal_reconstructed` or `provider_nominal`. Missing, `None`,
  `adjusted` and `provider_unverified` all refuse. Preserve the original basis
  and source manifest identity; never infer verified volume from dollar-volume
  invariance or relabel it to pass. Carry 044 FR-005's refusal red proof here.
- **FR-005 — Config and provenance binding.** Canonical slippage config
  contains `model="spread_plus_sqrt_impact"`, `spread_window=21`,
  `impact_coef=1.0`, `sigma_window=21`, `adv_window=21`, and `source`, plus the
  estimator/version, statistical conventions and all result-affecting policies
  defined in `plan.md`. Serialize unchanged into trial config and sidecar costs:
  `metadata.costs == {"commission": config.commission, "slippage": config.slippage}`.
  Preserve the matching actual config in harness output. Costs are registered
  before evaluation; execution cannot silently change them. Record per-fill
  fractions, Q, ADV, sigma, cutoff/window bounds, basis and handling status,
  bound to run/source identity. Do not insert per-fill data into the invariant
  cost mapping or falsely assert OOS/CV/corporate-action eligibility.
- **FR-006 — Warm-up and invalid estimates.** A required incomplete window
  or undefined estimator is an explicit refusal before executing that order.
  Never substitute zero, flat bps, shortened windows or stale estimates. Data
  history may precede the evaluation start; the same declared start and refusal
  policy apply to strategy and baselines. A paper-defined valid zero, if any,
  must be distinguished from warm-up and supported by the verified oracle.
- **FR-007 — Disclosure.** Every surface reporting a Rule 13 result carries
  **“costs modeled, not calibrated against real fills”**, source/run/date
  provenance and the applicable Rule 16 limitations. Include costs for strategy
  and both baselines; unknown/unavailable states show reasons, not fabricated
  results. Do not reinterpret any prior flat-bps artifact as Rule 13 evidence.
- **FR-008 — Injection and accounting.** The injected function receives only
  market inputs through the cutoff, quantity and cost config, returns a finite
  valid breakdown or explicit refusal, and cannot select orders or resize them.
  Buys pay adverse slippage; sells and terminal liquidation receive adverse
  slippage. Affordability includes actual modeled fill cost and commission.
  Preserve ledger reconciliation using recorded per-fill costs rather than
  reconstructing flat-bps fills. Invalid fractions that would yield nonpositive
  fill prices refuse; no silent cap or model substitution.
- **FR-009 — Diagnostics boundary.** Reported paths have no flat-bps option
  or default. Diagnostic flat-bps runs require explicit intent and the D-3
  label in their output/metadata, remain ineligible for 033, and retain recording
  obligations for real inspected attempts. Absence/failure of the injected model
  cannot select diagnostics implicitly. Unmigrated paths refuse reportable
  output; a model string alone cannot certify a run.
- **FR-010 — Evidence and review size.** Tests are offline, use synthetic
  temporary ledgers, and do not write production history or fetch market data.
  Every gate has its named planted defect and clean control (§5). The three
  implementation units in the plan each have a hard ≤300 added-plus-removed
  line cap, including tests/evidence/status edits. Scope pressure is reported
  before proceeding; it cannot remove a required check or waive the cap.

## 5. Rule 12 acceptance and planted defects

All fixtures are labelled `EXAMPLE — NOT A RESULT`. Expected spread values come
from the human-verified paper oracle, never the implementation under test.
Observe contract failures before implementation, then record mutant kills and
unmutated green controls separately. Mutants live in memory or isolated copies;
unrelated exceptions, imports or collection failures are not successful kills.

| ID | Planted defect / field changed | Acceptance that must catch it |
|---|---|---|
| M1 | Center the spread window or include t+1 in sigma/ADV | Future O/H/L/C/Volume perturbations leave the prefix cost unchanged only in the clean implementation. |
| M2 | Replace `sqrt(Q/ADV)` with `Q/ADV` | At fixed history/sigma/ADV, 4× Q gives 2× the **impact component**, with half-spread unchanged. |
| M3 | Permit `volume_basis="adjusted"` or `provider_unverified` | Specific volume-basis refusal; both permitted bases pass on valid controls. |
| M4 | Return zero during warm-up | First-incomplete-window order is refused, while first-complete-window order has an oracle-backed estimate. |
| M5 | Execute flat bps while stamping the correct model string | Real harness fill/cash/impact assertions and sidecar config checks fail; metadata-only assertions are insufficient. |
| M6 | Alter one sidecar cost parameter after config is registered | Otherwise eligible fixture is excluded by `build_matrix` with `cost_mismatch`; equal config/sidecar control is included. |
| M7 | Use full spread as half-spread, or replace undefined handling with zero | Independent paper fixture and handling-status assertions fail. |
| M8 | Charge the buy sign on a sell, use requested rather than held exit Q, or reconcile via flat bps | Hand-enumerated buy/sell/split/liquidation funded accounting fails on the changed operand. |
| M9 | Omit the limitation or expose a flat-bps control/result | API/schema/rendered-report or CLI acceptance fails on the actual consumed field/text. |
| M10 | Select the best robustness Y or drop a cost convention from canonical config | Primary remains 1.0; labelled 0.5/2.0 rows cannot replace it; changed convention changes the config identity. |

## 6. Success criteria

- **SC-001**: The published-source human gate is recorded in future
  `research.md`, with equation/page, units, policies and independent expected
  values; D-2 compatibility is verified. No such verification is claimed today.
- **SC-002**: Offline fixtures prove exact trailing cutoffs, impact scaling,
  volume refusal, warm-up, edge cases and paper-defined spread behavior.
- **SC-003**: Strategy and baseline fills reconcile under the injected model;
  the complete actual cost mapping reaches 033 unchanged, and M5/M6 go red.
  Other eligibility failures retain their true reasons and are not bypassed.
- **SC-004**: Reported surfaces expose the actual model and Rule 16 limitation;
  no flat-bps result is reportable. Diagnostic exceptions are explicit.
- **SC-005**: M1–M10 have named failures and green controls; the full offline
  suite passes with actual passed/failed/xfailed/skipped counts reported. Each
  implementation unit meets its measured ≤300-line cap.
- **SC-006 — HUMAN GATE, real-data readiness**: After upstream source/bundle,
  volume and ledger permissions are satisfied, a separately authorized run
  binds a valid bundle and actual cost evidence. Until then report offline
  mechanism readiness only; neither 044 completion nor synthetic fixtures
  establish real Rule 13 results or a passing capital gate.

## 7. Decisions — DECIDED 2026-10-03

- **D-1**: Y = 1.0 fixed and preregistered; {0.5, 2.0} is a robustness table
  only, never selected on.
- **D-2**: 21 trading days trailing through t for spread, sigma and ADV.
  Published-paper compatibility must be verified before freezing, as FR-001
  requires. This is verification of the chosen design, not an open tuning choice.
- **D-3**: Remove flat bps from every reported surface. The harness may retain
  it solely for unit tests/unreported diagnostics labelled
  `not reportable (Rule 13)`.
- **Placement**: S3b, after S2 and before S4, with 044 and S1/035 prerequisites.

## 8. Open verification items and exclusions

No D-1–D-3 or placement decision is reopened. Outstanding evidence is the
published estimator equation/page and negative/undefined rules, the precise
21-session observation/return and split conventions, the square-root-law
citation, and verified production volume. These are explicit pre-coding or
real-data gates, not permission to invent formulas or fetch data in this task.

This spec-writing task changes no code, tests, manifests, existing specifications,
governance, finish plan, state file, ledger or cache. It produces no strategy
results. Future implementation still owes Rules 1, 5, 6, 12, 13 and 16 and all
unchanged independent accounting, provenance and human gates.
