"use client";

import Link from "next/link";

import { T, useT } from "@/components/chrome/I18n";
import type { ChangeRow } from "@/lib/insights";

/** overview.json highlights (score-ordered). In full on /reports/wasde/ (score bars, Excel link,
 *  bar note); on the home page the top `limit` rows without bars, linking to the full list. */
export default function BiggestRevisions({
  changes,
  prevMonth,
  excel,
  limit,
  bars = true,
  month,
  className = "",
}: {
  changes: ChangeRow[];
  prevMonth: string;
  excel: string | null;
  limit?: number;
  bars?: boolean;
  /** Home: the WASDE month of the source footer ("October 2026"). */
  month?: string;
  className?: string;
}) {
  const t = useT();
  const full = limit === undefined;
  const id = full ? "h-chg" : "h-chg-top";
  const rows = full ? changes : changes.slice(0, limit);
  if (!rows.length) return null;
  return (
    <section
      aria-labelledby={id}
      className={full ? `card flex min-w-0 flex-col gap-2.5 p-5 ${className}` : `card flex min-w-0 flex-col px-4 pt-4 min-[560px]:px-[22px] min-[560px]:pt-5 ${className}`}
      data-testid={full ? "revisions" : "revisions-top"}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-[1_1_220px]">
          <div className="eyebrow">
            <T k="chg.eyebrow" />
          </div>
          <h2 id={id} className={`m-0 text-[17px] ${full ? "mt-0.5 font-bold" : "mt-1.5 font-semibold"}`}>
            <T k={full ? "chg.title" : "chg.topTitle"} v={{ month: prevMonth }} />
          </h2>
        </div>
        {full && excel && (
          <a href={excel} download className="inline-flex min-h-11 items-center text-[13px] font-semibold text-link">
            <T k="chg.all" />
          </a>
        )}
      </div>
      <ol className={`m-0 list-none p-0 ${full ? "" : "mt-3.5 flex-1"}`}>
        {rows.map((c) => (
          <li key={c.key} className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-t border-line ${full ? "py-2.5" : "py-3"}`}>
            <Link href={`/commodity/${c.commodity}/`} className="font-semibold">
              {c.what}
            </Link>
            <div className={`mono text-right font-semibold ${c.dir === "up" ? "text-up" : c.dir === "down" ? "text-down" : "text-muted"}`}>{c.delta}</div>
            <div className={`text-xs text-muted ${bars ? "" : "col-span-2"}`}>
              {t(c.dir === "up" ? "chg.raised" : c.dir === "down" ? "chg.cut" : "chg.unch", { v: c.to })}
              {bars && c.extra.map((e) => ` · ${e}`).join("")}
            </div>
            {bars && (
              <div aria-hidden="true" className="h-1.5 w-[120px] overflow-hidden rounded-[3px] bg-grid">
                <div
                  className="h-1.5 rounded-[3px]"
                  style={{ width: `${Math.round(c.frac * 120)}px`, background: c.dir === "down" ? "var(--down)" : "var(--up)" }}
                />
              </div>
            )}
          </li>
        ))}
      </ol>
      {full ? (
        <p className="m-0 text-xs text-muted">
          <T k="chg.bar" />
        </p>
      ) : (
        <div className="mt-auto flex min-h-12 flex-wrap items-center justify-between gap-x-3 border-t border-line text-xs text-muted" data-testid="card-footer">
          {month && <span data-testid="revisions-source">{t("chg.source", { month })}</span>}
          <Link href="/reports/wasde/#h-chg" className="inline-flex min-h-11 items-center font-semibold text-link" data-testid="all-revisions">
            <T k="chg.allLink" />
          </Link>
        </div>
      )}
    </section>
  );
}
