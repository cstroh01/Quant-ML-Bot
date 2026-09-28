# Spec 036 implementation handoff — 2026-09-27

T001 was completed before this resumption. T002-T023 are complete locally. Camden reviews and commits in GitKraken; no Git command or PR creation occurred here.

## Verification

- Pre-change full suite: 887 collected; **885 passed, 2 failed, 0 errors** in 449.24s. Failing IDs: `tests/test_reports_api.py::TestReportsApi::test_backtest_tearsheet` and `tests/test_clean_clone_037.py::test_changed_baseline_funding_mutant_is_killed`.
- Post-change full suite: 903 collected; **902 passed, 1 failed, 0 errors** in 355.59s. The tearsheet passes and all 16 new tests pass. Only the same clean-clone mutation ID fails; its expected inline source fragment is absent from the currently reformatted `scripts/multi_ticker_comparison.py`. That source and `tests/test_multi_ticker_comparison.py` were not edited in this lane.
- Focused: 68 passed plus 27 subtests for resolver/spec 020/data; 24 passed for CLI/legacy crossover; 17 passed for reports API. Six mutation controls passed; all seven spec 036 mutants were killed; source hashes were identical before/after mutation runs.
- Real-cache smoke: `data/cache/unadjusted/` absent; CLI stderr was `AAPL: unadjusted price data unavailable (missing): C:\GitHub\Quant-ML-Bot\data\cache\unadjusted`, exit 1. Production ledger remained 174 lines with identical SHA-256.

## Review units and seams

1. **Resolver and synthetic fixture** — `scripts/data.py`, `tests/unadjusted_fixtures.py`, resolver/loader portion of `tests/test_unadjusted_caller_wiring.py`. Seam: a ticker resolves to one validated manifest or raises `UnadjustedDataUnavailable`.
2. **CLI and signal** — `scripts/ma_crossover_backtest.py`, CLI/signal portion of `tests/test_unadjusted_caller_wiring.py`. Seam: the loaded nominal frame funds every strategy/baseline, while causal `Research_Close` drives the SMA.
3. **Tearsheet** — `reports/api/routes/backtest.py`, `reports/api/schemas.py`, `tests/api_fixtures.py`, `tests/test_reports_api.py`. Seam: the route maps bundle unavailability to 503 and returns a funded 200 with provenance.
4. **Mutation and evidence** — `tests/mutation/run_unadjusted_wiring_mutants.py`, this handoff, `tasks.md`, `spec.md`, `quickstart.md`. Seam: isolated mutant proofs and full-suite comparison.

Each unit is under the approximately 400 changed-line review limit. Review in that order; the second and third units depend on the resolver.

## PR description draft for Camden

**Spec 036 — wire funded callers to validated unadjusted bundles.** The AAPL crossover CLI and tearsheet now load a single manifest-backed bundle, fail closed on missing/ambiguous/invalid data, compute SMA signals from causal `Research_Close`, and fund only nominal Open/Close dollars. The route returns documented 503 details or a funded 200 with source provenance. The CLI resolves before opening a trial, so unavailable runs leave the trial ledger unchanged. No fallback to adjusted prices remains in these callers. The split signal and all seven wiring gates have red/green and mutation proof.

No metrics reported: real data is unavailable (B-1); synthetic P&L is a test oracle. No new dependencies. B-1 awaits spec 041's approved dividend-pay-date bound; F-1 awaits Rule 14 second-source verification. The unrelated spec 037 mutation test remains red in this checkout on its old source fragment. Four sequential review units are listed above; no PR was opened.

## Files touched in this resumption

`scripts/data.py`; `scripts/ma_crossover_backtest.py`; `reports/api/routes/backtest.py`; `reports/api/schemas.py`; `tests/unadjusted_fixtures.py`; `tests/test_unadjusted_caller_wiring.py`; `tests/api_fixtures.py`; `tests/test_reports_api.py`; `tests/mutation/run_unadjusted_wiring_mutants.py`; `.specify/specs/036-unadjusted-caller-wiring/{HANDOFF.md,spec.md,tasks.md,quickstart.md}`.

