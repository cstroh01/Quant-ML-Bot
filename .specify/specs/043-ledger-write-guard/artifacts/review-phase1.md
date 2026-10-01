# Spec 044 re-review and Spec 043 Phase 1 review

Date: 2026-09-30. **Verdict: request changes before Phase 2 or Spec 044 P-1.**

Review-only. I ran no Git command, pytest, probe, production script, or network call. I edited only
this review file. The Phase 1 runtime conclusions below are a static cross-check of the committed
test code against the saved `phase1-full*`, `entry-red*`, `incident-red*`, `enabled-red*`, and
`root-red*` evidence; they are not a new execution claim.

**Current actionable count: 5 P1, 5 P2.** The two unresolved historical 044 findings are included
in those counts. Historical 044 disposition: **9 fixed, 2 not fixed**.

## Ranked findings

### F1 — P1 — 044 R2 is not fixed: Q-P4 still cannot establish the volume basis

**Location:** `044-nominal-price-reconstruction/spec.md:147-161,260-271`;
`044-nominal-price-reconstruction/artifacts/p1_probe.py:238-270`.

The revision makes the bands disjoint and requires five agreeing 4:1-or-larger events, but it still
compares median volume on different sessions. Real trading activity remains an uncontrolled cause
of `post/pre`; five agreeing observations reduce sampling noise but do not identify whether one
historical observation is on a pre- or post-split share basis. The probe can therefore return PASS
and label Volume `provider_nominal` or `nominal_reconstructed` from evidence the spec itself calls
“internal consistency only.” That certification unlocks a future cost-model consumer even though
the causal basis was never established.

Keep the result `provider_unverified` unless a same-observation or primary-source contract actually
identifies the provider convention. The median heuristic may be recorded as diagnostic evidence,
but it cannot select either verified branch.

### F2 — P1 — A future-dated response passes both 044 horizon rules

**Location:** `044-nominal-price-reconstruction/spec.md:128-138`;
`044-nominal-price-reconstruction/artifacts/p1_probe.py:99-111`;
`tests/test_data.py:222`.

Both rules count sessions strictly after `last_response_session` through `last_completed_session`
and accept a count of at most one. If the response ends after the as-of session, the interval is
reversed and therefore empty; the existing `trading_days` contract explicitly returns `[]` for a
reversed range. The probe has the analogous `pd.bdate_range(last + 1 day, completed)` construction.
Thus a provider row, split, or revision from the future can establish the factor horizon and enter
`F(t)`.

Require `last_response_session <= last_completed_session` before measuring lag, in both the spec
contract and probe, and add a future-session planted defect plus a current-session control.

### F3 — P1 — The 044 self-check is not a Rule 12 proof of the decision probe

**Location:** `044-nominal-price-reconstruction/spec.md:226-229`;
`044-nominal-price-reconstruction/artifacts/p1_probe.py:331-367`.

`--self-check` directly exercises Q-P2, split-value validation, timezone handling, literal factor
math, the volume classifier, and horizon lag. It never calls Q-P1, Q-P3, D-3, `read_inputs`, or the
end-to-end aggregation/writing path. A broken filed-range check, missing required-dividend check,
same-day convention check, input-schema gate, or citation gate can therefore coexist with an all-`ok`
self-check. Q-P3 selects price reconstruction behavior; this is not a cosmetic coverage gap.

Add offline fixtures that make every decision gate fail for its named defect and pass a valid
control. The self-check should also prove duplicate/citation rejection and the future-session case
from F2.

### F4 — P1 — None of the 14 expected Phase 1 failures is `xfail(strict=True)`

**Location:** `tests/test_043_enabled_control.py:5`;
`tests/test_043_entry_points.py:11-12`; `tests/test_043_incident.py:5`;
`tests/test_043_project_root.py:22-24,86-87`.

There is no `xfail` marker in any `test_043_*.py` file. The saved full suite consequently exits 1
with 14 ordinary failures. More importantly, a contract that starts passing during implementation
does not become a strict XPASS and force removal/review of its expected-red state.

The exact 14 are: enabled control (1), E1-E5 (5), incident (1), six root-contract parameters (6),
and relocated registry (1). Mark them individually or by parameter with `xfail(strict=True)` and a
task-specific reason. E1-E4, E5, and the root/registry cases need separate parameter marks because
they turn green in different review units. Remove each mark in the unit that makes that contract
pass. The nine existing passing controls remain unmarked.

### F5 — P1 — The E5 test can pass with a permanently closed route

