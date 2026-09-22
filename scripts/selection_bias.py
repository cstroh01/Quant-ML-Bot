"""Pure selection statistics on one exact-date, provenance-checked return matrix.

DSR uses raw lifetime N. Moments use daily excess log returns; sample standard
deviation uses ddof=1, skew/kurtosis use standardized central population moments.
The latter is Pearson kurtosis, not excess kurtosis. No clustering is performed.
"""
from __future__ import annotations
import hashlib
import math
import re
from itertools import combinations
from typing import Iterator
import numpy as np
import pandas as pd
from scipy.stats import norm
from constants import TRADING_DAYS_PER_YEAR, RISK_FREE_RATE_ANNUAL
from metrics import mean_log_return_se
from trial_registry import canonical_json, digest, validate_rows

def undefined(reason: str, **fields) -> dict:
    return {"value": None, "reason": reason, **fields}

def _eligible(trial: dict) -> str | None:
    if trial.get("role") != "candidate": return "not_candidate"
    if trial.get("event_type") != "completed": return "not_completed"
    try:
        source = trial["source"]
        if not re.fullmatch(r"[0-9a-f]{40}", source.get("git_sha") or ""): return "source_missing"
        if source.get("workspace_state") not in {"clean", "dirty", "unknown"}: return "source_missing"
        if source["workspace_state"] != "clean" and not re.fullmatch(r"[0-9a-f]{64}", source.get("source_tree_hash") or ""): return "source_missing"
        rows = validate_rows(trial["returns"])
        payload = b"".join(canonical_json(r)+b"\n" for r in rows)
        side = trial["sidecar"]
        if hashlib.sha256(payload).hexdigest() != side["sha256"]: return "return_digest_mismatch"
        meta, config = side["metadata"], trial["config"]
        if meta["frequency"] != "daily" or meta["return_convention"] != "funded_account_log": return "return_convention_ineligible"
        if meta["oos"] is not True or meta["net_costs"] is not True: return "oos_net_costs_required"
        cv, horizon = meta["cv"], config["target"]["horizon"]
        if cv["scheme"] != "purged_embargoed_walk_forward" or cv["folds"] < 1 or horizon < 1 or min(cv["purge"], cv["embargo"]) < horizon: return "invalid_cv"
        if cv != config["cv"]: return "cv_mismatch"
        if meta["costs"] != {"commission": config["commission"], "slippage": config["slippage"]}: return "cost_mismatch"
        if config["slippage"]["model"] != "spread_plus_sqrt_impact": return "realistic_costs_missing"
        if config["data"]["price_basis"] != "unadjusted_dollars" or config["data"]["corporate_actions_verified"] is not True: return "data_provenance_missing"
    except (KeyError, TypeError, ValueError): return "invalid_return_evidence"
    return None

def build_matrix(trials: list[dict], *, family: dict) -> dict:
    """Align exact shared session labels under a preregistered coverage policy."""
    if family.get("alignment") != "exact_intersection" or family.get("objective") != "daily_sharpe": raise ValueError("preregistered family alignment/objective required")
    minimum = family.get("min_coverage")
    if not isinstance(minimum, (float, int)) or not 0 < minimum <= 1: raise ValueError("family min_coverage required")
    included, excluded = [], []
    seen = set()
    for trial in sorted(trials, key=lambda t: t["trial_id"]):
        if trial["trial_id"] in seen: raise ValueError("duplicate matrix trial")
        seen.add(trial["trial_id"])
        reason = "outside_family" if trial.get("family") != family["id"] else _eligible(trial)
        if not reason and trial["config"]["risk_free"] != family["risk_free"]: reason = "risk_free_mismatch"
        if reason: excluded.append({"trial_id": trial["trial_id"], "reason": reason})
        else: included.append(trial)
    maps = [{r["session"]: r["log_return"] for r in t["returns"]} for t in included]
    dates = sorted(set.intersection(*(set(m) for m in maps))) if maps else []
    reason = None
    if not included or not dates: reason = "no_shared_returns"
    elif any(len(dates)/len(m) < minimum for m in maps): reason = "insufficient_shared_coverage"
    if included and any(t["sidecar"]["metadata"]["costs"] != included[0]["sidecar"]["metadata"]["costs"] for t in included): reason = "matrix_cost_mismatch"
    body = {"dates": dates, "columns": [t["trial_id"] for t in included], "values": [[m[d] for m in maps] for d in dates],
            "excluded_trials": excluded, "family": family, "convention": "daily_funded_net_log_returns", "reason": reason,
            "return_digests": {t["trial_id"]: t["sidecar"]["sha256"] for t in included}}
    return {**body, "matrix_hash": digest(body)}

