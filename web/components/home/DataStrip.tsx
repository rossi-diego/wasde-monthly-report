"use client";

import Link from "next/link";

import { T } from "@/components/chrome/I18n";

const ghostBtn =
  "flex min-h-11 items-center rounded-full border border-white/70 px-4 font-semibold text-white hover:bg-white/10 hover:no-underline";

export default function DataStrip({
  links,
  history,
}: {
  links: { excel: string | null; csv: string | null; parquet: string | null };
  history: { first: string; reports: string; rows: string; tag: string | null };
}) {
  return (
    <section
      aria-labelledby="h-data"
      className="flex flex-wrap items-center gap-x-7 gap-y-4 rounded-2xl px-[22px] py-5 text-white"
      style={{ background: "var(--data-bg)" }}
    >
      <div className="min-w-0 flex-[1_1_280px]">
        <div className="text-xs font-semibold uppercase tracking-[0.06em]">
          <T k="data.eyebrow" />
        </div>
        <h2 id="h-data" className="m-0 text-lg font-bold">
          <T k="data.title" v={{ first: history.first }} />
        </h2>
        <div className="text-[13px]">
          <T k="data.sub" v={{ reports: history.reports, rows: history.rows, tag: history.tag ?? "local build" }} />
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {links.excel && (
          <a
            href={links.excel}
            download
            className="flex min-h-11 items-center rounded-full bg-white px-4 font-bold hover:no-underline"
            style={{ color: "var(--data-ink)" }}
          >
            <T k="data.excel" />
          </a>
        )}
        {links.csv && (
          <a href={links.csv} download className={ghostBtn}>
            <T k="data.csv" />
          </a>
        )}
        {links.parquet && (
          <a href={links.parquet} download className={ghostBtn}>
            <T k="data.parquet" />
          </a>
        )}
        <Link href="/data/" className={ghostBtn}>
          <T k="data.catalogue" />
        </Link>
      </div>
    </section>
  );
}
