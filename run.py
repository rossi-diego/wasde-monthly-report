"""
WASDE Monthly Report — Script unico de setup + pipeline.

Uso:
    python run.py

Faz tudo automaticamente:
  1. Instala dependencias que faltam
  2. Baixa dados WASDE do USDA (2010-hoje)
  3. Limpa e valida os dados
  4. Cria tabelas analiticas no DuckDB
  5. Mostra resumo
  6. (Opcional) Inicia servidor API
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
TOTAL_STEPS = 6


def _banner(step: int, msg: str) -> None:
    print(f"\n{'='*55}")
    print(f"  [{step}/{TOTAL_STEPS}] {msg}")
    print(f"{'='*55}\n")


def _setup_path() -> None:
    """Adiciona src/ ao sys.path para importar o pacote wasde."""
    src_dir = str(PROJECT_ROOT / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)


# ---------------------------------------------------------------------------
# Etapa 1 — Dependencias
# ---------------------------------------------------------------------------
def install_deps() -> None:
    """Instala apenas os pacotes que estao faltando."""
    required = {
        "duckdb": "duckdb",
        "pandas": "pandas",
        "httpx": "httpx",
        "tenacity": "tenacity",
        "pydantic": "pydantic",
        "pydantic_settings": "pydantic-settings",
        "pyarrow": "pyarrow",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "lxml": "lxml",
        "requests": "requests",
        "dotenv": "python-dotenv",
    }

    missing: list[str] = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if not missing:
        print("\n  Dependencias ja estao instaladas.")
        return

    _banner(1, "Instalando dependencias que faltam")
    print(f"  Pacotes: {', '.join(missing)}\n")

    cmd = [PYTHON, "-m", "pip", "install", "--user"] + missing
    subprocess.check_call(cmd)

    print("\n  Instalacao concluida! Reiniciando...\n")
    os.execv(PYTHON, [PYTHON] + sys.argv)


# ---------------------------------------------------------------------------
# Etapa 2 — Bronze (download dos CSVs do USDA)
# ---------------------------------------------------------------------------
def run_bronze():
    from wasde.config import Settings, configure_logging

    configure_logging()
    cfg = Settings()

    _banner(2, "Baixando dados WASDE do USDA (2010 ate hoje)")
    print("  Dados publicos — nao precisa de login ou API key.")
    print("  Na primeira vez pode demorar alguns minutos (baixa ~180 relatorios).")
    print("  Se cair por timeout, rode de novo — ele continua de onde parou.\n")

    from wasde.pipelines.bronze.wasde_csv import backfill_wasde

    bronze_dir = cfg.bronze_dir / "wasde"
    paths = backfill_wasde(start_year=cfg.wasde_backfill_start_year, output_dir=bronze_dir)

    if paths:
        print(f"\n  {len(paths)} novos arquivos baixados!")
    else:
        print("\n  Todos os arquivos ja tinham sido baixados anteriormente.")

    return cfg


# ---------------------------------------------------------------------------
# Etapa 3 — Silver (limpeza e validacao)
# ---------------------------------------------------------------------------
def run_silver(cfg) -> None:
    _banner(3, "Limpando e validando os dados (camada Silver)")

    from wasde.pipelines.silver.wasde_csv import transform_wasde

    bronze_dir = cfg.bronze_dir / "wasde"
    silver_path = cfg.silver_dir / "wasde.parquet"

    n_rows = transform_wasde(bronze_dir, silver_path)
    print(f"\n  {n_rows:,} registros validados e salvos.".replace(",", "."))


# ---------------------------------------------------------------------------
# Etapa 4 — Gold (tabelas analiticas no DuckDB)
# ---------------------------------------------------------------------------
def run_gold(cfg) -> None:
    _banner(4, "Construindo tabelas analiticas (camada Gold)")

    from wasde.pipelines.gold.metrics import build_gold

    build_gold(cfg)
    print(f"\n  Banco DuckDB criado em: {cfg.duckdb_path}")


# ---------------------------------------------------------------------------
# Etapa 5 — Resumo
# ---------------------------------------------------------------------------
def print_summary(cfg) -> None:
    import duckdb

    _banner(5, "Resumo dos dados criados")

    con = duckdb.connect(str(cfg.duckdb_path), read_only=True)
    tables = con.execute("SHOW TABLES").fetchall()

    print(f"  {'Tabela':<35} {'Linhas':>10}")
    print(f"  {'-'*35} {'-'*10}")
    for (name,) in tables:
        count = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"  {name:<35} {count:>10,}".replace(",", "."))

    try:
        df = con.execute("""
            SELECT commodity, region, marketing_year,
                   production, ending_stocks, exports
            FROM gold_wasde_latest
            ORDER BY commodity, region, marketing_year DESC
            LIMIT 10
        """).fetchdf()
        print("\n  Amostra — gold_wasde_latest (ultimas posicoes):\n")
        print(df.to_string(index=False))
    except Exception:
        pass

    con.close()


# ---------------------------------------------------------------------------
# Etapa 6 — Servidor API (opcional)
# ---------------------------------------------------------------------------
def ask_api() -> None:
    _banner(6, "Pronto! Deseja iniciar o servidor API?")
    print("  Abre um servidor local para consultar os dados pelo navegador.")
    print("  Documentacao interativa: http://localhost:8000/docs\n")

    try:
        resp = input("  Iniciar servidor? (s/n): ").strip().lower()
    except EOFError:
        return

    if resp in ("s", "sim", "y", "yes"):
        print("\n  Iniciando em http://localhost:8000 ...")
        print("  Pressione Ctrl+C para parar.\n")
        import uvicorn
        uvicorn.run("wasde.api.main:app", host="0.0.0.0", port=8000)
    else:
        print("\n  OK! Para iniciar depois:")
        print(f"    {PYTHON} -m uvicorn wasde.api.main:app --port 8000")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    os.chdir(PROJECT_ROOT)
    _setup_path()

    print("\n" + "=" * 55)
    print("   WASDE Monthly Report — Setup Automatico")
    print("=" * 55)

    try:
        install_deps()       # 1
        cfg = run_bronze()   # 2
        run_silver(cfg)      # 3
        run_gold(cfg)        # 4
        print_summary(cfg)   # 5
        ask_api()            # 6

    except KeyboardInterrupt:
        print("\n\n  Operacao cancelada.")
        sys.exit(0)

    except subprocess.CalledProcessError as exc:
        print(f"\n  Erro ao instalar dependencias: {exc}")
        print("  Verifique sua conexao com a internet e tente novamente.")
        sys.exit(1)

    except Exception as exc:
        msg = str(exc)
        if "ReadTimeout" in msg or "ConnectTimeout" in msg:
            print(f"\n  Timeout ao baixar dados do USDA.")
            print("  Rode o script de novo — ele continua de onde parou.")
        else:
            print(f"\n  Erro: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
