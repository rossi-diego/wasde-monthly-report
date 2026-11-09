import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { T } from "@/components/chrome/I18n";
import TopBar from "@/components/chrome/TopBar";
import LensView from "@/components/lens/LensView";
import { releaseInfo } from "@/lib/dashboard";
import { getInsights, getLenses, getReleaseCatalog, takeFiles } from "@/lib/data";
import { LENSES } from "@/lib/reports";

export const dynamicParams = false;

export function generateStaticParams() {
  return LENSES.map((l) => ({ slug: l.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const l = LENSES.find((x) => x.id === slug);
  return { title: l ? `${l.label}: every report · USDA Reports Dashboard` : "USDA Reports Dashboard" };
}

export default async function CommodityLensPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const def = LENSES.find((x) => x.id === slug);
  if (!def) notFound();
  const lens = getLenses().find((l) => l.commodity_id === slug);
  if (!lens) {
    return (
      <>
        <TopBar title={def.label} release={releaseInfo()} />
        <p className="m-0 text-muted">
          <T k="lens.none" />
        </p>
      </>
    );
  }
  const all = new Set((getReleaseCatalog()?.files ?? []).map((f) => `${f.report_id}:${f.dataset}`));
  return <LensView lens={lens} insights={getInsights()} files={takeFiles(all)} release={releaseInfo()} />;
}
