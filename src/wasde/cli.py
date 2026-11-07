"""Command-line entry point: ``wasde <command>``."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from wasde.config import get_settings
from wasde.logs import configure_logging, get_logger

app = typer.Typer(add_completion=False, no_args_is_help=True, help="WASDE data pipeline")
log = get_logger("wasde.cli")


@app.callback()
def _main() -> None:
    s = get_settings()
    configure_logging(s.log_level, json=s.log_json or bool(os.environ.get("GITHUB_ACTIONS")))


def _gh_output(**kv: str) -> None:
    """Expose values to later GitHub Actions steps."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            for k, v in kv.items():
                fh.write(f"{k}={v}\n")


def _this_month() -> str:
    return f"{datetime.now(UTC):%Y-%m}"


@app.command()
def backfill(
    seed_dir: Annotated[Path | None, typer.Option(help="Local folder with ESMIS XML files")] = None,
    start: Annotated[str | None, typer.Option(help="First month YYYY-MM")] = None,
    end: Annotated[str | None, typer.Option(help="Last month YYYY-MM")] = None,
) -> None:
    """Ingest every missing report into bronze (CSV 2021+, ESMIS XML otherwise)."""
    from wasde.bronze import BronzeStore
    from wasde.bronze import backfill as run_backfill
    from wasde.manifest import Manifest
    from wasde.net import make_client

    s = get_settings()
    manifest = Manifest.load(s.manifest_path)
    store = BronzeStore(s.bronze_dir, manifest)
    with make_client() as client:
        new = run_backfill(client, store, end or _this_month(), seed_dir, start)
    manifest.save(s.manifest_path)
    log.info("backfill.done", new=len(new), **manifest.summary())


@app.command("refresh-calendar")
def refresh_calendar() -> None:
    """Scrape the official release dates from usda.gov into config/release_calendar.yaml."""
    from wasde.net import get, make_client
    from wasde.sources.calendar import parse_calendar_html, save_calendar

    s = get_settings()
    with make_client() as client:
        resp = get(client, s.usda_calendar_url)
    dates = parse_calendar_html(resp.text if resp else "")
    if not dates:
        log.error("calendar.empty")
        raise typer.Exit(1)
    save_calendar(s.config_dir / "release_calendar.yaml", dates)
    log.info("calendar.saved", dates=len(dates), last=str(dates[-1]))


@app.command()
def detect(
    force_month: Annotated[
        str | None, typer.Option(help="Ingest this YYYY-MM regardless of calendar")
    ] = None,
) -> None:
    """Ingest the latest scheduled report if it is out and not yet in bronze.

    Sets GitHub outputs: ``new_report`` (true/false), ``report_month``, ``overdue``.
    """
    from wasde.bronze import BronzeStore, ingest_month
    from wasde.manifest import Manifest
    from wasde.net import make_client
    from wasde.sources.calendar import is_overdue, latest_due, load_calendar
    from wasde.sources.esmis import list_releases

    s = get_settings()
    manifest = Manifest.load(s.manifest_path)
    now = datetime.now(UTC)
    dates = load_calendar(s.config_dir / "release_calendar.yaml")
    due = latest_due(dates, now)
    month = force_month or (f"{due:%Y-%m}" if due else None)
    overdue = is_overdue(dates, now, set(manifest.reports))
    _gh_output(overdue="true" if overdue else "false")

    if month is None or (month in manifest.reports and not force_month):
        log.info(
            "detect.nothing_new",
            latest_due=str(due),
            have=month in manifest.reports if month else None,
        )
        _gh_output(new_report="false", report_month=month or "")
        return

    store = BronzeStore(s.bronze_dir, manifest)
    with make_client() as client:
        entry = ingest_month(client, store, month, None)
        if entry is None:  # CSV not up yet / not published: try the ESMIS XML
            entry = ingest_month(client, store, month, list_releases(client, max_pages=1))
    if entry is None:
        log.warning("detect.not_yet_available", month=month, overdue=str(overdue))
        _gh_output(new_report="false", report_month=month)
        if overdue:
            raise typer.Exit(2)
        return
    manifest.save(s.manifest_path)
    log.info("detect.ingested", month=month, source=entry.source)
    _gh_output(new_report="true", report_month=month)


