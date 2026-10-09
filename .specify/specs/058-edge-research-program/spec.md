# Feature Specification: Preregistered multi-asset edge research program

**Spec number**: 058
**Created**: 2026-10-09
**Status**: Draft. Decisions D-1 to D-5 are recorded (Camden, 2026-10-09).
Governance follow-ups (a `docs/SCOPE-V1.md` universe amendment, a spec 033 family-N amendment) are
separate PRs, each touching only its own file.
**Related**: 033 (ledger, DSR, PBO, Gate 3), 035/056 (free data), 046 (cost model), 052 (registry),
Rules 1–5, 9, 11, 12, 14.

EXAMPLE — NOT A RESULT. No figure in this spec is a performance result. The Sharpe bars in §6 are
planning arithmetic under a null-dispersion assumption, not observations.

## 1. Purpose
Give a genuine edge the best honest chance of passing Gate 3. The approach has five parts:
- **Longer history.** Use the longest free daily history available.
- **Diversified universe.** Trade a multi-asset ETF universe instead of the 5-stock survivor basket.
- **Small, fixed hypothesis set.** Write down a small set of economically motivated hypotheses
  before any data for this universe is fetched.
- **Realistic costs.** Use spec 046's cost model.
- **Sealed holdout.** Keep a holdout that is opened exactly once.

## 2. Why this spec exists
- **Gate 3 is effectively out of reach today.** Gate 3 deflates by the lifetime trial count, and the
  approved backfill is `N = 16777216` (`BACKFILL_REVIEW.md`). With that count, the null-dispersion
  arithmetic in §6 puts the required net annualized Sharpe at roughly 1.3–2.2. That is beyond
  typical honest daily strategies.
- **More screening would only make it worse.** Further screening of the 5-stock basket adds trials
  and cannot lower the bar.

## 3. Recorded decisions (Camden, 2026-10-09)
- **D-1 Family count.** This program is evaluated against its own family count, `N_family`. This is
  allowed only while all of the following hold:
  - (a) Every hypothesis and parameter in §5 is fixed and hashed into the ledger before any data for
    the §4 universe is fetched.
  - (b) The §4 instruments and data are disjoint from every prior screen. This was verified: no prior
    `scripts/`, `reports/` or `docs/trials/` reference to any §4 ticker at `13d915d`.
  - (c) The family declaration is hashed into the ledger.
  - (d) The lifetime-`N` DSR is computed and published beside the family DSR on every surface.

  If any condition breaks, the family reverts to lifetime `N`. Recording this rule after a result was
  seen would void it. It is recorded here first.
- **D-2 Universe.** Expand from the static 5-stock basket to the liquid multi-asset ETF list in §4.
  This requires a `docs/SCOPE-V1.md` amendment (separate governance PR, on Camden's explicit
  instruction of 2026-10-09).
- **D-3 Holdout.** All sessions on or after **2023-10-02** are sealed. Research, fitting, selection
  and every reported research statistic use sessions **≤ 2023-09-29** only. The sealed window runs
  once, after the §5 selection rule has chosen, and that run is recorded in the ledger. A second
  holdout run is refused.

## 4. Universe (fixed now; D-2)
An instrument enters on its first full session after listing. Signals for an instrument start once
its lookback is fully observed, so there is no backfill before listing. Point-in-time membership is
by listing date only. The universe is all ETFs; no single stock is included.

| Class | Tickers |
|---|---|
| US equity | SPY, QQQ, IWM, DIA |
| US sectors | XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY |
| International equity | EFA, EEM |
| Treasuries | SHY, IEF, TLT |
| Credit / inflation | LQD, HYG, TIP |
| Real assets | GLD, VNQ, DBC |
| Dollar | UUP |

- **Disclosed limitation.** ETFs that closed are absent. This is a smaller survivorship bias than
  single stocks, but it is not zero.
- **Disclosed limitation.** Early years have few instruments; only SPY, DIA and QQQ exist before 1998.

## 5. Preregistered hypotheses (D-1a; 15 configurations; `N_family` cap 50)
All hypotheses share these settings:
- **Timing.** Daily close data. Signals are computed at close `t` and executed at the open of `t+1`
  (Rule 1).
- **Rebalancing.** Monthly, on the first session of each month.
- **Volatility.** Per-asset volatility is the 60-session EWMA. The portfolio targets 10% annualized
  volatility.
- **Leverage.** Gross leverage is capped at 1.0.
- **Shorting.** Long-only unless the hypothesis says otherwise.
- **Costs.** Spec 046's model.

