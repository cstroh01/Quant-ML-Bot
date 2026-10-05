# Feature Specification: Paper-loop prototype (Alpaca paper, daily, market-on-open)

**Spec number**: 049
**Created**: 2026-10-04
**Status**: Implemented in an interactive session (reviewed lane, Rule 7). Not merged. Not yet run against Alpaca.
**Relation to SCOPE**: builds the core of `docs/SCOPE-V1.md` §4 (v1.1) ahead of the v1.0 tag, by Camden's 2026-10-04 decision to have a working trading prototype by 2026-10-07. It changes no item of the v1.0 Definition of Done (§3) and advances no step of the capital gate (§5). Spec 048 (queue Q14/Q19/Q20) is superseded by this spec for the adapter and loop; its reconciliation-report and timing-comparison parts carry forward as follow-ons.

## 1. What it does

One run, before the open on an NYSE session:

1. Reconcile every open safety-gate reservation against Alpaca by client order ID. Terminal (`filled`, `canceled`, `expired`, `rejected`) releases it; anything else stays open.
2. Load free daily bars (`data.download_market_data`, research-adjusted closes) for the static five-ticker panel.
3. Take the last completed session strictly before today (America/New_York). Abort unless it is exactly the previous NYSE session (`data.trading_days`).
4. Decide with `scripts/paper_targets.py`: confidence = 1 while the 10-day SMA is above the 30-day SMA at that close (the state of `signals.sma_crossover_signal`'s rule), sized by `portfolio_risk.target_weights` under `PAPER_RISK_CONFIG`.
5. Convert targets to whole-share deltas: buys floored, sells never below zero, held names outside the targets flattened, sells first.
6. Without `--submit`: log the plan only. Nothing reaches the broker; the gate reserves nothing.
7. With `--submit`: each order goes through `order_gateway.submit_order` with a fresh `BrokerSnapshot`; ALLOW leads to a market-on-open (`time_in_force=opg`) order. Refuses to run while the market is open.
8. Append one JSON line per run to `data/live_safety/paper-runs/runs.jsonl` (gitignored).

## 2. Requirements

- **FR-001 Paper only.** The trading base URL is the constant `https://paper-api.alpaca.markets`. No parameter, flag or environment variable changes it.
- **FR-002 Credentials.** `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` from the environment or a gitignored `.env`. Never logged, printed, in `repr`, or in an exception message.
- **FR-003 Gate in the order path.** No order reaches the broker except through `order_gateway.submit_order` with `SafetyConfig` version `2026-09-29-v1` (ADR 0002 item 5).
- **FR-004 Point-in-time.** The decision for session t uses only rows at or before t; today's partial bar is ignored.
- **FR-005 Stale data aborts.** A last completed bar other than the previous NYSE session aborts the run.
- **FR-006 No inference on failure.** A timed-out or 5xx submission is UNKNOWN; its reservation stays open. A 4xx refusal is terminal (`BROKER_REFUSED`).
- **FR-007 Sizing inside the gate.** `PAPER_RISK_CONFIG.max_weight` and `max_gross`, grossed up by the 5% gap allowance, stay strictly below the gate's `max_position_pct` and `max_gross_pct`.
- **FR-008 Disclosure.** Every run record carries "Paper mechanics prototype. Not a performance result."

## 3. Decisions for Camden (open)

- **D-1** Build the paper loop before the v1.0 tag (this spec exists because of the 2026-10-07 target). Recommended: yes, with the statement above that §3 and §5 are unchanged.
- **D-2** Do paper days before §5 steps 1–4 pass count toward step 5's 1–2 months? Recommended: no. They are prototype evidence; the step-5 clock starts when steps 1–4 pass.
- **D-3** `PAPER_RISK_CONFIG` (max_weight 0.08, max_gross 0.40, rest = spec 017 recommended). Derived from your gate limits; confirm or change.
- **D-4** Signal: SMA 10/30 trend state is a reference rule, not a validated strategy. Swapping in the ML signal is a follow-on spec.
- **D-5** Scheduling: Windows Task Scheduler on your PC, weekdays 08:45 ET, `--submit`. A cloud schedule needs the keys in a secrets store; out of scope here.

## 4. Known limitations (disclosed)

- Research-adjusted closes drive the signal; no funded nominal-price ledger is involved (that is v1.0's spec 035/044 track).
- `external_cash_flow` is 0.0. A paper-account reset reads as a large P&L move and the gate halts (fail closed).
- The 5% gap allowance bounds the gate's worst-case price; a larger overnight gap is not caught by the reservation math.
- Alpaca's `opg` acceptance window and IEX-only data on the free plan are from vendor documentation, UNVERIFIED in this repo until the first `--submit` run.
- No model monitoring and no broker-vs-ledger position report yet (follow-ons).

## 5. Acceptance

- `python -m pytest tests` green on Windows, including `tests/test_049_paper_loop.py` (18 tests).
- `python exec/paper_loop.py --offline` prints a plan on real free data with no credentials.
- `python exec/paper_loop.py` (keys set, dry run) prints a plan from the real paper account.
- `python exec/paper_loop.py --submit` before 09:28 ET places paper orders; the next morning's run releases their reservations.
