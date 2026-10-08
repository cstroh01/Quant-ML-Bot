# Scope and Definition of Done — v1.0

_Authoritative as of 2026-09-25. Supersedes every earlier roadmap statement in
`README.md`, `docs/PROJECT_CONTEXT.md`, and any spec's "Status" line where the
two conflict. Scope questions are settled here._

---

## 1. What this project is now

A **quantitative research framework**, built to industry standards, using
**only free data**, shipped publicly as a finished and reproducible artifact.

Three things it is, in priority order:

1. **A research and learning vehicle.** The point is the machinery — anti-lookahead
   discipline, purged/embargoed cross-validation, false-discovery correction,
   realistic cost modeling, an execution safety layer — not the returns.
2. **A public, credentialed deliverable.** A repo a quant reviewer can read and
   conclude the author knows what silently breaks a backtest.
3. **A system that actually runs.** End-to-end, on demand, on free data, with
   every reported number carrying provenance.

What changed on 2026-09-25: the charter's earlier claim — a system "capable of
earning real money over time" — is retired as the **primary** framing. The
intersection of ML and public-market alpha is among the most competitively
saturated problems in existence, and a solo part-time builder with free daily
bars, no colocation, no PIT fundamentals, and no institutional capital has no
structural edge in it. Pretending otherwise would distort every design decision
downstream.

**The real-capital path is retained, not deleted.** The capital gate in §5 stays
binding and stays unreached. Paper trading begins at v1.1. Any real capital
remains gated behind every step of that gate, and nothing about the v1.0
deadline may loosen it.

## 2. Hard constraint: free data only

No paid data vendor, no paid API tier, no subscription. Norgate Data and
Sharadar are **out of scope**, not deferred purchases. WRDS/CRSP/Compustat/FactSet
remain closed (Villanova academic license, confirmed denial 2026-09-22).

The free stack:

| Need | Source | Status |
|---|---|---|
| Unadjusted daily OHLCV | `yfinance` (`auto_adjust=False`) | Available; cache not yet built |
| Corporate actions (splits, dividends) | `yfinance` `.actions` | Available; unverified |
| Second source for Rule 14 reconciliation | EODHD free plan (splits/dividends, includes `paymentDate`) | Verified 2026-09-25: free plan is **capped at 1 year of history**, so reconciliation is partial by construction. Tiingo's corporate-actions API is on no free tier. |
| Historical dividend **payment** dates, 10-year | none available free | Verified 2026-09-25. yfinance exposes ex-dates only. This is why spec 020 Q1 resolves to a declared conservative bound rather than a vendor field. |
| Point-in-time fundamentals | none available free | Out of scope; see §6 |

Consequence accepted deliberately: the universe is a static survivor basket and
the data has no survivorship-bias protection. That is a **stated limitation**,
not a solved problem, and it is disclosed everywhere results appear.

## 3. v1.0 — Definition of Done

v1.0 ships when **all eight** hold. Each is binary; none is "mostly".

1. **The backtester runs.** An unadjusted OHLCV + corporate-actions cache exists,
   passes `_validate_unadjusted_prices` and `_validate_corporate_actions`, and
   `backtest_harness.run_backtest` completes end-to-end on it. _(Today it raises:
   no unadjusted cache has ever been fetched.)_
2. **The suite is green from a clean clone.** `python -m pytest tests` passes on a
   fresh checkout. Tests that depend on gitignored artifacts are either fixed to
   generate what they need or skipped with an explicit documented reason — never
   left failing.
3. **Spec 033 complete.** Phases 8–9 done: Gate 3 artifact, API wiring, DSR and
   PBO operational against the real trial ledger, backfill manifest resolved and
   approved.
4. **Spec 032 complete.** All four audited defects fixed with a red-proof each
   (kill/rolling-halt deadlock recovery, pending-sell netting, `kill_confirmed`
   race, divide-by-zero at zero equity), the gate wired into
   `scripts/order_gateway.py`, and the real numeric config values chosen (REQ-009
   refuses defaults, so this is a decision, not code).
5. **Rule 11 clean.** No unsourced or placeholder figure in the terminal UI,
   `reports/`, any tearsheet, this repo's markdown, or a spec's results section.
6. **Repo split executed** per ADR 0001: private companion repo created; tuned
   parameters, weights, risk numbers, and any credential live only there.
