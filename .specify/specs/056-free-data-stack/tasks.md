# Tasks: 056
- [x] T001 U0 `research.md` from the verified Codex report; final role map.
- [x] T002 U1 contracts red + manifest schema/validation. Mutants: missing fetched_at, credential in manifest.
- [x] T003 U2 contracts red + cross-source checks. Mutant: mismatch averaged.
- [x] T004 U3 contracts red + EDGAR as-of filter. Mutant: fact used before filed date.
- [x] T005 U4 adapters with injected clients, offline fixtures.
- [ ] T006 **Human (Camden)**: free keys as secrets; authorized first fetch per source; manifests hashed.

## F02 — repository-readable acceptance (amendment 2026-10-09)
- [x] T007 Docs only: inline the already-adopted M01–M10 detail, replace the private pointer, and verify IDs/control/refusal wording. This closes the documentation dependency only; runtime gates and T006 remain separately unverified.

## Supplemental EODHD role — 2026-10-17 completion request
- [x] T008 Extend U4 with the adopted last-year EODHD action role: nominal cash,
  environment-only credentials, bounded free requests, manifests and the real
  spec-035 reconciler. Offline fixtures/mutants and integrated suite required.
  This does not complete T006's real-account entitlement and first-fetch gate.

## Local reconciliation follow-up
- [ ] T009 Fail closed when callers pass splits or unknown action types to the dividend-only EODHD reconciler. Preserve spec 035/044 split ownership; add a semantic regression and document the separate split gate. Add explicit credential-name configuration for the existing local name without reading secrets.

- [ ] T010 Review safety proofs: exercise the configured redirect opener with
  synthetic responses and prove both socket guards go red when removed. No real sockets.

## Completion diagnostic extension — Camden, 2026-10-20
- [x] T011 Preserve a controlled transport exception category and validated numeric
  HTTP status in SourceFetchError without messages, URLs, headers, bodies or credentials.
  Use injected fake failures, sentinel redaction, status-dropping/leaking mutants
  and clean controls. No retries, broker calls, new dependency, deployment or arming.
  This closes diagnostic software only, not T006 or the failed preview's root cause.

The PAPER adapter refuses redirects through its configured opener before any
header can be forwarded. A synthetic HTTPS redirect test and guard-removal mutant
exercise that actual opener without DNS or sockets; no raw error output is kept.
