# Spec 044 review

Date: 2026-09-30. **Verdict: request changes before implementation.**

Static review only. No Git, pytest, network, probe execution, or repository-code execution. Only
this review file was written. Read all five input files present in the spec directory, including
`artifacts/p1_probe.py`, which appeared during the review; the requested adapter, validators, and
yfinance fakes; and supporting snapshot/cache, fixture, and mutation-helper code. Line references
below refer to the refreshed snapshot after concurrent edits to the spec, plan, tasks, and probe
were observed and reread. Those edits were not made by this review.

Benchmarks: constitution Rules 1, 5, 12 and 14; `CLAUDE.md:127-144` session-label rules; the
requested hard limit of 300 changed lines per unit. No implementation or executed mutant evidence
exists in the reviewed 044 materials. The draft cross-check explicitly has pending provider values
and incomplete coverage.

## Ranked findings

No P0 established. The following are five P1 and six P2 findings. Paths `spec.md`, `plan.md`,
`tasks.md`, and `artifacts/*` are relative to this spec.

### R1 — P1: Q-P2 can certify missing adjustment data

**Location:** `artifacts/p1_probe.py:107-119`.

If `Adj Close` is NaN on the examined rows while Close and Dividends exist, `observed` is NaN.
Equality with Close is false, so the equality stop does not fire. `abs(NaN - expected) >
ADJ_CLOSE_TOL` is also false, so `bad` stays empty and the function returns PASS. This is a false
determination of a prerequisite to reconstructing prices. Require finite, positive price
denominators and finite observed/expected factors before comparisons; a missing usable observation
must stop. Add a local synthetic NaN case and a finite passing control when tests are authorized. Do
not count the blanket exception handler as protection: NaN arithmetic need not raise.

### R2 — P1: The volume decision does not identify the adjustment convention

**Location:** `spec.md:157-160,224-233`; `artifacts/p1_probe.py:149-167`.

Medians across different sessions confound adjustment with actual trading activity. Nominal volume
can be similar before and after a split; dividing such history by a later split factor would change
an earlier nominal observation because of an event after that observation. Conversely, activity can
create a step in already-adjusted volume. Dollar-volume invariance cannot validate the provider
convention: multiplying price and dividing volume by the same factor guarantees that identity even
when the convention is wrong.

The registered bands also overlap. **EXAMPLE — NOT A RESULT:** for a 2:1 split, a measured post/pre
ratio of 1.8 fits both [0.5, 2] and [1.5, 2.5]. The probe skips overlapping bands at lines 154-156,
which improves ambiguity handling but differs from the registered rule and does not remove the
activity confound. Require evidence that distinguishes the same observation's share basis, or keep
the conclusion explicitly inconclusive and define which downstream uses remain blocked. An
inconclusive pass-through must not be certified as nominal volume. M3 must also branch on the final
decision: pass-through has a different mutant and oracle from division by F.

### R3 — P1: An open request end does not establish the response's adjustment horizon

**Location:** `spec.md:61-67,143-147,176-180`; `tasks.md:66-70`. Related existing checks:
`scripts/data.py:598-605,1099-1116`.

There is no rule for a stale/truncated response, beyond recording its last session. Existing
contiguity validates only the returned first-to-last range; the writer records those actual
endpoints. Neither checks coverage against the request or the latest completed market session. A
response containing prices adjusted for a later split but ending before that event's row supplies an
incomplete factor. If that event is beyond `verified_through`, FR-006 cannot catch it; with no
returned event, even the event-specific disclosure can miss it.

Define the required response horizon against an explicit as-of time and market calendar, distinguish
normal weekend/holiday lag from missing completed sessions, and refuse an unestablished adjustment
horizon. Separately define requested-window coverage. Compare reference events over an explicit
common coverage interval: blindly comparing through `verified_through` also rejects an intentionally
earlier as-of response for events that had not happened yet. Add stale-response, ordinary
non-session lag, missing endpoint, and known missing post-window split cases. A
`split_factor_basis_through` label alone does not establish completeness.

