# src/wasde/api/main.py
"""FastAPI application entry point.

Uses connection-per-request pattern for DuckDB (avoids concurrency bugs).
Static frontend (frontend/) is served at the root path.
Interactive API docs are available at /docs.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from wasde.api.routers import exports, nopa, supply_demand, wasde
from wasde.config import configure_logging

configure_logging()

app = FastAPI(
    title="WASDE Dashboard API",
    version="1.0.0",
    description=(
        "REST API for USDA agricultural supply & demand data. "
        "Sources: USDA FAS PSD, NOPA monthly crush, USDA FAS Export Sales."
    ),
)

_cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(
    supply_demand.router, prefix="/v1/supply-demand", tags=["Supply & Demand"]
)
app.include_router(nopa.router, prefix="/v1/nopa", tags=["NOPA Crush"])
app.include_router(exports.router, prefix="/v1/exports", tags=["Export Sales"])
app.include_router(wasde.router, prefix="/v1/wasde", tags=["WASDE"])


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


# Serve static frontend at root (must be last — catches all unmatched paths)
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
