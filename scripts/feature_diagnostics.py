"""Conditioning diagnostics for a feature set: correlation, VIF, condition number.

Spec 014 rests on a claim about the design matrix — that the level features
are collinear and badly scaled, and that the scale-free set is neither. A
claim about a matrix should be measured, not asserted, so the measurement
lives here rather than in a comment.

Three numbers, and what each one is for:

- **Correlation** answers "are these two columns the same column twice?"
  `Short_SMA` and `Long_SMA` are the pair spec 014 was opened over.
- **VIF** answers the same question against *every other column at once*
  rather than pairwise, which is what catches a column that is redundant
  only in combination. `VIF_i = 1 / (1 - R²_i)` from regressing column `i`
  on the rest; it is read straight off the diagonal of the inverted
  correlation matrix, which is the same quantity without fitting anything.
- **Condition number** answers "how much does the coefficient vector move
  when the data moves a little?" It is the whole-matrix summary, and it is
  the one that was reported as ill-conditioned.

The condition number is computed on the *standardized* matrix throughout. On
a raw matrix it mostly measures the unit mismatch between `Log_Return` and
`Volume`, which is real but is exactly what the pipeline's scaler already
fixes; standardizing first isolates the part scaling cannot fix, which is
the part this spec's ratio change is for.

Rule 8: this is a diagnostic entry point over the signal layer. It imports
`data` and `features` and knows nothing of fills, positions, or P&L.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import download_market_data
from features import FEATURE_SETS, build_features, feature_columns

TICKER = "AAPL"
PERIOD = "10y"

# The cached download is the five-ticker universe (spec 013's
# `TICKER_UNIVERSE`), so the whole list is requested and `TICKER` selected out
# of it. Asking for `[TICKER]` alone would miss that cache file — the key is
# the sorted ticker list — and trigger a network call this lane cannot make.
CACHE_TICKERS = ["AAPL", "AMZN", "GOOGL", "MSFT", "NVDA"]

# Conventional reading thresholds, printed beside the numbers so a reader
# does not have to remember them. VIF above 10 is the usual "serious
# collinearity" line and above 5 the usual "worth looking at" one; a
# standardized condition number above 30 is the usual ill-conditioning line.
VIF_CONCERN = 5.0
VIF_SERIOUS = 10.0
CONDITION_CONCERN = 30.0


def standardized_matrix(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    """The selected columns, z-scored per column, as a float array.

    A zero-variance column would divide by zero. It is left as all-zeros
    rather than dropped or errored on: a constant feature is a real thing to
    discover in a diagnostic, and silently removing it would hide it.
    """
    matrix = frame[columns].to_numpy(dtype=float)
    centered = matrix - matrix.mean(axis=0)
    deviations = matrix.std(axis=0, ddof=0)
    safe = np.where(deviations == 0.0, 1.0, deviations)
    return centered / safe


def condition_number(frame: pd.DataFrame, columns: list[str]) -> float:
    """Condition number of the standardized design matrix (2-norm)."""
    return float(np.linalg.cond(standardized_matrix(frame, columns)))


def variance_inflation_factors(
    frame: pd.DataFrame, columns: list[str]
) -> pd.Series:
    """VIF per column, from the diagonal of the inverted correlation matrix.

    Equivalent to regressing each column on all the others and taking
    `1 / (1 - R²)`, without fitting anything.

    A singular correlation matrix — an exactly duplicated column — has no
    inverse and no finite VIF. `numpy.linalg.pinv` returns the
    pseudo-inverse there rather than raising, and the resulting enormous-
    but-finite values read correctly as "this column is redundant". That is
    the right behavior for a diagnostic, whose job is to report the problem
    rather than to refuse to run in its presence.
    """
    correlation = np.corrcoef(standardized_matrix(frame, columns), rowvar=False)
    correlation = np.atleast_2d(correlation)
    inverse = np.linalg.pinv(correlation)
    return pd.Series(np.diag(inverse), index=columns, name="VIF")


def correlation_frame(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """The correlation matrix of the selected columns, as a labelled frame."""
    correlation = np.corrcoef(standardized_matrix(frame, columns), rowvar=False)
    return pd.DataFrame(np.atleast_2d(correlation), index=columns, columns=columns)


def max_abs_offdiagonal_correlation(
    frame: pd.DataFrame, columns: list[str]
) -> tuple[float, tuple[str, str]]:
    """The largest absolute pairwise correlation, and which pair it was.

    The pair is returned alongside the number because "0.97" is a fact and
    "`Short_SMA` vs `Long_SMA` is 0.97" is a finding.
    """
    # `.to_numpy()` can hand back a read-only view of the frame's block, and
    # the diagonal is zeroed in place below — so copy rather than mutate
    # whatever buffer pandas happened to share.
    correlation = correlation_frame(frame, columns).to_numpy().copy()
    np.fill_diagonal(correlation, 0.0)
    flat = int(np.argmax(np.abs(correlation)))
    row, column = np.unravel_index(flat, correlation.shape)
    return float(abs(correlation[row, column])), (columns[row], columns[column])


def diagnose(frame: pd.DataFrame, feature_set: str) -> dict:
    """Every diagnostic for one feature set, as a plain dict."""
    columns = feature_columns(feature_set)
    worst_correlation, worst_pair = max_abs_offdiagonal_correlation(frame, columns)
    vif = variance_inflation_factors(frame, columns)
    return {
        "feature_set": feature_set,
        "columns": columns,
        "rows": len(frame),
        "condition_number": condition_number(frame, columns),
        "vif": vif,
        "max_vif": float(vif.max()),
        "max_abs_correlation": worst_correlation,
        "max_abs_correlation_pair": worst_pair,
        "correlation": correlation_frame(frame, columns),
        "describe": frame[columns].describe().T,
    }


def format_report(results: list[dict]) -> str:
    """A printable side-by-side report over one or more feature sets."""
    lines: list[str] = []
    for result in results:
        lines.append("")
        lines.append(f"=== feature_set = {result['feature_set']!r} ===")
        lines.append(f"rows: {result['rows']}")
        lines.append("")
        lines.append("Per-column summary:")
        lines.append(
            result["describe"][["mean", "std", "min", "max"]].to_string(
                float_format="{:,.6g}".format
            )
        )
        lines.append("")
        lines.append("Correlation:")
        lines.append(result["correlation"].to_string(float_format="{: .3f}".format))
        lines.append("")
        lines.append("VIF:")
        lines.append(result["vif"].to_string(float_format="{:,.3f}".format))
        lines.append("")
        lines.append(
            f"condition number (standardized): "
            f"{result['condition_number']:,.2f}"
            f"   [concern above {CONDITION_CONCERN:,.0f}]"
        )
        lines.append(
            f"max VIF: {result['max_vif']:,.3f}"
            f"   [concern above {VIF_CONCERN:,.0f}, serious above "
            f"{VIF_SERIOUS:,.0f}]"
        )
        left, right = result["max_abs_correlation_pair"]
        lines.append(
            f"largest |correlation|: {result['max_abs_correlation']:.3f} "
            f"({left} vs {right})"
        )

    if len(results) == 2:
        first, second = results
        lines.append("")
        lines.append("=== comparison ===")
        ratio = first["condition_number"] / second["condition_number"]
        lines.append(
            f"condition number {first['feature_set']} / {second['feature_set']}"
            f" = {ratio:,.2f}x"
        )
        lines.append(
            f"max VIF: {first['max_vif']:,.2f} -> {second['max_vif']:,.2f}"
        )
        lines.append(
            f"largest |correlation|: {first['max_abs_correlation']:.3f} -> "
            f"{second['max_abs_correlation']:.3f}"
        )
    return "\n".join(lines)


def main():
    """Print the levels-vs-scale_free diagnostic for `TICKER`.

    Runs outside the agent lane: it reads `data/cache/`, and downloads if the
    cache is cold, which the GitHub Actions lane cannot reach.
    """
    market_data = download_market_data(CACHE_TICKERS, period=PERIOD)
    prices = market_data[market_data["Ticker"] == TICKER].copy()
    prices = prices.sort_values("Date").reset_index(drop=True)

    # One frame, diagnosed under both sets. `build_features` computes every
    # column whichever set is selected, so the only thing `feature_set`
    # changes here is which rows survive the completeness drop — and the
    # level set is the one with the shorter warm-up, so it is built first and
    # the row counts are printed for the reader to compare.
    print(f"{TICKER} feature diagnostics over {PERIOD}")
    print(f"registered feature sets: {sorted(FEATURE_SETS)}")

    results = []
    for name in ("levels", "scale_free"):
        frame, _task, _horizon = build_features(
            prices, target_kind="return", label_horizon=1, feature_set=name
        )
        results.append(diagnose(frame, name))

    print(format_report(results))


if __name__ == "__main__":
    main()
