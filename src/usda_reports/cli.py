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
    from usda_reports.detect import WeeklyDue
    from usda_reports.reports.base import ReportSpec

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
    report: Annotated[str | None, typer.Option(help="Only this report_id")] = None,
) -> None:
    """Ingest every missing release of every enabled report into bronze."""
    from usda_reports.bronze.store import BronzeStore
    from usda_reports.core.manifest import Manifest
    from usda_reports.core.net import make_client
    from usda_reports.core.registry import load_registry
    from usda_reports.reports.export_sales.source import MissingKeyError

    s = get_settings()
    manifest = Manifest.load(s.manifest_path)
    new: dict[str, int] = {}
    failed: list[str] = []
    with make_client() as client:
        for spec in load_registry(s.config_dir).enabled_specs(s):
            if report and spec.report_id != report:
                continue
            store = BronzeStore(s.bronze_dir, manifest, spec.report_id, spec.config.release_time_et)
            try:
                keys = spec.backfill(
                    client, store, end or _this_month(), seed_dir=seed_dir, start=start
                )
            except MissingKeyError as exc:
                # Per-report isolation: WASDE needs no key; Export Sales is skipped.
                log.warning("backfill.skipped", report=spec.report_id, reason=str(exc))
                continue
            except spec.source_errors() as exc:
                # Isolated reports (Export Sales, oilseed crush) fail alone.
                log.error("backfill.failed", report=spec.report_id, error=str(exc))
                failed.append(spec.report_id)
                continue
            new[spec.report_id] = len(keys)
    manifest.save(s.manifest_path)
    log.info("backfill.done", new=new, failed=failed, **manifest.summary())
    if failed:
        raise typer.Exit(1)


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
    report: Annotated[
        str,
        typer.Option(
            help="Report to detect (wasde | export_sales | oilseed_crush | crop_progress | "
            "grain_stocks)"
        ),
    ] = WASDE,
    force: Annotated[bool, typer.Option(help="Date-keyed reports: pull even if not due")] = False,
) -> None:
    """Ingest the latest scheduled release (or a revised edition) of one report if it is out.

    WASDE sets GitHub outputs ``new_report`` (true/false), ``report_month`` and ``problems``;
    date-keyed reports (Export Sales, NASS crush, Crop Progress, Grain Stocks) set
    ``new_<report>``, ``<report>_release`` and ``<report>_problems``.
    Exit code 2 = a watchdog fired (overdue report, stale data, empty calendar);
    exit code 1 = a forced month could not be found / the source failed.
    """
    if report != WASDE:
        _detect_dated(report, force)
        return
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


def _weekly_state(spec: ReportSpec, have: set[str], now: datetime) -> WeeklyDue:
    from usda_reports.core.calendar import load_calendar
    from usda_reports.detect import weekly_due

    return weekly_due(
        load_calendar(spec.calendar_path),
        now,
        have,
        spec.config.release_time_et,
        spec.config.grace_days,
        overdue_days=2 if spec.config.cadence == "weekly" else 3,
        cadence_days=spec.config.cadence_days,
    )


def _detect_dated(report_id: str, force: bool) -> None:
    """Date-keyed reports (Export Sales weekly, oilseed crush monthly).

    ET-clock guard first: no network at all unless a release is due and missing (or forced).
    """
    from usda_reports.core.net import make_client
    from usda_reports.core.registry import load_registry

    s, manifest, store = _store(report_id)
    spec = load_registry(s.config_dir).spec(report_id, s)
    ingest = getattr(spec, "ingest", None)
    if spec.config.release_key_format != "date" or ingest is None:
        raise typer.BadParameter(f"{report_id} is not a date-keyed report with an ingest")
    now = datetime.now(UTC)
    have = {k for k, e in store.entries.items() if e.status == "ok"}
    state = _weekly_state(spec, have, now)
    new: list[str] = []
    note = "nothing due"
    if force or not have or state.missing:
        try:
            with make_client() as client:
                result = ingest(client, store, now, force=force)
        except spec.source_errors() as exc:
            log.error("detect.failed", report=report_id, error=str(exc))
            _gh_output(**{f"new_{report_id}": "false", f"{report_id}_problems": str(exc)})
            raise typer.Exit(1) from exc
        new = result.ingested
        note = result.note or ("ingested" if new else "not yet available")
        if new:
            manifest.save(s.manifest_path)
            have |= set(new)
            state = _weekly_state(spec, have, now)
    _gh_output(
        **{
            f"new_{report_id}": "true" if new else "false",
            f"{report_id}_release": max(have) if have else "",
            f"{report_id}_problems": "; ".join(state.problems),
        }
    )
    log.info(
        "detect.done",
        report=report_id,
        ingested=new,
        due=str(state.due) if state.due else None,
        note=note,
        problems=state.problems,
    )
    if state.problems:
        for p in state.problems:
            typer.echo(f"::error::{report_id}: {p}", err=True)
        raise typer.Exit(2)


