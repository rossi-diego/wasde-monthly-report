"""Command-line entry point: ``usda-reports <command>`` (``wasde`` is a deprecated alias)."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from usda_reports.core.config import LEGACY_ENV_USED, get_settings
from usda_reports.core.logs import configure_logging, get_logger

if TYPE_CHECKING:
    from usda_reports.bronze.store import BronzeStore
    from usda_reports.core.config import Settings
    from usda_reports.core.manifest import Manifest

app = typer.Typer(add_completion=False, no_args_is_help=True, help="USDA reports data pipeline")
log = get_logger("usda_reports.cli")

WASDE = "wasde"


@app.callback()
def _main() -> None:
    s = get_settings()
    configure_logging(s.log_level, json=s.log_json or bool(os.environ.get("GITHUB_ACTIONS")))
    if LEGACY_ENV_USED:
        log.warning(
            "config.deprecated_env_prefix",
            variables=LEGACY_ENV_USED,
            hint="rename WASDE_* to USDA_*; the old prefix is dropped in the next release",
        )


def _gh_output(**kv: str) -> None:
    """Expose values to later GitHub Actions steps."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            for k, v in kv.items():
                fh.write(f"{k}={v}\n")


def _this_month() -> str:
    return f"{datetime.now(UTC):%Y-%m}"


def _store(report_id: str = WASDE) -> tuple[Settings, Manifest, BronzeStore]:
    from usda_reports.bronze.store import BronzeStore
    from usda_reports.core.manifest import Manifest
    from usda_reports.core.registry import load_registry

    s = get_settings()
    manifest = Manifest.load(s.manifest_path)
    cfg = load_registry(s.config_dir).get(report_id)
    return s, manifest, BronzeStore(s.bronze_dir, manifest, report_id, cfg.release_time_et)


@app.command()
def backfill(
    seed_dir: Annotated[Path | None, typer.Option(help="Local folder with ESMIS XML files")] = None,
    start: Annotated[str | None, typer.Option(help="First month YYYY-MM")] = None,
    end: Annotated[str | None, typer.Option(help="Last month YYYY-MM")] = None,
) -> None:
    """Ingest every missing release of every enabled report into bronze."""
    from usda_reports.bronze.store import BronzeStore
    from usda_reports.core.manifest import Manifest
    from usda_reports.core.net import make_client
    from usda_reports.core.registry import load_registry

    s = get_settings()
    manifest = Manifest.load(s.manifest_path)
    new: dict[str, int] = {}
    with make_client() as client:
        for spec in load_registry(s.config_dir).enabled_specs(s):
            store = BronzeStore(s.bronze_dir, manifest, spec.report_id, spec.config.release_time_et)
            keys = spec.backfill(
                client, store, end or _this_month(), seed_dir=seed_dir, start=start
            )
            new[spec.report_id] = len(keys)
    manifest.save(s.manifest_path)
    log.info("backfill.done", new=new, **manifest.summary())


@app.command("refresh-calendar")
def refresh_calendar() -> None:
    """Scrape the official WASDE release dates from usda.gov into config/calendars/wasde.yaml."""
    from usda_reports.core.calendar import save_calendar
    from usda_reports.core.net import get, make_client
    from usda_reports.reports.wasde.sources.calendar_page import parse_calendar_html

    s = get_settings()
    with make_client() as client:
        resp = get(client, s.usda_calendar_url)
    dates = parse_calendar_html(resp.text if resp else "")
    if not dates:
        log.error("calendar.empty")
        raise typer.Exit(1)
    save_calendar(s.calendars_dir / f"{WASDE}.yaml", dates)
    log.info("calendar.saved", dates=len(dates), last=str(dates[-1]))


@app.command()
def detect(
    force_month: Annotated[
        str | None, typer.Option(help="Ingest this YYYY-MM regardless of calendar")
    ] = None,
) -> None:
    """Ingest the latest scheduled WASDE report (or a revised edition) if it is out.

    Sets GitHub outputs ``new_report`` (true/false), ``report_month`` and ``problems``.
    Exit code 2 = a watchdog fired (overdue report, stale data, empty calendar);
    exit code 1 = a forced month could not be found.
    """
    from usda_reports.core.calendar import load_calendar
    from usda_reports.core.net import make_client
    from usda_reports.detect import DetectError, run_detect

    s, manifest, store = _store()
    dates = load_calendar(s.calendars_dir / f"{WASDE}.yaml")
    try:
        with make_client() as client:
            result = run_detect(client, store, dates, datetime.now(UTC), force_month)
    except DetectError as exc:
        log.error("detect.failed", error=str(exc))
        raise typer.Exit(1) from exc
    if result.new_report:
        manifest.save(s.manifest_path)
    _gh_output(
        new_report="true" if result.new_report else "false",
        report_month=max(result.ingested) if result.ingested else (result.due_month or ""),
        problems="; ".join(result.problems),
    )
    log.info(
        "detect.done", ingested=result.ingested, due=result.due_month, problems=result.problems
    )
    if result.problems:
        for p in result.problems:
            typer.echo(f"::error::{p}", err=True)
        raise typer.Exit(2)


