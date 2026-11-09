// Portuguese names for the ids the published JSON uses (commodities, regions, balance-sheet
// lines). The JSON labels are English; an id missing here falls back to that label.

import type { Lang } from "./i18n";

const COMMODITY_PT: Record<string, string> = {
  corn: "milho",
  soybeans: "soja",
  soybean_meal: "farelo de soja",
  soybean_oil: "óleo de soja",
  wheat: "trigo",
  cotton: "algodão",
  rice: "arroz",
  sorghum: "sorgo",
  barley: "cevada",
  sugar: "açúcar",
};

const REGION_PT: Record<string, string> = {
  united_states: "EUA",
  world: "Mundo",
  world_less_china: "Mundo ex-China",
  brazil: "Brasil",
  argentina: "Argentina",
  china: "China",
  european_union: "União Europeia",
  russia: "Rússia",
  ukraine: "Ucrânia",
  canada: "Canadá",
  mexico: "México",
  japan: "Japão",
  australia: "Austrália",
  india: "Índia",
  major_exporters: "Principais exportadores",
  major_importers: "Principais importadores",
};

const ATTR_PT: Record<string, string> = {
  beginning_stocks: "estoques iniciais",
  production: "produção",
  imports: "importações",
  domestic_feed: "ração",
  domestic_total: "uso doméstico",
  exports: "exportações",
  ending_stocks: "estoques finais",
  stocks_to_use_pct: "estoque/uso (%)",
  area_planted: "área plantada",
  area_harvested: "área colhida",
  yield: "produtividade",
  total_supply: "oferta total",
  feed_residual: "ração e residual",
  food_seed_industrial: "alimentos, sementes e indústria",
  ethanol: "dos quais etanol",
  total_use: "uso total",
  farm_price: "preço médio ao produtor",
  crush: "esmagamento",
};

const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);

/** "Soybeans" / "Soja" (pill and title case). */
export function commodityName(id: string, lang: Lang, fallback: string): string {
  return lang === "pt" && COMMODITY_PT[id] ? cap(COMMODITY_PT[id]) : fallback;
}

export function regionName(id: string, lang: Lang, fallback: string): string {
  return lang === "pt" ? (REGION_PT[id] ?? fallback) : fallback;
}

/** Lower-case balance-sheet line ("ending stocks" / "estoques finais"). */
export function attrName(id: string | null | undefined, lang: Lang, fallback: string): string {
  if (lang === "pt" && id && ATTR_PT[id]) return ATTR_PT[id];
  return fallback.trim().toLowerCase();
}

/** Lower-case commodity noun for PT copy ("soja"). */
export const commodityNounPt = (id: string): string | undefined => COMMODITY_PT[id];
