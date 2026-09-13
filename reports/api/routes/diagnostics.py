"""Feature diagnostics and paired significance API endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends, Query

# Ensure repo root and scripts are in path
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from feature_diagnostics import diagnose
from features import build_features, feature_columns
from reports.api.routes.data import get_cache_dir, get_cached_ticker_data
from reports.api.schemas import (
    CollinearityEntry,
    FeatureDiagnosticsResponse,
    SignificanceResponse,
)

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/collinearity", response_model=FeatureDiagnosticsResponse)
def get_collinearity_diagnostics(
    ticker: str = Query("AAPL", description="Ticker symbol"),
    cache_dir: Path = Depends(get_cache_dir),
) -> FeatureDiagnosticsResponse:
    """Return condition numbers, VIFs, and correlations comparing levels vs scale-free."""
    raw_df = get_cached_ticker_data(ticker.upper(), cache_dir)

    # Build features under both sets with label_horizon=1
    df_levels, _, _ = build_features(
        raw_df, target_kind="direction", label_horizon=1, feature_set="levels"
    )
    df_scale_free, _, _ = build_features(
        raw_df, target_kind="direction", label_horizon=1, feature_set="scale_free"
    )

    cols_levels = feature_columns("levels")
    cols_scale_free = feature_columns("scale_free")

    # Diagnose complete rows only: build_features may keep warm-up sessions
    # whose features are not yet defined, and one NaN row breaks the matrix
    # algebra instead of describing the design matrix.
    diag_levels = diagnose(df_levels.dropna(subset=cols_levels), "levels")
    diag_scale_free = diagnose(df_scale_free.dropna(subset=cols_scale_free), "scale_free")

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


SIGNIFICANCE_NOT_COMPUTED = (
    "No saved experiment run is wired to this endpoint, so no p-value is shown for "
    "any ticker. Paired significance results arrive with the experiment run store "
    "(audit work order 3)."
)


@router.get("/significance", response_model=SignificanceResponse)
def get_significance_screening(
    ticker: str = Query("AAPL", description="Ticker symbol")
) -> SignificanceResponse:
    """Paired significance screening: not computed, for every ticker (spec 018, finding 45).

    This endpoint used to return four literal p-values, the same for every
    ticker and different from the saved run. Real values need validated run
    artifacts keyed by ticker and run.
    """
    return SignificanceResponse(ticker=ticker.upper(), reason=SIGNIFICANCE_NOT_COMPUTED)
