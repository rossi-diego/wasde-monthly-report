"use client";

import { useLang, useT } from "@/components/chrome/I18n";
import { bytes } from "@/lib/format";
import type { Key } from "@/lib/i18n";
import { commodityName } from "@/lib/labels";
import type { Meta } from "@/lib/types";

type Download = Meta["downloads"][number];

/** The publisher writes file labels in English; in PT they are named from the file pattern. */
function ptText(d: Download, t: (k: Key, v?: Record<string, string | number>) => string, lang: "en" | "pt") {
  const hist = /^wasde_history_(.+)\.xlsx$/.exec(d.file);
  if (hist) return { label: t("dl.history", { c: commodityName(hist[1], lang, hist[1]) }), desc: t("dl.historyDesc") };
  if (/_latest\.xlsx$/.test(d.file)) return { label: t("dl.latest"), desc: t("dl.latestDesc") };
  if (/\.parquet$/.test(d.file)) return { label: t("dl.parquet"), desc: t("dl.parquetDesc") };
  if (/\.csv(\.gz)?$/.test(d.file)) return { label: t("dl.csv"), desc: t("dl.csvDesc") };
  return null;
}

export default function FileCards({ downloads, tag }: { downloads: Download[]; tag: string | null }) {
  const t = useT();
  const { lang } = useLang();
  return (
    <ul className="grid-fit-240 m-0 list-none p-0">
      {downloads.map((d) => {
        const pt = lang === "pt" ? ptText(d, t, lang) : null;
        return (
          <li key={d.file} className="card flex flex-col gap-2 p-4" lang={pt || lang === "en" ? undefined : "en"}>
            <div className="flex items-start justify-between gap-2">
              <h3 className="m-0 text-[15px] font-semibold">{pt?.label ?? d.label}</h3>
              <span className="shrink-0 rounded-full bg-bg px-2 py-0.5 text-xs text-muted">{bytes(d.bytes)}</span>
            </div>
            <p className="m-0 flex-1 text-[13px] text-muted">{pt?.desc ?? d.description}</p>
            <div className="flex flex-wrap gap-x-4 text-[13px]">
              <a className="inline-flex min-h-11 items-center font-semibold text-link" href={`/data/${d.url}`} download>
                {t("cat.download", { ext: d.file.split(".").slice(1).join(".") })}
              </a>
              {d.release_url && (
                <a className="inline-flex min-h-11 items-center text-muted underline" href={d.release_url}>
                  {t("cat.versioned", { tag: tag ?? "" })}
                </a>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
