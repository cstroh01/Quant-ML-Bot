# Contract: Fabricated-literal regression and mutation runner (Spec 018)

This contract is normative for `tests/test_terminal_truthfulness.py` and
`tests/mutation/run_spec_018_mutants.py`. The design rationale is in
[../research.md](../research.md) R3.

---

## Numeric figure (text tokenizer)

A substring of text counts as a **numeric figure** when it matches any of the
following:

```text
[-+]?\d+\.\d+            decimal         e.g. 54.2, +0.17, 0.084
\d+(\.\d+)?\s*%          percentage      e.g. 55%, 54.2%
\d+\s*/\s*\d+            ratio           e.g. 311/311
(?<![\w.])\d{3,}(?![\w.])  bare integer, three or more digits   e.g. 301
```

Not figures: two-digit bare integers ("10-day", "SMA30") and digits inside
identifiers. The limitation is deliberate and stated: a two-digit literal
inside text escapes L1 and L2. Numeric JSON leaves are always checked,
whatever their size.

---

## L1 — differential

- **Fixtures**: `api_fixtures.panel(seed=1, sessions≈300, drift>0)` and
  `api_fixtures.panel(seed=2, sessions≈347, drift<0)`, each served through
  `app.dependency_overrides[get_cache_dir]`.
- **Covered endpoints** (the table grows per PR; see *Coverage* below):

| Endpoint | Query | Added in |
|---|---|---|
| `/api/data/ohlcv`, `/api/data/stats`, `/api/data/gaps` | `ticker=AAPL` | PR B |
| `/api/diagnostics/significance` | `ticker=AAPL` | PR B |
| `/api/diagnostics/collinearity` | `ticker=AAPL` | PR B |
| `/api/ml/rundown` | `ticker=AAPL` | PR B |
| `/api/backtest/tearsheet` | defaults | PR B (with pending fields), completed PR D |

**Check.** For each JSON path, with list indices normalized to `[]`:
- **Numeric leaves** (int/float, not bool): if
  `set(values_A[path]) == set(values_B[path])` and the path is not
  allowlisted, **fail**, printing the path and the value set.
- **Text leaves**: the same test on `set(figures(text) for text in values[path])`.
- **Paths present in only one fixture**: skipped. That can only happen for
  branch-dependent keys, and L2 covers those.

---

## L2 — static

**Files**: `reports/api/routes/*.py` and `reports/api/schemas.py`.
**Schema classes**: every `BaseModel` subclass defined in `schemas.py`.

| Rule | Fails when | Mutants it catches |
|---|---|---|
| S1 numeric keyword | a call to a schema class passes `field=<int/float Constant>`, or `field=<Name>` where `Name` was assigned an int/float `Constant` in the same function | 1, 7 |
| S2 pass-flag literal | a call to a schema class passes a `True`/`False` `Constant` to a field whose name contains `passed` or `reconcil` | 8 |
| S3 gate status literal | a `CapitalGateItem(...)` call passes `status=` a string `Constant` other than `"unknown"` | 4 |
| S4 figure in text | any `str` `Constant`, or any `Constant` part of a `JoinedStr` (format specs and docstrings excluded), contains a numeric figure | 2, 3, 5 |
| S5 numeric schema default | an annotated assignment in a schema class has an int/float `Constant` default | 7 (schema half) |

Each rule honours the allowlist. S4 entries must carry `permitted_figures`,
and a figure not matching that pattern still fails.

---

## L3 — UI source scan

**Files**: `reports/web/src/**/*.ts` and `reports/web/src/**/*.tsx`.

| Pattern (case-insensitive unless noted) | Scope | Mutants |
|---|---|---|
| `\d+\s*/\s*\d+\s*PASS` | all | 6 |
| `\b\d+\s+passed\b` | all | 5 (UI copy) |
| `P\((Up|Down)\)\s*=` | all | 2, 3 |
| `\bLogit\b` | all | 2 |
| `\bKelly\b` | all | — (FR-015) |
| `chance of being luck`, `less than a \d+% chance` | all | — (FR-013) |
| `\d+x\s+Improvement` | all | — (FR-014) |
| `of 5 Gates` | all | — (FR-008) |
| `\?\?\s*0\b` | `FeatureDiagnosticsView.tsx` | 17 |
| `✓\s*1e-9` | all | — (FR-021) |

---

## Allowlist

The allowlist lives in `tests/test_terminal_truthfulness.py` as a literal tuple
of `AllowlistEntry` ([../data-model.md](../data-model.md)). Every entry needs a
reason a reviewer can check.

| Category | Admissible when | Example |
|---|---|---|
| `request_echo` | the value is a request parameter returned verbatim | `/api/backtest/tearsheet` `commission_per_trade` |
| `configuration` | the value equals a named module constant, and the test asserts that equality | `reconciliation.tolerance == metrics.RECONCILIATION_TOLERANCE` |
| `structural_ordinal` | position in a fixed list | `rule_readings[].rank`; `gates[].gate_number` |
| `structurally_constant` | identical by construction of the computation, and the reason says why | buy-and-hold `total_trades` (one round trip) |
| `roadmap_reference` | text naming a stage, finding or spec | `reason` fields, with `permitted_figures = r"Stage \d+\.\d+|finding \d{2}|spec \d{3}"` |

A test fails if any entry matched nothing in the run (`stale allowlist entry`).

---

## Coverage

