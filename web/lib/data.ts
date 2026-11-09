import "server-only";

import fs from "node:fs";
import path from "node:path";

import type {
  CommodityLens,
  CropProgressCrop,
  CropProgressIndex,
  CrushCommodity,
  CrushIndex,
  EsrCommodity,
  EsrIndex,
  GrainStocksCommodity,
  GrainStocksIndex,
  InsightsDoc,
  LensIndex,
  MetaReports,
  ReleaseCatalog,
  TakeFile,
} from "./data-contract";
import type { CatalogEntry, CommodityIndex, Meta, Overview, Series } from "./types";

// Build-time loaders: the static export embeds the latest data in every page.
const PUBLIC = path.join(process.cwd(), "public");
const DATA = path.join(PUBLIC, "data");

function read<T>(rel: string): T {
  return JSON.parse(fs.readFileSync(path.join(DATA, rel), "utf-8")) as T;
}

/** Optional cut-A files: a data release built before them simply has no such page content. */
function readOptional<T>(rel: string): T | null {
  const p = path.join(DATA, rel);
  return fs.existsSync(p) ? (JSON.parse(fs.readFileSync(p, "utf-8")) as T) : null;
}

export const getMeta = () => read<Meta>("meta.json");
export const getMetaReports = (): MetaReports => (read<Meta & { reports?: MetaReports }>("meta.json").reports ?? {});
export const getOverview = () => read<Overview>("overview.json");
export const getIndex = () => read<CommodityIndex>("commodities/index.json");
// WASDE table index for the explorer. Since cut A it is `wasde_tables.json` and
// `catalog.json` is the release catalogue (see lib/data-contract.ts); data releases built
// before that still carry the table index as `catalog.json` (an array).
export const getCatalog = (): CatalogEntry[] => {
  if (fs.existsSync(path.join(DATA, "wasde_tables.json"))) return read<CatalogEntry[]>("wasde_tables.json");
  const legacy = read<unknown>("catalog.json");
  return Array.isArray(legacy) ? (legacy as CatalogEntry[]) : [];
};
export const getSeries = (commodity: string, region: string) =>
  read<Series>(`commodities/${commodity}/${region}.json`);

export const getInsights = () => {
  const d = readOptional<InsightsDoc>("insights.json");
  return d && d.schema_version === 1 ? d : null;
};

/** The release catalogue (null for a pre-cut-A build, where catalog.json is the table index). */
export const getReleaseCatalog = (): ReleaseCatalog | null => {
  const d = readOptional<unknown>("catalog.json");
  return d && !Array.isArray(d) && (d as ReleaseCatalog).schema_version === 1 ? (d as ReleaseCatalog) : null;
};

export const getEsrIndex = () => readOptional<EsrIndex>("reports/export_sales/index.json");

export function getEsrCommodities(): EsrCommodity[] {
  const idx = getEsrIndex();
  if (!idx) return [];
  return idx.commodities
    .map((c) => readOptional<EsrCommodity>(c.file))
    .filter((c): c is EsrCommodity => c !== null);
}

export const getCrushIndex = () => readOptional<CrushIndex>("reports/oilseed_crush/index.json");

/** The soybean crush page payload (null for a build without NASS crush data). */
export function getCrush(): CrushCommodity | null {
  const f = getCrushIndex()?.commodities[0]?.file;
  return f ? readOptional<CrushCommodity>(f) : null;
}

// ---------------------------------------------------------------------- cut C

export const getCropProgressIndex = () => readOptional<CropProgressIndex>("reports/crop_progress/index.json");

/** Every crop page payload (empty for a build without Crop Progress data). */
export function getCropProgressCrops(): CropProgressCrop[] {
  const idx = getCropProgressIndex();
  if (!idx) return [];
  return idx.crops.map((c) => readOptional<CropProgressCrop>(c.file)).filter((c): c is CropProgressCrop => c !== null);
}

export const getGrainStocksIndex = () => readOptional<GrainStocksIndex>("reports/grain_stocks/index.json");

export function getGrainStocks(): GrainStocksCommodity[] {
  const idx = getGrainStocksIndex();
  if (!idx) return [];
  return idx.commodities.map((c) => readOptional<GrainStocksCommodity>(c.file)).filter((c): c is GrainStocksCommodity => c !== null);
}

export const getLensIndex = () => readOptional<LensIndex>("lens/index.json");

export function getLenses(): CommodityLens[] {
  const idx = getLensIndex();
  if (!idx) return [];
  return idx.commodities.map((c) => readOptional<CommodityLens>(c.file)).filter((c): c is CommodityLens => c !== null);
}

/** Per-report latest release: meta.json `reports`, completed from catalog.json (a site built
 *  from an older data release with newer report JSON has the report in the catalogue only). */
export function getReportsMeta(): MetaReports {
  const out: MetaReports = { ...(getReleaseCatalog()?.reports ?? {}) } as unknown as MetaReports;
  for (const [id, r] of Object.entries(out)) if (!r.latest_release_key) delete out[id];
  return { ...out, ...getMetaReports() };
}

/** Catalogue files of the given datasets ("report:dataset"), linked to the site copy when
 *  this build serves it, else to the release asset; files with neither are dropped. */
export function takeFiles(datasets: Set<string>): TakeFile[] {
  const cat = getReleaseCatalog();
  if (!cat) return [];
  return cat.files
    .filter((f) => datasets.has(`${f.report_id}:${f.dataset}`) && !f.legacy_alias_of)
    .map((f) => ({ f, href: servedPath(f.site_url) ?? f.release_url }))
    .filter((x): x is { f: (typeof cat.files)[number]; href: string } => Boolean(x.href))
    .map(({ f, href }) => ({ file: f.file, report_id: f.report_id, dataset: f.dataset, format: f.format, href, bytes: f.bytes, rows: f.rows }));
}

/** Site path ("/data/downloads/x.parquet") of a catalogue file when the build serves it, else null. */
export function servedPath(siteUrl: string | null | undefined): string | null {
  if (!siteUrl) return null;
  const rel = siteUrl.replace(/^\/+/, "");
  return fs.existsSync(path.join(PUBLIC, rel)) ? `/${rel}` : null;
}
