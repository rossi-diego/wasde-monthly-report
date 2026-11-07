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
ENV WASDE_DATA_DIR=/app/data \
    WASDE_WEB_DATA_DIR=/app/web/public/data \
    WASDE_CONFIG_DIR=/app/config \
    WASDE_DBT_DIR=/app/dbt \
    WASDE_LOG_JSON=true
ENTRYPOINT ["wasde"]
CMD ["--help"]