@app.command("learn-xml-layout")
def learn_xml_layout(
    seed_dir: Annotated[
        Path, typer.Option(help="Folder with ESMIS XML files overlapping the CSV era")
    ],
) -> None:
    """Re-learn config/xml_layout from months where both CSV and XML exist."""
    from wasde.bronze import find_seed_files
    from wasde.silver.parse_csv import parse_csv
    from wasde.silver.parse_xml import cells_frame, flatten
    from wasde.silver.xml_layout import XmlLayout, learn, learn_units

    s = get_settings()
    csvs = {p.stem: p for p in (s.bronze_dir / "usda_csv").glob("*.csv")}
    seeds = find_seed_files(seed_dir)
    overlap = sorted(set(csvs) & set(seeds))
    if not overlap:
        log.error("layout.no_overlap")
        raise typer.Exit(1)
    pairs = [(cells_frame(flatten(seeds[m]), m), parse_csv(csvs[m], m)) for m in overlap]
    tables = learn(pairs)
    units = learn_units(parse_csv(p, m) for m, p in sorted(csvs.items()))
    folder = s.config_dir / "xml_layout"
    old = XmlLayout.load(folder) if (folder / "positions.csv").exists() else None
    layout = XmlLayout(
        tables["positions"], tables["position_attributes"], tables["attributes"], units
    )
    if old:
        layout.title_aliases, layout.commodity_aliases = old.title_aliases, old.commodity_aliases
    layout.save(folder)
    log.info("layout.saved", months=len(overlap), positions=len(tables["positions"]))


@app.command("build-silver")
def build_silver_cmd() -> None:
    """Parse + harmonize every bronze report into data/silver/wasde.parquet."""
    from wasde.manifest import Manifest
    from wasde.silver.build import build_silver, new_labels_in

    s = get_settings()
    manifest = Manifest.load(s.manifest_path)
    silver = build_silver(s, manifest)
    latest = str(silver["report_month"].max())
    fresh = new_labels_in(s.silver_dir / "unmapped_labels.json", latest)
    if fresh:
        log.error("silver.new_labels", month=latest, labels=fresh)
        typer.echo(
            "New unmapped labels in the latest report; add them to config/mappings.yaml:", err=True
        )
        for label in fresh:
            typer.echo(f"  - {label}", err=True)
        raise typer.Exit(3)


@app.command("build-gold")
def build_gold_cmd() -> None:
    """Run the dbt-duckdb project (models + tests) on top of silver."""
    from wasde.gold import run_dbt

    if run_dbt(get_settings()) != 0:
        raise typer.Exit(4)


@app.command()
def publish(
    tag: Annotated[
        str | None, typer.Option(help="Data release tag recorded in the manifest")
    ] = None,
) -> None:
    """Write web JSON + Excel/Parquet/CSV download files from gold."""
    from wasde.manifest import Manifest
    from wasde.publish.run import publish_all

    s = get_settings()
    manifest = Manifest.load(s.manifest_path)
    publish_all(s, manifest, tag)
    manifest.save(s.manifest_path)


@app.command()
def run(
    tag: Annotated[
        str | None, typer.Option(help="Data release tag recorded in the manifest")
    ] = None,
) -> None:
    """silver → gold → publish."""
    build_silver_cmd()
    build_gold_cmd()
    publish(tag)


@app.command("pack-bronze")
def pack_bronze(out: Path) -> None:
    """Archive bronze files (+ manifest) for the GitHub data release."""
    from wasde.bronze import pack

    pack(get_settings().bronze_dir, out)


@app.command("unpack-bronze")
def unpack_bronze(archive: Path) -> None:
    from wasde.bronze import unpack

    unpack(archive, get_settings().bronze_dir)


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
