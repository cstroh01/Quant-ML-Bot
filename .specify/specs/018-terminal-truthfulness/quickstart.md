# Quickstart: Validating Spec 018

This guide describes how to verify spec 018 once it is implemented. It uses
PowerShell on the local Windows workstation; the CI commands are in
`.github/workflows/test.yml`. No step uses `git`.

## Prerequisites

- The repository's `venv` is activated, with `requirements.txt` and
  `reports/requirements-ui.txt` installed.
- Node 24 and `npm` are installed, for the web checks only.
- No network access is needed by any step below.

## 1. Full suite in the working tree

```powershell
python -m unittest discover -s tests
```

Expected: 0 failures, 0 errors. `test_reports_api` and
`test_terminal_truthfulness` run and are not skipped.

## 2. Clean-checkout check (pass-condition clause 3)

This reproduces the audit's method of a copied tree without ignored state
(`docs/audit-2026-09-12/clean-checkout-api.log`), without using `git` to
export.

```powershell
$dest = Join-Path $env:TEMP "qmb-clean-018"
Remove-Item -Recurse -Force $dest -ErrorAction SilentlyContinue
robocopy . $dest /E /XD .git venv .venv node_modules dist data __pycache__ .claude /NFL /NDL /NJH /NJS | Out-Null
Push-Location $dest
python -m unittest discover -s tests
Pop-Location
```

Expected: 0 failures, 0 errors, with neither `data/` nor `reports/web/dist/`
present. Compare with the audit's pre-018 result: `Ran 11 tests … FAILED
(failures=7)`.

To confirm the API tests read only fixtures, point the real cache at a missing
directory and rerun the API modules:

```powershell
python -m unittest tests.test_reports_api tests.test_terminal_truthfulness
```

The modules do this themselves in `setUpModule` (research R4). If a test
bypasses the seam, it returns 404 and fails.

## 3. Pass-condition clause 1 — no fabricated evidence

```powershell
python -m unittest tests.test_terminal_truthfulness -v
```

Expected: L1, L2 and L3 test classes pass. There are no stale allowlist
entries, and (after PR G) `PENDING_COVERAGE` is empty. For the rules, see
[contracts/regression-and-mutation.md](contracts/regression-and-mutation.md).

## 4. Pass-condition clause 2 — malformed input fails

```powershell
python -m unittest tests.test_cost_domain tests.test_backtest_harness tests.test_metrics -v
```

Expected: every row of the domain table raises at the library boundary, and
returns a 4xx carrying the standard error body at the HTTP boundary
([contracts/api-responses.md](contracts/api-responses.md)).

## 5. Statistics oracles

```powershell
python -m unittest tests.test_feature_scaling tests.test_ma_crossover_backtest -v
```

Expected results:
- **McNemar**: matches the exhaustive binomial oracle, and 0 of 2 returns
  1.0.
- **VIF**: duplicate and linear-combination columns are `inf`; a constant
  column is `NaN` and doesn't raise.
- **Holding bars**: match the hand counts across the holiday, the same-session
  trade and the forced exit.
- **Cost breakdown**: matches the zero-cost rerun within 1e-9.

## 6. Mutation check (SC-002)

```powershell
python tests/mutation/run_spec_018_mutants.py
```

Expected:
- the control passes
- all 17 mutants are caught
- source hashes match before and after
- the printed table is pasted into `tasks.md`

Exit code 0.

## 7. Web terminal build and lint (SC-005)

```powershell
Push-Location reports/web
npm ci
npm run lint
npm run build
Pop-Location
```

Expected: lint passes, and the build (`tsc -b && vite build`) succeeds.

## 8. Manual look at the terminal

```powershell
python -m reports.api.main
```

Open `http://127.0.0.1:8000/` (after `npm run build`), or run the Vite dev
server on port 5173. Check each of these:

| Screen | Expected |
|---|---|
| Header | Test status "Not reported", with no count and no pulsing green dot |
| Feature Diagnostics | The significance section shows "Not computed" with its reason; conditioning badges follow the displayed values; unknown correlations show as unavailable |
| Rundown pane | "Model forecast: Not computed"; four indicator rule readings; no "ML", "model predicts" or trading advice |
| Capital Gate | Five gates, all "Unknown"; the explanation names the same five gates |
| Walk-Forward CV | Labelled "Illustration of the splitting scheme — not a saved run" |
| Backtest & Tearsheet | Labelled "Rule-based SMA crossover — not an ML model"; commission and slippage shown separately; spread "not modeled"; holding bars vary per trade |

A request from another origin returns no `access-control-allow-origin`
header:

```powershell
curl.exe -s -D - -o NUL -H "Origin: https://untrusted.example" http://127.0.0.1:8000/api/health
```
