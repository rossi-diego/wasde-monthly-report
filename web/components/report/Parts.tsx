"use client";

// Shared building blocks of the cut-C report pages (same look as the Export Sales and crush
// pages): numbered chapters with an anchor (#ch-1 …), header stats, the suppressed state, the
// n / small-sample / caveat line, the "take this report" downloads and the selector pills.

import Link from "next/link";
import { useEffect, useState } from "react";

import { Chevron } from "@/components/charts/common";
import { T, useLang, useT } from "@/components/chrome/I18n";
import { SmallChip } from "@/components/home/InsightCards";
import type { Insight, TakeFile } from "@/lib/data-contract";
import { bytes } from "@/lib/format";
import type { Key } from "@/lib/i18n";
import { caveatText, suppressedText } from "@/lib/insight-text";

export function Chapter({
  n,
  color,
  eyebrow,
  title,
  children,
}: {
  n: number;
  color: string;
  eyebrow: Key;
  title: Key;
  children: React.ReactNode;
}) {
  const hid = `h-ch-${n}`;
  return (
    <article id={`ch-${n}`} aria-labelledby={hid} className="card flex min-w-0 scroll-mt-4 flex-col gap-3 p-5" data-testid={`chapter-${n}`}>
      <div>
        <div className="eyebrow" style={{ color }}>
          <T k="esr.ch" v={{ n: `0${n}` }} /> · <T k={eyebrow} />
        </div>
        <h2 id={hid} className="m-0 mt-0.5 text-[17px] font-bold">
          <T k={title} />
        </h2>
      </div>
      {children}
    </article>
  );
}

export function Stat({
  label,
  value,
  sub,
  testid,
  color,
}: {
  label: React.ReactNode;
  value: React.ReactNode;
  sub?: React.ReactNode;
  testid?: string;
  color: string;
}) {
  return (
    <div className="card flex min-w-0 flex-col gap-0.5 p-4" style={{ borderTop: `4px solid ${color}` }}>
      <div className="text-xs font-semibold text-muted">{label}</div>
      <div className="mono text-[22px] font-semibold" data-testid={testid}>
        {value}
      </div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  );
}

export function Suppressed({ i }: { i: Insight }) {
  const { lang } = useLang();
  return (
    <p className="m-0 rounded-xl bg-bg px-3 py-2 text-[13px] text-muted" data-testid="suppressed" data-suppressed={i.id}>
      {suppressedText(i.suppressed_reason!, lang)}
    </p>
  );
}

/** The selected id of a page with a ?c= deep link (home cards link to /reports/x/?c=corn). */
export function useSelection(ids: string[], fallback: string) {
  const [sel, setSel] = useState(fallback);
  const key = ids.join(",");
  useEffect(() => {
    const c = new URLSearchParams(window.location.search).get("c");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time sync from the URL after hydration
    if (c && key.split(",").includes(c)) setSel(c);
  }, [key]);
  const pick = (id: string) => {
    setSel(id);
    try {
      const u = new URL(window.location.href);
      u.searchParams.set("c", id);
      u.hash = "";
      window.history.replaceState(null, "", u);
    } catch {
      /* ignore */
    }
  };
  return [ids.includes(sel) ? sel : fallback, pick] as const;
}

/** n, the small-sample chip, the position chip and the caveats of a passing insight. */
export function InsightMeta({ i, chip }: { i: Insight; chip?: string | null }) {
  const t = useT();
  const { lang } = useLang();
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted" data-testid="insight-meta" data-for={i.id}>
      {chip ? <span className="rounded-full bg-nav-active px-2 py-[1px] font-semibold text-ink">{chip}</span> : null}
      <span className="font-semibold text-ink" data-testid="n">
        {t("card.n", { n: i.n ?? "—" })}
      </span>
      {i.caveats.includes("small_sample") && <SmallChip />}
      {i.caveats
        .filter((x) => x !== "small_sample")
        .map((x) => (
          <span key={x} data-testid="caveat">
            · {caveatText(x, lang, i.rule)}
          </span>
        ))}
    </div>
  );
}

