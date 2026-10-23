# Spec 064 Amendment 002 — LIVE daily deploy fraction 1.0 and profile-only replacement

**Status:** Decided by Camden in chat, 2026-10-23 America/New_York ("1.0").
**Verified against:** `main` at `c2dd0ce0d94e44d2ab93e42e00b0ae52a3c77113`.

## 1. Decision

The `live_fidelity` profile's `daily_deploy_fraction` changes from 0.2 to 1.0.
This supersedes 057 D-3's "0.20 daily deploy fraction"; the $200 pilot budget,
SafetyConfig values, monthly cadence, buffer and every halt are unchanged.

Why: at $200 and 0.2 the bot may buy $40 per session, so the 93% target book
takes about five sessions to fund and runs partial meanwhile.
`v12-build-20261017/fidelity-sizing-findings.md` (private notes) found 1.0 is the
only setting that funds all eight sleeves on day one (about $23.25 per ETF).
`mode_config.bound_buys` still caps new buy notional per session at
`fraction × budget − deployed_today`, so 1.0 means at most $200 per session,
which the budget cap already implies.

## 2. FR-001a — profile-only replacement (amends FR-001)

FR-001 refuses when any of the six names already exists, so the provisioned
0.2 profile cannot be replaced with the existing helper. Add one explicit mode:

`--apply --replace-profile --template T --expected-safety-config-version V`

- Same template validation as FR-001, now requiring `daily_deploy_fraction` 1.0.
- Same five hidden, twice-entered, validated values; they are used only to
  rebuild the keyed HMAC fingerprint and are never written.
- Names-only listing must show **all six** names already present; otherwise
  refuse `secret_missing` with no write.
- Exactly one write: `gh secret set QMB_FIDELITY_PROFILES_JSON --repo
  cstroh01/Quant-ML-Bot-private`, value on stdin only. No retry.
- `--replace-profile` without `--apply` refuses before any prompt or call.

Everything else in FR-001 (no echo, no argv/env/file values, sanitized
categories, no rollback claim) applies unchanged.

## 3. Operator step (Camden, before arming)

After this merges and both pins move to the merged main, run locally:

```
python scripts/fidelity_provision.py --apply --replace-profile --template <reviewed template with daily_deploy_fraction 1.0> --expected-safety-config-version 2026-10-14-alloc-v1
```

Expect `COMPLETED: QMB_FIDELITY_PROFILES_JSON`. Until then the private
secret still holds 0.2, and the preview host is unaffected either way.
