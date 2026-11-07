.PHONY: install demo backfill pipeline test lint format web-dev web-build e2e up clean

PY ?= python

install:            ## Python package + dev tools, and web dependencies
	$(PY) -m pip install -e ".[dev,dbt]" openpyxl
	cd web && npm ci

demo:               ## Fastest start: latest published data + local site (no pipeline run)
	gh release download --repo rossi-diego/wasde-monthly-report --pattern web-data.tar.gz --dir /tmp --clobber
	mkdir -p web/public && tar -xzf /tmp/web-data.tar.gz -C web/public
	cd web && npm run dev

backfill:           ## Download every WASDE report since 2010-07 into bronze
	wasde backfill

pipeline:           ## silver → gold (dbt) → publish
	wasde run

test:
	pytest --cov
	cd web && npx playwright test

lint:
	ruff check src tests && ruff format --check src tests && mypy src
	cd web && npm run lint && npm run typecheck

format:
	ruff format src tests && ruff check --fix src tests

web-dev:
	cd web && npm run dev

web-build:
	cd web && npm run build

up:                 ## Full stack in Docker
	docker compose up --build

clean:
	rm -rf data/silver data/gold data/publish web/public/data web/out web/.next
