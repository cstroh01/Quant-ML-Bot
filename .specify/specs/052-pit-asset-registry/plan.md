# Plan: 052
Module `scripts/asset_registry.py` (pure). Tests `tests/test_052_*.py`. Synthetic fixtures only.
- **U1** identity/history model + `snapshot(as_of)` (FR-001/002/006).
- **U2** research eligibility with reasons (FR-003/007).
- **U3** executable eligibility from an injected snapshot (FR-004), consuming 051 limits.
- **U4** causal membership helper for CV (FR-005) — after 044/035 acceptance for real data.

- **F02 / T008**: validate quote-age configuration before freshness comparison, reject negative spread/minimum with named reasons; preserve zero boundaries, valid sibling and stale control. Synthetic offline unit, <=300 changed lines including tests/evidence; no broker/config-risk changes.
