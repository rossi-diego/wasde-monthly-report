import type { Metadata } from "next";
import { notFound } from "next/navigation";

import CommodityView from "@/components/CommodityView";
import { commodityPills, releaseInfo } from "@/lib/dashboard";
import { getIndex, getSeries } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return getIndex().map((c) => ({ slug: c.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const c = getIndex().find((x) => x.id === slug);
  return { title: c ? `${c.label} · USDA Reports Dashboard` : "USDA Reports Dashboard" };
}

export default async function CommodityPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const entry = getIndex().find((x) => x.id === slug);
  if (!entry) notFound();
  const initial = getSeries(entry.id, "united_states");
  return <CommodityView entry={entry} initial={initial} release={releaseInfo()} pills={commodityPills()} />;
}
