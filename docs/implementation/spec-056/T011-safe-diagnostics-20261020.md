# 056 T011: safe transport diagnostics

Source: completion instruction, October 20, 2026. Offline follow-up to the
failed hosted large-profile preview; this does not recover its lost HTTP status.

The separate PAPER transport wrapper exposes a fixed category and integer HTTP status,
or explicit unknown. It never renders backend messages/class names, URLs,
headers or bodies. Existing non-transport SourceFetchError callers remain valid.
Responses, digests, manifests, retry behavior and execution limits are unchanged.

The delivered separate-adapter contracts have a tests-first red receipt, a clean
control and three named copied-tree mutations (status dropped, raw payload leak,
PAPER wiring removed). The focused suite includes historical source-binding and
PAPER URL/profile/refusal controls. Exact counts and XML are in the private
separate-adapter receipts; the discarded shared-file receipts are historical.

The production sequence stays stopped. No broker call, deployment repin, new
dependency, credential read, order, schedule or production ledger/cache write.
Full-suite delivery evidence is retained separately for its exact source.

Historical `scripts/data_sources.py` and spec061 declaration bytes stay exact.
049 T014 wires the new adapter into PAPER; the discarded shared-file attempt
failed two source-binding contracts and was not delivered.

The PAPER adapter refuses redirects through its configured opener before any
header can be forwarded. A synthetic HTTPS redirect test and guard-removal mutant
exercise that actual opener without DNS or sockets; no raw error output is kept.
