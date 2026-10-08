# Plan: 056
Module `scripts/data_sources.py` (manifest schema, cross-source checks, EDGAR as-of filter; fetchers
take injected HTTP clients so tests stay offline).
- **U0** adopt the Codex verification report into `research.md` (docs).
- **U1** manifest schema + validation (FR-003/006).
- **U2** cross-source close/action checks (FR-004).
- **U3** EDGAR facts as-of filter (FR-005).
- **U4** fetcher adapters per adopted source with injected clients; human-authorized first runs.
