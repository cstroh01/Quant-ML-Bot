# Spec 037 — clean-clone categorization, 2026-10-03

Report only. It changes no code, test, spec checkbox, or ledger byte. It records
one run of the full suite on clean `origin/main` and puts every non-passing node
in a category.

**Provenance.** Source: `origin/main` at `5840b62b8adff152dbd435251eb072f158e758c6`
(merge of PR #12). Produced by an unattended cloud scheduled-session run on
2026-10-03. Numbers come from that run's raw pytest output. The output was not
committed because it is regenerable with the command below.

**Environment.** Linux 6.18, 4 CPUs, CPython 3.12.3. The venv was built from
`requirements.txt` and `requirements-dev.txt` exactly as pinned (spot-checked:
numpy 2.5.3, pandas 3.0.6, scipy 1.18.1, scikit-learn 1.9.1, pytest 9.1.1,
fastapi 0.142.0). No network was used beyond pip. **This Linux run is evidence,
not the gate. Camden's Windows venv is authoritative.**

## Runs

| Run | Tree | Command | Exit | Passed | Failed | Errors | Skipped | xfailed | XPASS |
|---|---|---|---|---|---|---|---|---|---|
| A | Fresh clone of `origin/main` (working tree, no gitignored files present) | `python -m pytest tests` | 0 | 1057 | 0 | 0 | 0 | 4 | 0 |
| B | Export of A's tracked files to a scratch directory outside the repo, with no `.git` and no `__pycache__` | `python -m pytest tests` | 0 | 1057 | 0 | 0 | 0 | 4 | 0 |

Both runs also passed 1386 subtests and raised one warning: Starlette's
`httpx` deprecation from `fastapi/testclient.py`. That warning comes from the
environment, not a defect. Run B shows the suite does not depend on the
repository's `.git` directory or on any cached bytecode.

After each run, `docs/trials/trials.jsonl` still had 174 lines with SHA-256
`1bb5dbfe…275f30f`. `trials.head.json` was unchanged at `f83b1b9b…d22d764`, and
`docs/trials/returns/` was absent.

## Categorization

**Failures and errors: none.** No node needs a category.

**Skips: none.**

**xfails: four, all `strict=True`.** To check that each one is red for the
reason its marker names, and not for some unrelated defect, I re-ran the two
modules with `--runxfail`:

| Node | Marker reason (as written) | Actual failure under `--runxfail` | Category | Owning task |
|---|---|---|---|---|
| `tests/test_043_enabled_control.py::test_record_trial_flag_records_complete_funded_trials` | "guard lands in T020+" | `ma_crossover_backtest.main` argparse exits 2: `unrecognized arguments: --record-trial` | Deliberate-contract churn: the enablement flag does not exist yet | 043 T025 |
| `tests/test_043_entry_points.py::test_default_entry_changes_no_ledger_bytes[E3]` | "CLI refusal lands in T023-T025 (U2)" | `assert_refused` fails (`ledger_copy_support.py:156`). No ledger bytes change, but E3 does not exit before output, as its comment in the test says | Deliberate-contract churn: the preflight does not exist yet | 043 T025 |
| `tests/test_043_entry_points.py::test_default_entry_changes_no_ledger_bytes[E5]` | "read-only route lands in T027 (U3)" | The route returns **HTTP 500 `Internal Server Error`** where the contract expects a 409. Ledger counts are unchanged (87 → 87, 0 records, 0 sidecars) | Deliberate-contract churn, with a visible side effect (below) | 043 T027 |
| `tests/test_043_entry_points.py::test_e5_serves_recorded_configuration_read_only` | "read-only route lands in T027 (U3)" | The E1 recording step fails first with the same `--record-trial` argparse exit 2, so it never reaches the route | Deliberate-contract churn. It depends on both T025 and T027 | 043 T025 + T027 |

**Real defects: none in the test sense.** Every red is a strict xfail that
waits on a named, unchecked 043 task.

**Environment: none.**

## Observations for Camden (not fixed here)

1. **The tearsheet GET returns 500 on `main` today.**
   `reports/api/routes/backtest.py:60` enters `trial_runner.research_attempt`.
   Since 043 T024 (PR #15), that call raises `LedgerWriteRefused` outside
   synthetic contexts unless production recording is enabled, which nothing
   can enable before T025. The route does not catch it, so the result is an
   unhandled 500. This is the intended fail-closed behaviour until T027. A
   reader of the API sees a bare server error, though, not a message that
   names the recording command. The E5 xfail above is the evidence.
2. **The xfail reason strings are stale.** `test_043_enabled_control.py:7`
   says "T020+", and `test_043_entry_points.py:14` says "T023-T025". The
   remaining owner of both is T025 (`docs/STATE.md` agrees). The reasons are
   message text, not assertions. Fixing them belongs in T025's PR, which
   removes the markers anyway.
3. **037's own records disagree with the tree.** The spec 037 `Status` line
   (`spec.md:5`) still says "886 passed, 1 failed". `tasks.md` T017 is still
   unchecked and names its blocker as "the unchanged Spec 036 tearsheet
   success test". That test no longer produces a failure in this run. As of this run, SC-001's measurable condition holds on Linux:
   zero failed or error nodes from an artifact-free export, and no skips. The
   four strict xfails are deliberate 043 contracts. Whether strict xfails
   satisfy SC-001's "full suite passes", and whether T017 can be checked, is
   Camden's call. Windows confirmation is still outstanding. This report does
   not edit 037's spec or tasks.

## Reproduce

```
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest tests -q -rfEsxX
.venv/bin/python -m pytest tests/test_043_enabled_control.py tests/test_043_entry_points.py --runxfail -q --tb=short
```
