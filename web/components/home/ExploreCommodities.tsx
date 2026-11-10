"use client";

import Link from "next/link";

import { T, useLang, useT } from "@/components/chrome/I18n";
import type { CommodityLens } from "@/lib/data-contract";
import { commodityName } from "@/lib/labels";
import { lensHeadlines } from "@/lib/lens";
import { REPORT_COLOR, REPORT_NAME } from "@/lib/reports";

/** Home: one link tile per commodity page (/commodities/<id>/) with the reports that cover it,
 *  side by side (stacked below 560px). No numbers here: the commodity page shows the latest number
 *  of every report. */
export default function ExploreCommodities({ lenses, className = "" }: { lenses: CommodityLens[]; className?: string }) {
  const t = useT();
  const { lang } = useLang();
  if (!lenses.length) return null;
  return (
    <section
      aria-labelledby="h-explore"
      className={`card flex min-w-0 flex-col p-4 min-[560px]:px-[22px] min-[560px]:py-5 ${className}`}
      data-testid="explore"
    >
      <div className="eyebrow text-muted">
        <T k="home.explore.eyebrow" />
      </div>
      <h2 id="h-explore" className="m-0 mt-1.5 text-[17px] font-semibold">
        <T k="home.explore.title" />
      </h2>
      <ul className="m-0 mt-3.5 grid flex-1 list-none content-end grid-cols-1 gap-2.5 p-0 min-[560px]:grid-cols-2">
        {lenses.map((l) => {
          const reports = [...new Set(lensHeadlines(l, lang).map((r) => r.reportId))];
          const name = commodityName(l.commodity_id, lang, l.label);
          const row = t("home.explore.row", { n: reports.length });
          return (
            <li key={l.commodity_id} className="min-w-0">
              <Link
                href={`/commodities/${l.commodity_id}/`}
                aria-label={`${t("home.explore.aria", { c: name.toLowerCase() })}. ${row}`}
                className="grid min-h-12 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2.5 gap-y-0.5 rounded-xl border border-line px-3.5 py-3 hover:bg-nav-active hover:no-underline"
                data-testid="explore-link"
              >
                <span className="text-[15px] font-semibold">{name}</span>
                <span aria-hidden="true" className="font-semibold text-link">
                  →
                </span>
                <span className="col-span-2 text-xs text-muted">{row}</span>
                <span className="col-span-2 mt-1.5 flex items-center gap-1" aria-hidden="true">
                  {reports.map((r) => (
                    <span key={r} title={t(REPORT_NAME[r])} className="inline-block h-[9px] w-[9px] rounded-full" style={{ background: REPORT_COLOR[r] }} />
                  ))}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
