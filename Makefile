.PHONY: install lint format test run-api up

install:
	pip install uv && uv pip install -e ".[dev,pipelines]"

lint:
	ruff check src/ tests/ dags/
	ruff format --check src/ tests/ dags/

format:
	ruff format src/ tests/ dags/
	ruff check --fix src/ tests/ dags/

test:
	pytest tests/ -v --tb=short --cov=src/wasde --cov-report=term-missing

run-api:
	uvicorn wasde.api.main:app --reload --port 8000

up:
	docker compose up --build