`PENDING_COVERAGE` maps each not-yet-covered endpoint or field to the PR that
owns its fix:
- after PR B: `trade_log[].holding_bars` → PR D, and
  `reconciliation_passed` → PR C
- PR G: `test_every_api_get_route_is_covered` enumerates `app.routes` and
  asserts each `GET /api/*` path is in L1's table or in
  `FIXTURE_INDEPENDENT = {"/api/health", "/api/data/tickers",
  "/api/capital_gate/status"}`, and that `PENDING_COVERAGE == {}`

**Fixture-independent endpoints** get explicit assertions instead of L1:
- `/api/capital_gate/status` — every gate `unknown`, `evidence is None`,
  `test_run.status == "not_computed"`, and no figure outside roadmap
  references
- `/api/health` and `/api/data/tickers` — no numeric leaves

---

## Must fail against pre-018 code (spec 007 precedent)

PR B's description records the regression run against the unmodified route
modules (via the mutation runner's `--baseline` mode). It must show failures
naming, at minimum:
- `p_value` in `/api/diagnostics/significance`
- `P(Up) = 54.2%` in `ml_rundown.py`
- `status="passed"` and `301` in `capital_gate.py`
- `311/311` in `Header.tsx`

PR C and PR D record the same for the reconciliation literal and
`holding_bars=1`.

---

## Mutation runner — `tests/mutation/run_spec_018_mutants.py`

```text
python tests/mutation/run_spec_018_mutants.py [--only ID[,ID...]] [--baseline]
```

- **Not collected.** `tests/mutation/` has no `__init__.py`, and the filename
  does not match `test*.py`.
- **Workspace.** Copies `scripts/`, `reports/api/`, `reports/web/src/` and
  `tests/` into a fresh temporary directory; `tempfile`, stdlib only. It never
  writes to the repository.
- **Control.** Runs the unmutated copy first: `python -m unittest` over the
  mutant table's target test modules, in a fresh interpreter with the copy as
  working directory. The control must pass, or the run aborts.
- **Mutants.** For each mutant, a fresh copy gets `find → replace` applied
  (which must match exactly once, or the mutant is reported
  `NOT APPLICABLE` and the run fails), then runs its target modules.
  Expected result: at least one failure or error.
- **Hashing.** SHA-256 of every mutated source file in the repository, before
  and after the run; they must match.
- **Output.** A Markdown table (`id | file | defect | tests run | failed |
  caught`) printed for pasting into `tasks.md`. Exit is non-zero if any mutant
  survives.
- **`--baseline`.** Skips the mutants; instead runs the regression tests
  against a copy whose target files are replaced with an explicitly supplied
  pre-fix snapshot directory. Used once per PR, for the "fails against pre-fix
  code" evidence.

### Mutant table (SC-002)

| ID | File | Find → replace (summary) | Target test modules |
|---|---|---|---|
| 1 | `reports/api/routes/diagnostics.py` | significance body → adds an entry with `p_value=0.084` | `test_terminal_truthfulness`, `test_reports_api` |
| 2 | `reports/api/routes/ml_rundown.py` | forecast reason → `"P(Up) = 54.2% \| Logit Score = +0.17"` | same |
| 3 | `reports/api/routes/ml_rundown.py` | adds an unreachable branch string `"P(Down) = 53.8%"` | `test_terminal_truthfulness` (L2 only) |
| 4 | `reports/api/routes/capital_gate.py` | gate 1 `status="unknown"` → `"passed"` | `test_terminal_truthfulness`, `test_reports_api` |
| 5 | `reports/api/routes/capital_gate.py` | gate 1 reason → `"301 passed in pytest suite"` | same |
| 6 | `reports/web/src/components/layout/Header.tsx` | badge text → `CORE: 311/311 PASS` | `test_terminal_truthfulness` |
| 7 | `reports/api/routes/backtest.py` | `holding_bars=holding[i]` → `holding_bars=1` | `test_terminal_truthfulness`, `test_reports_api` |
| 8 | `reports/api/routes/backtest.py` | computed reconciliation → literal `passed=True` | `test_terminal_truthfulness` |
| 9 | `scripts/cost_domain.py` | finiteness check removed (reduces to `x < 0`) | `test_cost_domain`, `test_backtest_harness` |
| 10 | `scripts/backtest_harness.py` | boolean-dtype signal check removed | `test_backtest_harness` |
| 11 | `scripts/feature_set_comparison.py` | `binomtest(...)` → `two_sided/2 if favours_b else 1 - two_sided/2` | `test_feature_scaling` |
| 12 | `scripts/feature_diagnostics.py` | regression VIF → `np.diag(np.linalg.pinv(corr))` | `test_feature_scaling` |
| 13 | `reports/api/routes/backtest.py` | `long_window > short_window` check removed | `test_cost_domain`, `test_reports_api` |
| 14 | `reports/api/main.py` | origins → `["*"]`, `allow_credentials=True` | `test_reports_api` |
| 15 | `reports/api/routes/data.py` | loader ignores `cache_dir`, reads `CACHE_DIR` | `test_reports_api` |
| 16 | `scripts/backtest_harness.py` | `spread_total=None` → `0.0` | `test_backtest_harness`, `test_terminal_truthfulness` |
| 17 | `reports/web/src/components/views/FeatureDiagnosticsView.tsx` | undefined-correlation rendering → `?? 0` | `test_terminal_truthfulness` |

Exact `find`/`replace` strings are fixed when the post-fix code exists, and
are recorded in the runner, not here.
