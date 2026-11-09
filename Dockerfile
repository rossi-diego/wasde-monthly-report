# Pipeline image: bronze → silver → gold (dbt-duckdb) → publish.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[dbt]"
COPY config ./config
COPY dbt ./dbt
# The package is installed non-editable, so point it at the project files explicitly.
ENV USDA_DATA_DIR=/app/data \
    USDA_WEB_DATA_DIR=/app/web/public/data \
    USDA_CONFIG_DIR=/app/config \
    USDA_DBT_DIR=/app/dbt \
    USDA_LOG_JSON=true
ENTRYPOINT ["usda-reports"]
CMD ["--help"]