def deflated_sharpe(*, observed_sharpe: float, observations: int, skewness: float,
                   pearson_kurtosis: float, trial_sharpe_std: float, n_current: int) -> dict:
    """Direct Bailey–Lopez de Prado equations (2014), using daily Sharpe inputs."""
    inputs = dict(observed_sharpe=observed_sharpe, observations=observations, skewness=skewness, pearson_kurtosis=pearson_kurtosis, trial_sharpe_std=trial_sharpe_std, n_current=n_current)
    if isinstance(n_current, bool) or not isinstance(n_current, int) or n_current < 1: return undefined("invalid_lifetime_count", inputs=inputs)
    if isinstance(observations, bool) or not isinstance(observations, int) or observations < 2: return undefined("insufficient_observations", inputs=inputs)
    if not all(math.isfinite(v) for v in (observed_sharpe, skewness, pearson_kurtosis)): return undefined("nonfinite_moments", inputs=inputs)
    if not math.isfinite(trial_sharpe_std) or trial_sharpe_std <= 0: return undefined("invalid_trial_dispersion", inputs=inputs)
    denominator = 1-skewness*observed_sharpe+(pearson_kurtosis-1)*observed_sharpe**2/4
    if denominator <= 0 or not math.isfinite(denominator) or pearson_kurtosis < 1: return undefined("invalid_psr_denominator", inputs=inputs)
    gamma = float(np.euler_gamma)
    benchmark = 0. if n_current == 1 else trial_sharpe_std*((1-gamma)*norm.ppf(1-1/n_current)+gamma*norm.ppf(1-1/(n_current*math.e)))
    if not math.isfinite(benchmark): return undefined("invalid_extreme_value_benchmark", inputs=inputs)
    z = (observed_sharpe-benchmark)*math.sqrt(observations-1)/math.sqrt(denominator)
    return {"value": float(norm.cdf(z)), "reason": None, "inputs": inputs, "benchmark_sharpe": float(benchmark), "psr_denominator": denominator, "z": z}

def _excess(matrix: dict) -> np.ndarray:
    rf = matrix["family"]["risk_free"]
    return np.asarray(matrix["values"], dtype=float)-math.log1p(rf["annual_rate"])/rf["days_per_year"]

def matrix_dsr(matrix: dict, *, selected_trial: str, n_current: int) -> dict:
    """Derive every DSR input from the committed matrix except raw lifetime N."""
    if selected_trial not in matrix["columns"]: return undefined("selected_candidate_missing")
    if matrix.get("reason"): return undefined(matrix["reason"])
    x = _excess(matrix)
    if x.shape[0] < 2 or x.shape[1] < 2: return undefined("insufficient_matrix")
    scales = x.std(axis=0, ddof=1)
    if not np.isfinite(x).all() or np.any(scales <= 0): return undefined("zero_or_nonfinite_variance")
    sharpes = x.mean(axis=0)/scales
    j = matrix["columns"].index(selected_trial)
    centered = x[:, j]-x[:, j].mean(); variance = np.mean(centered**2)
    result = deflated_sharpe(observed_sharpe=float(sharpes[j]), observations=len(x), skewness=float(np.mean(centered**3)/variance**1.5), pearson_kurtosis=float(np.mean(centered**4)/variance**2), trial_sharpe_std=float(sharpes.std(ddof=1)), n_current=n_current)
    return {**result, "matrix_hash": matrix["matrix_hash"], "trial_sharpes": sharpes.tolist(), "conventions": {"sharpe_ddof": 1, "moments": "central_population_Pearson", "risk_free": matrix["family"]["risk_free"]}}

