import type { Metadata } from "next";

import { T } from "@/components/chrome/I18n";
import TopBar from "@/components/chrome/TopBar";
import CrushView, { type TakeFile } from "@/components/crush/CrushView";
import { releaseInfo } from "@/lib/dashboard";
import { getCrush, getInsights, getReleaseCatalog, servedPath } from "@/lib/data";
import { NOPA_URL } from "@/lib/nopa";

export const metadata: Metadata = { title: "Soybean crush (NASS) · USDA Reports Dashboard" };

const CRUSH_DATASETS = new Set(["oilseed_crush:monthly", "cross:crush_pace"]);

/** Crush files of the release catalogue: the site copy when served, else the release asset. */
function takeFiles(): TakeFile[] {
  const cat = getReleaseCatalog();
  if (!cat) return [];
  return cat.files
    .filter((f) => CRUSH_DATASETS.has(`${f.report_id}:${f.dataset}`) && !f.legacy_alias_of)
    .map((f) => ({ f, href: servedPath(f.site_url) ?? f.release_url }))
    .filter((x): x is { f: (typeof cat.files)[number]; href: string } => Boolean(x.href))
    .map(({ f, href }) => ({ file: f.file, dataset: f.dataset, format: f.format, href, bytes: f.bytes, rows: f.rows }));
}

export default function OilseedCrushPage() {
  const d = getCrush();
  if (!d) {
    return (
      <>
        <TopBar title={<T k="report.crush" />} release={releaseInfo()} />
        <p className="m-0 text-muted">
          <T k="crush.none" />
        </p>
        <aside className="card flex flex-col gap-1.5 p-5 text-[13px]" data-testid="nopa-note">
          <p className="m-0">
            <T k="crush.nopa.note" />
          </p>
          <a href={NOPA_URL} rel="noopener noreferrer" className="inline-flex min-h-11 items-center self-start text-link">
            <T k="crush.nopa.link" />
          </a>
        </aside>
      </>
    );
  }
  return <CrushView d={d} insights={getInsights()} take={takeFiles()} release={releaseInfo()} />;
}
