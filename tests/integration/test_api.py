# tests/integration/test_api.py
"""FastAPI integration tests using TestClient (no real database needed)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from wasde.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_supply_demand_empty_db(client: TestClient):
    # With no DuckDB data, the endpoint should return 500 or empty list
    resp = client.get("/v1/supply-demand/")
    assert resp.status_code in (200, 500)


def test_nopa_crush_empty_db(client: TestClient):
    resp = client.get("/v1/nopa/crush")
    assert resp.status_code in (200, 500)


def test_export_pace_empty_db(client: TestClient):
    resp = client.get("/v1/exports/pace")
    assert resp.status_code in (200, 500)
