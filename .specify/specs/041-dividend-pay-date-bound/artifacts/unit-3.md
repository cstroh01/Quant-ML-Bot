# Spec 041 Unit 3 evidence (T007-T012, production)

Date: 2026-09-28 (Claude Code, local Windows session). No Git command was run.
Nothing here is a strategy result. Every test value is `EXAMPLE — NOT A RESULT`.
Environment: Windows 11, repository venv, `python -m pytest`, from `C:\GitHub\Quant-ML-Bot`.

## Files changed

| File | Change (CR-stripped unified diff) |
|---|---|
| `scripts/data.py` | +185 / -13 (Checkpoint A: +114 / -8; Checkpoint B: +71 / -5) |
| `tests/test_020_unadjusted_price_data.py` | +7 / -1 (the one authorized assertion change, see below) |
| `.specify/specs/041-dividend-pay-date-bound/tasks.md` | T007-T012 checked; Unit 3 evidence section |
| this file | new |

`tests/test_041_pay_date_bound.py` is unchanged (SHA-256 `9909c17d2f9c6183b1af681fe7d0bd0055738682fc649e8d2281788ac086821c`).
`scripts/backtest_harness.py` was not opened for writing.

Post-edit SHA-256: `scripts/data.py` `2c0d1ccf003f13125ff8a1f21cccd0347604f35f2f3e0fc799d704274202e4b8`,
`tests/test_020_unadjusted_price_data.py` `867bedfa09286bad7e303c20a662e76e345910f5bd2ba7a8ed3913a3f697b303`.

**Line endings.** `scripts/data.py` has mixed endings: original lines 1-34, 43-55
and 106-479 are CRLF, the rest LF. The editor normalized the file to LF. Every
unchanged line was restored to its original ending, and each new line takes the
ending of the line before it. The raw diff and the CR-stripped diff are both 198
changed lines, so no whole-file ending churn reaches Camden's diff.

## What was implemented

- **T007 (FR-001).** `DIVIDEND_PAY_DATE_DECLARED_LAG_SESSIONS: int | None = None`,
  `DIVIDEND_PAY_DATE_BOUND_SOURCE: str | None = None`, with the spec's comment
  block verbatim. `declared_dividend_pay_date_policy()` is the one derivation
  function; it returns `"unbounded"` or `"bound_sessions:N"`. `UNBOUNDED_PAY_DATE`
  is `pd.Timestamp.max.normalize()` (2262-04-11, naive midnight). No lag literal
  appears at any call site.
- **T008 (FR-002).** The derivation raises `ValueError` for a zero, negative,
  boolean or non-integer lag (`... must be a positive number of sessions`) and for
  a finite lag whose source is `None`, empty or blank (`... requires a cited
  upper-bound source`). The yfinance adapter calls it first in `fetch`, before any
  download, so nothing is written.
- **T009 (FR-003).** `Dividend_Pay_Date_Basis` added to `CORPORATE_ACTION_COLUMNS`
  and to the empty-actions frame. `UnadjustedSourceSnapshot` gains
  `dividend_pay_date_policy = "sourced"` and `dividend_pay_date_bound_source = None`.
  The adapter writes basis `bound` on every dividend, empty on splits, and still
  writes no date; its "Never substitute" comment stays true.
- **T010 (FR-004).** `_validate_corporate_actions(..., *, pay_date_policy="sourced",
  manifest_version=UNADJUSTED_MANIFEST_VERSION)`. Every existing message is
  unchanged. The null-date check is relaxed only for `bound & policy != "sourced"`.
  New messages: `dividend pay-date basis missing or invalid`, `split must not
  have a pay-date basis`, `bound dividend must not have a payment date`. The
  schema message for a missing basis column comes from the existing check.
  Version 1 uses the five original columns and is exactly as strict as before.
- **T011 (FR-003).** `UNADJUSTED_MANIFEST_VERSION = 2`. Versions 1 and 2 load.
  Version 2 requires the policy (`manifest dividend_pay_date_policy check failed`)
  and, for `bound_sessions:N`, a non-blank source
  (`manifest dividend_pay_date_bound_source check failed`). Version 1 ignores any
  stray policy field. The writer records both fields from the snapshot.
