# Note for the ledger-write-guard spec (not 040 work)

Recorded 2026-09-28 during 040 task review. **Nothing here is in 040's scope.**
It predates the migration. Moved on 2026-09-28 from
`.specify/specs/040-installable-package/` into spec 043, which owns it: see
spec.md D-3(a) and FR-012.

## 1. Alias-assignment bypass in the instrumentation guard

`tests/test_033_trial_instrumentation.py:18-23` (`bypasses`) resolves aliases
only from `ImportFrom` (`from m import run_backtest as rb`). A primitive bound
by plain assignment and then called is not recognised:

```python
rb = run_backtest          # ast.Assign: not in `aliases`
rb(prices, **costs)        # name "rb" is not in PRIMITIVES, so not flagged
```

`getattr(module, "run_backtest")(…)` escapes the same way.

- **Status on 2026-09-28**: latent. An AST scan of `scripts/` and `reports/api/`
  found no assignment of a primitive to a name, and no primitive passed as a
  keyword argument. The guard is incomplete, but nothing uses the gap.
- **Why not 040**: 040 rewrites paths and import forms (T032). This gap exists
  identically before and after the move. Fixing it in 040 would widen a
  migration that AC-1 holds to an allowlist.
- **Proof shape for the fix (Rule 12)**: a planted `rb = run_backtest; rb(x)`
  outside `research_attempt` must be reported, and the clean tree is the
  green control.

## 2. Why the spec is needed: production is the default

`scripts/trial_runner.py:17-31` `current_ledger()` returns the production
`TrialLedger()` unless `SPEC033_SYNTHETIC_ROOT` is set, and only
`tests/conftest.py` sets it. Any process that reaches `research_attempt`
outside pytest therefore writes to `docs/trials/trials.jsonl`, its
`.head.json` and `docs/trials/returns/<trial_id>.jsonl`.

The incident that motivated this: on 2026-09-28, standalone verification
scripts called `multi_ticker_comparison._baseline_rows` outside pytest and
appended 21 synthetic trials: 42 ledger records, a new head, and 21 return
sidecars.

The inventory of every path that reaches the ledger is now spec.md §2. T004
re-runs it rather than trusting it.