### R4 — P1: Post-window factor events bypass the existing action validator

**Location:** `spec.md:140-147`; `plan.md:68-74`; `tasks.md:66-68`. Existing boundary:
`scripts/data.py:693-707,1091-1095`.

The new factor consumes events outside the bundle, but only window action rows reach the unchanged
corporate-actions validator. No requirement validates all factor events before multiplying them.
**EXAMPLE — NOT A RESULT:** two negative post-window ratios, both beyond the reference coverage, can
multiply to a positive factor of 4. Earlier OHLC remain positive; no corresponding action is in the
bundle, so the existing positive-value and discontinuity checks cannot reject them. Duplicate factor
events can likewise silently double-adjust rows.

Validate the full factor input for unique normalized session labels, finite positive event ratios,
and a finite positive cumulative factor before slicing. Distinguish zero meaning "no split" from
malformed events; do not silently discard invalid ratios. The probe currently discards
nonpositive/NaN event values at `artifacts/p1_probe.py:50-58`, so it is not evidence of this guard.
Add malformed post-window events with no-write assertions and passing controls.

### R5 — P1: T-PIT does not yet guarantee that M2 goes red

**Location:** `spec.md:259`; `tasks.md:46-48`; `plan.md:71-72`.

The test describes two response ends but never fixes the requested bundle `end`. If call A requests
through A's last row and call B requests through B's last row, the window-only mutant includes the
new split in B. Both correct and mutated implementations can reconstruct the common prefix
identically, so M2 survives the named test. Testing only the pure helper also misses an adapter that
slices away events before invoking it.

Require the same requested `[start, end]` in both adapter calls; put the added split strictly after
that fixed end; let only the supplied as-of response grow and coherently re-adjust its prefix.
Compare explicit expected market fields after download/load, excluding response-specific provenance.
A fake must also assert one history call with open end, rather than ignore a wrong closed end.
Coordinate injected reference coverage with each as-of response so that a reference-table refusal
does not mask the intended M2 assertion.

### R6 — P2: T010 needs explicit assertion/reference migration, not just price edits

**Location:** `tasks.md:35-39,57-60`; `tests/test_041_pay_date_bound.py:163-188`;
`tests/test_020_unadjusted_price_data.py:242-291`.

The 041 offline-flow test requires an exact closed-end history call. It remains red after correct
FR-002 implementation until that assertion explicitly requires open end. The fakes also need
injected reference tables: 020 uses `TEST`, and 041 uses a synthetic AAPL split in January 2024.
FR-006's production default will reject them. Authorize those narrow fixture-seam changes rather
than dropping the gate or switching the success path to `SyntheticSource`.

T013's claim that the migrated tests all fail against the old adapter is also incorrect. The first
020 test calls `fetch` and asserts options/limitations, not reconstructed prices. The second checks
a null pay date and the existing sourced-policy refusal. Both can still pass after an OHLC-only
fixture edit. Record the actual intended red assertion per case. Preserve the null-date refusal,
no-write checks, funded-ledger assertions, and nominal non-yfinance fixtures; details appear below.

### R7 — P2: The planned mutant wiring cannot produce the stated Unit 1 evidence

**Location:** `spec.md:190-191,252-263`; `tasks.md:54-60,64-76,80-82`;
`tests/mutation_support_019.py:7-21`.

Unit 1 requires M1/M2/M3/M4/M6 with green controls before the function they mutate exists. The
helper requires exactly one matching production fragment and runs the clean oracle before mutation.
Those conditions are unavailable on the pre-044 tree. Write red contracts/oracles first, then
explicitly defer source-fragment wiring and green-control/kill evidence to the implementation unit,
as separate task statuses.

The helper catches only `AssertionError`. M1/M6 naturally raise `ValueError` from the split oracle;
translate only the expected named semantic failure into the helper's assertion protocol, leaving
unrelated exceptions as errors. M5 also needs a defined code mutation: an omitted-event input alone
is a negative test, not an in-memory source mutant. Pair that input with a comparison-bypass mutant
and a valid-table control, or specify an extraction mutant and its exact assertion behavior.