/** Toggle pills (crop / commodity); the pressed one is the page's selection. */
export function PickPills({ label, items, active, onPick }: { label: string; items: { id: string; label: string }[]; active: string; onPick: (id: string) => void }) {
  const pill = (on: boolean) =>
    `flex min-h-11 min-w-11 shrink-0 cursor-pointer items-center justify-center whitespace-nowrap rounded-full px-3.5 font-semibold ${on ? "bg-[var(--pill-active)] text-white" : "text-ink hover:bg-nav-active"}`;
  return (
    <div role="group" aria-label={label} className="flex max-w-full flex-wrap gap-1 rounded-3xl border border-line bg-card p-1">
      {items.map((x) => (
        <button key={x.id} type="button" aria-pressed={x.id === active} className={pill(x.id === active)} onClick={() => onPick(x.id)}>
          {x.label}
        </button>
      ))}
    </div>
  );
}

/** Collapsed "Explore" section (closed by default). */
export function ExploreDetails({ title, testid, children }: { title: Key; testid: string; children: React.ReactNode }) {
  return (
    <details className="card group p-5" data-testid={testid}>
      <summary className="flex min-h-11 items-center justify-between gap-3 text-[15px] font-semibold">
        <T k={title} />
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line text-link group-hover:bg-nav-active">
          <Chevron size={16} />
        </span>
      </summary>
      <div className="flex flex-col gap-4 pt-3">{children}</div>
    </details>
  );
}

/** A scrollable data table with a visible heading. */
export function DataTable({ id, title, head, rows }: { id: string; title: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 id={id} className="m-0 text-[14px] font-semibold">
        {title}
      </h3>
      <div tabIndex={0} role="region" aria-labelledby={id} className="max-h-96 overflow-auto">
        <table className="data-table">
          <thead>
            <tr>
              {head.map((h) => (
                <th key={h} scope="col">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) =>
                  j === 0 ? (
                    <th key={j} scope="row" className="font-normal">
                      {c}
                    </th>
                  ) : (
                    <td key={j} className="tabular">
                      {c}
                    </td>
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** "Take this report": the report's files, the catalogue and the methodology. */
export function TakeSection({
  title,
  testid,
  files,
  reportId,
  methodAnchor,
  children,
}: {
  title: Key;
  testid: string;
  files: TakeFile[];
  reportId: string;
  methodAnchor: string;
  children?: React.ReactNode;
}) {
  const t = useT();
  return (
    <section aria-labelledby="h-take" className="card flex flex-col gap-2 p-5" data-testid={testid}>
      <h2 id="h-take" className="m-0 text-[17px] font-bold">
        <T k={title} />
      </h2>
      {files.length > 0 && (
        <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-[13px]">
          {files.map((f) => (
            <li key={f.file}>
              <a href={f.href} className="inline-flex min-h-11 items-center gap-1.5 font-semibold text-link" download={f.href.startsWith("/") ? "" : undefined}>
                {t((f.report_id === "crop_progress" && f.dataset === "weekly" ? "ds.crop_progress.weekly" : `ds.${f.dataset}`) as Key)} ·{" "}
                {f.format === "csv" ? (f.file.endsWith(".gz") ? "CSV.gz" : "CSV") : "Parquet"}
                <span className="font-normal text-muted">({bytes(f.bytes)})</span>
              </a>
            </li>
          ))}
        </ul>
      )}
      {children}
      <div className="flex flex-wrap gap-x-5 text-[13px]">
        <Link href={`/data/#report-${reportId}`} className="inline-flex min-h-11 items-center text-link">
          <T k="esr.take.all" />
        </Link>
        <Link href={`/methodology/#${methodAnchor}`} className="inline-flex min-h-11 items-center text-link">
          <T k="esr.take.method" />
        </Link>
      </div>
    </section>
  );
}

/** Legend swatch: a thick line, a band, a dashed or dotted line, or a thin line. */
export function Swatch({ kind, color }: { kind: "line" | "band" | "dashed" | "thin" | "dotted"; color?: string }) {
  if (kind === "line") return <span aria-hidden="true" className="inline-block h-1 w-5 rounded" style={{ background: color }} />;
  if (kind === "band") return <span aria-hidden="true" className="inline-block h-2.5 w-5 rounded" style={{ background: color, opacity: 0.18 }} />;
  if (kind === "dashed") return <span aria-hidden="true" className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: "var(--muted)" }} />;
  if (kind === "dotted") return <span aria-hidden="true" className="inline-block w-5 border-t-2 border-dotted" style={{ borderColor: "var(--muted)" }} />;
  return <span aria-hidden="true" className="inline-block h-0.5 w-5" style={{ background: "var(--bar-past)" }} />;
}
