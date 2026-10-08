# Feature Specification: PAPER/LIVE mode and bot-budget isolation

**Spec number**: 051
**Created**: 2026-10-07
**Status**: Adopted under `docs/SCOPE-V1.md` §10. Offline units authorized; `exec/` wiring is Rule 7 reviewed lane; LIVE activation locked behind §5.
**Depends on**: 034 (safety gate config), 049 (paper loop). Feeds 052, 054, 055, 057.

## 1. Objective
Grow Camden's selected capital through profitable trading, net of costs, inside explicit budget,
liquidity and loss limits. An objective, never acceptance evidence (§5 governs).

## 2. Requirements
- **FR-001 Profiles.** A mode profile is immutable and validated: `name`, `mode` (PAPER|LIVE),
  `broker` (alpaca_paper|fidelity), `account_fingerprint` (SHA-256 of the account id, never the id),
  `credential_refs` (environment variable NAMES only), `state_dir`, `log_namespace`, `bot_budget_usd`,
  `daily_deploy_fraction`, `instruments`, `fractional`, `safety_config_version`.
- **FR-002 Default PAPER.** With no profile selected, the loader returns the small PAPER profile.
  No URL, environment variable or flag alone can produce a LIVE profile.
- **FR-003 Isolation.** Two loaded profiles never share `state_dir`, `log_namespace`,
  `credential_refs` or `account_fingerprint`; a collision refuses to load.
- **FR-004 Budget, not equity.** Sizing equity = min(bot_budget_usd, bot-owned value + bot cash).
  Broker equity above the budget never increases order size.
- **FR-005 Daily deployment cap.** New buy notional per session ≤ `daily_deploy_fraction` ×
  bot_budget_usd. Sells are not capped.
- **FR-006 Ownership.** Only bot-owned lots may produce sell intents. External holdings count toward
  aggregate exposure and concentration but never generate a sell or rebalance.
- **FR-007 Fractional and minimums.** Fractional quantities only when profile and instrument allow;
  otherwise floor to whole shares. Orders below the broker minimum notional are dropped with a reason.
- **FR-008 Cash and settlement.** Buys use settled cash only (LIVE is a cash account: T+1).
  Unsettled proceeds are not spent.
- **FR-009 Arming.** LIVE requires an arming record: profile name, account fingerprint, capital-gate
  evidence digest, Camden's activation timestamp, expiry. Missing, expired or mismatched → refuse.
  An arming record is not evidence that §5 passed.
- **FR-010 Restart.** After restart, no new exposure until reservations and positions reconcile (049/055).

## 3. Decisions (recorded 2026-10-07)
- **D-1 (Camden)** PAPER at Alpaca paper (two accounts); LIVE at Fidelity individual brokerage (057).
- **D-2 (Camden)** `paper_large`: $100,000 virtual, `daily_deploy_fraction` 0.50 ("buy more per day").
  `paper_small`: $5,000, 0.20. `live_fidelity`: budget set at arming (a few hundred dollars), 0.20.
- **D-3 (Camden)** US-listed common stocks and ETFs; fractional where supported; no options, margin or shorts.
- **D-4 (Camden)** Safety limits: config `2026-09-29-v1` (max_position_pct 0.10, max_gross_pct 0.60) for all profiles.
- **D-5 (quant-ml-genius)** Profiles are JSON in the private companion repo; values never public.
  Credentials resolve only through `credential_refs` at call time (GitHub Secrets / env). Arming is a
  JSON record in the profile's `state_dir`. Benchmark: Alpaca/IBKR separate paper vs live keys and hosts.

## 4. Rule 12 mutants (each must be killed by the consuming path, with a clean control)
Endpoint-only LIVE switch; shared state_dir/log path; wrong account fingerprint; budget cap removed
(broker equity raised, orders must stay bounded); external shares treated as bot-owned; fractional
allowed when instrument is not fractionable; unsettled cash spent; arming across the wrong account;
expired arming accepted; daily cap ignored.

## 5. Acceptance
All mutants killed; full suite green; reviewed `exec/` wiring merged after Camden's line-by-line read;
supervised small-profile PAPER run. LIVE feature acceptance and LIVE activation are separate rows.