### R8 — P2: Exact historical invariance is stronger than the rounding model permits

**Location:** `spec.md:76-84,88-100`; `plan.md:77-78`; `tasks.md:42,46-48`.

The draft acknowledges provider rounding noise but requires identical rebuilt values across
adjustment horizons. **EXAMPLE — NOT A RESULT:** an earlier nominal price 100 reported as 33.333333
after a 3:1 adjustment reconstructs as 99.999999, not 100. Exact synthetic cancellation proves
algebra for those inputs; it does not establish exact invariance of provider observations.

Retain exact tests on hand-derived, exactly representable fixtures and add a quantized-provider case
documenting the residual and its limits. Distinguish that evidence from strict historical identity;
do not silently relax the split oracle's tolerance. Expected factors must be independently
enumerated, not computed with the same helper under test. FR-006 cannot guarantee arbitrary rounding
or vendor-revision errors disappear.

### R9 — P2: The new factor alignment has no timezone regression contract

**Location:** `plan.md:68-70`; `tasks.md:42-53`; `scripts/data.py:1162-1165`; `CLAUDE.md:127-144`.

The current adapter strips the label's zone without shifting its displayed date, then normalizes to
midnight/nanoseconds. New search/slice operations must use those same labels for prices and split
events. Raw aware indices versus naive bounds can raise; an implicit timezone conversion can move a
label and change which factor applies. The existing 041 validator tests reject aware on-disk
actions; they do not test this new adapter alignment.

Add equivalent naive and exchange-zone-labelled histories across a DST boundary, a split on a slice
boundary, and assertions for the preserved date, naive midnight dtype, factors, and provenance date.
Normalize consistently before comparison; do not reinterpret session labels as UTC instants.

### R10 — P2: The unit plan does not enforce 300 changed lines

**Location:** `plan.md:24-25,54-60`; `tasks.md:33,62,78`.

The plan expressly permits about 400 changed lines, while the task headings use approximate budgets.
No completed diffs exist to prove any unit is within 300. Unit 1's estimate already consumes 300 for
tests and fixture migration; reports, task edits, reference injection, and the call assertion also
count. Unit 2's estimate omits the deferred mutation wiring needed by R7.

Unit 0 now includes a 215-line probe and a 25-line cross-check draft: 240 lines before input CSVs,
determination output, baseline evidence, or decision edits. That is an inventory, not a measured
completed-unit diff. Its ~150-line estimate is already stale. Replace the standing rule with a hard
300-line added-plus-removed budget including evidence and task edits; reserve room and split the
test/mutation/probe work at reviewable boundaries. Measure every actual unit against saved pre-unit
files without Git. No unit is certified here.

### R11 — P2: The probe omits reproducible rows and does not enforce dividend coverage

**Location:** `tasks.md:19-31`; `spec.md:132-134,224-229`;
`artifacts/p1_probe.py:66-95,98-119,122-146,157-162,188-210`.

The probe writes quarter extrema, one worst dividend factor discrepancy, selected dividend values,
and volume medians; it does not save the daily rows behind the decisions. These summaries cannot
reproduce those decisions offline if the provider revises its history. Q-P3 can infer a global
convention from one informative declaration, without enforcing the registered basket/event coverage.
A same-day split/dividend convention can remain unverified even though the spec applies it. The
refreshed Q-P1 rule now expressly permits one quarter preceding two splits; that is no longer a
mismatch with the probe.

Record the exact input rows, selected evidence coverage, file provenance, and per-case outcomes.
Require the specified informative cases or mark the unsupported cases unresolved. Primary
declarations must state the share basis on a split ex-date. Reconcile the overlap handling with the
registered Q-P4 rule before the probe runs. The refreshed spec now registers Q-P1's 1% range
expansion, resolving that earlier mismatch; the volume inference issue remains.

## Point-in-time conclusion

