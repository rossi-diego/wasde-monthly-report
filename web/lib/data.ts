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
export const getCatalog = () => read<CatalogEntry[]>("catalog.json");
export const getSeries = (commodity: string, region: string) =>
  read<Series>(`commodities/${commodity}/${region}.json`);