def hac_t_stat(returns: list[float], *, horizon: int, lags: int,
               annual_risk_free: float = RISK_FREE_RATE_ANNUAL,
               days_per_year: int = TRADING_DAYS_PER_YEAR) -> dict:
    """Reuse the repository Bartlett/Newey–West mean standard error exactly."""
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1: return undefined("invalid_horizon")
    if isinstance(lags, bool) or not isinstance(lags, int) or lags < horizon-1: return undefined("hac_lag_below_horizon")
    if not math.isfinite(annual_risk_free) or annual_risk_free <= -1 or days_per_year <= 0: return undefined("invalid_risk_free")
    excess = pd.Series(returns, dtype=float)-math.log1p(annual_risk_free)/days_per_year
    se = mean_log_return_se(excess, lags=lags, min_lags=horizon-1)
    if not math.isfinite(se) or se <= 0: return undefined("nonpositive_hac_se", hac_lags=lags)
    return {"value": float(excess.mean()/se), "reason": None, "hac_lags": lags, "standard_error": se, "mean_excess_log_return": float(excess.mean()), "annual_risk_free": annual_risk_free, "days_per_year": days_per_year}


def cscv_blocks(dates: list[str]) -> list[dict]:
    """Partition validated session labels into 16 contiguous, near-equal blocks.

    Extra rows go to the earliest blocks. Bounds are zero-based, stop-exclusive;
    session gaps stay gaps. CSCV is offline analysis, not model walk-forward CV.
    """
    validate_rows([{"session": d, "log_return": 0.} for d in dates])
    if len(dates) < 16:
        raise ValueError("CSCV requires at least 16 observations")
    size, extra = divmod(len(dates), 16)
    blocks, start = [], 0
    for i in range(16):
        stop = start + size + (i < extra)
        blocks.append({"block_id": i, "row_start": start, "row_stop": stop,
                       "first_session": dates[start], "last_session": dates[stop - 1]})
        start = stop
    return blocks


def cscv_splits() -> Iterator[tuple[tuple[int, ...], tuple[int, ...]]]:
    """Enumerate all C(16,8) IS choices and their complements, without sampling."""
    for chosen in combinations(range(16), 8):
        yield chosen, tuple(i for i in range(16) if i not in chosen)


def _pbo_input(matrix: dict) -> tuple[np.ndarray | None, str | None]:
    """Validate the committed matrix before evaluating any split."""
    try:
        x = np.asarray(matrix["values"], dtype=float)
        columns, dates = matrix["columns"], matrix["dates"]
        if x.ndim != 2 or x.shape != (len(dates), len(columns)):
            return None, "invalid_matrix"
        if not all(isinstance(c, str) and c for c in columns) or len(set(columns)) != len(columns):
            return None, "invalid_matrix"
        if not np.isfinite(x).all():
            return None, "nonfinite_matrix"
        if digest({k: v for k, v in matrix.items() if k != "matrix_hash"}) != matrix["matrix_hash"]:
            return None, "matrix_digest_mismatch"
        if matrix.get("reason"):
            return None, matrix["reason"]
        if len(dates) < 16:
            return None, "insufficient_pbo_rows"
        if len(columns) < 2:
            return None, "insufficient_pbo_columns"
        cscv_blocks(dates)
        if matrix["family"]["objective"] != "daily_sharpe" or matrix["convention"] != "daily_funded_net_log_returns":
            return None, "invalid_pbo_objective"
        rf = matrix["family"]["risk_free"]
        if not math.isfinite(rf["annual_rate"]) or rf["annual_rate"] <= -1 or rf["days_per_year"] <= 0:
            return None, "invalid_matrix"
        excess = _excess(matrix)
        if not np.isfinite(excess).all():
            return None, "nonfinite_matrix"
        return excess, None
    except (KeyError, TypeError, ValueError, OverflowError):
        return None, "invalid_matrix"


