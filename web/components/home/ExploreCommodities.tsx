"use client";

import Link from "next/link";

import { T, useLang, useT } from "@/components/chrome/I18n";
import type { CommodityLens } from "@/lib/data-contract";
import { commodityName } from "@/lib/labels";
import { lensHeadlines } from "@/lib/lens";
import { REPORT_COLOR, REPORT_NAME } from "@/lib/reports";

/** Home: one row per commodity page (/commodities/<id>/) with the reports that cover it. No
 *  numbers here: the commodity page shows the latest number of every report. */
export default function ExploreCommodities({ lenses }: { lenses: CommodityLens[] }) {
  const t = useT();
  const { lang } = useLang();
  if (!lenses.length) return null;
  return (
    <section aria-labelledby="h-explore" className="card flex min-w-0 flex-col gap-1 p-5" data-testid="explore">
      <h2 id="h-explore" className="m-0 text-[17px] font-bold">
        <T k="home.explore.title" />
      </h2>
      <ul className="m-0 list-none p-0">
        {lenses.map((l) => {
          const reports = [...new Set(lensHeadlines(l, lang).map((r) => r.reportId))];
          const name = commodityName(l.commodity_id, lang, l.label);
          const row = t("home.explore.row", { n: reports.length });
          return (
            <li key={l.commodity_id} className="border-t border-line first:border-t-0">
              <Link
                href={`/commodities/${l.commodity_id}/`}
                aria-label={`${t("home.explore.aria", { c: name.toLowerCase() })}. ${row}`}
                className="flex min-h-12 items-center gap-3 py-2 hover:no-underline"
                data-testid="explore-link"
              >
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{name}</span>
                  <span className="block text-xs text-muted">{row}</span>
                </span>
                <span className="flex shrink-0 items-center gap-1" aria-hidden="true">
                  {reports.map((r) => (
                    <span key={r} title={t(REPORT_NAME[r])} className="inline-block h-2 w-2 rounded-full" style={{ background: REPORT_COLOR[r] }} />
                  ))}
                </span>
                <span aria-hidden="true" className="font-semibold text-link">
                  →
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
