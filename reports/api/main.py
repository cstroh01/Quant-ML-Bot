"""FastAPI application entrypoint for Quant-ML-Bot Terminal."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure repo root and scripts are in path
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from reports.api.routes.backtest import router as backtest_router
from reports.api.routes.capital_gate import router as capital_gate_router
from reports.api.routes.data import router as data_router
from reports.api.routes.diagnostics import router as diagnostics_router
from reports.api.routes.ml_rundown import router as ml_rundown_router

# Production build of the web terminal, present only after `npm run build`.
DIST_DIR = REPO_ROOT / "reports" / "web" / "dist"


def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "Quant-ML-Bot Terminal API"}


def create_app(*, dist_dir: Path | None = DIST_DIR) -> FastAPI:
    """Build the API app, serving the built terminal from `dist_dir` if it exists.

    Pass `dist_dir=None` to serve the API only. Tests pass a directory they
    create, so the suite never depends on the gitignored build output
    (spec 018, finding 57).
    """
    app = FastAPI(
        title="Quant-ML-Bot Research & Trading Terminal API",
        description="Institutional-grade quant reporting, feature diagnostics, and backtest API.",
        version="1.0.0",
    )

    # Allow local frontend dev server (Vite on port 5173 or 3000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register route modules
    app.include_router(data_router)
    app.include_router(diagnostics_router)
    app.include_router(backtest_router)
    app.include_router(capital_gate_router)
    app.include_router(ml_rundown_router)
    app.get("/api/health")(health_check)

    if dist_dir is not None and dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="static")
    return app


app = create_app()


def start():
    """Entrypoint for running the API directly via python -m reports.api.main."""
    import uvicorn
    uvicorn.run("reports.api.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    start()