**Location:** `tests/test_043_entry_points.py:16-26`;
`tests/ledger_guard_child.py:107-121`; Spec 043 AC-10 at `spec.md:432-436`.

The test covers only an unrecorded configuration and accepts two 409 responses containing
`--record-trial`. An implementation that returns that 409 unconditionally, without looking up
`config_hash` or serving a recorded sidecar, passes every E5 assertion. It does not test AC-10's
required green branch: after deliberate recording, GET returns 200 from the recorded trial, and two
identical GETs leave both ledger bytes and N unchanged.

Add the recorded-configuration control now as a red contract. Assert the response comes from the
expected sidecar/configuration, not merely that the status is 200.

### F6 — P2 — 044 R10 is not fixed: Unit 0 already exceeds the hard cap

**Location:** `044-nominal-price-reconstruction/tasks.md:22-32`;
`044-nominal-price-reconstruction/spec.md:313-314`; `plan.md:25-27`.

The documents now state a hard 300-line added-plus-removed cap, but T002 records a 382-line probe
written as one unit and treats two later reading passes as the remedy. Dividing review attention does
not divide the changed-line unit. SC-007 cannot truthfully report that every unit is at most 300.

Physically split/re-stage Unit 0 against saved pre-unit copies, or amend SC-007 transparently. The
current text is still a waiver of the rule it calls hard.

### F7 — P2 — The 044 input/provenance schema is declared but not enforced

**Location:** `044-nominal-price-reconstruction/artifacts/p1_probe.py:84-96,195-210,287-290,370-378`.

`read_inputs` validates existence, exact headers, non-emptiness, and date parsing, but it never
requires nonblank `accession` or `source_url`. Q-P3 also does not validate `form`. Its dictionary
comprehension silently overwrites duplicate `(ticker, ex_date)` rows, so conflicting declarations
can disappear. Finally, `--revision` accepts any string while the output labels it as the revision.

Reject blank citation fields, invalid forms, duplicate keys, tickers outside the basket, and a
revision that is not the required full hexadecimal identifier. Plant each rejection in F3's
self-check.

### F8 — P2 — Missing dividend cells can disappear before the 044 finite-value gate

**Location:** `044-nominal-price-reconstruction/artifacts/p1_probe.py:62-76,149-169,182-192`;
FR-013 at `spec.md:212-214`.

`sessions` validates only `Stock Splits`. Q-P2 and `required_dividend_cases` discover dividends with
`history["Dividends"] > 0`; a NaN or negative action value is false in that filter and is never sent
to `positive()`. The probe can therefore PASS while a missing dividend observation was silently
discarded, contrary to FR-013's “missing observation is never a pass.”

Validate the complete action column before event selection, with an explicit zero-means-no-dividend
contract, and add NaN/negative planted cases.

### F9 — P2 — Six root tests are red at one prerequisite, not at their case contracts

**Location:** `tests/test_043_project_root.py:22-55`; saved `root-red.txt`.

All six `test_project_root_contract` parameters stop at line 26 because `_project.py` is absent.
That matches the Phase 1 summary's stated immediate reason, but it does not yet demonstrate the
override, invalid-override, marker walk, missing-marker, wrong-nearer, or foreign-cwd assertions.
The cases are well formed statically; the limitation is the evidence claim.

Describe these six as one missing-resolver red plus six pending semantic contracts. Once T021 adds
the module, preserve per-parameter strict-xfail behavior so each case independently XPASSes or stays
red for its own assertion.

### F10 — P2 — `run_child` mutates the checkout on ordinary test runs

**Location:** `tests/ledger_copy_support.py:97-103`.

Every `run_child` call appends to
`.specify/specs/043-ledger-write-guard/artifacts/phase1-events.jsonl` under `REPO`. The saved Phase 1
suite ran from an outer disposable copy, so its source checkout was protected, but a normal
`python -m pytest tests` from the repository appends to the live working tree. Repeated or concurrent
runs accumulate nondeterministic paths and hashes.

Keep tests side-effect-free: return evidence to the caller or write only below a pytest temporary
directory. A separate, explicit evidence-harvesting command may copy a completed record into the
spec artifacts.

## Spec 044 R1-R11 disposition

