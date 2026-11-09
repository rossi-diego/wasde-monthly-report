import type { Metadata } from "next";

import { T } from "@/components/chrome/I18n";
import TopBar from "@/components/chrome/TopBar";
import GrainStocksView from "@/components/stocks/GrainStocksView";
import { releaseInfo } from "@/lib/dashboard";
import { getGrainStocks, getGrainStocksIndex, getInsights, takeFiles } from "@/lib/data";

export const metadata: Metadata = { title: "Grain Stocks (NASS) · USDA Reports Dashboard" };

const DATASETS = new Set(["grain_stocks:quarterly", "cross:stocks_vs_wasde", "cross:stocks_disappearance"]);

export default function GrainStocksPage() {
  const index = getGrainStocksIndex();
  const commodities = getGrainStocks();
  if (!index || commodities.length === 0) {
    return (
      <>
        <TopBar title={<T k="report.grain_stocks" />} release={releaseInfo()} />
        <p className="m-0 text-muted">
          <T k="gs.none" />
        </p>
      </>
    );
  }
  return <GrainStocksView index={index} commodities={commodities} insights={getInsights()} take={takeFiles(DATASETS)} release={releaseInfo()} />;
}
