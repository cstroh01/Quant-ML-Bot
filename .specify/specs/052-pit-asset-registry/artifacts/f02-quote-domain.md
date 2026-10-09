# 052 T008 / F02: executable quote input domains

Source: independent review of #98 at `0a6b61861d7b7d569eeaf5cc1182b90e73c11a0f`, tree `4b1d435c4f0ba35bb2856ac83434a30d3c3442eb`.
Verified 2026-10-09 in an immutable GitHub archive on Windows, Python 3.13.14 (local venv;
CI validation of the published head is separate). Synthetic inputs only. EXAMPLE - NOT A RESULT.

## Defect and boundary
A quote 61 seconds old yields `stale_quote` at an unchanged 60-second limit but passes with an
infinite limit. Negative spread and broker minimum also pass. Refuse invalid quote-age config
before the comparison; return `spread_invalid` / `broker_minimum_invalid` for negative values.
Valid fresh, finite-stale and zero-domain controls retain their original behavior.

## Test-first verification
- Original #98 plus new contracts: 11 failed, 3 passed; infinite age DID NOT RAISE ValueError,
  spread/minimum admission failed the explicit named assertions. Nonnumeric/missing age also
  exposed old comparison TypeErrors; those are recorded separately, not counted as mutant kills.
- Implemented source: 69 focused 052 contracts passed, no failures/errors.
- New mutation driver: 3/3 intended contract kills, unmutated control green, original bytes restored.
  Age: `test_invalid_age_configuration_refused[infinite]` DID NOT RAISE.
  Spread/minimum: `test_negative_quote_domain_refused_with_valid_sibling`, named domain assertion.
- Full command: `python -B -m pytest tests -q -p no:cacheprovider` with isolated basetemp/JUnit output.
  1484 passed, 2 existing dependency deprecation warnings, 1386 subtests passed; exit 0; 479.11s.
- Copied and production ledger manifests equal before/after; all unplanned base source blobs equal.
  Environment scrubbed, GITHUB_SHA absent, SPEC043_REAL_ROOT bound to protected production root.

## Tested source hashes (SHA-256)
- `scripts/asset_registry.py`: `ecbe07644c81b2df343da7cfdb246120ae81a328c5be19948fdafd2ac708945d`
- `tests/test_052_quote_domain.py`: `946a2ec7a0e848974515a5f53bf57b836eca8cb7bafbe745cd65b6fb607637e9`
- `tests/mutation/run_052_quote_domain_mutants.py`: `4b81bc8857e5c186feb914bcf806ba909273a5428e1127638a478a3a53191d8e`

Unit is bounded below 300 added+removed lines including contracts, driver, plan/tasks and this
evidence. A draft/CI result does not establish broker execution, populated data or capital readiness.
