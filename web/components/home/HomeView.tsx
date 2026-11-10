"use client";

import { T, useLang } from "@/components/chrome/I18n";
import TopBar, { type ReleaseInfo } from "@/components/chrome/TopBar";
import DataStrip from "@/components/home/DataStrip";
import ExploreCommodities from "@/components/home/ExploreCommodities";
import ReportTiles, { HeroBand } from "@/components/home/InsightCards";
import BiggestRevisions from "@/components/wasde/BiggestRevisions";
import type { HomeData } from "@/lib/dashboard";
import { shownChangeKeys } from "@/lib/lens";
import type { CommodityLens, InsightsDoc } from "@/lib/data-contract";
import type { Lang } from "@/lib/i18n";

/** The overview is a front door: what is new (hero), how sure we are (the evidence card with its
 *  n and range), and where to go next (one tile per report, the WASDE revisions, the commodity
 *  pages). The charts live on the report and commodity pages. */
export default function HomeView({
  data: all,
  release,
  insights,
  lenses = [],
}: {
  /** Every derived string in each language (computed at build time). */
  data: Record<Lang, HomeData>;
  release: ReleaseInfo;
  /** insights.json (null in a build without it: the home then shows WASDE only). */
  insights: InsightsDoc | null;
  /** lens/<commodity>.json (cut C): the "Explore by commodity" rows. */
  lenses?: CommodityLens[];
}) {
  const { lang } = useLang();
  const data = all[lang] ?? all.en;
  // A change the WASDE tile (or the hero evidence) already prints is not repeated in the list.
  const shown = shownChangeKeys(insights);
  const changes = data.changes.filter((c) => !shown.has(c.key));

  return (
    <>
      <TopBar title={<T k="home.title" />} release={release} />

      {insights && <HeroBand doc={insights} />}

      {insights && <ReportTiles doc={insights} />}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-6">
        <div className={`flex min-w-0 flex-col [&>*]:flex-1 ${lenses.length ? "lg:col-span-7" : "lg:col-span-12"}`}>
          <BiggestRevisions changes={changes} prevMonth={data.prevMonth} excel={data.downloads.excel} limit={3} bars={false} />
        </div>
        {lenses.length > 0 && (
          <div className="flex min-w-0 flex-col lg:col-span-5 [&>*]:flex-1">
            <ExploreCommodities lenses={lenses} />
          </div>
        )}
      </div>

      <DataStrip links={data.downloads} history={data.history} compact />
    </>
  );
}
