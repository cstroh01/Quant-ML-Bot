"""Shared numeric conventions.

These live in one place because they are *comparison* constants: two Sharpe
ratios in this repository computed against two different risk-free rates, or
annualized on two different bar counts, would be silently incomparable. That
is a different situation from the cost model in `logistic_baseline.py:26-31`,
which is restated locally on the grounds that a shared illustrative *value*
is not a real coupling — a denominator that every risk metric divides by is.

Deliberately importless: any module may depend on this one without dragging
in scipy, matplotlib, or yfinance.
"""

# Bars per year, not calendar days per year. Every annualized figure in this
# repository treats one row as one trading day.
TRADING_DAYS_PER_YEAR = 252

# 3-month T-bill, ~Sept 2026 snapshot — not live-fetched, revisit periodically.
RISK_FREE_RATE_ANNUAL = 0.0378
