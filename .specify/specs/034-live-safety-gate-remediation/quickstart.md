# Validation Quickstart: Live-Safety-Gate Remediation

From the repository root with `requirements.txt` and `requirements-dev.txt`
installed:

1. Run the focused safety engine tests:

   `python -m pytest tests/test_live_safety_gate.py -q`

2. Run the chokepoint/static-guard tests:

   `python -m pytest tests/test_order_gateway.py -q`

3. Run the five endpoint contract tests:

   `python -m pytest tests/test_safety_router.py -q`

4. Run the canonical suite:

   `python -m pytest tests`

Expected invariants:

- No submission callback runs after a non-`ALLOW` gate result.
- A rolling halt can clear while kill remains latched; kill clears second.
- A pending sell never creates capacity for a new buy.
- Zero and negative equity return `NON_POSITIVE_EQUITY`, never an exception.
- All five `/api/safety` endpoints delegate to the injected gate.
- `reports/api/routes/capital_gate.py` retains SHA-256
  `9ca1f16f8de9c85f4acdf3f41c5a848b63ad6abb1e47baa21083139c485855c3`.

Compare the full-suite outcome to the recorded Phase 7 baseline:
`817 passed / 18 failed / 9 errors`. Any additional failing/error node ID is a
spec-034 regression even if the repository remains historically red.
