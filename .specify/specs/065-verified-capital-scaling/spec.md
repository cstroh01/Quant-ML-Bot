# 065 — Verified capital scaling: successor LIVE mandate (PROPOSAL)

Date: 2026-10-22 America/New_York. Status: **DRAFT PROPOSAL — adopts nothing.**
Nothing in this packet changes `MAX_LIVE_BUDGET_USD`, a profile, a `SafetyConfig`,
`exec/`, a workflow, `docs/SCOPE-V1.md` or arming. The $200 pilot stays in force
until every adoption condition in §6 holds. LIVE remains NOT ARMABLE.

Baseline: `main` at `bbd4e26` (merge of #284). Every `file:line` below is
against that commit.

## 1. Authority and requirement

Camden, chat, 2026-10-21: "I have 200 in now, but I plan to add more in the
future. It could be anywhere from 200-5000 and the model needs to adapt to
handle anywhere in there".

Camden's standing requirements, carried from 064 and earlier sessions:

- No arbitrary permanent dollar ceiling.
- A future reviewed, account-scoped policy may manage verified funds in the
  dedicated Fidelity account under percentage limits.
- A newly settled deposit becomes eligible at the next daily run without forcing
  a trade.
- The existing $200 pilot cap stays until a reviewed successor mandate is
  adopted.

064 left this open on purpose: "Any successor account-scoped mandate remains a
separate reviewed decision" (`.specify/specs/064-final-v1-completion/spec.md:21`);
its final contract records "No successor account-scoped mandate adopted;
deposits cannot raise authority" (`docs/implementation/spec-064/final-v1-contract.md:19`).
This spec is that successor mandate, as a proposal.

Out of scope: any new strategy, universe, sleeve, weight rule, ML model, cadence
or execution venue. The traded object stays spec 061's buffered monthly
equal-weight allocation over `ALLOCATION_SLEEVES` (`scripts/signals.py:402-403`:
SPY, EFA, EEM, IEF, TLT, TIP, GLD, DBC) with its 7% pre-cost reserve
(`scripts/buffered_allocation.py:9`), labelled
`ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED` on every surface (constitution
Rule 15 carve-out).

## 2. Current mechanics (what exists on `main`)

| Concern | Where | Behaviour today |
|---|---|---|
| Dollar cap | `scripts/mode_config.py:20-21` | `MAX_LIVE_BUDGET_USD = 200.0` |
| Profile fields | `scripts/mode_config.py:49-52`, validated `:65-68` | `bot_budget_usd` positive finite; `daily_deploy_fraction` in (0, 1]; `fractional` bool |
| Sizing equity | `scripts/mode_config.py:200-205` | `min(bot_budget_usd, bot_owned_value + bot_cash)` |
| Quantity floor | `scripts/mode_config.py:208-211` | floor to 6 dp if fractional, else whole shares |
| Buy bounding | `scripts/mode_config.py:214-258` | daily cap `daily_deploy_fraction × bot_budget_usd` (`:232`); buys shrunk **in list order** until cap or settled cash runs out (`:236-257`) |
| Sell ownership | `scripts/mode_config.py:279-298` | only `owner == "bot"` lots are ever sold |
| LIVE cap check | `exec/live_loop.py:31-35` | `LIVE_CAP = MAX_LIVE_BUDGET_USD`; profile budget above it halts |
| Order precision | `exec/live_loop.py:37-44`, `:140-147` | 0.001-share step when fractional, else 1; floors toward zero |
| Grant / equity | `exec/live_loop.py:115`, `:128` | `grant = min(budget, settled cash, LIVE_CAP)`; `equity = min(budget, LIVE_CAP, cash + bot positions at last close)` |
| Minimum notional | `exec/live_loop.py:138`, `:144` | $1.00 at the worst-case price; smaller orders refused `below_minimum` |
| Worst-case price | `exec/paper_loop.py:77`, used `exec/live_loop.py:132` | last close × 1.05 (`GAP_ALLOWANCE`) |
| Safety snapshot | `exec/live_loop.py:167` | `BrokerSnapshot(..., market_value + cash, 0.0, ...)`: `external_cash_flow` is hard-coded **0.0** |
| Loss/drawdown breaker | `scripts/live_safety_gate.py:768-802` | adjusted equity = previous + (raw change − `external_cash_flow`) (`:785`); daily breach at `-daily_loss_pct` (`:797-798`), rolling at `-rolling_drawdown_pct` (`:801-802`) |
| Allocation limits | `exec/paper_loop.py:99-108` | `ALLOCATION_SAFETY_CONFIG` version `2026-10-14-alloc-v1`: position 0.40, gross 1.00, daily loss 0.03, drawdown 0.15 over 63 sessions; shared with PAPER (`exec/paper_loop.py:618`) |
| Config identity | `scripts/live_safety_gate.py:231-246`, `:477` | a changed version or values under a stored version raise `ConfigMismatchError` |
| Monthly cadence | `scripts/paper_targets.py:239-254` | a decision is held once executed; an unfinished one keeps moving toward the same target; no-trade band `ALLOCATION_MIN_TRADE = 0.005` of equity (`:213`) |
| Settled cash source | `exec/fidelity_live.py:294-295`, `exec/fidelity_session.py:90-91` | configured-account settled cash only, never buying power; zero refuses the run |
| Provisioning pins | `scripts/fidelity_provision.py:34-35`, `:90`, `:92` | template must say `bot_budget_usd == 200.0` and `daily_deploy_fraction == 0.2` |
| Re-provision refusal | `scripts/fidelity_provision.py:182-193` | refuses if **any** of the six secret names already exists (`:191-192`) |
| Transfer journal | `scripts/cash_flow_journal.py:1-8`, `:129-170` | pure, settlement-aware, once-only; quarantine latches the whole batch; grants no authority |
| Scope gate | `docs/SCOPE-V1.md:290-291` (§11.3 item 7) | "LIVE budget $200 of settled cash (Camden, 2026-10-17); deposits never raise it." |

Two defects in today's path matter for this spec, and both are already 064 T003's
job (`.specify/specs/064-final-v1-completion/spec.md:92-105`):

- **A withdrawal reads as a loss.** With `external_cash_flow = 0.0`
  (`exec/live_loop.py:167`), withdrawing $10 from a $200 account moves adjusted
  equity by −5% (`scripts/live_safety_gate.py:785`), past the 3% daily-loss limit
  (`exec/paper_loop.py:103`), and halts trading. A deposit reads as a gain and
  raises the high-water mark, so a later real loss is measured from an inflated
  peak. (Arithmetic on configuration — EXAMPLE — NOT A RESULT.)
- **Cash is not net of commitments.** `equity` and `grant` (`exec/live_loop.py:115`,
  `:128`) use settled cash without subtracting open, unfilled buy notional.

## 3. Requirements

### FR-001 — Verified authority

The bot's spendable authority is derived only from **verified, attributable
funds in the dedicated account**. Definitions, all in USD, computed once per run
after reconciliation (`exec/live_loop.py:96-110`) and before any sizing:

- `C` — settled cash from the configured account (`exec/fidelity_live.py:294-295`),
  never buying power or margin.
- `K` — open commitments: worst-case notional of every bot buy not yet terminal
  in the bot book, plus any active gate reservation valued at the same
  worst-case price (last close × 1.05; gate reservations are share quantities,
  `pending_orders.quantity`), plus every **pending outbound** transfer from the
  FR-005 accessor. The gate applies only *settled* flows (064 T003a), so a
  pending outflow counted here is never also counted by the breaker; when it
  settles it leaves `K` and reaches the breaker once. A bot buy that has
  **filled but not settled** stays in `K` at its fill notional until its
  settlement date (FR-002 convention), so its cash is never counted twice.
- `U` — unmanaged cash: the running total of unexplained cash increases from
  FR-002, clamped to `0 ≤ U ≤ C`. It sits in the account, is reported every run
  as `unmanaged_cash_usd`, and is never traded.
- `R` — receivables: proceeds of bot sells that have filled but not settled,
  at fill notional from the bot book. They leave `R` on their settlement date,
  when they arrive in `C`. `R` counts toward `V` but is never spendable.
- `B` — bot-owned position value: Σ bot-owned quantity × last completed close.
  External holdings (`owner == "external"`, `scripts/mode_config.py:263-276`)
  are excluded from `B` and from authority. They still count in the gate's
  aggregate exposure, as today.
- `V = C − U − K + R + B` — verified equity, valid only when (a) reconciliation
  is clean, (b) the 064 journal is not blocked and (c) persisted `U` state is
  present (FR-002a). Unexplained cash is excluded through `U`; it never
  invalidates `V` or freezes authority (FR-002).
- `A = min(H, f × V)` — authority, where `f` is the managed fraction and `H` the
  hard ceiling (FR-003).

`A` replaces `bot_budget_usd`/`LIVE_CAP` as the sizing equity in
`exec/live_loop.py:128` and as the base of the daily cap
(`scripts/mode_config.py:232`). It does **not** replace the cash bound: new buys
stay inside managed settled cash through
`grant = max(0, min(C − U − K, A − B − R))`, passed as `settled_cash` to
`bound_buys` where `grant` is passed today (`exec/live_loop.py:115`, `:138`).
So unsettled sale proceeds and `U` are never spent, even while `A` includes `R`. It is never computed from raw account equity, a
raw cash jump, buying power, or a balance difference.

This satisfies SCOPE §10's "never sizes from total account equity"
(`docs/SCOPE-V1.md:202-203`): `V` is built bottom-up from attributed parts, not
read from the account total, and it excludes external holdings.

### FR-002 — Cash bridge and unmanaged cash

Each run explains the change in `C` since the last acknowledged snapshot:

`ΔC = attributable settled net flow (064 journal) + settling bot fill cash (sells − buys whose settlement date is in this interval, from the bot book) + evidenced income on bot-owned lots − evidenced fees + residual`

**One convention: settlement date.** The bot book records each fill's trade
date and its settlement date (next NYSE session, T+1, from `scripts/data.py`
`trading_days`). A fill's cash enters the bridge only on its settlement date;
until then a buy stays in `K` and a sell sits in `R` (FR-001). `C` is settled
cash, so both sides use the same date. Whether Fidelity's `settled_amt` moves on
the settlement date is UNVERIFIED in this repo. Adoption condition 3 (§6) needs
it evidenced by the $200 pilot's own first rebalance: a zero bridge residual on
both the fill run and the settlement run. If `settled_amt` moves on trade date
instead, authority stays at $200 and this convention is amended before adoption.
Scenario S11 pins the convention.

- An **unexplained increase** (residual > $0.01) is added to `U`, so it is
  excluded from `V`: unexplained money **never raises authority** and is never
  traded. It does **not** freeze `A` or refuse buys, because the account's
  existing verified funds are unaffected. Each run reports
  `unmanaged_cash_usd` and an incident the first time `U` grows. Moving money
  out of `U` into `V` needs evidence; the review path is the 064 journal's
  (`scripts/cash_flow_journal.py:4-5`).
  The same increase is passed to the breaker as an external flow in the run
  where raw equity moved, so it is neither a gain nor, if attributed later, a
  loss.
- **Late attribution.** A settled journal flow that arrives after its cash
  already went to `U` moves that amount from `U` to `V` with no incident, and
  its breaker flow is 0 in that run, because the breaker already excluded it.
  Only an amount up to the current `U` is matched; any excess is an ordinary
  attributed flow. Scenario S13.
- An **unexplained decrease** first reduces `U`, then `V` (conservative: it
  shrinks authority immediately). It is reported as an incident. It is not fed
  to the breaker as a flow, so a real loss is never masked as a withdrawal.
- **Income** (dividends, interest) counts as attributed only with broker
  activity evidence of the same quality the journal demands for transfers.
  Without that evidence it lands in `U`. Several sleeves distribute monthly
  (IEF, TLT, TIP) or quarterly, so in practice un-evidenced distributions
  accumulate in `U` as a small, disclosed cash drag instead of halting the bot.
  This is why the design is not a freeze: a freeze would demand manual review
  roughly monthly, against Camden's requirement (2026-10-22): "I need things to
  run entirely autonomously". Spec 064 already forbids deriving flows from
  dividends (`.specify/specs/064-final-v1-completion/spec.md:85-86`); this
  keeps income out of the transfer journal and in the bridge. D-7 offers an
  optional bounded income allowance.

Malformed or conflicting **transfer evidence** still quarantines exactly as
064 T002/T003a define (add-exposure denied, reductions allowed); that latch is
about bad evidence, not about unexplained cash, and this spec adds no
auto-unblock to it.

**Reading of 064.** 064 says "Unknown movements remain quarantined and
ineligible for new exposure" (`.specify/specs/064-final-v1-completion/spec.md:86-87`).
This spec reads `U` as that ineligibility: unknown cash is never traded and
never counts toward `A`. It adds no new 064 quarantine and does not latch the
journal for unexplained cash.

### FR-002a — `U` persistence, seeding and loss

- **Persistence.** `U`, the bridge's last `C` and its `as_of` are written in the
  same `BEGIN IMMEDIATE` transaction as the 064 T003a flow observation
  (`SafetyGate.observe_equity_with_flows`), as new `kv_state` keys. A crash
  either keeps both the boundary and `U` or neither. This needs a protected gate
  unit (task T006b), not a second store.
- **Seeding.** On the first successor run only, seed
  `U₀ = clamp(C − K − M₀, 0, C)`, where `M₀` is the managed cash the pilot's own
  records explain: the $200 grant, plus settled bot sell proceeds, minus settled
  bot buy cost since arming (bot book), plus journal-attributed settled net flow
  since arming. The seed and its inputs are recorded in that run's evidence.
- **Missing or corrupt state.** If any prior successor observation exists and
  the `U` keys are missing or invalid, the run refuses new buys (reductions
  allowed), raises an incident and never re-seeds. Re-seeding is a separately
  named Camden operator action. Scenario S12.

### FR-003 — Mandate shape: percentages plus one separate hard ceiling

The mandate is a small, immutable record held in the LIVE profile:

| Field | Meaning | Proposed value (Camden decides, D-1..D-3) |
|---|---|---|
| `managed_fraction` (`f`) | Share of verified equity the bot may manage | 1.00 (the account is dedicated) |
| `hard_ceiling_usd` (`H`) | Absolute authority ceiling, a safety rail | 5000.0 |
| `daily_deploy_fraction` | Daily new-buy cap as a share of `A` | 0.20 (unchanged) |
| `min_operating_authority_usd` | Below this, no new buys (hold and report) | 100.0 |
| `SafetyConfig` percentages | Position, gross, daily loss, drawdown | Unchanged: 0.40 / 1.00 / 0.03 / 0.15 / 63 (`exec/paper_loop.py:99-108`) |

Values in this table are proposed configuration, not results.

**Why a hard ceiling is still prudent though Camden rejects an arbitrary
one.** `H` is not a statement of how much the strategy deserves. It bounds the
damage from the failures that a percentage cannot bound, because each of them
corrupts the base the percentage is applied to:

1. **Attribution or feed defect.** A mis-parsed balance (a decimal shift, a
   wrong account row, a misclassified transfer) inflates `V`. `f × V` inflates
   with it; `H` does not.
2. **Unofficial integration.** Fidelity access is unofficial and Camden has
   accepted ToS risk (`docs/SCOPE-V1.md:205-210`). Order and balance behaviour
   above the pilot size is unobserved.
3. **Tested range.** Acceptance (FR-009) proves behaviour at $200, $1000 and
   $5000. `H` equals the top of the tested range, so it is not arbitrary: it is
   the largest size with evidence. Raising it is the same reviewed change with
   tests at the new endpoint, not a standing limit on Camden's capital.

Funds above `H` stay in the account as unmanaged cash, reported each run as
`above_ceiling_usd`. They are never traded and never cause a sell.

### FR-004 — Behaviour from $200 to $5000

All figures in this section are arithmetic on the proposed configuration —
EXAMPLE — NOT A RESULT. `P` is a sleeve's worst-case price (close × 1.05).

| Authority `A` | Per-sleeve target (`A × 0.93 / 8`) | Daily cap (`0.2 × A`) | No-trade band (`0.005 × A`) | Max rounding shortfall per sleeve, as share of target |
|---|---|---|---|---|
| $200 | $23.25 | $40 | $1.00 | `0.001 × P / 23.25` |
| $1000 | $116.25 | $200 | $5.00 | `0.001 × P / 116.25` |
| $5000 | $581.25 | $1000 | $25.00 | `0.001 × P / 581.25` |

1. **Fractional sizing keeps all eight sleeves held.** With a 0.001-share step
   (`exec/live_loop.py:37-44`), every sleeve is buyable at $200 provided Fidelity
   allows fractional orders on it. Without fractions a sleeve priced above
   $23.25 cannot be held at $200 at all, and the allocation silently becomes a
   different portfolio. Fractional eligibility is UNVERIFIED for all eight
   sleeves (`docs/STATE.md:24`). Adoption precondition: each sleeve's
   fractional eligibility is evidenced in a read-only 057 preview session, or
   the run halts rather than trading a partial sleeve set.
2. **Rounding.** Floor-to-step loses at most `0.001 × P` per sleeve. That share
   of the target shrinks five times from $200 to $1000 and 25 times from $200 to
   $5000. The 6-dp floor in `_floor_qty` (`scripts/mode_config.py:208-211`) and
   the 3-dp floor in `live_loop` (`exec/live_loop.py:140-142`) must stay
   consistent: the 3-dp step governs.
3. **Minimum notional and band.** At $200 the no-trade band equals the $1
   minimum notional, so both bind together; any rebalance leg under $1 is
   skipped. From $1000 up the band ($5, $25) dominates and the $1 minimum is
   inert. `min_operating_authority_usd` stops a withdrawal-shrunk account from
   trading where most legs fall under $1.
4. **Costs.** Spread cost (spec 046 EDGE half-spread) scales with notional, so
   its share of the trade is roughly size-independent across this range.
   Square-root impact against these sleeves' volume is negligible at $5000.
   Rounding and the $1 floor are the size-dependent effects, and they are worst
   at $200. Commission at Fidelity for these ETFs is UNVERIFIED in this repo and
   is recorded as a per-order parameter, never assumed zero (Rule 3).
5. **Staged deployment is pro-rata.** Today `bound_buys` fills buys in list order
   (`scripts/mode_config.py:236-257`), so on a capped day the first sleeves get
   everything and the last get nothing. The successor scales every buy in a run
   by the same factor `s = min(1, cap_left / Σ buy notional)` before flooring,
   so a partly deployed book keeps the allocation's proportions. Sessions to
   finish a first deployment, `ceil(0.93 / 0.20) = 5`, are the same at every
   size, because the cap scales with `A`.
6. **A deposit never forces an off-cycle rebalance.** A settled deposit raises
   `A` at the next daily run (064 FR-002 eligibility). Then:
   - If the current monthly decision is not yet fully executed, the planner keeps
     moving toward that same target with the larger `A`
     (`scripts/paper_targets.py:242-244`). That is continuation, not a new trade.
   - If the decision is already executed, nothing trades until the next monthly
     decision (`scripts/paper_targets.py:242`). The deposit waits as cash for at
     most one month, then deploys over about 5 sessions under the daily cap.
   - Why no off-cycle deploy: spec 061's costed trial models monthly decisions
     with no flows. Buying on deposit dates would trade a schedule the trial
     never costed. The cash drag is disclosed instead. D-4 records Camden's
     choice; a buy-only top-up toward the current month's targets is the only
     alternative this spec would accept, and only with its own disclosure.
7. **Withdrawals reduce authority and never look like losses.**
   - An attributable outbound transfer counts against `A` from the run it is
     first **observed**, pending or settled (inflows count only when settled).
     This asymmetry is deliberately conservative.
   - Its settled amount reaches `BrokerSnapshot.external_cash_flow` as a negative
     flow (064 T003), so the breaker's adjusted equity
     (`scripts/live_safety_gate.py:785`) does not move.
   - A withdrawal never triggers a sell. If it pushes bot positions above the new
     target, the excess is sold at the next monthly decision through
     `bot_sell_quantities` (`scripts/mode_config.py:279-298`).
   - Withdrawing more than the account's unallocated settled cash is not
     supported in v1. To shrink the managed book, Camden lowers `f` through the
     reviewed path, and the next monthly decision sells down.

### FR-005 — Pending outflows from the journal

The 064 journal persists pending transfers
(`.specify/specs/064-final-v1-completion/spec.md:75-79`). A pure accessor returns
the sum of pending outbound amounts for the account so `K` can include them.
It grants no authority and does not change the journal's existing semantics.

### FR-006 — Protected changes, named exactly

Adoption changes exactly these protected values. Each one is Camden-reviewed line
by line and merged by Camden only, under Rule 7a and Rule 9b condition 2.

| # | Protected item | Today | Successor |
|---|---|---|---|
| P1 | `MAX_LIVE_BUDGET_USD` (`scripts/mode_config.py:21`) | 200.0 | Replaced by `MAX_LIVE_AUTHORITY_USD = H` (proposed 5000.0) |
| P2 | `ModeProfile` (`scripts/mode_config.py:40-84`) | `bot_budget_usd` is the LIVE budget | LIVE profiles carry `managed_fraction`, `hard_ceiling_usd` (≤ P1) and `min_operating_authority_usd`; PAPER profiles unchanged |
| P3 | `sizing_equity` / `bound_buys` (`scripts/mode_config.py:200-258`) | budget-based cap, list-order shrink | cap base is `A`; pro-rata staging (FR-004.5) |
| P4 | `exec/live_loop.py:31-35`, `:115`, `:128`, `:138`, `:193` (lines at `bbd4e26`; 064 T003b shifts them, and T007 is built on top of it) | `$200` cap, grant, equity, disclosure | `A` from FR-001, `unmanaged_cash_usd`, `above_ceiling_usd`, disclosure names `f`, `H`, `A` |
| P5 | Profile template pins (`scripts/fidelity_provision.py:34-35`, `:90`, `:92`) | `== 200.0`, `== 0.2` | pins the adopted mandate values |
| P6 | `ALLOCATION_SAFETY_CONFIG.version` (`exec/paper_loop.py:100`) | `2026-10-14-alloc-v1` | **Recommended unchanged** (D-3); see below |

**Why P6 should probably not change.** The percentages are already relative to
equity and do not need to change for $200–$5000. The config object is shared
with PAPER (`exec/paper_loop.py:618`), and the gate's durable store refuses a
changed version (`scripts/live_safety_gate.py:477`). Bumping it would force new
PAPER and LIVE gate stores, reset drawdown history, and break continuity of the
PAPER sessions §11.3 item 4 counts. If Camden still wants the mandate bound to a
new version, P6 becomes a Camden-only unit with an explicit gate-store migration,
and the PAPER evidence clock consequence is accepted in writing first.

**Scope conflict to resolve before adoption.** §11.3 item 7
(`docs/SCOPE-V1.md:290-291`) says deposits never raise the $200 budget. This spec
does not edit §11.3, and its gate items 1–6 stay as they are. But P1–P5 cannot
take effect while item 7 reads that way. A separate, Camden-instructed
governance PR touching only §11.3 item 7 is a precondition (task T002). It is
not part of this packet.

### FR-007 — Re-provisioning

`QMB_FIDELITY_PROFILES_JSON` is written only by the 064 T001 helper. That helper
refuses when **any** of its six secret names already exists
(`scripts/fidelity_provision.py:191-192`). So, after P5 merges, re-provisioning
means Camden personally deletes all six secrets (the five credentials and the
profiles JSON), then re-runs the helper with the reviewed template and the
installed safety version. Deleting only the profiles JSON is not enough with
today's helper. D-5 asks whether to add a reviewed profile-only mode instead.
Agents never run provisioning, never see values, and never delete secrets.

### FR-008 — What does not change

- No new strategy, universe, sleeve, weight rule, cadence or ML. The allocation
  keeps `ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED`.
- §11.3 gate items 1–6 stay as they are. Nothing in this spec arms LIVE, writes an
  arming record or relaxes `require_armed` (`scripts/mode_config.py:151-175`).
- Ownership, reconciliation, the gateway, the kill switch, durable persistence,
  the 09:35–12:00 ET window (`exec/live_loop.py:76-77`), the stale/jump bar
  checks (`:117-126`), and every existing halt stay as they are.
- `docs/trials/` and the trial ledger are untouched. No metric is reported. No
  dependency is added.

### FR-009 — Acceptance

All tests are fake-only: injected broker, journal, clock and closes; sockets
blocked; no `gh`, broker or market call. Each scenario runs through the real
consumer (`exec/live_loop.run_once` with a fake broker) as well as the pure unit.

Scenarios (each with a clean control):

| # | Scenario | Must hold |
|---|---|---|
| S1 | $200 verified, first deployment | `A = 200`; daily buys ≤ $40; pro-rata across 8 sleeves; complete in 5 sessions; each sleeve within its rounding bound |
| S2 | $1000 verified | `A = 1000`; band $5 dominates the $1 floor |
| S3 | $5000 verified | `A = 5000`; daily buys ≤ $1000 |
| S4 | $6000 verified | `A = 5000`; `above_ceiling_usd = 1000`; nothing above `H` trades |
| S5 | $800 settled deposit after an executed decision | `A` rises next run; zero orders until the next monthly decision; breaker adjusted equity unchanged |
| S6 | Pending deposit | no change to `A` until settled |
| S7 | $100 withdrawal, observed pending, then settled | `A` falls on observation; no breaker trip; no sell |
| S8 | Unexplained $500 cash increase | `U` += 500; `A` unchanged (not raised, not frozen); buys still sized from prior `V`; `unmanaged_cash_usd = 500` reported; survives restart |
| S8b | Un-evidenced $0.40 TLT distribution | lands in `U`; no halt, no incident beyond the first `U` growth; bot keeps trading |
| S8c | Unexplained $50 decrease with `U = 30` | `U` → 0, `V` falls by 20; incident; breaker not fed a flow |
| S9 | External holding in the account | excluded from `V`; included in gate exposure; never sold |
| S10 | Authority below `min_operating_authority_usd` | no buys; held book unchanged |
| S11 | Rebalance sell $X and buy $Y, fill day then T+1 settlement day | `U` unchanged on both runs; buy stays in `K` until settled; sell sits in `R`; `grant` excludes `R` |
| S12 | `U` state missing after a prior successor run | no new buys; reductions allowed; incident; no automatic re-seed |
| S13 | Settled $500 deposit seen in `C` one run before the journal attributes it | run 1: `U` += 500, breaker unchanged; run 2: `U` → `V`, no incident, breaker unchanged |

Planted defects (Rule 12). Each must turn a named test red, in an isolated copy,
never committed:

1. Authority read from raw account equity instead of `C − U − K + B` (S4, S8 red).
2. `external_cash_flow` left at 0.0 (S7 red: daily-loss breach).
3. Hard ceiling removed (S4 red).
4. List-order staging restored (S1 red: proportions).
5. Pending deposit credited (S6 red).
6. Settled deposit applied twice across a restart (S5 red).
7. Buying power used for `C` (S1/S3 red with a fake whose buying power exceeds
   settled cash).
8. Pending withdrawal ignored in `K` (S7 red).
9. A deposit reopens an executed decision (S5 red: orders appear).
10. Unexplained increase freezes authority or refuses buys (S8b red).
11. Unexplained increase added to `V` instead of `U` (S8 red).
12. Fill cash bridged on trade date (S11 red: `U` moves).
13. `U` state reset to 0 when missing (S12 red).
14. `grant = A` instead of `min(C − U − K, A − B − R)` (S11 red: `U` or `R` spent).
15. Late attribution raises an incident or a breaker flow (S13 red).

Final verification: `python -m pytest tests` from the repo root on the exact
head, plus the relevant mutation drivers and CI. Ledger hashes recorded before
and after, unchanged.

## 4. Decisions for Camden (unrecorded; agents do not tick)

| ID | Decision | Proposal |
|---|---|---|
| D-1 | `managed_fraction` | 1.00 |
| D-2 | `hard_ceiling_usd` | 5000.0, top of the tested range |
| D-3 | `SafetyConfig` version | unchanged; percentages unchanged |
| D-4 | Deposit deployment | wait for next monthly decision; no off-cycle top-up |
| D-5 | Re-provisioning | delete all six and re-run T001 helper, or add a reviewed profile-only mode |
| D-6 | `min_operating_authority_usd` | 100.0 |
| D-7 | Un-evidenced income | Default: lands in `U` (unmanaged, disclosed cash drag). Optional: a bounded allowance treating an increase no larger than bot quantity × the last declared distribution (free data) as income, **at most once per declared distribution per sleeve**, only within 5 sessions of its pay date |

## 5. Limitations (Rule 16)

A static survivor basket, free-tier corporate actions, no point-in-time
fundamentals, daily bars only, and modeled rather than fill-calibrated costs
(`docs/SCOPE-V1.md` §6). Also specific to this spec: Fidelity transfer-history
access, fractional eligibility and commission are UNVERIFIED; behaviour above
$200 is unobserved at the broker; the last-close + 5% price is an estimate, not
a fill guarantee.

## 6. Adoption conditions (all required, in order)

1. Camden records D-1..D-7.
2. The separate §11.3 item 7 amendment is merged by Camden.
3. 064 T003 is complete: T003a (`SafetyGate.observe_equity_with_flows`) merged in
   PR #291 under amendment 001
   (`.specify/specs/064-final-v1-completion/amendment-001-t003-atomic-gate.md`,
   admitted by PR #288), and T003b (`exec/live_loop.py` calling it once per run)
   merged by Camden. The Fidelity transfer-history capability check is evidenced
   read-only, and the pilot's first rebalance evidences the settlement-date
   convention (FR-002). Until all three hold, authority cannot rise above $200
   under any reading of this spec.
4. Tasks T004–T009 are merged; every protected unit by Camden after line review.
5. Camden personally re-provisions (FR-007).
6. §11.3 items 1–6 still hold; Camden arms LIVE himself, separately.