def _block_moments(x: np.ndarray, blocks: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cache counts, accurate means and centered sums, avoiding raw-square cancellation."""
    counts, means, sums = [], [], []
    with np.errstate(over="ignore", invalid="ignore"):
        for block in blocks:
            part = x[block["row_start"]:block["row_stop"]]
            # Sum scaled observations so a finite mean does not overflow its sum.
            mean = np.array([math.fsum(col / len(part)) for col in part.T])
            counts.append(len(part)); means.append(mean)
            sums.append(np.sum((part - mean) ** 2, axis=0))
    return np.asarray(counts), np.asarray(means), np.asarray(sums)


def _half_sharpes(moments: tuple, chosen: tuple[int, ...]) -> np.ndarray:
    """Combine disjoint block moments into sample daily Sharpe for each column."""
    counts, means, sums = (v[list(chosen)] for v in moments)
    n = int(counts.sum())
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        mean = np.array([math.fsum(col * (counts / n)) for col in means.T])
        variance = np.sum(sums + counts[:, None] * (means - mean) ** 2, axis=0) / (n - 1)
        scores = mean / np.sqrt(variance)
    scores[(variance <= 0) | ~np.isfinite(variance)] = np.nan
    return scores


def _cscv_record(moments: tuple, columns: list[str], split_id: int, chosen: tuple, other: tuple) -> dict:
    """Carry the IS winner into OOS; retain invalid column identities explicitly."""
    inside, outside = _half_sharpes(moments, chosen), _half_sharpes(moments, other)
    bad = ~np.isfinite(inside) | ~np.isfinite(outside)
    record = {"split_id": split_id, "is_blocks": list(chosen), "oos_blocks": list(other),
              "is_sharpes": [float(v) if math.isfinite(v) else None for v in inside],
              "oos_sharpes": [float(v) if math.isfinite(v) else None for v in outside],
              "winner_trial_id": None, "relative_rank": None, "rank_logit": None,
              "degradation": None, "reason": None,
              "invalid_columns": [c for c, invalid in zip(columns, bad) if invalid]}
    if bad.any():
        return {**record, "reason": "undefined_split_sharpe"}
    # Columns are sorted by stable trial ID; argmax resolves exact IS ties.
    winner = int(np.argmax(inside))
    rank = float(np.sum(outside < outside[winner]) + (np.sum(outside == outside[winner]) + 1) / 2)
    relative = rank / (len(columns) + 1)
    return {**record, "winner_trial_id": columns[winner], "relative_rank": relative,
            "rank_logit": math.log(relative / (1 - relative)),
            "degradation": float(inside[winner] - outside[winner])}


def _distribution(values: list[float]) -> dict | None:
    if not values:
        return None
    return {"min": float(np.min(values)), "median": float(np.median(values)),
            "max": float(np.max(values)), "mean": float(np.mean(values))}


def matrix_pbo(matrix: dict) -> dict:
    """Compute exhaustive S=16 CSCV on the existing committed DSR matrix.

    Relative rank is ascending average rank/(M+1); PBO counts logits <= 0.
    Degradation is winner IS Sharpe minus that same column's OOS Sharpe.
    Every split is retained. Any rejected split makes the aggregate undefined;
    summaries over valid splits remain diagnostic only. No lifetime-N input or
    backfill columns are accepted. This function does no IO and sets no gate.
    """
    result = {"value": None, "reason": None, "S": 16, "expected_splits": math.comb(16, 8),
              "matrix_hash": matrix.get("matrix_hash"), "matrix_rows": len(matrix.get("dates", [])),
              "matrix_columns": len(matrix.get("columns", [])), "columns": [], "blocks": [],
              "total_splits": 0, "valid_splits": 0, "rejected_splits": 0, "splits": [],
              "rank_logit_summary": None, "degradation_summary": None,
              "conventions": {"objective": "daily_excess_log_return_sharpe", "sharpe_ddof": 1,
                              "is_ties": "lexicographic_trial_id", "oos_rank": "ascending_average_rank_divided_by_M_plus_1",
                              "pbo_comparator": "rank_logit <= 0", "invalid_splits": "aggregate_undefined",
                              "degradation": "winner_IS_Sharpe_minus_same_column_OOS_Sharpe"}}
    x, reason = _pbo_input(matrix)
    if reason:
        return {**result, "reason": reason}
    columns = sorted(matrix["columns"])
    x = x[:, [matrix["columns"].index(c) for c in columns]]
    blocks = cscv_blocks(matrix["dates"])
    moments = _block_moments(x, blocks)
    records = [_cscv_record(moments, columns, i, a, b) for i, (a, b) in enumerate(cscv_splits())]
    valid = [r for r in records if r["reason"] is None]
    rejected = len(records) - len(valid)
    reason = "no_valid_cscv_splits" if not valid else "rejected_cscv_splits" if rejected else None
    return {**result, "value": sum(r["rank_logit"] <= 0 for r in valid) / len(valid) if not reason else None,
            "reason": reason, "columns": columns, "blocks": blocks, "splits": records,
            "total_splits": len(records), "valid_splits": len(valid), "rejected_splits": rejected,
            "rank_logit_summary": _distribution([r["rank_logit"] for r in valid]),
            "degradation_summary": _distribution([r["degradation"] for r in valid])}
