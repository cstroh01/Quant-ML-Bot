# 052 F01: listing-gated activity, fail-closed eligibility, quote timestamps

Source: Codex cross-review 2026-10-08 (CROSS-REVIEW-MAIN.md, private folder), 052 P1 findings at
`scripts/asset_registry.py` L59 (any visible fact set `active=True` before a listing), L129
(executable eligibility failed open on NaN), L106 (`ExecutableQuote` had no timestamp/expiry).
Also closes the pending decision "membership should require a `listed` fact". Synthetic only.
EXAMPLE — NOT A RESULT.

## Red
New registry/membership tests against main 2c72c9a's `asset_registry.py`:
```
FAILED tests/test_052_registry.py::test_a_symbol_without_a_listing_is_known_but_not_active
FAILED tests/test_052_membership.py::test_membership_requires_a_visible_listing
2 failed, 11 passed in 0.11s
```
Fail-open on main 2c72c9a (direct calls, all should have refused):
```
main: spread_bps=NaN -> []
main: adv_shares=NaN -> []
main: min_notional_usd=NaN -> []
main: order_notional=NaN -> []
main: last Close=NaN -> []
```

## Fixes (`scripts/asset_registry.py`)
- Snapshot entries start inactive; a visible `listed` fact activates, a later `delisted` deactivates.
  `causal_membership` admits only `active is True`.
- `research_eligibility`: NaN last close → `price_below_floor`; any NaN dollar volume in the 20-row
  window → `illiquid` (pandas `median` used to skip NaN silently).
- `ExecutableQuote` gains required `quoted_at` (aware). `executable_eligibility` takes `now` and
  `max_quote_age_seconds`; a naive, future or older quote → `stale_quote`.
- Non-finite spread/ADV/broker minimum → `spread_unknown` / `adv_unknown` / `broker_minimum_unknown`;
  NaN, zero or negative order qty/notional → `order_invalid`.

Contract change: callers must pass `quoted_at`, `now`, `max_quote_age_seconds`. Only tests consume
these today (`grep`); existing tests updated accordingly.

- Follow-up from Codex's independent review (2026-10-08): `EligibilityLimits` validates itself at
  construction (`max_participation` finite in (0, 1]; floors and spread cap finite ≥ 0;
  `min_sessions` a positive int) — a NaN cap disabled `participation_too_high`. Research
  eligibility now checks every observation in the window: one infinite or negative volume left the
  median finite and the name eligible.

## Rule 12
`python tests/mutation/run_052_fail_closed_mutants.py` → 12/12 killed.
