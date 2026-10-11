# Spec 033 T046 — reported DSR and t-stat inputs verified independently (queue Q31)

EXAMPLE — NOT A RESULT. Synthetic dyadic fixture only; no market data, no ledger write.
Base: main `6348bc4`. This record closes T046 and cites the evidence for the Phase 5–6 boxes that
queue items Q26–Q29 and the T034 PR filled without ticking them.

## What the new test pins
`tests/test_033_dsr.py::test_t046_reported_dsr_and_t_stat_inputs_verified_independently`
- **One selected column, both statistics.** Three trial columns stored as dyadic excess returns plus
  a log-rate risk-free (10% annual, 250 days). `matrix_dsr` selects column c at `N_current = 37`.
  Column c is neither the first column nor the best Sharpe. The test hands the same column to
  `hac_t_stat` with the family's risk-free, horizon 2 and lags 3 (above the horizon − 1 floor).
- **Not covered here.** No production entry point joins the two statistics yet; that is Gate 3
  (T056+). A caller that hands the t-stat the wrong column is out of this test's reach.
- **Independent oracle.** Every expected value comes from the declared column literals alone:
  exact `Fraction` moments (`t037_moments`), exact Newey–West/Bartlett `t²` (`t040_exact_t_squared`),
  and the standard library's `NormalDist`. Nothing reads the output object to derive an expectation.
- **Named assertions:** DEFINED, INPUTS (all six DSR inputs), SHARPES (column order), DSR (PSR
  denominator, benchmark, z, value), PROVENANCE (matrix hash, risk-free convention), REPLAY (a
  consistency check: the oracle inputs, not the reported ones, give the same value), TSTAT (excess
  mean, value, recorded lag and risk-free convention, standard error).

## Rule 12 — `python tests/mutation/run_033_t046_mutants.py`
One site per mutant in an isolated copy (spec 043 D-4 `driver_support`). A kill requires a JUnit
**failure**, not an error, in the T046 test, with the named witness in the assertion message.

| Mutant | Witness | Pre-T046 tests |
|---|---|---|
| reported Sharpe rounded, value from the exact one | T046 INPUTS | caught |
| simple-rate risk-free in the matrix | T046 INPUTS | caught |
| trial Sharpes reported sorted, not by column | T046 SHARPES | caught |
| best column reported, not the selected one | T046 INPUTS | caught |
| PSR denominator reported as its square root | T046 DSR | caught |
| matrix hash recomputed from values only | T046 PROVENANCE | caught |
| density instead of CDF | T046 DSR | caught |
| simple-rate risk-free in the t-stat | T046 TSTAT | caught |
| t-stat reports the raw mean | T046 TSTAT | caught |
| t-stat uses the lag floor, not the requested lag | T046 TSTAT | caught |
| t-stat records the lag floor | T046 TSTAT | **survives** |
| t-stat uses the repository day count | T046 TSTAT | **survives** |

- Result: 12/12 killed. Control: the unchanged copy is green with exactly 1 test collected.
- Negative control: the same mutants against the pre-T046 `test_033_dsr.py` and `test_033_pbo.py`.
  The control is green (55 passed). 2 of 12 survive. These are the "record the actual lag" (T045) and "family day count" cases.
- A fresh-context review found the first draft selected the best-Sharpe column, so an argmax mutant
  survived; the selected column, the hash, the denominator and the convention checks were added.
- Production sources and every `docs/trials/` file are byte-identical after the run.

## Checkbox evidence (Phase 5–6)
| Task | Evidence on `main` |
|---|---|
| T034 | `test_t034_committed_literal_matrix_hash_and_canonical_body`, PR #120; `T034-matrix-hash.md`, 6/6 mutants |
| T035 | `test_t035_session_alignment_boundaries_and_perturbation` (fold join included), PR #148 (queue Q28) |
| T037 | `test_t037_named_dsr_inputs_and_conventions` (dispersion and benchmark isolated), PR #147 (queue Q27) |
| T039 | `test_t039_lifetime_n_counts_every_candidate_start`, PR #151 (queue Q29) |
| T040 | `test_t040_hac_gate_boundary_oracle` (exact 3.0 and one value below), PR #146 (queue Q26) |
| T044 | `selection_bias.lifetime_count` and `counted_dsr`; `test_t044_lifetime_dsr_always_family_dsr_beside_it`, PR #151 |
| T046 | This record. T034–T040 and the paper fixture (T036) are green in the suite run below |

Each gap the 2026-10-04 checkbox audit named for T034, T035, T037, T039, T040 and T044
(`.specify/specs/033-trial-ledger-dsr-pbo-gate/artifacts/checkbox-audit-20261004.md`) now has the
test cited above.

## Suite and ledger (Linux, Python 3.12.3)
- `python -m pytest tests -q -p no:cacheprovider` on clean main `6348bc4`: 1835 passed, 0 failed, 0 xfailed, 0 errors, 1386 subtests passed, exit 0.
- The same command after this change: 1836 passed, 0 failed, 0 xfailed, 0 errors, 1386 subtests passed, exit 0.
- `docs/trials/trials.jsonl` (174 lines) `1bb5dbfe…5275f30f` and `trials.head.json` `f83b1b9b…7d22d764`
  are unchanged, before and after. `returns/` is absent.
- Camden's Windows venv remains the acceptance gate. CI on the exact head is separate evidence.
