# Backfill worksheet for Camden — UNAPPROVED

Source: `docs/trials/backfill/manifest.json`, SHA-256 `c68e61a0de445d1ed2ad3c4418c58492f5c503cdeafff7a47c4f8d9579402ab5`, draft date `2026-09-22T16:15:42.367906+00:00`.

These are proposed counting surfaces, not performance results. No lifetime total is approved or calculable while the execution/configuration ceilings remain unresolved. Separate rows are added without configuration deduplication.

| Campaign | Current per-batch Cartesian surface | Missing before approval |
|---|---:|---|
| pre-spec-sma | 1 | Historical execution/configuration ceiling |
| ma-crossover-costed | 1 | Historical execution/configuration ceiling |
| logistic-baseline | 2 | Historical execution/configuration ceiling |
| model-cv-search | 16 | Historical execution/configuration ceiling |
| multi-ticker-comparison | 20 | Historical execution/configuration ceiling |
| api-backtest | 1 | Historical execution/configuration ceiling |
| feature-set-comparison | 510760 | Historical execution/configuration ceiling |
| screen-014-inspected | 510760 | Historical execution/configuration ceiling |
| screen-2026-09-06-interrupted | 510760 | Historical execution/configuration ceiling |
| screen-015-serial | 510760 | Historical execution/configuration ceiling |
| screen-015-parallel | 510760 | Historical execution/configuration ceiling |
| screen-previous-partial | 510760 | Historical execution/configuration ceiling |
| required-baselines-promotion-uncertain | 147 | Historical execution/configuration ceiling |
| audit-2026-09-12 | 8 | Historical execution/configuration ceiling |
| audit-2026-09-18-history-gap | unbounded history; no numeric bound | Historical execution/configuration ceiling |
| manual-ai-off-repo | unbounded history; no numeric bound | Historical execution/configuration ceiling |

The full JSON provides descriptions, dimension factors, evidence passages, source paths/hashes, and every existing pre-033 spec classification. Per-batch surfaces are not substituted for lifetime bounds. The screening rows include possible full grid/refold executions even where only interrupted or partial output survives. The generic script surface and distinct observed runs are intentionally retained separately.

Please supply campaign-specific upper bounds on reruns and additional configurations, plus a closed upper bound for ad hoc/AI/off-repo work and baseline promotions. A range is acceptable; the calculation uses its upper endpoint. Once all rows have defensible finite bounds, review the summed count, upward power-of-two rounding and doubling reserve, and explicitly approve the exact finalized manifest digest.

Until then: `approval = null`, `N_backfill = undefined`, real Gate 3 = `unknown`.