- **T012 (FR-005).** `_merge_actions_for_execution(..., *, pay_date_policy)` takes
  the manifest's policy. `bound` under `unbounded` resolves to `UNBOUNDED_PAY_DATE`;
  under `bound_sessions:N` it resolves to the N-th NYSE session after the ex-date
  from `trading_days`, not the bundle rows. `sourced` rows keep the vendor date.
  The frame carries `Dividend_Pay_Date_Basis` right after `Dividend_Pay_Date`.
  `attrs` gains `dividend_pay_date_policy`, `dividend_pay_date_bound_source`,
  `dividends_sourced` and `dividends_bound`.
- FR-008: `capital_gate_eligible` and `source_limitations` are untouched.

## Runs

Every run was wrapped in the ledger tripwire. Before and after each one:
`docs/trials/trials.jsonl` 174 lines, SHA-256
`1bb5dbfe90c9df370c65910650ade15dd9d0e0366d011e09baf303975275f30f`;
`docs/trials/trials.head.json` SHA-256
`f83b1b9be5a608d444d61496899d25139eb56184fd924acd030e61347d22d764`;
`docs/trials/returns/` absent; `tests/test_019_prices.py`
`b7cc6cc48fe409e1e1cfdce96eb6c98ad25b960cb7da89aaa8ead74e361ec706` and
`tests/test_019_conventions.py`
`05669610855dc98297ff79d0d242bc07f0066bf334d3b7720dbc40624a5b157f`. All matched every time.

| Run | Command | Result | Tripwire (America/New_York) |
|---|---|---|---|
| U0 before edits | `python -m pytest tests/test_041_pay_date_bound.py tests/test_020_unadjusted_price_data.py -q --tb=no` | 22 passed / 64 failed | 21:36:53 -> 21:36:57 OK |
| UA after Checkpoint A | same, `--tb=line -p no:cacheprovider` | 27 passed / 59 failed | 21:39:24 -> 21:39:27 OK |
| UB1 after Checkpoint B | same, `--tb=short -p no:cacheprovider` | 84 passed / 2 failed | 21:40:40 -> 21:40:44 OK |
| UB2 after the Spec 020 change | same, `--tb=line -p no:cacheprovider` | 85 passed / 1 failed | 21:41:35 -> 21:41:39 OK |
| F1 full suite | `python -m pytest tests -p no:cacheprovider -q --tb=short` | **973 passed / 1 failed, exit 1**, 1386 subtests passed, 290.14s | 21:41:45 -> 21:46:37 OK |

U0 reproduces Unit 2's expected Windows state of 7 + 15 passed. At UA the
remaining failures were all the version-2 guard or the still-version-1 writer,
which is expected before T011. At UB1 the two failures were the offline flow
(`KeyError: 'Pay_Date_Basis'` at test line 209, which is T013) and the Spec 020
yfinance refusal (`ValueError not raised`), which is the anticipated change.

F1's only failure is `test_offline_download_load_and_funded_backtest`, which
stops at the harness `Pay_Date_Basis` assertion. Every data-layer assertion
before it passes: manifest v2, the on-disk columns, the attrs, and resolution
after the last session, and `run_backtest` completes. 973 + 1 = 974 = 903 + 71,
the Unit 1 baseline plus this file's cases. The two warnings are third-party
deprecations from fastapi/starlette.

## The Spec 020 change

In `test_provisional_adapter_does_not_invent_dividend_payment_date`, the adapter
passed to `cache_unadjusted_market_data` is wrapped. The wrapper returns the
adapter's own snapshot with `dividend_pay_date_policy="sourced"`
(`dataclasses.replace`). The assertion is still
`assertRaisesRegex(ValueError, "dividend payment date missing")`, and the
preceding assertion that the adapter leaves the date null is unchanged. Intent
kept: a null vendor date is still refused under the strict policy. Added: one
import line and the four-line wrapper class. The target argument changed from
`adapter` to `SourcedPolicy()`.

## Deviations from the prompt

1. `_validate_corporate_actions` has a second keyword-only argument,
   `manifest_version`. The validator has to know whether the basis column is
   required, because version 2 must reject its absence and version 1 must not
   need it.
