import type { Metadata } from "next";

import { T } from "@/components/chrome/I18n";
import TopBar from "@/components/chrome/TopBar";
import CropProgressView from "@/components/progress/CropProgressView";
import { releaseInfo } from "@/lib/dashboard";
import { getCropProgressCrops, getCropProgressIndex, getInsights, takeFiles } from "@/lib/data";

export const metadata: Metadata = { title: "Crop Progress (NASS) · USDA Reports Dashboard" };

const DATASETS = new Set(["crop_progress:weekly", "crop_progress:condition"]);

export default function CropProgressPage() {
  const index = getCropProgressIndex();
  const crops = getCropProgressCrops();
  if (!index || crops.length === 0) {
    return (
      <>
        <TopBar title={<T k="report.crop_progress" />} release={releaseInfo()} />
        <p className="m-0 text-muted">
          <T k="cp.none" />
        </p>
      </>
    );
  }
  return <CropProgressView index={index} crops={crops} insights={getInsights()} take={takeFiles(DATASETS)} release={releaseInfo()} />;
}