@app.command()
def due(
    json_out: Annotated[bool, typer.Option("--json", help="Print the state as JSON")] = False,
) -> None:
    """Which enabled reports have a release due and not yet ingested (no network).

    Used by the workflow's fast gate. Sets GitHub output ``due`` (space-separated report ids,
    empty when nothing is due).
    """
    import json as _json

    from usda_reports.core.calendar import latest_due, load_calendar, parse_time_et
    from usda_reports.core.manifest import Manifest
    from usda_reports.core.registry import load_registry
    from usda_reports.detect import weekly_due

    s = get_settings()
    manifest = Manifest.load(s.manifest_path)
    now = datetime.now(UTC)
    out: dict[str, dict[str, object]] = {}
    for cfg in load_registry(s.config_dir).enabled():
        dates = load_calendar(s.calendars_dir / f"{cfg.id}.yaml")
        have = set(manifest.report(cfg.id).ok())
        if cfg.release_key_format == "date":
            st = weekly_due(
                dates,
                now,
                have,
                cfg.release_time_et,
                cfg.grace_days,
                cadence_days=cfg.cadence_days,
            )
            out[cfg.id] = {
                "due": str(st.due) if st.due else None,
                "latest": st.have_latest,
                "missing": st.missing or not have,
            }
        else:
            d = latest_due(dates, now, parse_time_et(cfg.release_time_et))
            key = f"{d:%Y-%m}" if d else None
            out[cfg.id] = {
                "due": str(d) if d else None,
                "latest": max(have) if have else None,
                "missing": key is not None and key not in have,
            }
    ids = [rid for rid, st in out.items() if st["missing"]]
    _gh_output(due=" ".join(ids))
    log.info("due", reports=out)
    if json_out:
        typer.echo(_json.dumps(out, indent=2))


@app.command("esr-verify")
def esr_verify() -> None:
    """Check the configured ESR commodity codes and unit against the live lookups."""
    from usda_reports.core.net import make_client
    from usda_reports.core.registry import load_registry
    from usda_reports.reports.export_sales.ingest import check_codes, discover
    from usda_reports.reports.export_sales.source import EsrClient, EsrError
    from usda_reports.reports.export_sales.spec import ExportSalesSpec

    s = get_settings()
    spec = load_registry(s.config_dir).spec("export_sales", s)
    assert isinstance(spec, ExportSalesSpec)
    with make_client() as client:
        esr = spec.esr_client(client)
        assert isinstance(esr, EsrClient)
        try:
            check_codes(esr)
            rel = discover(esr)
        except EsrError as exc:
            log.error("esr.verify_failed", error=str(exc))
            raise typer.Exit(1) from exc
    log.info("esr.verified", release=rel.release_key, market_years=rel.market_years)