## Prior stopped state (archived)

## Completed

- STEP 0: renamed the eight-file spec directory to 036 and repointed `.specify/feature.json`; updated references except the protected finish plan.
- STEP 1 / T001: D-1 through D-7 marked DECIDED, preserving recommendation substance; added the 021 handoff pointer and marked 018 T024 superseded by 036.
- Required dependency installation completed (exit 0).

## Blocker and verification

Before implementation: **0 passed / 0 failed / 1 collection error**. The failing collection ID is `tests/test_multi_ticker_comparison.py`; line 23 contains non-UTF-8 byte `0x97` without an encoding declaration. This file belongs to the other lane and is expressly protected. No change was made there. The expected 886 passed / 1 failed baseline was not reproduced.

After implementation: **not run; implementation has not started**. T002 remains blocked; T003-T023 remain open. Resume with the required baseline after the owning lane repairs this file. Logs: `baseline.log`, `baseline.xml`.

All explicitly protected files and existing `data/cache/**` files have identical SHA-256 hashes to the pre-work snapshot. No source or test file was edited. No Git command was run.

## Unexpected findings

- `docs/V1-FINISH-PLAN.md:76` contains the old placeholder reference. It remains untouched because the explicit protected-file constraint wins over the broad reference-update instruction.
- Pip reported an existing environment conflict: numba 0.65.1 needs numpy<2.5; the project pins numpy 2.5.2. Installation still exited 0. No requirements were edited.
- D-7 contains historical Norgate references. Its recommendations were preserved as requested, with an explicit note that the authoritative scope permits only free sources. B-1 and F-1 remain open.
- The spec 037 initial-provenance artifact's eight path keys were updated for the rename. Its historical hash values were preserved; they are not current hashes of edited spec files.

## Review units

Only the metadata unit is present. Future sequential units: resolver and fixtures; CLI and signal tests; API and tests; mutation driver and final evidence. Keep each within about 400 changed lines and subdivide if needed. No PR was opened.

## Files touched

- `.specify/feature.json` (2 changed lines)
- `.specify/specs/018-terminal-truthfulness/tasks.md` (2 changed lines)
- `.specify/specs/020-unadjusted-price-data/spec.md` (2 changed lines)
- `.specify/specs/021-finish-spec-019-migration/tasks.md` (4 changed lines)
- `.specify/specs/037-clean-clone-green/artifacts/initial-provenance.json` (16 changed lines)
- `.specify/specs/036-unadjusted-caller-wiring/checklists/requirements.md` (6 changed lines; renamed)
- `.specify/specs/036-unadjusted-caller-wiring/contracts/cli-and-api.md` (renamed; content unchanged)
- `.specify/specs/036-unadjusted-caller-wiring/data-model.md` (renamed; content unchanged)
- `.specify/specs/036-unadjusted-caller-wiring/plan.md` (8 changed lines; renamed)
- `.specify/specs/036-unadjusted-caller-wiring/quickstart.md` (renamed; content unchanged)
- `.specify/specs/036-unadjusted-caller-wiring/research.md` (renamed; content unchanged)
- `.specify/specs/036-unadjusted-caller-wiring/spec.md` (31 changed lines; renamed)
- `.specify/specs/036-unadjusted-caller-wiring/tasks.md` (14 changed lines; renamed)
- `docs/HANDOFF-2026-09-25.md` (11 changed lines)
- `.specify/specs/036-unadjusted-caller-wiring/baseline.log` (new baseline output)
- `.specify/specs/036-unadjusted-caller-wiring/baseline.xml` (new machine-readable baseline)
- `.specify/specs/036-unadjusted-caller-wiring/HANDOFF.md` (this report)

A temporary `.specify/spec036-backup-path.txt` bookkeeping file was created and removed; it is not a deliverable.