| ID | Hypothesis (economic basis) | Configurations |
|---|---|---|
| H1 | Time-series momentum: hold an asset if its trailing return (excluding the last month) is positive, volatility-targeted | lookback 3, 6, 12 months → 3 |
| H2 | Trend filter: hold an asset if close is above its SMA | SMA 100, 200 → 2 |
| H3 | Cross-asset momentum: top-k by 12-1 return | k = 3, 5 → 2 |
| H4 | Inverse-volatility risk parity, always invested | 1 |
| H5 | H4 weights gated by the H1 12-month signal | 1 |
| H6 | Dual momentum: relative winner, held only if its absolute return exceeds SHY's | lookback 6, 12 → 2 |
| H7 | Low-volatility tilt within the 9 sector ETFs: hold the 3 lowest-vol | 1 |
| H8 | Short-term reversal within sectors: hold the 3 worst prior-week, weekly rebalance | 1 |
| H9 | Equal-weight H1(12) + H2(200) + H4 | 1 |
| H10 | 60/40 SPY/IEF, monthly rebalance (allocation reference, also a candidate) | 1 |

- **Rule 4 baselines.** Each configuration is reported beside equal-weight buy-and-hold of the
  available universe and a seeded random-signal baseline, over the identical period with identical
  costs.
- **Baselines do not count.** Baselines are not candidates and do not add to `N_family`.
- **Reruns.** Reruns and bug-fix reruns add to `N_family`, up to the cap of 50. Exceeding 50 voids D-1.

**Selection rule (fixed now).** The candidate with the highest research-window DSR at `N_family` is
selected. Ties go to the lower ID.

## 6. Planning arithmetic (null dispersion, skew 0, kurtosis 3; not a result)
Approximate net annualized Sharpe needed for DSR ≥ 0.95 (HAC t ≥ 3 binds less in every cell):

| Research years | Lifetime N 16.8M | N 50 |
|---|---|---|
| 20 | ~1.6 | ~0.9 |
| 30 | ~1.3 | ~0.7 |

- **Usable years.** Research history with ≥ 10 instruments starts around 2003–2007. That leaves
  roughly 16–20 usable years, so the realistic bar is about 0.9–1.0.
- **Not assured.** A pass is plausible for diversified trend following, but it is not assured.
- **A fail is a valid outcome.** An honest fail is a valid v1.0 outcome.

## 7. Requirements
- **FR-001 Preregistration first.** Before any §4 fetch, the ledger records a family declaration. It
  holds the §5 table, the selection rule, the holdout date, the cost-model version, the universe and
  `N_family` cap, and the SHA-256 of this spec. A fetch without that record is refused.
- **FR-002 Holdout seal.** The data loader refuses sessions ≥ 2023-10-02 unless it is given a
  one-shot holdout token bound to the selected configuration hash. A second use of that token is
  refused.
- **FR-003 Validation.** Purged and embargoed walk-forward runs within the research window (Rule 2).
  The embargo is ≥ the longest lookback.
- **FR-004 Costs.** Costs come from spec 046's model only. No flat-bps fallback (046 D-3). A run
  before 046 lands is labeled `EXAMPLE — NOT A RESULT`.
- **FR-005 Data.** Data comes from the free 056 sources only: Tiingo EOD primary for long history,
  Alpaca raw SIP as the check from 2016. Fetches are bounded human-authorized runs (Codex lane).
  Raw data stays private; manifests are public.
- **FR-006 Publication.** Every surface shows the family DSR, the lifetime-N DSR, HAC t, PBO (S = 16),
  the holdout result, the baselines, costs, folds, purge and embargo, and the limitations register.

## 8. Recorded decisions, continued (Camden, 2026-10-09)
- **D-4 Holdout pass condition.** The selected configuration passes the holdout only if its holdout
  net Sharpe is above 0 **and** its one-sided HAC t is ≥ 1.645. Gate 3's thresholds (spec 033)
  still apply to the research window. Both must pass.
- **D-5 Costs first.** §5 research runs wait for spec 046 T001/T002 (Camden's source review). No
  provisional-cost run may be selected, gated or published as a result.

- **D-6 Module placement (T004).** A new `scripts/portfolio_backtest.py` owns weights → fills → P&L
  for a panel. Its `CLAUDE.md` row is a separate governance PR (Camden, 2026-10-09 (gate packet `claude/gate-packet-20261009.md`)).

## 9. Out of scope
Intraday data, single stocks, futures, leverage above 1.0, ML models in this family. ML stays a later
challenger under 053.