7. **README rewritten** for a first-time reader: what it is, what it is not, how
   to reproduce every number, and the limitations register from §6.
8. **Tagged `v1.0` and public on GitHub.**

## 4. v1.1 — Paper trading

Ships immediately after v1.0, and starts the capital gate's paper clock:

- A broker paper adapter in `exec/` (Alpaca paper is the free candidate), under
  Rule 7 — never an autonomous agent lane.
- Spec 032's gate in the live order path, not beside it.
- Scheduled daily run on fresh free data, producing a signal report.
- Position-state reconciliation between broker truth and internal ledger.
- Model monitoring: rolling prediction accuracy and signal decay against a
  baseline.

Paper trading is split out of v1.0 for one reason: it is the first time this
system runs against a clock rather than a DataFrame, which is where a new class
of bug appears. Bundling it into the v1.0 tag would mean shipping neither well.

## 5. The capital gate — unchanged and unreached

No real capital until, in order: full suite plus mutation/AST suites green
(specs 012, 017, 019, 032, 033 — **not** 003 or 007, which contain no such
suites; that earlier citation was false) → purged/embargoed walk-forward OOS
expectancy positive net of Rule 13 costs → **DSR ≥ 0.95** on net funded OOS
returns against the full lifetime trial count → the §4 safety layer live and
tested → 1–2 months paper trading with execution reality reconciled against
backtest assumptions through at least one volatile regime → a small, explicitly
capped amount sized by the risk layer.

Until the DSR step passes, "the bot's returns" always means backtest or paper
numbers. Shipping v1.0 does not advance this gate by a single step, and the
deadline never justifies relaxing one.

## 6. Limitations register — permanent, disclosed

Stated in the README and in every surface that reports a result:

- **Survivorship bias.** Static 5-ticker mega-cap survivor panel
  (AAPL/MSFT/GOOGL/NVDA/AMZN), selected as of 2026. No delisted names. Results
  are an accounting and machinery smoke test, not evidence of generalizable alpha.
- **Corporate-action data is free-tier and only partially reconciled.** yfinance
  has documented split/dividend/100× pricing defects, and the only free second
  source covers one year of history, so older actions are unreconciled by
  construction and labelled as such.
- **Dividend payment dates are a declared conservative bound, not observed
  data.** No free source provides them historically. Dividend cash is credited no
  earlier than it could have arrived, so the ledger is never optimistic.
- **No point-in-time fundamentals.** Nothing knowable-on-date beyond price and
  volume.
- **Daily bars only.** No intraday, no microstructure, no order-book data.
- **Costs are modeled, not calibrated.** Rule 13's half-spread plus square-root
  impact is an estimate from daily OHLC, never validated against real fills.
- **No real capital has ever been deployed**, and none will be before §5 passes.

## 7. Explicitly cut from v1.0

Deferred, with the condition that would justify each — not abandoned, and not to
be pulled forward because it sounds sophisticated:

| Deferred | Pull it forward when |
|---|---|
| ONC effective-N clustering for DSR | Trial count reaches thousands; raw lifetime N is the conservative default until then |
| Regime detection (HMM, vol buckets) | A single-regime model's OOS performance visibly breaks across regimes |
| Meta-labeling (AFML) | A primary signal is validated and stable |
| Ensembling across signal families | Single-model baselines are validated and their limits felt |
| Deep learning (LSTM/transformer) | Logistic/ridge/HGB baselines are genuinely outgrown |
| Alternative data | Price/volume features exhausted **and** a named hypothesis exists |
| Survivorship-free universe / PIT fundamentals | A paid vendor is in budget — out of scope today |
| Multi-asset beyond the 5-ticker panel | v1.1 or later; sizing and correlation layers must exist first |

## 8. Process changes for the finish push

- **Single-threaded through Spec Kit** remains the default. A parallel lane
  requires module-ownership split with zero file overlap, as on 2026-09-13.
- **Every remaining work item is a numbered spec.** No ad hoc patching, including
  spec 032's bug fixes — tests first, red proof per Rule 12.
- **Rule 10 unchanged.** Agents never run `git`; Camden commits in GitKraken.
- **Rule 9 unchanged.** The deadline does not suspend the merge gate. A PR Camden
  cannot explain does not merge, on any timeline.

## 9. Amendment 2026-10-03 — data sources and broker (decided by delegation from Camden)

Free-data rule unchanged. No paid tier is introduced.

