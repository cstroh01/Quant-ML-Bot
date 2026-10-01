# Spec 041 handoff

Date: 2026-09-30. T019 only; documentation closeout.
Sources: [tasks.md](../tasks.md), [spec.md](../spec.md),
[unit-5a.md](unit-5a.md), [unit-5b.md](unit-5b.md), and
[aapl-bundle.txt](aapl-bundle.txt). Status below records their evidence;
no tests or download were rerun for this handoff.

## Final task status

| Task | Status | Delivered or remaining |
|---|---|---|
| T000 | Complete | Sequencing cleared by Camden; merge state not queried. |
| T001 | Complete | Recorded baseline: 903 passed. |
| T002 | Complete | FR-004 rule-table contracts. |
| T003 | Complete | Synthetic offline bundle flow. |
| T004 | Complete | Fail-closed scenarios. |
| T005 | Complete | M1-M3 oracles; final mutation wiring recorded under T015. |
| T006 | Complete | Bound direction and configuration checks. |
| T007 | Complete | Policy constants, derivation, and sentinel. |
| T008 | Complete | Invalid finite-lag refusal. |
| T009 | Complete | Snapshot policy and per-dividend basis. |
| T010 | Complete | Policy-aware corporate-action validation. |
| T011 | Complete | Manifest v2 and strict v1 compatibility. |
| T012 | Complete | Loader resolution and provenance attributes. |
| T013 | Complete | Dividend event basis recording. |
| T014 | Complete | CLI/API disclosure and synthetic checks. |
| T015 | Complete | M1-M3 killed with green controls; all five M4 cases raise. |
| T016 | Complete | Pinned 019 files recorded byte-identical and green. |
| T017 | Complete | Full suite recorded green: 1003 passed. |
| T018 | Open, unticked | run; FAILED; finding recorded. |
| T019 | Complete | This handoff. |

T000-T017 retain their existing checked status. Completing T019 does not
complete SC-001 or establish that Spec 041 has merged.

## Suite evidence

- **1003 passed on Camden's venv (Python 3.13.14)**, as reported by Camden in
  the T019 instruction on 2026-09-30. The supplied artifacts do not contain
  that venv run's log; it was not independently verified in this handoff.
- Separately, Unit 5b records `python -m pytest tests`: **1003 passed,
  0 failed, 0 errors; 1 warning; exit 0**, on Windows with Anaconda
  **Python 3.14.6**, pytest 9.1.1, dated 2026-09-29. Its count is Unit 5a's
  1000 plus three M1-M3 mutation cases. These are synthetic test results.
- Unit 5a records the pinned 019 file hashes; Unit 5b records unchanged
  trial-ledger/head hashes, 174 lines/records, and absent returns before and
  after its runs. These are historical artifact checks, not new measurements.

## SC-001: FAILED

Camden's recorded AAPL run used 2016-01-04 through 2025-12-31 on
2026-09-30, revision `bb16148d075aace16d52615a4397cc3a7b3b1965`.
The artifact states:

> SC-001 RESULT: FAILED on a non-pay-date check (data finding; no check relaxed)

The exact failure is:

> ValueError: split reconciliation check failed: nominal price discontinuity does not match the 4:1 action

The diagnostic records prior Close / split-day Open as
`124.807503 / 127.580002 = 0.978`, versus the declared `4.0` split.
It establishes that the observed pre-split Open/Close were already
split-adjusted despite `auto_adjust=False`; the nominal-price check refused.
It does not establish dividend/volume adjustment behavior or split-table
completeness for other tickers or dates.

**SC-001 is unmet, so no real-data bundle exists from this run.** The artifact
records `data/cache/unadjusted/` absent and nothing written. It records unchanged
trial hashes and absent returns. No successful manifest or strategy result is
available. The failure is a data finding on a separate check, not evidence of
a pay-date failure; no check was relaxed.

## Decisions and downstream assumptions

Rule 14 is still owed.

Q-1 is confirmed: `unbounded`.

- **Spec 043:** may use the recorded completed pay-date implementation and
  synthetic verification as its starting evidence. Preserve manifest policy,
  dividend basis, sentinel refusal, and disclosure. It cannot assume a real
  AAPL bundle or SC-001 success. Its own preconditions still apply: 041 must
  land first; remeasure the production ledger at T002 and the suite baseline
  at T003. The historical 1003 count is not a substitute for those measurements.
- **Spec 040:** may expect the 041 contracts to survive packaging, including
  v2 policy/basis and strict v1 behavior. Per its hard preconditions, specs
  036, 041, and 043 must have merged, the lane must be single-threaded, and
  the suite must be measured green at PRE. This handoff establishes no merge
  state and supplies no real-data bundle. Packaging cannot close SC-001.
- Rule 14 reconciliation remains separate from pay-date handling. Per
  FR-008, yfinance remains `capital_gate_eligible=False`; existing source
  limitations remain in force.

## Open items for Camden

1. Take the recorded nominal-price finding into a tests-first reconstruction
   spec. Preserve the split check and rerun SC-001 as that spec's acceptance
   test, as directed by the AAPL artifact; retain dated revision-stamped
   evidence. Keep T018 open until the acceptance criterion is met.
2. Complete Rule 14's independent corporate-action cross-check and disclose
   unreconciled coverage. The artifact's dividend/volume observations from
   memory remain unverified.
3. Retain the Python 3.13.14 venv run log with date and revision so its reported
   1003-pass result has artifact provenance distinct from Unit 5b.
4. Review and handle version control and downstream sequencing. No merge or
   permission to start 043/040 is established by this documentation closeout.

Only this handoff and the T018 note/T019 checkbox in tasks.md were edited.
No Git, pytest, network, or writes to scripts/**, tests/**, or docs/trials/**
were used for this task.
