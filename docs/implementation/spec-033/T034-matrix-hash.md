# Spec 033 T034 — committed literal matrix hash (partial-task closure evidence)

EXAMPLE — NOT A RESULT. Synthetic dyadic fixture only; no market data, no ledger write.
Base: main `a2f6fa3`. Closes the gap the 2026-10-04 checkbox audit named for T034
(`artifacts/checkbox-audit-20261004.md`, T034 row): "no test asserts a literal hash value".
It does not tick T034 or T046, and it does not touch T035/T037/T039/T040 or Phases 8–9.

## What the test pins
`tests/test_033_dsr.py::test_t034_committed_literal_matrix_hash_and_canonical_body`
- **Declared bytes.** Each return sidecar's canonical bytes, and the whole matrix body's bytes, are
  written out literally. The expected SHA-256 values were computed from those bytes with `hashlib`
  alone. `trial_registry.digest` and `build_matrix` were never used to derive an expected value.
  The test re-checks each literal against its declared bytes ("T034 DECLARED").
- **Input.** Trials are passed unsorted (b, c, a). Trial b has one extra date, which the exact
  intersection drops. Trial c is a `buy_and_hold_baseline`, excluded as `not_candidate`.
- **Named assertions, in order:** KEYS, COLUMNS, DATES, VALUES, EXCLUDED, DIGESTS, BODY
  (family/convention/reason), CANONICAL (production canonical bytes == declared bytes; this covers
  the UTF-8 em dash and the null reason), HASH (`matrix_hash` == the literal).
- **First run:** green against the existing T042 implementation. Production agrees with the
  contract, so nothing in `scripts/` changed. The failing proof is the mutants below.

## Rule 12 — `python tests/mutation/run_033_t034_mutants.py`
Each mutant is one site in an isolated copy (spec 043 D-4 `driver_support`). A kill requires a JUnit
**failure**, not an error, in the T034 test, with an assertion message carrying the named witness.

| Mutant | File | Witness | Pre-T034 tests (21) |
|---|---|---|---|
| values misaligned with columns | selection_bias | T034 VALUES | survives |
| dates in reverse order | selection_bias | T034 DATES | 2 fail |
| columns reversed | selection_bias | T034 COLUMNS | 2 fail |
| digest of rows, not sidecar bytes | selection_bias | T034 DIGESTS | survives |
| hash omits a body field | selection_bias | T034 HASH | survives |
| ASCII-escaped canonical bytes | trial_registry | T034 CANONICAL | survives |

- Result: 6/6 killed.
- Control: the unchanged copied modules are green, with exactly 1 test collected.
- Every mutated file compiles.
- Production sources and all 5 `docs/trials/` files are byte-identical after the run, and the real-ledger tripwire stayed silent.
- Negative control: the same mutants run against `test_033_dsr.py -k "not t034"`, with fixtures copied. 4 of 6 survive.

## Suite and ledger (Linux, Python 3.13.16)
- `python -B -m pytest tests -q -p no:cacheprovider`: 1469 passed, 1386 subtests passed, 1 warning, exit 0.
- `docs/trials/trials.jsonl` `1bb5dbfe…5275f30f` and `trials.head.json` `f83b1b9b…7d22d764` are unchanged, before and after. `returns/` is absent.
- Camden's Windows venv remains the acceptance gate. CI on the exact head is separate evidence.
