"""049 T012: signal-decay monitor for the paper loop's trend state.

Per ticker, how often the long state of ``paper_targets``' rule (10-day SMA
above 30-day SMA at close t) was followed by an up move r(t -> t+1), as known
at the close of an ``as_of`` session, beside a fair coin and a seeded random
baseline at matched frequency. Built on ``paper_monitor.monitor`` (spec 049
T012), which owns the state and next-session outcome per decision session.

Point-in-time: the hit of decision t matures at t+1's close, so a value
reported as of s counts only decisions with t+1 <= s. The panel is cut at s
before anything is computed, and only matured rows are read.

Definitions: a flat state (no position) predicts nothing and is excluded, not
counted as a miss; a zero or missing next return is excluded. Direction only:
no P&L, cost, Sharpe or edge claim. Nothing here is a performance result.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from _project import project_root

if str(project_root()) not in sys.path:
    sys.path.insert(0, str(project_root()))

from scripts import paper_monitor  # noqa: E402
from scripts.paper_report import LIMITATIONS  # noqa: E402

DECAY_NOTE = (
    "Direction diagnostic of the SMA 10/30 reference rule (spec 049 D-4), not a validated strategy. "
    "The binomial p-value assumes independent sessions, which serial dependence violates, and is not "
    "corrected for testing many tickers or as-of dates."
)


def binomial_two_sided(hits: int, n: int) -> float:
    """Exact two-sided p-value of ``hits`` successes in ``n`` fair coin flips; NaN if n is 0."""
    if not 0 <= hits <= n:
        raise ValueError(f"need 0 <= hits <= n, got hits={hits}, n={n}")
    if n == 0:
        return math.nan
    tail = sum(math.comb(n, i) for i in range(min(hits, n - hits) + 1))
    return min(1.0, 2 * tail / 2 ** n)


def _positive_int(name: str, value: object, low: int = 1) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < low:
        raise ValueError(f"{name} must be an integer >= {low}, got {value!r}")


def decay_table(closes: pd.DataFrame, *, as_of, source: str, seed: int, window: int = 63,
                min_obs: int = 20, threshold: float = 0.5, n_draws: int = 200) -> pd.DataFrame:
    """One row per ticker: the trend state's hit rate as known at ``as_of``'s close.

    The window is the last ``window`` matured decision sessions. ``Decay`` is
    true when at least ``min_obs`` long observations give a hit rate strictly
    below ``threshold``. The random baseline places the same number of long
    calls uniformly, without replacement, among the window's known-outcome
    sessions, ``n_draws`` times, from ``np.random.default_rng([seed, column])``;
    global random state is never read or advanced.
    """
    for name, value, low in (("window", window, 1), ("min_obs", min_obs, 1),
                             ("n_draws", n_draws, 2), ("seed", seed, 0)):
        _positive_int(name, value, low)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold must lie in [0, 1], got {threshold!r}")
    label = pd.Timestamp(as_of)
    if label not in closes.index:
        raise ValueError(f"as_of {label.date()} is not a session in the panel")
    rows = paper_monitor.monitor(closes.loc[:label], source=source, window=1)
    matured = rows[rows["Outcome_Session"] <= label]
    out = {}
    for column, ticker in enumerate(closes.columns):
        recent = matured.xs(ticker, level="Ticker").iloc[-window:]
        move = recent["Next_Return"]
        known = np.isfinite(move) & (move != 0.0)
        longs = known & (recent["Confidence"] == 1.0)
        n, hits = int(longs.sum()), int((move[longs] > 0).sum())
        ups = (move[known] > 0).to_numpy()
        rng = np.random.default_rng([seed, column])
        draws = [ups[rng.choice(len(ups), size=n, replace=False)].mean() for _ in range(n_draws)] if n else []
        out[ticker] = {
            "As_Of": label, "Window_Sessions": len(recent), "Long_Obs": n, "Hits": hits,
            "Hit_Rate": hits / n if n else math.nan, "Coin_Flip": 0.5,
            "P_Value_Two_Sided": binomial_two_sided(hits, n),
            "Random_Mean": float(np.mean(draws)) if draws else math.nan,
            "Random_Std": float(np.std(draws, ddof=1)) if draws else math.nan,
            "Decay": bool(n >= min_obs and hits / n < threshold),
        }
    table = pd.DataFrame.from_dict(out, orient="index")
    table.index.name = "Ticker"
    table.attrs.update(source=source, input_sha256=rows.attrs["input_sha256"],
                       implementation_sha256=rows.attrs["implementation_sha256"], seed=seed,
                       n_draws=n_draws, window_sessions=window, min_obs=min_obs, threshold=threshold)
    return table


def render(table: pd.DataFrame) -> str:
    """Markdown table with provenance, and the Rule 16 block at top and bottom."""
    a = table.attrs
    block = [f"> {LIMITATIONS}", ">", f"> {DECAY_NOTE}"]
    as_of = pd.Timestamp(table["As_Of"].iloc[0]).date() if len(table) else "no tickers"
    lines = ["# Trend-state signal decay", "", *block, "",
             f"Source: {a['source']} (input sha256 {a['input_sha256']})",
             f"As of the close of {as_of}; window up to {a['window_sessions']} matured sessions; "
             f"min_obs {a['min_obs']}; threshold {a['threshold']}; seed {a['seed']}; {a['n_draws']} random draws.",
             "", "| Ticker | Long obs | Hits | Hit rate | Coin flip | p (two-sided) | Random mean | Random std | Flag |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for ticker, r in table.iterrows():
        cells = [r.Long_Obs, r.Hits, *(f"{v:.4f}" for v in (r.Hit_Rate, r.Coin_Flip, r.P_Value_Two_Sided,
                                                             r.Random_Mean, r.Random_Std))]
        lines.append(f"| {ticker} | " + " | ".join(map(str, cells)) + f" | {'DECAY' if r.Decay else 'no'} |")
    return "\n".join([*lines, "", *block]) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Read a wide close panel CSV (session label, one column per ticker) and print the table."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("panel", type=Path)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--window", type=int, default=63)
    parser.add_argument("--min-obs", type=int, default=20)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args(argv)
    try:
        closes = pd.read_csv(args.panel, index_col=0, parse_dates=True)
        table = decay_table(closes, as_of=args.as_of, source=str(args.panel.resolve()), seed=args.seed,
                            window=args.window, min_obs=args.min_obs, threshold=args.threshold)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(render(table), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
