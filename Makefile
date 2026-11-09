.PHONY: install demo backfill pipeline test lint format web-dev web-build e2e up clean

PY ?= python

install:            ## Python package + dev tools, and web dependencies
	$(PY) -m pip install -e ".[dev,dbt]" openpyxl
	cd web && npm ci

SITE_URL ?= https://usda-reports.vercel.app

demo:               ## Fastest start: the live site's data (resolved via its catalog.json) + local site
	@url=$$(curl -fsSL "$(SITE_URL)/data/catalog.json" 2>/dev/null | $(PY) -c "import json,sys;print(json.load(sys.stdin)['web_data']['release_url'] or '')" 2>/dev/null); \
	if [ -n "$$url" ]; then echo "data from $$url"; curl -fsSL "$$url" -o /tmp/web-data.tar.gz; \
	else echo "no live catalog.json yet: latest data release"; \
	gh release download --repo rossi-diego/usda-reports-dashboard --pattern web-data.tar.gz --dir /tmp --clobber; fi
	mkdir -p web/public && tar -xzf /tmp/web-data.tar.gz -C web/public
	cd web && npm run dev

backfill:           ## Download every WASDE report since 2010-07 into bronze
	usda-reports backfill

pipeline:           ## silver → gold (dbt) → publish
	usda-reports run

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
