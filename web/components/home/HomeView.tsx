"use client";

import { T, useLang } from "@/components/chrome/I18n";
import TopBar, { type ReleaseInfo } from "@/components/chrome/TopBar";
import DataStrip from "@/components/home/DataStrip";
import ExploreCommodities from "@/components/home/ExploreCommodities";
import ReportTiles, { LeadCard } from "@/components/home/InsightCards";
import BiggestRevisions from "@/components/wasde/BiggestRevisions";
import type { HomeData } from "@/lib/dashboard";
import { heroEvidence, shownChangeKeys } from "@/lib/lens";
import type { CommodityLens, InsightsDoc } from "@/lib/data-contract";
import type { Lang } from "@/lib/i18n";

/** Grid of a home row: one column below 1280px, then 12 columns cut 7 | 5, the same column lines
 *  in both rows. Cards stretch to the row height and pin their footer to the bottom. */
const ROW = "grid grid-cols-1 items-stretch gap-4 min-[1280px]:grid-cols-12";
const span = (cols: 7 | 5 | 12) =>
  cols === 7 ? "min-[1280px]:col-span-7" : cols === 5 ? "min-[1280px]:col-span-5" : "min-[1280px]:col-span-12";

/** The overview is a front door, top-anchored: the title, one solid tile per report right under
 *  it, then two card rows on one 7 | 5 grid — the lead story (the hero sentence and its evidence,
 *  with n and the range) beside what changed in WASDE, and the data downloads beside the commodity
 *  pages. The charts live on the report and commodity pages. */
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
  /** lens/<commodity>.json (cut C): the "Explore by commodity" tiles. */
  lenses?: CommodityLens[];
}) {
  const { lang } = useLang();
  const data = all[lang] ?? all.en;
  // A change the WASDE tile (or the lead evidence) already prints is not repeated in the list.
  const shown = shownChangeKeys(insights);
  const changes = data.changes.filter((c) => !shown.has(c.key));
  const hasChanges = changes.length > 0;
  // Without evidence the lead card is one sentence: it and the revisions each take the full row.
  const leadWide = !hasChanges || !heroEvidence(insights);
  const hasLenses = lenses.length > 0;

  return (
    <div className="flex flex-col gap-5 min-[1024px]:gap-6">
      <TopBar title={<T k="home.title" />} release={release} />

      {insights && <ReportTiles doc={insights} />}

      <div className={ROW} data-testid="home-row-b">
        {insights && <LeadCard doc={insights} className={span(leadWide ? 12 : 7)} />}
        <BiggestRevisions
          changes={changes}
          prevMonth={data.prevMonth}
          month={data.month}
          excel={data.downloads.excel}
          limit={3}
          bars={false}
          className={span(insights && !leadWide ? 5 : 12)}
        />
      </div>

      <div className={ROW} data-testid="home-row-c">
        <DataStrip links={data.downloads} history={data.history} compact variant="card" className={span(hasLenses ? 7 : 12)} />
        {hasLenses && <ExploreCommodities lenses={lenses} className={span(5)} />}
      </div>
    </div>
  );
}