| Finding | Status | Re-review basis |
|---|---|---|
| R1, Q-P2 can certify NaN adjustment data | **Fixed** | `positive()` and Q-P2 now require finite positive Close, Adj Close, observed, and expected values; the exact NaN Adj Close case is in self-check. F8 is a different pre-selection hole. |
| R2, volume decision does not identify convention | **Not fixed** | Disjoint bands and five cases do not remove the different-session activity confound (F1). |
| R3, open request end does not establish horizon | **Fixed** | The spec adds an injected as-of clock, completed-session lag, requested-window coverage, and common reference coverage. F2 is a new reversed-interval boundary defect. |
| R4, post-window events bypass validation | **Fixed** | FR-011 and `sessions()` validate the full response's labels, split values, and cumulative factors before use. |
| R5, T-PIT may not kill M2 | **Fixed** | The requested window is fixed, the added split is strictly after `end`, only the response grows, future fields are perturbed, and the fake asserts an open-end call. |
| R6, fixture migration incomplete | **Fixed** | FR-009/T010 preserve nominal expectations and rejection checks, inject reference/clock seams, change the open-end assertion, and state each migrated test's intended red/green result. |
| R7, premature mutant wiring | **Fixed** | Red contracts and post-implementation wiring are separated; message-matched exception translation, M3 branches, and the M5 comparison-bypass mutant are specified. |
| R8, exact invariance conflicts with quantization | **Fixed** | Exactness is limited to exactly representable fixtures and a separate quantized case asserts the registered residual bound. |
| R9, no timezone regression contract | **Fixed** | FR-014 and T024 pin wall-date-preserving zone removal, naive midnight labels, DST, slicing, factors, and provenance. |
| R10, unit plan does not enforce 300 lines | **Not fixed** | The stated rule is corrected, but the already completed 382-line Unit 0 is exempted in practice (F6). |
| R11, no raw rows/dividend coverage | **Fixed** | The probe records selected provider rows plus hash/count and Q-P3 derives/enforces the required cases, including same-day cases. The rows remain local/gitignored as required for market data. |

## Spec 043 expected-red audit

Saved evidence establishes the immediate failures below. “Right reason” means the observed failure
matches the Phase 1 artifact's stated pre-implementation reason, not that every final acceptance
branch is already proven.

| Expected-red group | Saved observation | Right reason? | Vacuity assessment |
|---|---|---|---|
| Enabled E1 control (1) | Exit 2: argparse rejects unimplemented `--record-trial`; 0 records/sidecars | **Yes**, exactly the stated T025-red reason | In isolation, accepting the flag as a no-op would make it pass on today's unsafe default. Paired E1-default prevents a green suite, and strict xfail would expose the premature XPASS. |
| E1 default | Main completed; 44 records, 22 sidecars; manifest changed | **Yes** | Non-vacuous write reachability. Future refusal also requires the named error, runner, copy ledger path, action, nonzero exit, empty stdout, and zero changed bytes. |
| E2 default | Main completed; 46 records, 22 sidecars; manifest changed | **Yes** | Same non-vacuity protections as E1. |
| E3 default | Main completed; 230 records, 110 sidecars; output-row assertion completed | **Yes** | Same protections, plus an explicit pipeline-completion assertion. |
| E4 default | Main completed with two workers; 16 records, 0 sidecars; ledger files changed | **Yes** | Non-vacuous for “can reach a write.” It does not claim every trial completes with a sidecar. |
| E5 default | Two status-200 GETs; each wrote 44 records/22 sidecars; N rose 87 to 89 | **Yes** | **Future pass is vacuous for AC-10** because unconditional 409 satisfies the present oracle (F5). |
| Incident call | Direct `_baseline_rows`; 6 records, 3 sidecars; child completed and verified | **Yes** | Non-vacuous write-layer reachability; `assert_refused` pins the named library refusal. |
| Root contract parameters (6) | Each stops at `_project.py` missing | **Yes for the summary's stated prerequisite; no for the six individual semantics** | Assertions are non-vacuous once the resolver exists, but current red evidence is shared (F9). |
| Relocated registry (1) | Resolves to `marked/extra`, not `marked` | **Yes** | Non-vacuous exact-path comparison. |

The eight copy-support tests and the planted depth test are legitimate passing controls. They are not
part of the 14 expected-red nodes and should not be marked xfail.

## Required disposition before continuing

1. Add parameter-specific `xfail(strict=True)` markers for exactly the 14 expected-red nodes.
2. Close F5 before representing AC-10 as covered; retain the saved pre-043 88-record red proof.
3. Correct the 044 volume decision, future-horizon boundary, and probe self-check before P-1 runs.
4. Resolve or openly amend the 044 Unit 0 cap before SC-007 is used as an acceptance claim.