**Data — candidates to verify in spec 035 `research.md` before any code depends on them.** Each claim below is from vendor documentation read 2026-10-03, not yet tested against this repo:

| Need | Candidate | Documented free terms | Why |
|---|---|---|---|
| Primary daily OHLCV | Tiingo EOD (free key) | 30+ years, 1,000 requests/day, 500 unique symbols/month | Documented API with keys and terms, versus yfinance's unofficial access. Corporate-action fields: UNVERIFIED. |
| Second source (Rule 14) | Alpaca market data (Basic plan, free key) | Daily bars since 2016, 200 requests/min, IEX real-time | Independent second source over 2016 onward, versus EODHD's 1-year cap. Corporate-action history depth: UNVERIFIED. |
| Cross-check | yfinance `auto_adjust=False`, EODHD free, SEC EDGAR | as §2 | Kept as tertiary checks. |
| Point-in-time fundamentals (deferred, §7) | SEC EDGAR XBRL `companyfacts` | Free, about 10 requests/s, roughly 2009 onward, filed dates per fact | Only free source with filing-date stamps. Not in v1.0. |

If verification fails for a candidate, §2's existing sources stand. The survivor-basket limitation (§6) is not solved by any of these.

**Broker.** Fidelity offers no public retail trading API, and automating its website would break its terms, so it is not integrated. Alpaca (free paper and live API) is the v1.1 adapter. Live trading through it stays behind every step of §5. Broker credentials live only in environment variables or a secrets vault, never in either repo.

**Execution timing.** At daily frequency, network latency is not the binding constraint; decision-to-fill delay is. v1.1 evaluates computing signals shortly before the close with market-on-close orders, against the current next-open fill, under identical Rule 13 costs.

## 10. Amendment 2026-10-07 — expanded product charter (Camden, explicit)

Adds a product objective on top of §1; it does not replace §3's v1.0 definition of done or loosen §5.

**Objective.** A professional, autonomous ML trading product intended to grow Camden's
user-selected capital through profitable trading, optimizing net performance under declared
capital, liquidity, exposure and drawdown limits. An objective, never evidence: no surface
claims profitability without §5's evidence.

**Modes.** PAPER (default) runs at Alpaca paper in two isolated profiles: large ($100,000
virtual, higher daily deployment) and small ($5,000, the prospective-live scenario). LIVE is a
separately verified account, credential set, store and log namespace with a bot budget Camden
sets at activation (a few hundred dollars initially). The bot never sizes from total account
equity and never sells holdings it does not own. LIVE stays locked until §5 passes and Camden arms it.

**Broker — supersedes §9's broker paragraph.** Camden requires LIVE execution at Fidelity
(individual brokerage account) and accepts, in writing on 2026-10-07, the risk that an
unofficial integration breaches Fidelity's terms and may lead to account restriction. Fidelity
has no paper mode, so PAPER stays at Alpaca. The Fidelity adapter (spec 057) lives in `exec/`
under Rule 7, defaults to preview-only, uses credentials only from a secrets store Camden
populates, and adds no detection-evasion features (no fingerprint spoofing, IP rotation, or
CAPTCHA/2FA bypass). Fidelity holdings import read-only for total-portfolio exposure (spec 054).

**Universe.** Broadened only through a dated point-in-time registry with research vs executable
eligibility and visible exclusion reasons (spec 052). §6's survivorship limitation stays until
evidence removes it.

**ML.** Versioned artifacts, purged/embargoed walk-forward net-cost evidence, two baselines,
lifetime trial recording, DSR/PBO, champion/challenger shadow evaluation. Camden alone promotes a
model to PAPER or LIVE (spec 053). The SMA rule remains the comparator and is never called ML.

**Operations.** The daily loop runs with Camden's computer off as a scheduled GitHub Actions
workflow in the private companion repo (ADR 0001): encrypted secrets, single-run concurrency,
durable state, missed-run detection, automatic failure and daily-summary notification with no
daily approvals (spec 055). Spare Actions minutes run research, data refresh and mutation jobs.

**Data.** §2's free-only rule stands. Spec 056 verifies and adopts the best free stack.

**Milestones.** M0 v1.0 → M1 reconciled PAPER on the cloud runner → M2 mode/budget isolation +
small-account PAPER → M3 registry/universe → M4 ML challenger in shadow → M5 capital-gated,
capped LIVE at Fidelity.
