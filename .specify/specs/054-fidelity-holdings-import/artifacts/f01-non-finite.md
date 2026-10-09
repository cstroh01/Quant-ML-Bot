# 054 F01: non-finite numbers in Fidelity exports refuse

Source: Codex cross-review 2026-10-08 (CROSS-REVIEW-MAIN.md, private folder), 054 P1 at
`scripts/holdings_import.py` L71: `float("NaN")`, `float("Infinity")` and overflowing `1e999` were
accepted as quantities, prices and amounts. Synthetic fixtures. EXAMPLE — NOT A RESULT.

## Red (main 2c72c9a, `test_non_finite_numbers_refuse`, 5 tokens × 2 parsers)
```
FAILED tests/test_054_fidelity_csv.py::test_non_finite_numbers_refuse[parse_history_csv-history_example.csv-,-51,-1e999]
10 failed, 8 passed in 0.64s
```

## Fix
`_number` raises `HoldingsImportError` for any non-finite parse. One choke point covers every numeric
field in both parsers.

## Rule 12
Removing the finiteness check turns the 10 new cases red (10 failed, 31 passed); restored: 41 passed.
