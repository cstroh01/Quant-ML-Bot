# Plan: 056
Module `scripts/data_sources.py` (manifest schema, cross-source checks, EDGAR as-of filter; fetchers
take injected HTTP clients so tests stay offline).
- **U0** adopt the Codex verification report into `research.md` (docs).
- **U1** manifest schema + validation (FR-003/006).
- **U2** cross-source close/action checks (FR-004).
- **U3** EDGAR facts as-of filter (FR-005).
- **U4** fetcher adapters per adopted source with injected clients; human-authorized first runs.

- **F02 / T007** documentation repair: spec.md + acceptance-matrix.md + tasks.md; inline only the previously adopted M01–M10, with no runtime or provider change.

- T011: separate `DiagnosticAlpacaDailyBars` failure sanitizer; tests use injected HTTP failures and
  fake-only sentinels. Status-dropping and raw-message mutants need named failures
  and a green control. Preserve success digests and all deployment/first-fetch gates.

Historical `scripts/data_sources.py` and spec061 declaration bytes stay exact.
049 T014 wires the new adapter into PAPER; the discarded shared-file attempt
failed two source-binding contracts and was not delivered.

The PAPER adapter refuses redirects through its configured opener before any
header can be forwarded. A synthetic HTTPS redirect test and guard-removal mutant
exercise that actual opener without DNS or sockets; no raw error output is kept.
