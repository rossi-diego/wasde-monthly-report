"use client";

import Link from "next/link";
import { useState } from "react";

import { T, useLang, useT } from "@/components/chrome/I18n";
import type { CommodityLens } from "@/lib/data-contract";
import { lensHeadlines } from "@/lib/lens";
import { commodityName } from "@/lib/labels";
import { REPORT_COLOR, REPORT_NAME } from "@/lib/reports";

/** Home section 02: one commodity, the latest number of every report that covers it. */
export default function LensTeaser({ lenses }: { lenses: CommodityLens[] }) {
  const t = useT();
  const { lang } = useLang();
  const [sel, setSel] = useState(lenses[0]?.commodity_id ?? "");
  const lens = lenses.find((l) => l.commodity_id === sel) ?? lenses[0];
  if (!lens) return null;
  const rows = lensHeadlines(lens, lang);
  const name = commodityName(lens.commodity_id, lang, lens.label);
  const pill = (on: boolean) =>
    `flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-full px-4 font-semibold ${on ? "bg-[var(--pill-active)] text-white" : "text-ink hover:bg-nav-active"}`;
  return (
    <section aria-labelledby="h-lens" className="card flex flex-col gap-3 p-5" data-testid="lens-teaser">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 id="h-lens" className="m-0 text-[17px] font-bold">
            <T k="home.lens.title" />
          </h2>
          <p className="m-0 text-xs text-muted">
            <T k="home.lens.note" />
          </p>
        </div>
        <div role="group" aria-label={t("nav.commodities")} className="flex gap-1 rounded-3xl border border-line bg-card p-1">
          {lenses.map((l) => (
            <button key={l.commodity_id} type="button" aria-pressed={l.commodity_id === lens.commodity_id} className={pill(l.commodity_id === lens.commodity_id)} onClick={() => setSel(l.commodity_id)}>
              {commodityName(l.commodity_id, lang, l.label)}
            </button>
          ))}
        </div>
      </div>
      <ul className="grid-fit-180 m-0 list-none p-0">
        {rows.map((r) => (
          <li key={`${r.reportId}-${r.metric}`} className="flex min-w-0 flex-col gap-0.5 rounded-xl border border-line p-3" style={{ borderTop: `4px solid ${REPORT_COLOR[r.reportId]}` }} data-testid="lens-mini" data-report={r.reportId} data-metric={r.metric}>
            <span className="text-[11px] font-bold uppercase tracking-[0.04em]" style={{ color: REPORT_COLOR[r.reportId] }}>
              {t(REPORT_NAME[r.reportId])}
            </span>
            <span className="text-xs text-muted">{r.label}</span>
            <span className="mono text-[20px] font-semibold" data-testid="lens-mini-value">
              {r.value}
            </span>
            <span className="text-[11px] text-muted">{r.period}</span>
          </li>
        ))}
      </ul>
      <Link href={`/commodities/${lens.commodity_id}/`} className="inline-flex min-h-11 items-center self-start font-semibold text-link">
        {t("home.lens.open", { c: name.toLowerCase() })}
      </Link>
    </section>
  );
}
