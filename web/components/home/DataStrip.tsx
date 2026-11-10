"use client";

import Link from "next/link";

import { T, useT } from "@/components/chrome/I18n";

const ghostBtn =
  "flex min-h-11 items-center rounded-full border border-white/70 px-4 font-semibold text-white hover:bg-white/10 hover:no-underline focus-visible:outline-white";

export default function DataStrip({
  links,
  history,
  compact = false,
  variant = "band",
  className = "",
}: {
  links: { excel: string | null; csv: string | null; parquet: string | null };
  history: {
    first: string;
    reports: string;
    rows: string;
    tag: string | null;
    esrReleases: string | null;
    crushReleases: string | null;
    cpReleases?: string | null;
    gsReleases?: string | null;
  };
  /** Home: one sub line (the per-report release counts stay in the sidebar and on /data/). */
  compact?: boolean;
  /** band: a full-width strip (text left, buttons right). card: a cell of the home grid, text over
   *  the buttons and vertically centred, so it matches the height of the card beside it. */
  variant?: "band" | "card";
  className?: string;
}) {
  const t = useT();
  const titleKey = history.cpReleases || history.gsReleases
    ? "data.titleAll"
    : history.esrReleases
    ? history.crushReleases
      ? "data.titleEsrCrush"
      : "data.titleEsr"
    : history.crushReleases
      ? "data.titleCrush"
      : "data.title";
  return (
    <section
      aria-labelledby="h-data"
      className={
        variant === "card"
          ? `flex min-w-0 flex-col justify-center gap-[18px] rounded-2xl px-4 py-[18px] text-white min-[560px]:px-6 min-[560px]:py-5 ${className}`
          : `flex flex-wrap items-center gap-x-7 gap-y-4 rounded-2xl px-[22px] py-5 text-white ${className}`
      }
      style={{ background: "var(--data-bg)" }}
      data-testid={variant === "card" ? "data-card" : "data-strip"}
    >
      <div className={variant === "card" ? "min-w-0" : "min-w-0 flex-[1_1_280px]"}>
        <div className="text-xs font-semibold uppercase tracking-[0.06em]">
          <T k="data.eyebrow" />
        </div>
        <h2 id="h-data" className="m-0 mt-1 text-lg font-bold leading-[1.3]">
          <T k={titleKey} v={{ first: history.first }} />
        </h2>
        <div className="text-[13px]">
          <T k="data.sub" v={{ reports: history.reports, rows: history.rows, tag: history.tag ?? t("footer.local") }} />
          {!compact && history.esrReleases && (
            <>
              {" · "}
              <T k="data.subEsr" v={{ releases: history.esrReleases }} />
            </>
          )}
          {!compact && history.crushReleases && (
            <>
              {" · "}
              <T k="data.subCrush" v={{ releases: history.crushReleases }} />
            </>
          )}
          {!compact && history.cpReleases && (
            <>
              {" · "}
              <T k="data.subCp" v={{ releases: history.cpReleases }} />
            </>
          )}
          {!compact && history.gsReleases && (
            <>
              {" · "}
              <T k="data.subGs" v={{ releases: history.gsReleases }} />
            </>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {links.excel && (
          <a
            href={links.excel}
            download
            className="flex min-h-11 items-center rounded-full bg-white px-4 font-bold hover:no-underline focus-visible:outline-white"
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