@app.command("esr-vocab")
def esr_vocab() -> None:
    """Regenerate config/vocab/countries.yaml from /api/esr/countries."""
    import yaml

    from usda_reports.core.net import make_client
    from usda_reports.core.registry import load_registry
    from usda_reports.reports.export_sales.source import EsrClient, countries_vocab
    from usda_reports.reports.export_sales.spec import ExportSalesSpec

    s = get_settings()
    spec = load_registry(s.config_dir).spec("export_sales", s)
    assert isinstance(spec, ExportSalesSpec)
    with make_client() as client:
        esr = spec.esr_client(client)
        assert isinstance(esr, EsrClient)
        rows = esr.get_json(esr.config.endpoints["countries"])
    path = s.config_dir / "vocab" / "countries.yaml"
    head = path.read_text(encoding="utf-8").split("kind:", 1)[0] if path.exists() else ""
    body = yaml.safe_dump(countries_vocab(rows), sort_keys=False, allow_unicode=True)
    path.write_text(head + body, encoding="utf-8")
    log.info("esr.vocab_written", countries=len(rows), path=str(path))


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
    from usda_reports.silver.build import build_all, write_status

    s = get_settings()
    manifest = Manifest.load(s.manifest_path)
    result = build_all(s, manifest, only=report)
    write_status(s, result)
    # Isolated reports (Export Sales) that failed were rebuilt from their last good bronze
    # state; the run carries on so WASDE still publishes, and build-info marks them failed.
    _gh_output(silver_failed=" ".join(sorted(result.failed)))
    for rid, err in result.failed.items():
        typer.echo(f"::error::{rid}: silver fell back to the last good state: {err}", err=True)
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


@app.command("build-info")
def build_info(
    sha: Annotated[str, typer.Option(help="Commit SHA of this build")],
    tag: Annotated[str, typer.Option(help="Data release tag the site is built from")],
    out: Annotated[Path, typer.Option(help="Where to write build.json")] = Path(
        "web/public/build.json"
    ),
    failed: Annotated[
        str, typer.Option(help="Space-separated report ids whose ingest failed this run")
    ] = "",
) -> None:
    """Write ``build.json``: commit, data tag and per-report freshness (from meta.json)."""
    import json as _json

    from usda_reports.core.registry import load_registry
    from usda_reports.detect import missed_since, season_closed
    from usda_reports.insights.gates import make_gates
    from usda_reports.silver.build import failed_reports

    s = get_settings()
    meta = _json.loads((s.web_data_dir / "meta.json").read_text(encoding="utf-8"))
    registry = load_registry(s.config_dir)
    stale_after = make_gates(registry).stale_after_days
    now = datetime.now(UTC)
    bad = set(failed.split()) | failed_reports(s)
    reports = {}
    for rid, m in (meta.get("reports") or {}).items():
        ts = datetime.fromisoformat(str(m["release_ts_utc"]).replace("Z", "+00:00"))
        age = (now - ts).days
        cfg = registry.reports.get(rid)
        # A seasonal report (Crop Progress) is off-season only once its season is closed: its
        # final November release is then the newest data until April. In season it is stale
        # only if a scheduled release has passed without arriving (missed_since): a gap
        # between two weekly releases, or cancelled dates, is not staleness.
        off_season = False
        stale = age > stale_after.get(rid, 45)
        if cfg is not None and cfg.seasonal:
            cal = s.calendars_dir / f"{rid}.yaml"
            latest_key = str(m["latest_release_key"])
            off_season = season_closed(cal, latest_key, now)
            stale = stale and not off_season and bool(missed_since(cal, latest_key, now, cfg))
        status = "failed" if rid in bad else ("stale" if stale else "ok")
        reports[rid] = {
            "latest_release_key": m["latest_release_key"],
            "release_ts_utc": m["release_ts_utc"],
            "next_release": m.get("next_release"),
            "age_days": age,
            "status": status,
            **({"off_season": off_season} if cfg and cfg.seasonal else {}),
        }
    body = {
        "sha": sha,
        "tag": tag,
        "data_tag": tag,
        "built_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reports": reports,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(body, indent=1) + "\n", encoding="utf-8")
    log.info("build_info.written", path=str(out), tag=tag, reports=list(reports))


@app.command("release-tag")
def release_tag(
    kind: Annotated[str, typer.Argument(help="data | weekly")],
    existing: Annotated[
        str, typer.Option(help="Space-separated tags that already exist (weekly suffixing)")
    ] = "",
) -> None:
    """Print the release tag for this build: ``data-<latest WASDE month>`` or
    ``weekly-<UTC date>`` (``.2``, ``.3``… when that weekly tag already exists)."""
    from usda_reports.core.manifest import Manifest
    from usda_reports.publish.contract import weekly_tag

    if kind == "data":
        keys = list(Manifest.load(get_settings().manifest_path).report(WASDE).ok())
        if not keys:
            raise typer.Exit(1)
        typer.echo(f"data-{keys[-1]}")
        return
    if kind != "weekly":
        raise typer.BadParameter("kind must be data or weekly")
    typer.echo(weekly_tag(datetime.now(UTC).date(), set(existing.split())))


