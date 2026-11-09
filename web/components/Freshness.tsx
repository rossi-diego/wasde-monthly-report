"use client";

import { useEffect, useState } from "react";

import { useLang, useT } from "@/components/chrome/I18n";
import { shortDate } from "@/lib/format";
import type { BuildInfo } from "@/lib/data-contract";
import type { Key } from "@/lib/i18n";

const DAY = 86_400_000;

/** Days since a release, measured in the reader's browser (a static page cannot know "now"). */
function useAge(releaseTs: string | null | undefined) {
  const [age, setAge] = useState<number | null>(null);
  useEffect(() => {
    if (!releaseTs) return;
    const ts = Date.parse(releaseTs);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the clock is only known after hydration
    if (Number.isFinite(ts)) setAge(Math.max(0, Math.floor((Date.now() - ts) / DAY)));
  }, [releaseTs]);
  return age;
}

/** build.json (written by the release workflow) flags a failed report run; absent locally. */
function useBuildStatus(reportId: string) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    fetch("/build.json")
      .then((r) => (r.ok ? (r.json() as Promise<BuildInfo>) : null))
      .then((b) => {
        if (live && b?.reports?.[reportId]?.status === "failed") setFailed(true);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [reportId]);
  return failed;
}

export function FreshnessChip({ releaseTs, maxDays, offSeason = false }: { releaseTs: string | null | undefined; maxDays: number; offSeason?: boolean }) {
  const t = useT();
  const age = useAge(releaseTs);
  if (age === null) return null;
  // A seasonal report (Crop Progress) between seasons is not stale: nothing is scheduled.
  if (offSeason) {
    const text = age === 0 ? t("reports.age0") : age === 1 ? t("reports.age1") : t("reports.age", { d: age });
    return (
      <span data-testid="freshness" data-stale="false" data-off-season="true">
        {text} · <span className="font-semibold text-muted">{t("reports.offSeason")}</span>
      </span>
    );
  }
  const stale = age > maxDays;
  const text = age === 0 ? t("reports.age0") : age === 1 ? t("reports.age1") : t("reports.age", { d: age });
  return (
    <span data-testid="freshness" data-stale={stale ? "true" : "false"}>
      {text} ·{" "}
      <span className={`font-semibold ${stale ? "text-down" : "text-up"}`}>{stale ? t("reports.staleChip") : t("reports.ok")}</span>
    </span>
  );
}

/** Banner when a report is older than its cadence + grace, or its last run failed. */
export function StaleBanner({
  reportId,
  name,
  cadence,
  releaseTs,
  maxDays,
  offSeason = false,
}: {
  reportId: string;
  name: Key;
  cadence: Key;
  releaseTs: string | null | undefined;
  maxDays: number;
  offSeason?: boolean;
}) {
  const t = useT();
  const age = useAge(releaseTs);
  const failed = useBuildStatus(reportId);
  const stale = !offSeason && age !== null && age > maxDays;
  if (!stale && !failed) return null;
  return (
    <div role="status" data-testid="stale-banner" className="rounded-xl border border-current px-4 py-3 text-[13px] text-down">
      {failed
        ? t("reports.failed", { report: t(name) })
        : t("reports.stale", { report: t(name), d: age ?? 0, cadence: t(cadence), max: maxDays })}
    </div>
  );
}

/** A translated string whose variables are ISO dates, formatted in the active language. */
export function KeyDates({ k, dates, vars }: { k: Key; dates: Record<string, string | null | undefined>; vars?: Record<string, string | number> }) {
  const t = useT();
  const { lang } = useLang();
  const v: Record<string, string | number> = { ...vars };
  for (const [name, iso] of Object.entries(dates)) v[name] = shortDate(iso, true, lang) ?? "—";
  return <>{t(k, v)}</>;
}

/** "Week ending Oct 29, 2026 · released Nov 5, 2026" in the active language. */
export function EsrLatestText({ week, release }: { week: string; release: string }) {
  const t = useT();
  const { lang } = useLang();
  return <>{t("reports.esrLatest", { week: shortDate(week, true, lang) ?? week, date: shortDate(release, true, lang) ?? release })}</>;
}