@app.command("learn-xml-layout")
def learn_xml_layout(
    seed_dir: Annotated[
        Path, typer.Option(help="Folder with ESMIS XML files overlapping the CSV era")
    ],
) -> None:
    """Re-learn config/reports/wasde/xml_layout from months where both CSV and XML exist."""
    from usda_reports.reports.wasde.ingest import find_seed_files
    from usda_reports.reports.wasde.parse_csv import parse_csv
    from usda_reports.reports.wasde.parse_xml import cells_frame, flatten
    from usda_reports.reports.wasde.xml_layout import XmlLayout, learn, learn_units

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
    folder = s.report_config_dir(WASDE) / "xml_layout"
    old = XmlLayout.load(folder) if (folder / "positions.csv").exists() else None
    layout = XmlLayout(
        tables["positions"], tables["position_attributes"], tables["attributes"], units
    )
    if old:
        layout.title_aliases, layout.commodity_aliases = old.title_aliases, old.commodity_aliases
    layout.save(folder)
    log.info("layout.saved", months=len(overlap), positions=len(tables["positions"]))


@app.command("build-silver")
def build_silver_cmd(
    report: Annotated[str | None, typer.Option(help="Only this report_id")] = None,
) -> None:
    """Full reparse of bronze into data/silver/<report_id>.parquet for every enabled report."""
    from usda_reports.core.manifest import Manifest
    from usda_reports.silver.build import build_all

    s = get_settings()
    manifest = Manifest.load(s.manifest_path)
    result = build_all(s, manifest, only=report)
    if result.alerts:
        for rid, labels in result.alerts.items():
            log.error("silver.new_labels", report=rid, labels=labels)
            typer.echo(
                f"New unmapped labels in the latest {rid} release; add them to "
                f"config/reports/{rid}/mappings.yaml:",
                err=True,
            )
            for label in labels:
                typer.echo(f"  - {label}", err=True)
        raise typer.Exit(3)


@app.command("build-gold")
def build_gold_cmd() -> None:
    """Run the dbt-duckdb project (seeds, models + tests) on top of silver."""
    from usda_reports.gold import run_dbt

    if run_dbt(get_settings()) != 0:
        raise typer.Exit(4)


@app.command()
def publish(
    tag: Annotated[
        str | None, typer.Option(help="Data release tag recorded in the manifest")
    ] = None,
) -> None:
    """Write web JSON, Excel and the versioned Parquet/CSV catalogue from gold."""
    from usda_reports.core.manifest import Manifest
    from usda_reports.publish.run import publish_all

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
    build_silver_cmd(report=None)
    build_gold_cmd()
    publish(tag)


@app.command("latest-key")
def latest_key(report: Annotated[str, typer.Argument()] = WASDE) -> None:
    """Print the newest ingested release key of a report (reads v1 and v2 manifests)."""
    from usda_reports.core.manifest import Manifest

    keys = list(Manifest.load(get_settings().manifest_path).report(report).ok())
    if not keys:
        raise typer.Exit(1)
    typer.echo(keys[-1])


@app.command("migrate-manifest")
def migrate_manifest() -> None:
    """Rewrite data/manifest.json in the current schema (v1 → v2 is lossless)."""
    from usda_reports.core.manifest import Manifest

    s = get_settings()
    Manifest.load(s.manifest_path).save(s.manifest_path)


@app.command("pack-shards")
def pack_shards_cmd(
    out_dir: Annotated[Path, typer.Option(help="Where to write new shard tarballs")] = Path(
        "data/shards"
    ),
) -> None:
    """Pack bronze files not yet in the bronze-store into new delta shards (updates manifest).

    Sets GitHub output ``shards`` (space-separated file names; empty when nothing is new).
    """
    from usda_reports.bronze.shards import pack_shards
    from usda_reports.core.manifest import Manifest

    s = get_settings()
    manifest = Manifest.load(s.manifest_path)
    written = pack_shards(s.bronze_dir, manifest, out_dir)
    manifest.save(s.manifest_path)
    _gh_output(shards=" ".join(p.name for p in written))
    log.info("bronze.pack_shards", shards=[p.name for p in written])


@app.command("required-shards")
def required_shards_cmd() -> None:
    """Print the bronze-store shards the manifest needs, one per line (empty = none)."""
    from usda_reports.bronze.shards import required_shards
    from usda_reports.core.manifest import Manifest

    for name in required_shards(Manifest.load(get_settings().manifest_path)):
        typer.echo(name)


@app.command("unpack-shards")
def unpack_shards_cmd(shard_dir: Path) -> None:
    """Restore bronze from downloaded bronze-store shards (sha256-verified)."""
    from usda_reports.bronze.shards import ShardError, unpack_shards
    from usda_reports.core.manifest import Manifest

    s = get_settings()
    try:
        unpack_shards(shard_dir, s.bronze_dir, Manifest.load(s.manifest_path))
    except ShardError as exc:
        log.error("bronze.unpack_shards_failed", error=str(exc))
        raise typer.Exit(1) from exc


@app.command("pack-bronze")
def pack_bronze(out: Path) -> None:
    """Archive every bronze file into one tarball (legacy single-asset format)."""
    from usda_reports.bronze.store import pack

    pack(get_settings().bronze_dir, out)


@app.command("unpack-bronze")
def unpack_bronze(archive: Path) -> None:
    """Restore bronze from a legacy single tarball (``bronze.tar.gz`` of a data-* release)."""
    from usda_reports.bronze.store import unpack

    unpack(archive, get_settings().bronze_dir)


def main() -> None:  # pragma: no cover
    app()


def legacy_main() -> None:  # pragma: no cover
    """``wasde`` entry point, kept for one release."""
    typer.echo("note: `wasde` is deprecated; use `usda-reports` (same commands).", err=True)
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
