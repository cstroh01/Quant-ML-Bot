# T004 write-surface inventory

Measured 2026-09-30; AST and text only, no research imports.
All four spec search patterns ran over scripts/, reports/api/, and tests/.

| research_attempt call | Enclosing function |
|---|---|
| `reports/api/routes/backtest.py:60` | `get_backtest_tearsheet` |
| `scripts/feature_set_comparison.py:167` | `_predictions_by_date` |
| `scripts/logistic_baseline.py:318` | `main` |
| `scripts/logistic_baseline.py:332` | `main` |
| `scripts/ma_crossover_backtest.py:123` | `baseline_results` |
| `scripts/ma_crossover_backtest.py:135` | `baseline_results` |
| `scripts/ma_crossover_backtest.py:268` | `main` |
| `scripts/model_cv.py:330` | `tune_on_fold` |
| `scripts/model_cv.py:461` | `nested_walk_forward` |
| `scripts/multi_ticker_comparison.py:137` | `_baseline_rows` |
| `scripts/multi_ticker_comparison.py:155` | `_baseline_rows` |
| `scripts/multi_ticker_comparison.py:282` | `run_one_ticker` |
| `scripts/multi_ticker_comparison.py:320` | `run_one_ticker` |

E1 moved to main:253, candidate:268, __main__:332 after 041.
E2-E4, E5 route and all other listed production writer anchors are unchanged.
No new production writer or entry point found by these scans.
`run_unadjusted_wiring_mutants.py:85-89` inherits the environment; it copies conftest.
The other two drivers omit conftest as recorded; D-4 remains required.
Search limitations in spec section 2 still apply.

Raw searches retained outside the repository:
- `C:\Users\Owner\AppData\Local\Temp\spec043-8u_zwprb\inventory-search-0.txt`; SHA-256 `b43d9370afba1a45704718f3f32a89803c0ef224f91a79304425c5a1130bc072`.
- `C:\Users\Owner\AppData\Local\Temp\spec043-8u_zwprb\inventory-search-1.txt`; SHA-256 `00cec824c4f02e98f02a21c361d4e0ca8de52b96aeae51efa679b53e30793e57`.
- `C:\Users\Owner\AppData\Local\Temp\spec043-8u_zwprb\inventory-search-2.txt`; SHA-256 `2a5d491a549562bce95a2580a6885bf222d51e166e3c2763f178edf10f1e7c75`.
- `C:\Users\Owner\AppData\Local\Temp\spec043-8u_zwprb\inventory-search-3.txt`; SHA-256 `e975f8e94bf206f02be9088129249985a4772e3da6550e75b602d6ee259c106a`.
