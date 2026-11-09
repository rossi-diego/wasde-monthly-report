import type { Metadata } from "next";

import DataCatalogue from "@/components/DataCatalogue";

export const metadata: Metadata = { title: "Data catalogue · USDA Reports Dashboard" };

export default function DataPage() {
  return <DataCatalogue />;
}
