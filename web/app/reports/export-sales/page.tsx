import type { Metadata } from "next";

import { T } from "@/components/chrome/I18n";
import TopBar from "@/components/chrome/TopBar";
import EsrView, { type TakeFile } from "@/components/esr/EsrView";
import { releaseInfo } from "@/lib/dashboard";
import { getEsrCommodities, getEsrIndex, getInsights, getReleaseCatalog, servedPath } from "@/lib/data";

export const metadata: Metadata = { title: "Export Sales · USDA Reports Dashboard" };

/** ESR and cross-report files of the release catalogue: the site copy when served, else the release asset. */
function takeFiles(): TakeFile[] {
  const cat = getReleaseCatalog();
  if (!cat) return [];
  return cat.files
    .filter((f) => (f.report_id === "export_sales" || f.report_id === "cross") && !f.legacy_alias_of)
    .map((f) => ({ f, href: servedPath(f.site_url) ?? f.release_url }))
    .filter((x): x is { f: (typeof cat.files)[number]; href: string } => Boolean(x.href))
    .map(({ f, href }) => ({ file: f.file, dataset: f.dataset, format: f.format, href, bytes: f.bytes, rows: f.rows }));
}

export default function ExportSalesPage() {
  const index = getEsrIndex();
  const commodities = getEsrCommodities();
  if (!index || commodities.length === 0) {
    return (
      <>
        <TopBar title={<T k="report.export_sales" />} release={releaseInfo()} />
        <p className="m-0 text-muted">
          <T k="esr.none" />
        </p>
      </>
    );
  }
  return <EsrView index={index} commodities={commodities} insights={getInsights()} take={takeFiles()} release={releaseInfo()} />;
}
