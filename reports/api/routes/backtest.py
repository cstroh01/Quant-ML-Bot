"""Backtest tearsheet and 3-way baseline comparison API endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

# Ensure repo root and scripts are in path
REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from data import UnadjustedDataUnavailable, load_unadjusted_for_ticker
from trial_runner import current_ledger
from trial_registry import canonical_config
from ma_crossover_backtest import tearsheet_config
from reports.api.routes.data import get_cache_dir
from reports.api.schemas import BacktestTearsheetResponse

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.get("/tearsheet", response_model=BacktestTearsheetResponse)
def get_backtest_tearsheet(
    ticker: str = Query("AAPL", description="Ticker symbol"),
    short_window: int = Query(10, description="Short MA window"),
    long_window: int = Query(30, description="Long MA window"),
    commission: float = Query(1.0, description="Commission per trade in dollars"),
    slippage_bps: float = Query(5.0, description="Slippage in basis points"),
    cache_dir: Path = Depends(get_cache_dir),
) -> BacktestTearsheetResponse:
    """Serve a verified, already-recorded response; never evaluate or write."""
    try:
        prices = load_unadjusted_for_ticker(ticker, cache_dir / "unadjusted")
    except UnadjustedDataUnavailable as error:
        raise HTTPException(status_code=503, detail={
            "error": "unadjusted_price_data_unavailable",
            "ticker": error.ticker, "reason": error.reason, "check": error.check,
        }) from error

    command = (f"python scripts/ma_crossover_backtest.py --record-trial --ticker {ticker.upper()} "
               f"--short-window {short_window} --long-window {long_window} "
               f"--commission {commission} --slippage-bps {slippage_bps} "
               f'--cache-dir "{cache_dir / "unadjusted"}"')
    unavailable = dict(error="recorded_configuration_unavailable", recording_command=command)
    try:
        ledger = current_ledger(read_only=True)
        config = tearsheet_config(prices, ticker, short_window, long_window, commission, slippage_bps)
        _, hashed = canonical_config(config, root=ledger.root)
        events = ledger.verify()["events"]
        event = next((e for e in reversed(events) if e["config_hash"] == hashed
                      and e["event_type"] == "completed"
                      and e["role"] == ("synthetic_test" if ledger.synthetic else "candidate")), None)
        if event is None:
            raise HTTPException(status_code=409, detail=unavailable)
        payload = event["sidecar"]["metadata"].get("reports", {}).get("tearsheet")
        response = BacktestTearsheetResponse.model_validate(payload)
        if (response.trial_id != event["trial_id"]
                or response.recorded_source_tree_hash != config["model"]["source_tree_hash"]
                or response.source_manifest_sha256 != prices.attrs["source_manifest_sha256"]):
            raise ValueError("recorded response provenance mismatch")
        return response
    except (ValueError, KeyError, OSError) as error:
        raise HTTPException(status_code=409, detail=unavailable) from error
