import type { Metadata } from "next";

import DataCatalogue from "@/components/DataCatalogue";

// Same content as /data/ (the catalogue); kept so existing links keep working.
export const metadata: Metadata = { title: "Data & downloads · USDA Reports Dashboard" };

export default function DownloadsPage() {
  return <DataCatalogue />;
}