For complete, correctly dated factors and a verified provider convention, the transformation is
algebraically sound. Writing provider price as `P_provider(t, h) = P_nominal(t) / F(t, h)` gives
`P_provider(t, h) * F(t, h) = P_nominal(t)` regardless of later splits. Reading future split events
to reverse that encoding is not, by itself, evidence that a future fact has entered the nominal
trading value.

That conclusion is conditional. A missing factor, incorrect volume/dividend convention, shifted
event date, or quantization can leave a dependence on the response horizon. In particular, passing
through a split-adjusted dividend retains a future-split dependence; dividing already-nominal volume
introduces one. FR-006 covers only its verified interval. The claim at `spec.md:83-84` that it
catches an incorrect split table is too broad beyond that interval. Response provenance may change
with the download and must not be compared as if it were a historical trading input. Perturb future
prices/volumes as well as future split encodings and verify the reconstructed prefix is unaffected
under the expressly supported convention.

## M1-M6: paper traces, not executed kills

All numeric examples in this section are **EXAMPLE — NOT A RESULT**. Use flat provider prices around
split boundaries to isolate the intended defect from overnight market moves and the unchanged 25%
oracle tolerance.

| Mutant | Clean control and defect trace | Would the named oracle go red? |
|---|---|---|
| M1: include the split date | One 2:1 split; provider prices 50 before/on the split. Correct F gives 100 then 50, ratio 2. Mutant gives 100 then 100, ratio 1; relative error is 0.5. | Yes, the real oracle raises `nominal price discontinuity does not match the 2:1 action`. Put the split after the first row. A small ratio such as 1.25 produces only 20% error and can pass the existing tolerance; pin a discriminating ratio. See R7 for helper exception handling. |
| M2: ignore splits after requested end | Fixed requested end precedes a later 2:1 split. Response A supplies earlier price 100 with no later event; B supplies 50 and that event. Correct output is 100 in both; mutant output is 100 versus 50. | Yes with the fixed-window, adapter-level setup in R5. Not guaranteed by the current text: extending the request end along with the response can make this mutant pass. |
| M3: multiply volume | Under the adjusted-volume decision, provider Close=50, Volume=200, F=2. Correct output 100 and 100 preserves dollar volume 10000; mutant volume=400 gives 40000. | Yes if F differs from 1 and volume is positive. If P-1 decides pass-through or remains inconclusive, the stated divide-to-multiply mutant is not the selected implementation; assert unchanged volume and mutate that treatment instead. |
| M4: opposite dividend treatment | With a pre-split dividend, F=2. Adjusted case: provider dividend 0.5 must become 1; pass-through gives 0.5. Nominal case: provider dividend 1 must remain 1; multiplication gives 2. | Yes only with a positive dividend strictly before a later split. A dividend on the last split date has F=1, so both treatments agree. Existing 041 dividends are on/after its only split and cannot kill M4 (`tests/test_041_pay_date_bound.py:158-159`). |
| M5: omit a reference split | Reference table contains a dated 2:1 event; provider table does not. Put it after the requested end but within reference coverage to ensure no in-window discontinuity catches it first. | FR-006 should refuse, naming ticker and ex-date, before any cache write. That is a valid negative-input test. A code kill still needs the explicit mutation/control design in R7; bypassing comparison must make the refusal assertion fail. |
| M6: nearest split only | Two later splits, 2:1 then 4:1; provider price is 20 on each relevant row. Correct nominal prices before/at first/at second are 160,80,20. Nearest-only gives 40,80,20. First observed ratio becomes 0.5 rather than 2, relative error 0.75. | Yes, at the first split, provided it has a preceding session in the bundle. The second split still reconciles. Pin the two ratios; a second ratio sufficiently close to 1 can leave the first error inside tolerance. |

The cross-check must have a matching synthetic reference table in every positive control. A refusal
from the wrong gate, an absent mutation fragment, or an unrelated exception is not proof that the
named mutant was killed.

## Required edge cases and expected behavior

