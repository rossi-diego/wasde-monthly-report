# src/wasde/api/main.py
"""FastAPI application entry point.

Startup: opens a read-only DuckDB connection shared across all requests.
Shutdown: closes the connection cleanly.

Static frontend (frontend/) is served at the root path.
Interactive API docs are available at /docs.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import duckdb
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from wasde.api.routers import exports, nopa, supply_demand
from wasde.config import configure_logging, settings

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    db_path = settings.duckdb_path
    if db_path.exists():
        app.state.db = duckdb.connect(str(db_path), read_only=True)
    else:
        # Allow startup without data (e.g. in tests)
        app.state.db = duckdb.connect(":memory:")
    yield
    app.state.db.close()


app = FastAPI(
    title="WASDE Dashboard API",
    version="1.0.0",
    description=(
        "REST API for USDA agricultural supply & demand data. "
        "Sources: USDA FAS PSD, NOPA monthly crush, USDA FAS Export Sales."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(supply_demand.router, prefix="/v1/supply-demand", tags=["Supply & Demand"])
app.include_router(nopa.router, prefix="/v1/nopa", tags=["NOPA Crush"])
app.include_router(exports.router, prefix="/v1/exports", tags=["Export Sales"])


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


# Serve static frontend at root (must be last — catches all unmatched paths)
import os
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
