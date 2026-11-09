import "server-only";

import fs from "node:fs";
import path from "node:path";

import type { CatalogEntry, CommodityIndex, Meta, Overview, Series } from "./types";

// Build-time loaders: the static export embeds the latest data in every page.
const DATA = path.join(process.cwd(), "public", "data");

function read<T>(rel: string): T {
  return JSON.parse(fs.readFileSync(path.join(DATA, rel), "utf-8")) as T;
}

export const getMeta = () => read<Meta>("meta.json");
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
