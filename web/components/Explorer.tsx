"use client";

import { useEffect, useMemo, useState } from "react";

import { useLang, useT } from "@/components/chrome/I18n";
import { bytes, flagLabel, monthOf, num } from "@/lib/format";
import type { CatalogEntry } from "@/lib/types";

type Row = {
  report_month: string;
  commodity: string;
  region: string;
  attribute: string;
  market_year: string;
  flag: string;
  period: string;
  stat: string;
  value: number;
  unit: string;
};

const EXCEL_MAX_ROWS = 1_048_575;
const ALL = "__all__";

function Select({
  label,
  allLabel,
  value,
  onChange,
  options,
}: {
  label: string;
  allLabel: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-xs text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-line bg-card px-2.5 min-h-11 text-sm text-ink"
      >
        <option value={ALL}>{allLabel}</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}

type Status = { kind: "loading"; label: string; bytes: number } | { kind: "error"; msg: string } | null;

/** WASDE table explorer: the controls follow the site language; the values and the exported
 *  column names stay as published (English ids and labels, the dataset's own schema). */
export default function Explorer({ catalog, defaultTable }: { catalog: CatalogEntry[]; defaultTable: string }) {
  const t = useT();
  const { lang } = useLang();
  const [tableId, setTableId] = useState(defaultTable);
  const table = catalog.find((c) => c.id === tableId) ?? catalog[0];
  const [rows, setRows] = useState<Row[] | null>(null);
  // Status as data, not a sentence, so it follows the language toggle.
  const [status, setStatus] = useState<Status>({ kind: "loading", label: table.label, bytes: table.bytes });
  const [commodity, setCommodity] = useState(ALL);
  const [region, setRegion] = useState(ALL);
  const [attribute, setAttribute] = useState(ALL);
  const [my, setMy] = useState(ALL);
  const [from, setFrom] = useState(table.first_report);
  const [to, setTo] = useState(table.last_report);
  const [busy, setBusy] = useState(false);

  const selectTable = (id: string) => {
    const next = catalog.find((c) => c.id === id) ?? catalog[0];
    setTableId(next.id);
    setRows(null);
    setStatus({ kind: "loading", label: next.label, bytes: next.bytes });
    setCommodity(ALL);
    setRegion(ALL);
    setAttribute(ALL);
    setMy(ALL);
    setFrom(next.first_report);
    setTo(next.last_report);
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { asyncBufferFromUrl, parquetReadObjects } = await import("hyparquet");
        const file = await asyncBufferFromUrl({ url: `/data/${table.file}` });
        const data = (await parquetReadObjects({ file })) as unknown as Row[];
        if (!cancelled) {
          setRows(data);
          setStatus(null);
        }
      } catch (e) {
        if (!cancelled) setStatus({ kind: "error", msg: (e as Error).message });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [table]);

  const filtered = useMemo(() => {
    if (!rows) return [];
    return rows.filter(
      (r) =>
        (commodity === ALL || r.commodity === commodity) &&
        (region === ALL || r.region === region) &&
        (attribute === ALL || r.attribute === attribute) &&
        (my === ALL || r.market_year === my) &&
        r.report_month >= from &&
        r.report_month <= to,
    );
  }, [rows, commodity, region, attribute, my, from, to]);

  const months = useMemo(() => {
    if (!rows) return [];
    return [...new Set(rows.map((r) => r.report_month))].sort();
  }, [rows]);

  const monthText = (m: string) => `${monthOf(Number(m.slice(5, 7)), "short", lang)} ${m.slice(0, 4)}`;

  const fileBase = `wasde_${table.id}${commodity !== ALL ? `_${commodity}` : ""}${region !== ALL ? `_${region}` : ""}_${from}_${to}`
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "_");

  const exportRows = () =>
    filtered.slice(0, EXCEL_MAX_ROWS).map((r) => ({
      Report: r.report_month,
      Commodity: r.commodity,
      Region: r.region,
      Line: r.attribute,
      "Marketing year": r.market_year,
      Flag: r.flag,
      Period: r.period,
      ...(r.stat ? { Statistic: r.stat } : {}),
      Value: r.value,
      Unit: r.unit,
    }));

  const downloadXlsx = async () => {
    setBusy(true);
    try {
      const XLSX = await import("xlsx");
      const ws = XLSX.utils.json_to_sheet(exportRows());
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "WASDE");
      XLSX.writeFile(wb, `${fileBase}.xlsx`);
    } finally {
      setBusy(false);
    }
  };

  const downloadCsv = () => {
    const data = exportRows();
    if (!data.length) return;
    const head = Object.keys(data[0]);
    const esc = (v: unknown) => {
      const s = v === null || v === undefined ? "" : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = [head.join(","), ...data.map((r) => head.map((h) => esc((r as Record<string, unknown>)[h])).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${fileBase}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const all = t("ex.all");
  const statusText =
    status?.kind === "loading"
      ? t("ex.loading", { t: status.label, b: bytes(status.bytes) })
      : status?.kind === "error"
        ? t("ex.error", { e: status.msg })
        : t("ex.match", { n: num(filtered.length) });
  const head = [t("ex.h.report"), t("ex.h.commodity"), t("ex.h.region"), t("ex.h.line"), t("ex.h.my"), t("ex.h.flag"), t("ex.h.value"), t("ex.h.unit")];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex min-w-0 flex-col gap-1 text-xs text-muted sm:col-span-2">
          {t("ex.table")}
          <select
            value={tableId}
            onChange={(e) => selectTable(e.target.value)}
            className="w-full min-w-0 rounded-lg border border-line bg-card px-2.5 min-h-11 text-sm text-ink"
          >
            {catalog.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label} — {t("ex.values", { n: num(c.rows) })}
              </option>
            ))}
          </select>
        </label>
        <Select label={t("ex.commodity")} allLabel={all} value={commodity} onChange={setCommodity} options={table.commodities} />
        <Select label={t("ex.region")} allLabel={all} value={region} onChange={setRegion} options={table.regions} />
        <Select label={t("ex.line")} allLabel={all} value={attribute} onChange={setAttribute} options={table.attributes} />
        <Select label={t("ex.my")} allLabel={all} value={my} onChange={setMy} options={[...table.market_years].reverse()} />
        <label className="flex min-w-0 flex-col gap-1 text-xs text-muted">
          {t("ex.from")}
          <select value={from} onChange={(e) => setFrom(e.target.value)} className="w-full min-w-0 rounded-lg border border-line bg-card px-2.5 min-h-11 text-sm text-ink">
            {months.map((m) => (
              <option key={m} value={m}>
                {monthText(m)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-0 flex-col gap-1 text-xs text-muted">
          {t("ex.to")}
          <select value={to} onChange={(e) => setTo(e.target.value)} className="w-full min-w-0 rounded-lg border border-line bg-card px-2.5 min-h-11 text-sm text-ink">
            {months.map((m) => (
              <option key={m} value={m}>
                {monthText(m)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted" aria-live="polite">
          {statusText}
          {filtered.length > EXCEL_MAX_ROWS && t("ex.cap")}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!filtered.length || busy}
            onClick={downloadXlsx}
            className="min-h-11 rounded-lg bg-[var(--pill-active)] px-4 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
          >
            {busy ? t("ex.preparing") : t("ex.xlsx")}
          </button>
          <button
            type="button"
            disabled={!filtered.length}
            onClick={downloadCsv}
            className="min-h-11 rounded-lg border border-line px-4 text-sm hover:bg-bg disabled:opacity-40"
          >
            CSV
          </button>
        </div>
      </div>

      <div tabIndex={0} role="region" aria-label={t("ex.preview")} className="max-h-[480px] overflow-auto rounded-lg border border-line">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="sticky top-0 bg-bg text-xs text-muted">
            <tr>
              {head.map((h, i) => (
                <th key={h} scope="col" className={`px-3 py-2 font-normal ${i === 6 ? "text-right" : "text-left"}`}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody lang="en">
            {filtered.slice(0, 200).map((r, i) => (
              <tr key={i} className="border-t border-line">
                <td className="px-3 py-1.5">{r.report_month}</td>
                <td className="px-3 py-1.5">{r.commodity}</td>
                <td className="px-3 py-1.5">{r.region}</td>
                <td className="px-3 py-1.5">
                  {r.attribute}
                  {r.stat ? ` · ${r.stat}` : ""}
                </td>
                <td className="px-3 py-1.5">{r.market_year}</td>
                <td className="px-3 py-1.5 text-muted">{flagLabel(r.flag)}</td>
                <td className="tabular px-3 py-1.5 text-right">{num(r.value, Math.abs(r.value) < 100 ? 2 : 0)}</td>
                <td className="px-3 py-1.5 text-muted">{r.unit}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > 200 && <p className="border-t border-line px-3 py-2 text-xs text-muted">{t("ex.first200")}</p>}
      </div>
    </div>
  );
}
