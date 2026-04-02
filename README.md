# WASDE Dashboard

Production-grade data pipeline and REST API for USDA agricultural supply & demand data.

Ingests three data sources monthly — USDA FAS PSD (supply/demand), NOPA crush reports, and USDA export sales — through a Bronze → Silver → Gold medallion architecture, storing the final layer in DuckDB and serving it via FastAPI.

## Stack

| Layer | Technology |
|---|---|
| Orchestration | Apache Airflow (TaskFlow API) |
| Storage | Parquet (Bronze/Silver) + DuckDB (Gold) |
| API | FastAPI |
| Frontend | HTML + Tailwind CSS + Chart.js |
| Containerisation | Docker Compose |
| CI | GitHub Actions |

## Data Sources

| Source | What | Frequency |
|---|---|---|
| USDA FAS PSD API | Supply & demand for wheat, corn, soybeans, soybean meal, soybean oil | Monthly |
| NOPA | US soybean crush volume + oil stocks | Monthly |
| USDA FAS Export Sales | Weekly export sales by commodity + destination | Weekly |

## Quick Start

The easiest way to get started — downloads data, builds tables, and starts the API:

```bash
git clone https://github.com/rossi-diego/wasde-monthly-report.git
cd wasde-monthly-report
python run.py
```

> On Windows you can also double-click `iniciar.bat`.

The script automatically installs dependencies, downloads WASDE reports from the USDA (public data, no API key needed), processes them through the Bronze → Silver → Gold pipeline, and optionally starts the API server.

## Manual Setup

### 1. Install

```bash
pip install uv
uv pip install -e ".[dev,pipelines]"
```

### 2. Configure (optional)

```bash
cp .env.example .env
# Add your USDA_PSD_KEY (free at https://api.data.gov/signup/)
# Only needed for the PSD pipeline — WASDE works without it
```

### 3. Run

```bash
make run-api        # starts FastAPI on http://localhost:8000
make up             # starts Airflow + FastAPI via Docker Compose
```

## Project Structure

```
dags/                   Airflow DAG
src/wasde/
  config.py             Pydantic settings
  models/               Pydantic schemas (PSD, NOPA, exports)
  pipelines/
    bronze/             Raw ingestion → Parquet
    silver/             Validation + cleaning → Parquet
    gold/               Aggregation → DuckDB
  api/                  FastAPI app + routers
frontend/               Single-page HTML/JS dashboard
tests/                  Unit + integration tests
data/                   Local only (gitignored) — rebuilt by pipeline
```

## API

Interactive docs available at `http://localhost:8000/docs` when running locally.

Key endpoints:

```
GET /health
GET /v1/supply-demand?commodity=Soybeans&marketing_year=2024
GET /v1/supply-demand/stock-to-use?commodity=Soybeans
GET /v1/supply-demand/revisions?commodity=Soybeans&marketing_year=2024
GET /v1/nopa/crush?months=24
GET /v1/nopa/crush-margin?months=24
GET /v1/exports/pace?commodity=Soybeans&marketing_year=2024
```

## Author

Diego Rossi Santanna — [linkedin.com/in/diego-rossi-santanna](https://www.linkedin.com/in/diego-rossi-santanna/)
