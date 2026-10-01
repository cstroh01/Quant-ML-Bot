# Tasks: Nominal price reconstruction

**Input**: [spec.md](spec.md), [plan.md](plan.md), [artifacts/review-codex.md](artifacts/review-codex.md)
**Organization**: single-threaded, in unit order. Stop and report after each unit. Nothing here
authorizes Git, parallel agents, or network use in tests.

**Standing rules**
- Do not edit `_validate_split_discontinuities` or `SPLIT_RATIO_RELATIVE_TOLERANCE`. Do not touch
  `docs/trials/**`.
- No research or backtest code runs outside pytest, because ad-hoc runs write the production ledger.
- Every network step is Camden's, run once, with the ledger hashes recorded before and after.
- **Unit cap: 300 lines, added plus removed, including evidence and task-status edits (SC-007).**
  1. Before a unit, copy every file it will touch to `<scratchpad>/pre-unit-N/`.
  2. After it, measure each file with
     `python -c "import difflib,sys; a,b=(open(p,encoding='utf-8').read().splitlines() for p in sys.argv[1:]); print(sum(1 for l in difflib.unified_diff(a,b,lineterm='',n=0) if l[:1] in '+-' and l[:3] not in ('+++','---')))" <pre> <post>`.
     A new file is measured against an empty file.
  3. Record the totals in the unit report. If a unit exceeds 300, split it before review. The cap
     is never waived.

---

## Unit 0: Probe, inputs and determination

- [x] T001 Camden decided D-1 to D-5 and R1–R11 on 2026-09-30 (spec §7).
- [x] T002 Wrote `artifacts/p1_probe.py`, the header-only input stubs, and `artifacts/.gitignore`
  (2026-09-30, not run). **Size note:** the probe is 382 lines, written in one pass before the
  R10 cap existed. Camden reviews it in two parts, T003 and T004. If Camden wants a physical
  split, it happens there.
- [ ] T003 **Review part A (Camden):** everything from the top of the file through `q_p1`, plus
  `run` and `QUESTIONS`. Covers session labels, factor validation, horizon, input schemas, Q-P1,
  raw rows and hashes.
- [ ] T004 **Review part B (Camden):** `q_p2` through `d3_googl`, plus `self_check` and `main`.
- [ ] T005 Baseline: run `python -m pytest tests`. Record the exit code and the counts in
  `artifacts/baseline.txt`. It must show 0 failed and 0 errors.
- [ ] T006 **Fill the inputs** with primary citations on every row, per spec §5's schemas:
  - `p1-filed-ranges.csv`: only filings made before the first split after each quarter, with at
    least one quarter preceding two splits.
  - `p1-declared-dividends.csv`: every Q-P3 required case. The probe lists any missing ones by name.
- [ ] T007 **Camden runs** `python artifacts/p1_probe.py --self-check`. Every line must read `ok`;
  a `FAIL` stops the unit. Then Camden runs `python artifacts/p1_probe.py --revision <full sha>`
  once. Commit `artifacts/p1-determination.txt` only; the raw rows stay under `data/cache/`.
  - A STOP on Horizon, Q-P1, Q-P2 or Q-P3 stops the spec for an open amendment.
  - A STOP on Q-P4 selects FR-005's `provider_unverified` branch.
  - A STOP caused by a registered tolerance is recorded, and any change is made by a dated
    amendment to §5.
- [ ] T008 Record P-1's selections in spec §4: the FR-004 branch, the FR-005 branch, the FR-012
  state, and D-3.
- [ ] T009 **Cross-check (SC-004, D-5), by a lane other than the drafting lane.**
  - Verify each row of `split-table-crosscheck.md` and fill its provider column from P-1.
  - Close the 2026 primary-8-K check through the download date.
  - Close the MSFT "no split" primary source.
  - Set `verified_through`.
  - Camden spot-checks at least one citation per ticker.

## Unit 1: Fixture migration and seams (tests only; red contracts)

- [ ] T010 FR-009, in `tests/test_020_unadjusted_price_data.py` and `tests/test_041_pay_date_bound.py`:
  - Divide the pre-split OHLC of the yfinance-response copies: by 4 in the 020 split history, by
    2 in 041 `synthetic_history`. Apply the volume change only if T008 selected ÷F.
  - Leave the second 020 history, `split_prices()`, `SyntheticSource` and `session_prices()`
    unchanged.
  - Change 041's call assertion to require one call with `end` open.
  - Inject a matching reference table and a clock into each fake.
  - Keep 041's Receivable 1.5, zero Cash and Buying_Power, Equity, basis and no-payment
    assertions, and 020's null-date refusal and no-write checks.