@app.command("datasets-changed")
def datasets_changed_cmd(
    old: Annotated[Path, typer.Argument(help="datasets.json of the existing release")],
    new: Annotated[Path, typer.Argument(help="datasets.json of this build")],
) -> None:
    """Print ``true`` when any dataset file was added, removed or changed bytes (sha256)."""
    import json as _json

    from usda_reports.publish.contract import datasets_changed

    diff = datasets_changed(
        _json.loads(old.read_text(encoding="utf-8")), _json.loads(new.read_text(encoding="utf-8"))
    )
    log.info("datasets.compared", changed=diff)
    typer.echo("true" if diff else "false")


@app.command("insights-schema")
def insights_schema(
    out: Annotated[Path, typer.Option(help="Where to write the JSON Schema")] = Path(
        "docs/schemas/insights.schema.json"
    ),
) -> None:
    """Write the JSON Schema of insights.json (generated from the pydantic models)."""
    import json as _json

    from usda_reports.insights.engine import json_schema

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(json_schema(), indent=2) + "\n", encoding="utf-8")
    log.info("insights.schema_written", path=str(out))


@app.command("catalog-schema")
def catalog_schema(
    out: Annotated[Path, typer.Option(help="Where to write the snapshot")] = Path(
        "docs/schemas/catalog.schema.json"
    ),
) -> None:
    """Write the catalogue schema snapshot (every dataset's columns and types) from gold."""
    import json as _json

    import duckdb

    from usda_reports.publish.schema_diff import snapshot_from_duckdb

    s = get_settings()
    con = duckdb.connect(str(s.duckdb_path), read_only=True)
    try:
        snap = snapshot_from_duckdb(con)
    finally:
        con.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(snap, indent=2) + "\n", encoding="utf-8")
    log.info("catalog.schema_written", path=str(out), datasets=len(snap["datasets"]))


@app.command("catalog-diff")
def catalog_diff(
    old: Annotated[Path, typer.Argument(help="Baseline: a snapshot or a datapackage.json")],
    new: Annotated[Path, typer.Argument(help="Candidate: a snapshot or a datapackage.json")],
) -> None:
    """Fail (exit 1) on a breaking catalogue change: a column removed, renamed or retyped, or
    a dataset removed, without a new major schema_version. Additive changes only print."""
    from usda_reports.publish.schema_diff import compare, load_snapshot

    diff = compare(load_snapshot(old), load_snapshot(new))
    for line in diff.additive:
        typer.echo(f"additive: {line}")
    for line in diff.breaking:
        typer.echo(f"::error::breaking catalogue change: {line}", err=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### catalog-diff: {old.name} → {new.name}\n\n")
            for line in diff.breaking:
                fh.write(f"- **breaking**: {line}\n")
            for line in diff.additive:
                fh.write(f"- additive: {line}\n")
            if not diff.breaking and not diff.additive:
                fh.write("- no change\n")
    log.info("catalog.diff", breaking=len(diff.breaking), additive=len(diff.additive))
    if not diff.ok:
        raise typer.Exit(1)


@app.command("retention-plan")
def retention_plan(
    releases: Annotated[
        Path, typer.Option(help="gh release list --json tagName,createdAt,isPrerelease,…")
    ],
    protect: Annotated[str, typer.Option(help="Space-separated tags never to prune")] = "",
    keep_days: Annotated[int, typer.Option(help="Keep weekly releases this recent")] = 90,
    keep_min: Annotated[int, typer.Option(help="Always keep this many newest weekly")] = 8,
) -> None:
    """Print the superseded weekly-* prereleases that retention may delete, one per line
    (never data-*, the Latest release or bronze-store). Sets GitHub output ``prune``."""
    import json as _json

    from usda_reports.publish.retention import parse_gh_list, select_prunable

    rows = parse_gh_list(_json.loads(releases.read_text(encoding="utf-8")))
    tags = select_prunable(rows, datetime.now(UTC), keep_days, keep_min, protected=protect.split())
    _gh_output(prune=" ".join(tags))
    log.info("retention.plan", candidates=len(rows), prune=tags)
    for t in tags:
        typer.echo(t)


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
