import type { Metadata } from "next";

import WasdeView from "@/components/wasde/WasdeView";
import { commodityPills, releaseInfo } from "@/lib/dashboard";
import { getInsights } from "@/lib/data";

export const metadata: Metadata = { title: "WASDE · USDA Reports Dashboard" };

export default function WasdePage() {
  return <WasdeView insights={getInsights()} release={releaseInfo()} pills={commodityPills()} />;
}