- [ ] T011 Run the migrated modules. Record each test's actual state:
  - the 041 flow test is red at the oracle, for a 2:1 split;
  - the 020 fetch test is red only on the one-call, open-end assertion;
  - the 020 null-date test is green.

  Any other outcome is reported, not normalized.

## Unit 2: Contracts A, red (`tests/test_044_nominal_reconstruction.py`, part 1)

Every fixture is labelled `EXAMPLE — NOT A RESULT`, and every expected factor is a hand-written literal.

- [ ] T020 Exact reconstruction on exactly representable fixtures (ratios 2 and 4, dyadic prices),
  passing the real, unchanged oracle.
- [ ] T021 Rule 5 edges from the spec §3 table: start on a split, end on a split, consecutive
  splits, first or last row, empty window, a split after `end` only.
- [ ] T022 FR-011: a malformed post-window event (NaN, negative, infinite, a duplicate label, or two
  negative ratios whose product is positive) is refused, and no file is written. Include a valid control.
- [ ] T023 FR-002: a stale response is refused; ordinary weekend and holiday lag passes; a missing
  first or last window session is refused; a response missing a known post-window split is refused
  by the horizon check.
- [ ] T024 FR-014: naive and `America/New_York`-labelled histories across the 2024-03-10 DST change,
  with a split on a slice boundary, give the same dates, naive midnight `datetime64[ns]`, the same
  factors, and the same `split_factor_basis_through`.
- [ ] T025 Run the module and record red for the named reason on each test.

## Unit 3: Contracts B, red (part 2)

- [ ] T030 T-PIT (spec §2, SC-003 M2): the same requested window, a 2:1 event strictly after `end`
  in response B only, B's prefix re-adjusted and its future prices and volumes perturbed; the
  explicit loaded market fields are compared; the fake asserts one open-end call.
- [ ] T031 Quantized case: 3:1 with a 6-decimal provider value, and the residual asserted within
  `F × q / 2`. It is documented as a bound, not an identity.
- [ ] T032 FR-004 dividend (a dividend strictly before a later split), and FR-005 volume in the branch
  T008 selected, including the `volume_basis` attr. FR-012 same-day, per T008.
- [ ] T033 FR-007 labels, the manifest fields `split_horizon_as_of_utc` and
  `split_factor_basis_through`, and the SC-002 twin through `run_backtest`.
- [ ] T034 Run the module and record red for the named reason on each test.

## Unit 4: Reconstruction core (`scripts/data.py`)

- [ ] T040 FR-001, FR-011, FR-013 and FR-014: the pure function and full factor-event validation.
- [ ] T041 FR-002: the clock seam, one open-end call, the horizon via `trading_days`, the requested
  coverage check, slicing after reconstruction, and the two new manifest fields.
- [ ] T042 Run `python -m pytest tests`. Units 1 and 2 are green, along with Unit 3's price-only tests.

## Unit 5: Conventions and labels

- [ ] T050 FR-004, FR-005 and FR-012, exactly as T008 recorded.
- [ ] T051 FR-007 labels and docstring. FR-010: the single loader attrs line for `volume_basis`.
- [ ] T052 SC-005: confirm zero diff lines in the oracle, by reading the files. Run the full suite,
  which must be green.

## Unit 6: Mutation evidence (after implementation, R7)

- [ ] T060 Wire M1, M2, M3 (in the branch T008 selected), M4 and M6 through `killed()`, using oracles
  that translate only their expected, message-matched `ValueError`.
- [ ] T061 Record, per mutant, the green control and the kill as separate statuses.

## Unit 7: Independent split table (FR-006)

- [ ] T070 Tests first, recorded red:
  - the provider omits a reference event dated after `end` but inside coverage;
  - a ratio mismatch;
  - an unknown ticker (D-2);
  - a provider event after `verified_through` is disclosed;
  - a reference event after the response's last session is not compared;
  - a valid-table control;
  - the constant equals the crosscheck file.
- [ ] T071 Add the constant from the verified crosscheck, the comparison over the common coverage
  interval with D-4's tolerance, and the constructor seam. Wire M5 as a comparison-bypass mutant.
  Run the full suite. If T070 and T071 together exceed 300 lines, they are separate units.

## Unit 8: Acceptance (Camden)

- [ ] T080 SC-001 re-run. Save the output, the manifest JSON and the ledger hashes to
  `artifacts/sc-001-rerun.txt`. A failure is a finding, and no check is relaxed.
- [ ] T081 SC-006 suite count, and the SC-007 table of measured unit sizes.
