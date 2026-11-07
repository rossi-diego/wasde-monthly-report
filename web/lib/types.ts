// Shapes of the JSON written by the Python publisher (src/wasde/publish/web_json.py).

export type Download = {
  file: string;
  label: string;
  description: string;
  bytes: number;
  url: string;
  release_url: string | null;
};

export type Meta = {
  generated_at: string;
  latest: { report_month: string; label: string; wasde_number: number | null; release_date: string | null };
  previous_report_month: string | null;
  next_release: string | null;
  history: { first_report: string; reports: number; rows: number };
  data_release_tag: string | null;
  downloads: Download[];
};

export type Highlight = {
  commodity: string;
  commodity_label: string;
  region_id: string;
  region: string;
  market_year: string;
  crop: "new" | "old";
  attribute: string;
  attribute_label: string;
  value: number;
  prev_value: number;
  delta: number;
  pct_delta: number | null;
  unit: string;
  unit_label: string;
  score: number;
  streak: number;
  stocks_to_use_pct: number | null;
  related: { attribute: string; label: string; delta: number; unit: string }[];
  sentence: string;
};

export type CropBlock = {
  market_year: string;
  flag: string | null;
  ending_stocks: number | null;
  prev_ending_stocks: number | null;
  delta: number | null;
  stocks_to_use_pct: number | null;
  prev_stocks_to_use_pct: number | null;
};

export type CardBlock = { unit: string; unit_label: string; new?: CropBlock; old?: CropBlock } | null;

export type Overview = {
  report_month: string;
  report_label: string;
  context: string | null;
  highlights: Highlight[];
  first_projections: { commodity: string; market_year: string; value: number; unit: string; sentence: string }[];
  cards: { commodity: string; label: string; us: CardBlock; world_ex_china: CardBlock; world: CardBlock }[];
  south_america: {
    commodity_id: string;
    region: string;
    region_id: string;
    market_year: string;
    value: number;
    prev_value: number | null;
    delta: number | null;
    unit_id: string;
  }[];
};

export type RegionRef = { id: string; label: string; table: string; commodity: string };
export type CommodityIndex = { id: string; label: string; regions: RegionRef[] }[];

export type SeriesPoint = [cycleMonth: number | null, value: number | null, reportMonth: string, flag: string | null];

export type Series = {
  table: string;
  commodity: string;
  region: string;
  region_label: string;
  report_month: string;
  previous_report_month: string | null;
  unit: string | null;
  unit_label: string | null;
  balance_sheet: {
    columns: { market_year: string; flag: string | null }[];
    rows: { id: string; label: string; values: { value: number | null; prev: number | null; delta: number | null }[] }[];
  };
  drivers: {
    market_year: string;
    from: number | null;
    to: number | null;
    components: { id: string; label: string; value: number | null }[];
  }[];
  revisions: Record<string, { market_year: string; points: SeriesPoint[] }[]>;
  stocks_to_use_history: {
    market_year: string;
    ending_stocks: number | null;
    stocks_to_use_pct: number | null;
    status: "current" | "final";
    flag: string | null;
  }[];
  stocks_to_use_percentile: number | null;
  n_final_years: number;
};

export type CatalogEntry = {
  id: string;
  label: string;
  rows: number;
  file: string;
  bytes: number;
  commodities: string[];
  regions: string[];
  attributes: string[];
  market_years: string[];
  first_report: string;
  last_report: string;
};
