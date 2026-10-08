# Feature Specification: Versioned ML artifacts, champion/challenger and promotion

**Spec number**: 053
**Created**: 2026-10-07
**Status**: Adopted under `docs/SCOPE-V1.md` §10. Offline contract units authorized. Real training,
evaluation and promotion wait on 043, 035/044, 046, 033 Gate 3 and 052.

## 1. Facts
The deployed signal is 049 `paper_targets.trend_confidence` (SMA 10/30 state) — a reference rule,
not ML. Research models in `scripts/` are not deployed-model evidence.

## 2. Requirements
- **FR-001 Manifest.** Every model artifact has an immutable manifest: algorithm and version, seed,
  training cutoff session, feature schema, label definition, dataset/membership/manifest hashes,
  code identity (source tree hash), dependency versions, artifact SHA-256. Loading verifies all.
- **FR-002 Fold-local fitting.** Scalers, encoders and models fit inside each purged/embargoed
  walk-forward training fold on that fold's past only (Rules 1, 2).
- **FR-003 Evaluation.** OOS net of Rule 13 costs, beside buy-and-hold and matched-frequency random
  baselines (seed count and dispersion). Fold count, purge and embargo recorded.
- **FR-004 Trial recording.** Every candidate, failed and abandoned attempt goes through the trial
  API (043). Lifetime N includes backfill; matrix width M is never N.
- **FR-005 Gates.** Promotion reads immutable Gate 3 (DSR ≥ 0.95, PBO) and risk evidence; it never
  computes statistics itself and refuses stale evidence.
- **FR-006 Champion/challenger.** A retrain produces a challenger only. Shadow evaluation alongside
  the champion precedes any PAPER promotion. Nothing auto-promotes; LIVE promotion is separate.
- **FR-007 Promotion/rollback records** name artifact, configuration, evidence hashes, approver
  (Camden), decision and effective session. Rollback is deterministic and never erases trial history.

## 3. Decisions (2026-10-07)
- **D-1 (quant-ml-genius)** Label: next-session open-to-open direction, matching next-open entry
  (closes the 2026-09-12 overnight-label finding). Features: existing causal price/volume features.
  First family: L2 logistic regression; challenger HistGradientBoosting (existing sklearn).
- **D-2 (quant-ml-genius)** Retrain monthly on the cloud runner, challenger only.
- **D-3 (quant-ml-genius)** Promotion evidence: Gate 3 pass; OOS net expectancy above both
  baselines; ≥ 20 shadow sessions without a risk or reconciliation breach.
- **D-4 (Camden)** Camden alone promotes to PAPER or LIVE.
- **D-5 (quant-ml-genius)** Rollback on: drawdown breach, reconciliation failure, feature-schema
  drift, or 40-session live hit rate below the random baseline's.

## 4. Rule 12 mutants
Scaler fit outside fold; future price perturbation changes a past prediction; purge or embargo
removed; manifest digest mismatch accepted; candidate omitted from ledger; M used for N; stale Gate 3
accepted; challenger auto-promoted; rollback loads the wrong artifact.

## 5. Acceptance
Reproducible training/artifacts; every trial counted; costed provenanced OOS metrics; mutants killed;
rollback demonstrated. A green suite never implies profitability or capital readiness.
