# WASDE Dashboard

[![CI](https://github.com/rossi-diego/wasde-monthly-report/actions/workflows/ci.yml/badge.svg)](https://github.com/rossi-diego/wasde-monthly-report/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**[Live Demo](https://wasde-dashboard.onrender.com)** | **[API Docs](https://wasde-dashboard.onrender.com/docs)**

Production-grade data pipeline and REST API for USDA agricultural supply & demand data. Ingests three sources monthly through a Bronze → Silver → Gold medallion architecture, stores the final layer in DuckDB, and serves it via FastAPI.

---

## Architecture

```
DATA SOURCES                  BRONZE              SILVER              GOLD               API
                              (raw Parquet)       (cleaned Parquet)   (DuckDB tables)    (FastAPI)

USDA FAS PSD API ──────────►  psd.parquet   ───►  psd.parquet   ───►  gold_supply_demand
  (supply/demand)                                                     gold_export_pace   ──► /v1/supply-demand
                                                                                          ──► /v1/exports/pace
NOPA Monthly Crush ────────►  nopa.parquet  ───►  nopa.parquet  ───►  gold_nopa_crush    ──► /v1/nopa/crush

USDA FAS Export Sales ─────►  exports.parquet ─►  exports.parquet ─►  gold_export_pace   ──► /v1/exports/pace

USDA WASDE CSV ────────────►  wasde/*.parquet ─►  wasde.parquet ───►  gold_wasde_latest  ──► /v1/wasde
                                                                      gold_wasde_revisions
```

---

## Stack

| Layer | Technology |
|---|---|
| Orchestration | Apache Airflow (TaskFlow API) + GitHub Actions |
| Storage | Parquet (Bronze/Silver) + DuckDB (Gold) |
| API | FastAPI + Pydantic v2 |
| Frontend | HTML + Tailwind CSS + Chart.js |
| Container | Docker Compose |
| CI | GitHub Actions (ruff, mypy, pytest, coverage) |
| Hosting | Render (free tier) |

---

## Data Sources

| Source | What | Frequency |
|---|---|---|
| USDA FAS PSD API | Supply & demand for wheat, corn, soybeans, soybean meal, soybean oil | Monthly |
| NOPA | US soybean crush volume + oil stocks | Monthly |
| USDA FAS Export Sales | Weekly export sales by commodity + destination | Weekly |
| USDA WASDE CSV | World agricultural supply & demand estimates | Monthly |

---

## Quick Start

```bash
git clone https://github.com/rossi-diego/wasde-monthly-report.git
cd wasde-monthly-report
python run.py
```

The script installs dependencies, downloads WASDE data from the USDA (public, no API key needed), processes it through Bronze → Silver → Gold, and starts the API.

### Manual Setup

```bash
pip install uv
uv pip install -e ".[dev]"
cp .env.example .env    # add USDA_PSD_KEY (free at https://api.data.gov/signup/)
make run-api            # starts FastAPI on http://localhost:8000
```

### Docker

```bash
docker compose up       # Airflow + FastAPI
```

### Run Pipeline Manually

Go to GitHub → Actions → **Monthly Data Update** → **Run workflow**. The pipeline fetches all sources, processes through Bronze → Silver → Gold, and commits the updated DuckDB.

---

## API Endpoints

Interactive docs at `/docs` when running.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/supply-demand` | Supply & demand by commodity/country/year |
| `GET` | `/v1/supply-demand/stock-to-use` | Stock-to-use ratio time series |
| `GET` | `/v1/supply-demand/revisions` | Ending stocks revision history |
| `GET` | `/v1/supply-demand/download` | Download as CSV or XLSX |
| `GET` | `/v1/nopa/crush` | Monthly soybean crush volume |
| `GET` | `/v1/nopa/crush/download` | Download crush data |
| `GET` | `/v1/exports/pace` | Export pace vs USDA target |
| `GET` | `/v1/exports/pace/download` | Download export pace |
| `GET` | `/v1/wasde` | Latest WASDE estimates |

### Download Data

All data routes support CSV and XLSX download:

```
GET /v1/supply-demand/download?commodity=Soybeans&country=World&format=csv
GET /v1/nopa/crush/download?format=xlsx
GET /v1/exports/pace/download?commodity=Corn&format=csv
```

---

## Project Structure

```
dags/                       Airflow DAG (monthly pipeline)
src/wasde/
  config.py                 Pydantic settings
  models/                   Pydantic schemas (PSD, NOPA, exports)
  pipelines/
    bronze/                 Raw ingestion → Parquet
    silver/                 Validation + cleaning → Parquet
    gold/                   Aggregation → DuckDB
  api/
    main.py                 FastAPI app
    download.py             CSV/XLSX streaming helper
    routers/                Endpoint modules
frontend/                   Single-page HTML/JS dashboard
tests/                      Unit + integration tests
```

---

## Deploy to Render

1. Go to [render.com](https://render.com) → **New Web Service** → connect the repo
2. Set **Dockerfile Path:** `./Dockerfile.api`
3. Add env var: `USDA_PSD_KEY` from [api.data.gov](https://api.data.gov/signup/)
4. Deploy

The `render.yaml` Blueprint also supports one-click deployment.

---

## Author

Diego Rossi — Market Risk & Data Engineering