| Case | Expected behavior and review result |
|---|---|
| Dividend on split ex-date | Exclude that day's ratio; include every strictly later ratio. Existing execution contract uses dividends per post-split share (`scripts/data.py:481`). A synthetic assertion pins implementation but cannot establish the provider's same-day share convention; unresolved empirical coverage stays explicit (R11). Preserve both action rows: uniqueness is per Date/Ticker/Action_Type (`data.py:693-694`). |
| Window starts on split date | Continue to raise `no preceding price session` (`data.py:745-747`), even if the extended source has other rows. Do not validate a larger frame and then omit validation of the sliced bundle. |
| Window ends on split date | Earlier rows include that ratio; the last row excludes it. If still later splits exist in the response, both sides retain those additional factors. Preserve the end-day action and inclusive requested end. |
| Consecutive split sessions | Before both: F=r1*r2; on first: F=r2; on second: F=1, before accounting for any still later splits. Both discontinuities have a predecessor if the first split is not the first window row. Add this explicitly; "two splits" alone does not require adjacency. |
| First/last row without a split | First row still includes all later factors. Last bundle row need not have F=1 if the response has a later split. A first/last-row dividend follows its own row factor. Empty sliced windows must refuse rather than index missing endpoints. |
| Timezone/DST | Preserve the provider's daily label date, remove its zone without converting the date, normalize before factor lookup and slicing, and emit naive midnight labels. Existing action rejection tests do not cover adapter search alignment (R9). |
| Response ends before download date | Weekend/holiday lag can be normal; missing completed sessions cannot be assumed normal. Explicit horizon/as-of rules and endpoint tests are absent (R3). |
| Missing/invalid post-window event | An omitted verified event must trigger FR-006; malformed events must be rejected before factor computation even outside reference coverage (R4). Unverified absence is not repaired by disclosure. |

## T010 / FR-009: does changing the fixture relax a check?

**No, if it changes only the provider representation and preserves the original nominal expectations
and rejection assertions.** For the split-bearing 020 fake, divide all four pre-split OHLC fields by
4; for 041 divide them by 2. If P-1 establishes adjusted volume, multiply the fake's pre-split
provider volume by the corresponding factor so reconstruction returns the original nominal volume.
Keep the nominal `split_prices()`/`SyntheticSource` and shared `session_prices()` helpers unchanged;
transform only copies used as yfinance responses. Current dividends occur on/after the split, so
their F is 1 and leaving those values unchanged is consistent with either proposed treatment.

The second 020 history has a nominal-looking price step but **no split event**
(`tests/test_020_unadjusted_price_data.py:265-267`). Its test purpose is missing payment-date
refusal, not split reconstruction. There is no declared factor with which to derive its new shape.
Treat any flattening as an explicit synthetic control cleanup; do not invent a split merely to
justify it.

Keep 041's Receivable=1.5, zero Cash/Buying_Power, quantity-adjusted Equity, basis, and no-payment
assertions (`tests/test_041_pay_date_bound.py:194-222`). Update the history-call assertion
specifically to require open end and inject matching synthetic references. Do not weaken the
unchanged oracle or replace the yfinance path with a nominal source. T010 as written is incomplete,
rather than evidence that any validation check has already been relaxed.

## Unit budget assessment

| Unit | Draft estimate | At most 300 lines established? |
|---|---:|---|
| 0 | ~150 | No. Probe plus current cross-check already total 240 physical lines; required remaining evidence/inputs are uncounted. |
| 1 | ~300 | No. Estimate reaches the cap before all migration, mutation, reporting, and task-status work is accounted for. |
| 2 | ~120 | No measured diff. Snapshot/manifest fields and deferred mutation wiring must be included, not just the pure function. |
| 3 | ~200 | No measured diff. Count cited table rows, guard, constructor seam, all tests/controls, migrated fixture injection, and evidence. |
| 4 | ~40 | No measured diff. Raw acceptance output, manifest JSON, and full-suite evidence may exceed that estimate; count the actual artifact edits. |

These are planning estimates, not completed-unit sizes. The explicit 400-line standing rule must be
corrected before any unit is represented as meeting the requested 300-line limit.
