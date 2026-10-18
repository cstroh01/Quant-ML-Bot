# 056 supplemental EODHD action adapter — 2026-10-17

Implements the already-adopted last-year corporate-action role (056 §3),
FR-003 manifests and FR-004 cross-source checks. Offline implementation;
T006's account/first-fetch evidence remains unverified. No new dependency.

Official pages opened today, documentation only:
[actions](https://eodhd.com/financial-apis/api-splits-dividends) and
[pricing](https://eodhd.com/pricing). The free plan advertises 20 calls/day,
20 requests/minute and one year of history including actions. JSON exposes
nominal `unadjustedValue`; `value` uses today's split-adjusted share basis.
Split strings are new shares / old shares. Payment dates may be null.
Documentation does not verify a particular account or historical completeness.

`EodhdActions.fetch("<symbol>.US", start, end)` makes exactly two requests,
with no retry, upgrade or demo fallback. It refuses older windows and malformed,
duplicate or out-of-window responses. The environment-only key is sent through
the provider's required URL token parameter; redirects are disabled, exceptions
are redacted, and manifests contain the credential-free endpoint and exact
response digest. Never enable HTTP URL debug logging around credential requests.
There is no dotenv/file credential fallback.

Every instance shares the default request rate and rolling-24-hour budget.
Failed/partial runs conservatively spend both reserved calls. This is an
in-process bound; other programs/hosts and pre-existing account usage remain
the operator's responsibility, and the API may refuse earlier. It is not a
quota receipt or permission to run this adapter automatically.

The returned `ActionBundle.reconcile(primary)` invokes spec 035's actual
reconciler at its existing amount tolerance, verifies the primary instrument,
and preserves mismatch/unreconciled statuses. Only known nominal USD amounts
claim the dollar-per-share basis. Missing nominal cash is not replaced with
adjusted cash. No payment date is synthesized. Outside the requested one-year
window remains unreconciled, rather than receiving an implied pass.

Synthetic checks cover nominal vs adjusted cash, forward splits, unknown basis,
partial coverage, disagreement, free-window edges, quota exhaustion/reset,
failed-call accounting, credential/transport redaction and malformed responses.
Planted defects change nominal cash, invert splits, bypass history/quota and
mislabel foreign currency; every oracle has a clean control. Integrated suite
and ledger hashes are recorded in the PR description. No real data was fetched,
no production ledger changed, and this does not make EODHD a model feature.
