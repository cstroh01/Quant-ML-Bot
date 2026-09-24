# Quickstart: Validating the Unadjusted Caller Wiring

Everything here runs offline, from the repository root.

## Prerequisites

```
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## 1. Record the pre-change baseline

```
python -m pytest tests -q
```

Record the failing set in `tasks.md` → Evidence **before** any edit. SC-006 is
measured against it.

## 2. Focused checks (PR-1)

```
python -m pytest tests/test_unadjusted_caller_wiring.py -v
```

Expected: every test passes. The following cases must be present by name:

- resolver: missing directory, zero matches, two matches (ambiguous), the `A`
  vs `AA` stem, an invalid symbol, exactly one match;
- loader: a tampered data hash raises `invalid` with the hash check message;
- CLI: an empty cache gives a nonzero exit, stderr names AAPL and "unavailable",
  no files are written, and the ledger is unchanged;
- CLI: a valid synthetic bundle gives exit 0, and every `run_backtest` input
  carries `unadjusted_dollars` (checked with a spy);
- signal basis: no signal on the split session, with the nominal-`Close`
  control emitting one;
- static: no `download_market_data` in `ma_crossover_backtest.py`.

## 3. Focused checks (PR-2, if D-3 is accepted)

```
python -m pytest tests/test_reports_api.py -v
```

Expected:

- `test_backtest_tearsheet` returns 200 on a synthetic bundle, with the
  provenance fields present;
- the new 503 tests (missing, ambiguous, invalid) pass.

## 4. Mutants

```
python tests/mutation/run_unadjusted_wiring_mutants.py
```

Expected: every mutant in [research R-6](research.md#r-6-mutants) is KILLED and
the control passes. Record the results in `tasks.md` → Evidence.

## 5. Full gate

```
python -m pytest tests
```

Expected: no failure outside the baseline recorded in step 1.

## 6. Manual smoke test (real cache, optional)

```
python scripts/ma_crossover_backtest.py ; echo "exit=$?"
```

Expected **today**: exit 1, and stderr reads
`AAPL: unadjusted price data unavailable (missing): …data/cache/unadjusted`.
That is the correct result while spec 020 Q1 is open (spec B-1). No trades CSV
or figure is modified. `docs/trials/trials.jsonl` gains no line.

**Do not** try to populate the cache with `download_unadjusted_market_data("AAPL", …)`
to make it green. It fails validation on missing dividend payment dates, which
is correct behavior.
