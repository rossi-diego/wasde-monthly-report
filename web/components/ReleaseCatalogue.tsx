"use client";

import { useState } from "react";

import { CommodityName, T, useLang, useT } from "@/components/chrome/I18n";
import type { ReleaseCatalog } from "@/lib/data-contract";
import { bytes, num, shortDate } from "@/lib/format";
import type { Key } from "@/lib/i18n";
import { REPORT_COLOR, REPORT_NAME } from "@/lib/reports";

/** One catalogue file with the link the site resolved at build time (site copy or release asset). */
export type CatFile = ReleaseCatalog["files"][number] & { href: string | null; served: boolean };
export type Workbook = { file: string; label: string; href: string; bytes: number; commodity: string | null };
export type CatCommodity = { id: string; label: string; reports: string[] };

const VINTAGE: Record<string, Key> = {
  wasde: "cat.vintage.wasde",
  export_sales: "cat.vintage.esr",
  oilseed_crush: "cat.vintage.crush",
  crop_progress: "cat.vintage.cp",
  grain_stocks: "cat.vintage.gs",
};

/** Report group of a catalogue file: cross-report datasets sit with the report they compare. */
export const groupOf = (f: { report_id: string; dataset: string }) =>
  f.report_id !== "cross"
    ? f.report_id
    : f.dataset === "crush_pace"
      ? "oilseed_crush"
      : f.dataset.startsWith("stocks_")
        ? "grain_stocks"
        : "export_sales";

/** Dataset name (Crop Progress "weekly" is not Export Sales "weekly"). */
export const datasetKey = (f: { report_id: string; dataset: string }): Key =>
  (f.report_id === "crop_progress" && f.dataset === "weekly" ? "ds.crop_progress.weekly" : `ds.${f.dataset}`) as Key;

function fmtKey(key: string | null | undefined, lang: "en" | "pt") {
  if (!key) return "—";
  return key.length === 10 ? (shortDate(key, true, lang) ?? key) : key;
}

function Sha({ file, sha }: { file: string; sha: string }) {
  const t = useT();
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      title={`sha256 ${sha}`}
      aria-label={t("cat.copy", { f: file })}
      className="mono inline-flex min-h-11 cursor-pointer items-center rounded px-1 text-xs text-link hover:underline"
      onClick={() => {
        navigator.clipboard?.writeText(sha).then(
          () => setDone(true),
          () => {},
        );
        setTimeout(() => setDone(false), 1500);
      }}
    >
      {done ? t("cat.copied") : `${sha.slice(0, 10)}…`}
    </button>
  );
}

