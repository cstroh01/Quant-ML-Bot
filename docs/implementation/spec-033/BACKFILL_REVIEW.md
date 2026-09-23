# Backfill worksheet for Camden — APPROVED; T032 COMPLETE

Approved source digest: `docs/trials/backfill/manifest.json` file SHA-256 `54b45a0ad11f59a768d6a84e503612bc5dc5f958237c2dee5cd4d6323606ba04`, generated `2026-09-22T22:57:18.1011870Z`. Camden approved that exact digest and `N_backfill = 16777216`. The approval envelope now has file SHA-256 `98c27aaab970596256d8674d90939be2eaacfb6f3140bc7a3b199dd3438c54d7` and canonical manifest hash `8cc9ef98f20c3d90e26c58a9c028e49c868463a249930a91180a12eb1975bcae`.

These are conservative lifetime counting bounds, not performance results. Every formerly unresolved campaign now has a finite bound supplied from Camden's direct recollection on 2026-09-22. Separate rows are added without configuration deduplication.

| Campaign | Cartesian surface | Rerun/range input | Chosen upper bound |
|---|---:|---:|---:|
| pre-spec-sma | 1 | 10 reruns | 10 |
| ma-crossover-costed | 1 | 10 reruns | 10 |
| logistic-baseline | 2 | 10 reruns | 20 |
| model-cv-search | 16 | 10 reruns | 160 |
| multi-ticker-comparison | 20 | 10 reruns | 200 |
| api-backtest | 1 | 10 reruns | 10 |
| feature-set-comparison | 510760 | 2 reruns | 1021520 |
| screen-014-inspected | 510760 | 2 reruns | 1021520 |
| screen-2026-09-06-interrupted | 510760 | 2 reruns | 1021520 |
| screen-015-serial | 510760 | 2 reruns | 1021520 |
| screen-015-parallel | 510760 | 2 reruns | 1021520 |
| screen-previous-partial | 510760 | 2 reruns | 1021520 |
| required-baselines-promotion-uncertain | 147 | 1 rerun; no promotion-bias inflation | 147 |
| audit-2026-09-12 | 8 | 1 evidenced inspection | 8 |
| audit-2026-09-18-history-gap | direct recollection bound | 10-20; upper endpoint | 20 |
| manual-ai-off-repo | direct recollection bound | 10-20; upper endpoint | 20 |

The six small one-off campaigns each receive the full `10` rerun ceiling even though Camden estimated `0-10` across the group. The six screening campaigns each use the upper endpoint `2`. The two ad hoc rows each receive `20`, deliberately over-allocating Camden's roughly `10-20` combined recollection. The audit re-inspection and required mechanical baselines each use one rerun.

Calculation:

`10 + 10 + 20 + 160 + 200 + 10 + (6 * 1021520) + 147 + 8 + 20 + 20 = 6129725`

`next_power_of_two(6129725) = 8388608`

`N_backfill = 2 * 8388608 = 16777216`

No earlier approved backfill artifact exists, so the non-decrease maximum does not raise this value.

Approval recorded: Camden Paul Stroh, `2026-09-22T23:04:33.4931090+00:00`, approved manifest SHA-256 `54b45a0ad11f59a768d6a84e503612bc5dc5f958237c2dee5cd4d6323606ba04` and `N_backfill = 16777216`.

Final T032 artifact: `docs/trials/backfill/a47232be-3d05-4c36-b984-f11b29b12a25.json`; embedded SHA-256 `fb61cc12715889250afc47fed5e5d31a99ccc1965d57cfa1b37da1732d34f008`; file SHA-256 `2d8ef10d1920d2380750b5022a2b77f536fe436560a4ea36765e65e79fe45155`.

The earlier immutable artifact `a6abdb76-5ec9-43db-b563-c5f66b67637f` is retained and superseded. Its bounds and `N_backfill` were correct, but its embedded manifest retained stale pre-approval state labels. The final artifact references it explicitly and preserves the same approved count.

T033 and all later work remain unstarted. Real Gate 3 remains `unknown`; `capital_gate.py` and Phases 8/9 remain untouched.
