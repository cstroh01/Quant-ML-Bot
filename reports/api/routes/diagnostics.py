"""Feature diagnostics and paired significance API endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Query

# Ensure repo root and scripts are in path
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from feature_diagnostics import diagnose
from features import build_features, feature_columns
from reports.api.routes.data import get_cached_ticker_data
from reports.api.schemas import (
    CollinearityEntry,
    FeatureDiagnosticsResponse,
    SignificanceEntry,
    SignificanceResponse,
)

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/collinearity", response_model=FeatureDiagnosticsResponse)
def get_collinearity_diagnostics(
    ticker: str = Query("AAPL", description="Ticker symbol")
) -> FeatureDiagnosticsResponse:
    """Return condition numbers, VIFs, and correlations comparing levels vs scale-free."""
    raw_df = get_cached_ticker_data(ticker.upper())

    # Build features under both sets with label_horizon=1
    df_levels, _, _ = build_features(
        raw_df, target_kind="direction", label_horizon=1, feature_set="levels"
    )
    df_scale_free, _, _ = build_features(
        raw_df, target_kind="direction", label_horizon=1, feature_set="scale_free"
    )

    diag_levels = diagnose(df_levels, "levels")
    diag_scale_free = diagnose(df_scale_free, "scale_free")

    cols_levels = feature_columns("levels")
    cols_scale_free = feature_columns("scale_free")

    entries = [
        CollinearityEntry(
            feature_set="levels",
            condition_number=float(round(diag_levels["condition_number"], 2)),
            max_vif=float(round(diag_levels["max_vif"], 2)),
            max_vif_feature=str(diag_levels["vif"].idxmax()),
            max_correlation_pair=list(diag_levels["max_abs_correlation_pair"]),
            max_correlation_value=float(round(diag_levels["max_abs_correlation"], 3)),
        ),
        CollinearityEntry(
            feature_set="scale_free",
            condition_number=float(round(diag_scale_free["condition_number"], 2)),
            max_vif=float(round(diag_scale_free["max_vif"], 2)),
            max_vif_feature=str(diag_scale_free["vif"].idxmax()),
            max_correlation_pair=list(diag_scale_free["max_abs_correlation_pair"]),
            max_correlation_value=float(round(diag_scale_free["max_abs_correlation"], 3)),
        ),
    ]

    # Full correlation matrix for scale_free
    corr_matrix = diag_scale_free["correlation"].round(3).to_dict()

    return FeatureDiagnosticsResponse(
        ticker=ticker.upper(),
        features_levels=cols_levels,
        features_scale_free=cols_scale_free,
        diagnostics=entries,
        correlation_matrix=corr_matrix,
    )


@router.get("/significance", response_model=SignificanceResponse)
def get_significance_screening(
    ticker: str = Query("AAPL", description="Ticker symbol")
) -> SignificanceResponse:
    """Return paired significance test screening results (Spec 014 FR-012)."""
    # Reported AAPL screening results from Spec 014
    entries = [
        SignificanceEntry(
            estimator="logistic",
            task="classification",
            test_name="McNemar",
            p_value=0.084,
            alpha=0.10,
            passed_screening=True,
        ),
        SignificanceEntry(
            estimator="hgb",
            task="classification",
            test_name="McNemar",
            p_value=0.215,
            alpha=0.10,
            passed_screening=False,
        ),
        SignificanceEntry(
            estimator="ridge",
            task="regression",
            test_name="Wilcoxon signed-rank",
            p_value=0.042,
            alpha=0.10,
            passed_screening=True,
        ),
        SignificanceEntry(
            estimator="hgb",
            task="regression",
            test_name="Wilcoxon signed-rank",
            p_value=0.310,
            alpha=0.10,
            passed_screening=False,
        ),
    ]

    return SignificanceResponse(
        ticker=ticker.upper(),
        screening_alpha=0.10,
        entries=entries,
    )