function DatasetTable({ files, reportId }: { files: CatFile[]; reportId: string }) {
  const t = useT();
  const { lang } = useLang();
  // One row per dataset; its files (Parquet, CSV) as links.
  const datasets = [...new Set(files.filter((f) => !f.legacy_alias_of).map((f) => f.dataset))];
  const aliases = files.filter((f) => f.legacy_alias_of);
  return (
    <div tabIndex={0} role="region" aria-label={t("cat.h.dataset")} className="overflow-x-auto">
      <table className="data-table min-w-[640px] text-[13px]">
        <thead>
          <tr>
            {[t("cat.h.dataset"), t("cat.h.rows"), t("cat.h.coverage"), t("cat.h.latest"), t("cat.h.files"), t("cat.h.schema"), t("cat.h.sha")].map((h) => (
              <th key={h} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {datasets.map((ds) => {
            const fs = files.filter((f) => f.dataset === ds && !f.legacy_alias_of).sort((a, b) => a.format.localeCompare(b.format));
            const f0 = fs.find((f) => f.format === "parquet") ?? fs[0];
            return (
              <tr key={ds} data-testid="dataset-row" data-report={reportId} data-dataset={ds}>
                <th scope="row" className="font-normal">
                  <div className="font-semibold">{t(datasetKey(f0))}</div>
                  <code className="text-xs text-muted">{`${f0.report_id}__${ds}__v${f0.schema_version}`}</code>
                </th>
                <td className="tabular">{num(f0.rows)}</td>
                <td className="tabular whitespace-nowrap">
                  {f0.coverage ? `${fmtKey(f0.coverage.start, lang)} → ${fmtKey(f0.coverage.end, lang)}` : "—"}
                </td>
                <td className="tabular whitespace-nowrap">{fmtKey(f0.latest_release_key, lang)}</td>
                <td>
                  <span className="flex flex-wrap justify-end gap-x-3">
                    {fs.map((f) =>
                      f.href ? (
                        <a key={f.file} href={f.href} className="inline-flex min-h-11 items-center font-semibold text-link" title={`${f.file} · ${bytes(f.bytes)}`}>
                          {f.format === "csv" ? (f.file.endsWith(".gz") ? "CSV.gz" : "CSV") : "Parquet"}
                        </a>
                      ) : null,
                    )}
                  </span>
                </td>
                <td className="tabular">v{f0.schema_version}</td>
                <td>
                  <span className="flex flex-col items-end">
                    {fs.map((f) => (
                      <span key={f.file} className="flex items-center gap-1 text-[11px] text-muted">
                        {f.format === "csv" ? "csv" : "parquet"}
                        <Sha file={f.file} sha={f.sha256} />
                      </span>
                    ))}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {aliases.length > 0 && (
        <p className="m-0 pt-1 text-xs text-muted">
          {aliases.map((a, i) => (
            <span key={a.file}>
              {i > 0 && " · "}
              {a.href ? (
                <a href={a.href} className="text-link underline">
                  {a.file}
                </a>
              ) : (
                a.file
              )}{" "}
              ({t("cat.alias", { f: a.legacy_alias_of ?? "" })})
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

export default function ReleaseCatalogue({
  catalog,
  files,
  workbooks,
  datapackageHref,
  commodities,
  vintageQuality,
}: {
  catalog: ReleaseCatalog;
  files: CatFile[];
  workbooks: Workbook[];
  datapackageHref: string | null;
  commodities: CatCommodity[];
  vintageQuality: string | null;
}) {
  const t = useT();
  const [by, setBy] = useState<"report" | "commodity">("report");
  const reportIds = Object.keys(catalog.reports);
  const groups = reportIds.map((id) => ({
    id,
    files: files.filter((f) => groupOf(f) === id),
  }));
  const btn = (on: boolean) =>
    `flex min-h-11 cursor-pointer items-center rounded-full px-4 font-semibold ${on ? "bg-[var(--pill-active)] text-white" : "text-ink hover:bg-nav-active"}`;

  return (
    <section aria-labelledby="h-cat" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="h-cat" className="m-0 text-[17px] font-bold">
          <T k="cat.title" />
        </h2>
        <div role="group" aria-label={t("cat.browse")} className="flex gap-1 rounded-3xl border border-line bg-card p-1">
          <button type="button" aria-pressed={by === "report"} className={btn(by === "report")} onClick={() => setBy("report")}>
            <T k="cat.byReport" />
          </button>
          <button type="button" aria-pressed={by === "commodity"} className={btn(by === "commodity")} onClick={() => setBy("commodity")}>
            <T k="cat.byCommodity" />
          </button>
        </div>
      </div>
      <div className="flex flex-wrap gap-x-5 text-[13px]">
        {datapackageHref && (
          <a href={datapackageHref} className="inline-flex min-h-11 items-center font-semibold text-link" data-testid="datapackage-link">
            <T k="cat.datapackage" />
          </a>
        )}
        {catalog.release_page && catalog.data_tag && (
          <a href={catalog.release_page} className="inline-flex min-h-11 items-center text-link">
            <T k="cat.release" v={{ tag: catalog.data_tag }} />
          </a>
        )}
      </div>

      {by === "report" ? (
        groups.map((g) => {
          const r = catalog.reports[g.id];
          const color = REPORT_COLOR[g.id] ?? "var(--muted)";
          const wb = g.id === "wasde" ? workbooks : [];
          return (
            <article key={g.id} id={`report-${g.id}`} aria-labelledby={`h-cat-${g.id}`} className="card flex min-w-0 flex-col gap-2 p-5" style={{ borderTop: `4px solid ${color}` }}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 id={`h-cat-${g.id}`} className="m-0 text-[15px] font-bold">
                  {REPORT_NAME[g.id] ? t(REPORT_NAME[g.id]) : g.id} <span className="font-normal text-muted" lang="en">· {r.title} · {r.agency}</span>
                </h3>
                <span className="text-xs text-muted">
                  {t(`cadence.${r.cadence}` as Key)} · {t("cat.reportsN", { n: new Set(g.files.map((f) => f.dataset)).size })}
                </span>
              </div>
              <DatasetTable files={g.files} reportId={g.id} />
              {wb.length > 0 && (
                <div className="text-[13px]">
                  <span className="font-semibold">{t("cat.workbooks")}: </span>
                  {wb.map((w, i) => (
                    <span key={w.file}>
                      {i > 0 && " · "}
                      <a href={w.href} download className="text-link underline" title={bytes(w.bytes)}>
                        {w.commodity ? <CommodityName id={w.commodity} fallback={w.label} /> : <span lang="en">{w.label}</span>}
                      </a>
                    </span>
                  ))}
                </div>
              )}
              <dl className="m-0 grid gap-1 text-xs text-muted">
                <div>
                  <dt className="inline font-semibold text-ink">{t("cat.vintage")}: </dt>
                  <dd className="inline m-0" data-testid={`vintage-${g.id}`}>
                    {t(VINTAGE[g.id] ?? "cat.vintage.wasde")}
                    {g.id === "export_sales" && vintageQuality ? ` ${t("cat.vintage.now", { q: t(`vq.${vintageQuality}` as Key) })}.` : ""}
                  </dd>
                </div>
                <div>
                  <dt className="inline font-semibold text-ink">{t("cat.licence")}: </dt>
                  <dd className="inline m-0" lang="en">
                    {r.licence}
                  </dd>
                </div>
              </dl>
            </article>
          );
        })
      ) : (
        <div className="grid-fit-240">
          {commodities.map((c) => (
            <article key={c.id} aria-labelledby={`h-catc-${c.id}`} className="card flex flex-col gap-1.5 p-4">
              <h3 id={`h-catc-${c.id}`} className="m-0 text-[15px] font-bold">
                <CommodityName id={c.id} fallback={c.label} />
              </h3>
              <ul className="m-0 list-none p-0 text-[13px]">
                {c.reports.includes("wasde") && <li>· {t("cat.wasdeIn")}</li>}
                {c.reports.includes("export_sales") && <li>· {t("cat.esrIn")}</li>}
                {c.reports.includes("oilseed_crush") && <li>· {t("cat.crushIn")}</li>}
                {c.reports.includes("crop_progress") && <li>· {t("cat.cpIn")}</li>}
                {c.reports.includes("grain_stocks") && <li>· {t("cat.gsIn")}</li>}
              </ul>
              {workbooks
                .filter((w) => w.commodity === c.id)
                .map((w) => (
                  <a key={w.file} href={w.href} download className="inline-flex min-h-11 items-center font-semibold text-link">
                    {t("cat.history")} (Excel, {bytes(w.bytes)})
                  </a>
                ))}
              <p className="m-0 mt-auto text-xs text-muted">{t("cat.commodityNote")}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