2. `UnadjustedSourceSnapshot` also gains `dividend_pay_date_bound_source`. The
   citation travels with the policy from the adapter that declared it. The writer
   never reads the module constants.
3. `_ValidatedUnadjustedBundle` gains two defaulted fields for the policy and source.
4. **The writer fills a missing basis column** as `sourced` on dividends and empty
   on splits. It does this only when the snapshot's policy is `sourced` and the
   column is absent. Existing fixtures (`unadjusted_fixtures.StubSource`, the Spec
   020 `SyntheticSource`) send five-column actions, and FR-003 says an adapter
   that declares nothing gets today's behavior. A null date is still refused.
   Under any other policy a missing column is a schema failure.
5. Stricter than the spec, which is silent: a manifest or snapshot with policy
   `sourced` or `unbounded` and a non-null bound source is rejected. Otherwise an
   unbounded bundle's attrs could show a citation. The writer always records
   both keys, with `null` for the source unless the policy is bound.
6. Version-1 loads have no basis column. Their attrs are
   `dividend_pay_date_policy=None`, `dividend_pay_date_bound_source=None`,
   `dividends_sourced=None` (unmarked, never inferred) and `dividends_bound=0`
   (strict validation makes a bound row impossible). T014's renderer must allow
   `None` for `dividends_sourced`.
7. Focused and full runs added `-p no:cacheprovider` so no `.pytest_cache` was
   written; F1 also added `-q --tb=short`. Collection and selection are unchanged.
8. `load_unadjusted_market_data`'s call to `_merge_actions_for_execution` changed.
   Those two lines are the exact `ORIGINAL` string in
   `tests/mutation/run_mutation_check.py`, a manual Spec 020 driver not run by the
   suite. It will now print `MUTATION SETUP FAILED: target occurred 0 times`. It
   fails loudly, not silently. The driver was not edited, because only the one
   Spec 020 assertion was authorized. Camden should update its `ORIGINAL` and
   `MUTANT` strings.

## Flags: conflicts and test concerns

- **The sentinel cannot be strictly later than every representable session.**
  FR-005 asks for "a naive midnight timestamp later than any representable
  session". The latest midnight that `datetime64[ns]` can hold is 2262-04-11, and
  under the repository's holiday rules that is an ordinary Friday session (Good
  Friday 2262 is 04-04). Mitigation: the loader refuses a marked bundle whose
  final session is at or after the sentinel. So the sentinel is later than every
  session of any bundle it is attached to, but not of every representable one.
- **The M2 oracle misses the "ignores the policy" mutant.** All three of its
  bundles use basis `sourced`. A mutant that keeps the basis condition and drops
  the policy (`null_pay_date_allowed = bound`) survives it. The rule-table case
  `bound-null` under the `sourced` policy catches that mutant in the normal run,
  but `killed()` at T015 runs only the oracle. Suggestion for T015: add a
  version-2 `sourced`-policy bundle with a `bound` null row to oracle M2.
- **Rule 12: new gates without red proof yet.** None of these is exercised by a
  test: the sentinel-reach refusal, a source on a non-bound policy, the snapshot
  (`source ...`) policy and source checks, and the validator's unknown-policy
  check. The last is defensive, since both callers pass an already-validated
  policy. All need a planted-defect test, T015 or a follow-up, before merge.
- Basis values are exact strings. A value such as `"Bound"` or `"bound "` is
  rejected, not normalized.
- **Nothing looks too good.** No performance figure was produced. The 46 v2
  rule-table cases and the manifest cases went green together because a single
  guard, the unsupported manifest version, had blocked all of them.

## Not done (out of scope)

T013 (harness `Pay_Date_Basis`), T014 (FR-007 disclosure), T015 (`killed()`
wiring and red proofs), T016-T017 final verification, T018 (Camden's online AAPL
run). `scripts/backtest_harness.py` was not touched.

## For Camden to run on Windows

    python -m pytest tests/test_041_pay_date_bound.py tests/test_020_unadjusted_price_data.py -q --tb=short
    python -m pytest tests

Expect 85 passed / 1 failed, then 973 passed / 1 failed. The single failure is
`test_offline_download_load_and_funded_backtest` with `KeyError: 'Pay_Date_Basis'`.
