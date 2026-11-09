// Shapes of the cut-A JSON written by the Python publisher (see docs/DATA_CONTRACT.md).
// Consumed by lib/data.ts (loaders), lib/insight-text.ts (insight copy) and the report pages.
//   insights.json                       src/usda_reports/insights/schema.py (JSON Schema: docs/schemas/insights.schema.json)
//   catalog.json                        src/usda_reports/publish/catalog.py
//   reports/export_sales/*.json         src/usda_reports/publish/web_export_sales.py
//   reports/oilseed_crush/*.json        src/usda_reports/publish/web_crush.py
//   meta.json `reports`                 src/usda_reports/publish/run.py (reports_meta)
//   build.json                          `usda-reports build-info`

// ------------------------------------------------------------------ insights.json

export type InsightRule = "W1" | "W2" | "W3" | "W4" | "E1" | "E2" | "E3" | "F1" | "F2" | "F3";
export type InsightKind =
  | "change_vs_prev"
  | "stocks_to_use_rank"
  | "revision_rank"
  | "brazil_soy_export_share"
  | "commitment_pace"
  | "required_weekly_sales"
  | "china_share_soy"
  | "crush_pace"
  | "required_monthly_crush"
  | "oil_yield";
export type SuppressedReason =
  | "n_below_min"
  | "stale_input"
  | "asof_missing"
  | "weeks_remaining_below_min"
  | "months_remaining_below_min"
  | "no_data"
  | "first_projection"
  | "gap_after_cancelled_report";
export type Caveat =
  | "small_sample"
  | "esr_not_census"
  | "unknown_may_hide_china"
  | "local_marketing_years"
  | "history_point_in_time"
  | "latest_only_history"
  | "partial_denominator"
  | "crush_history_from_2015"
  | "nass_revises_previous_month"
  | "wasde_oil_year_oct_sep";
export type InputRef = { report_id: string; release_key: string };

export type Insight = {
  id: string; // "W2:corn", "E1:soybeans", "F1:soybeans", "W1:headline" …
  rule: InsightRule;
  report_id: "wasde" | "export_sales" | "oilseed_crush" | "cross";
  commodity_id: string | null;
  kind: InsightKind;
  params: Record<string, unknown>; // numbers / ids only; see the per-rule params below
  n: number | null; // always shown
  window: string | null;
  robustness: "robust" | "fragile";
  caveats: Caveat[];
  inputs: InputRef[];
  as_of: string | null; // UTC ISO of the newest input release
  suppressed_reason: SuppressedReason | null; // non-null: never show as a finding
};

// Per-rule params (subset that the UI needs; every key listed is always present).
export type RankParams = { k: number; order: "tightest_first" | "largest_abs_first" | "highest_first"; market_year: string };
export type W2Params = RankParams & {
  table_id: string;
  stocks_to_use_pct: number;
  ending_stocks: number | null;
  unit_id: string;
  tercile: "tight" | "middle" | "loose";
  percentile_tighter_than: number | null; // only when n >= 10
  first_market_year: string;
  history: { market_year: string; stocks_to_use_pct: number }[];
};
export type E1Params = {
  market_year: string;
  esr_market_year: number;
  week_ending: string;
  week_of_my: number;
  release_key: string;
  unit_id: "mt";
  wasde_release_key: string | null;
  target_mt: number | null;
  target_native: number | null;
  target_unit_id: string | null;
  target_flag: string | null;
  total_commitment_mt: number | null;
  accumulated_exports_mt: number | null;
  outstanding_sales_mt: number | null;
  pct: number | null; // share (0.38 = 38%)
  hist_mean: number | null;
  hist_min: number | null;
  hist_max: number | null;
  position: "below" | "inside" | "above" | null;
  outside_distance: number | null;
  history: { market_year: string; pct: number; wasde_release_key: string }[];
};

export type HeroClause = {
  kind: "wasde_tightness" | "esr_pace";
  commodity_id: string;
  direction: "tighter" | "looser" | "lagging" | "ahead" | "in_line";
  insight_ids: string[];
};
export type Hero = {
  kind: "story" | "fallback";
  clauses: HeroClause[];
  n_reports: number; // story: "Computed from {n} reports since {since}"; fallback: "{n} USDA reports released since {since}"
  since: string | null;
  reports: InputRef[];
};

export type InsightsDoc = {
  schema_version: 1;
  generated_at: string;
  data_tag: string | null;
  gates: {
    min_n: number;
    percentile_min_n: number;
    small_sample_below: number;
    e2_min_weeks_remaining: number;
    f2_min_months_remaining?: number; // since cut B
    stale_after_days: Record<string, number>;
  };
  n_screened: Record<string, number>;
  insights: Insight[];
  home_cards: string[]; // insight ids, in display order (≤ 5)
  hero: Hero;
};

// ------------------------------------------------------------------ catalog.json

export type CatalogFile = {
  file: string;
  report_id: string;
  dataset: string;
  schema_version: number;
  format: "parquet" | "csv";
  rows: number;
  bytes: number;
  sha256: string;
  coverage: { start: string | null; end: string | null } | null;
  latest_release_key: string | null;
  legacy_alias_of: string | null;
  release_url: string | null; // GitHub release asset (not CORS-readable: plain link)
  site_url: string | null; // served by the site (previews ≤ 5 MB)
};
export type ReleaseCatalog = {
  schema_version: 1;
  generated_at: string;
  repo: string;
  data_tag: string | null;
  release_page: string | null;
  datapackage: { file: string; site_url: string; release_url: string | null };
  web_data: { file: string; release_url: string | null };
  reports: Record<
    string,
    {
      title: string;
      agency: string;
      cadence: "weekly" | "monthly" | "quarterly";
      licence: string;
      latest_release_key?: string;
      release_ts_utc?: string;
      next_release?: string | null;
      rows?: number;
      releases?: number;
      vintage_note?: string;
    }
  >;
  files: CatalogFile[];
};

// ------------------------------------------------- reports/export_sales/<commodity>.json

export type EsrIndex = {
  schema_version: 1;
  report_id: "export_sales";
  latest: EsrLatest;
  next_release: string | null;
  commodities: { id: string; label: string; market_year: string; file: string }[];
};
export type EsrLatest = {
  release_key: string;
  release_ts_utc: string | null;
  release_ts_source: "api" | "calendar_override" | "calendar_rule";
  week_ending: string;
  week_of_my: number;
  vintage_quality: "captured" | "latest_only";
};
/** [week_of_my, pct_of_target (share; null without an as-of target), wasde_release_key] */
export type PacePoint = [number, number | null, string | null];
/** [week_of_my, mean, min, max, n] of the 5 prior MYs at that week */
export type PaceBand = [number, number | null, number | null, number | null, number];

export type EsrCommodity = {
  schema_version: 1;
  commodity_id: string;
  label: string;
  unit_id: "mt";
  market_year: string;
  esr_market_year: number;
  latest: EsrLatest;
  next_release: string | null;
  target: {
    wasde_release_key: string | null;
    wasde_release_ts_utc: string | null;
    exports_mt: number | null;
    exports_native: number | null;
    unit_id: string | null; // m_bu | k_short_tons | m_lbs
    flag: string | null;
  };
  kpis: {
    total_commitment_mt: number | null;
    accumulated_exports_mt: number | null;
    outstanding_sales_mt: number | null;
    net_sales_mt: number | null;
    weekly_exports_mt: number | null;
    next_my_net_sales_mt: number | null;
    next_my_outstanding_mt: number | null;
    net_sales_4wk_avg_mt: number | null;
    pct_of_target: number | null;
    pct_shipped: number | null;
    weeks_remaining: number;
    required_weekly_sales_mt: number | null;
    n_5yr: number;
    pct_5yr_mean: number | null;
    pct_5yr_min: number | null;
    pct_5yr_max: number | null;
  };
  pace: {
    basis: "pct_of_usda_projection_at_the_time"; // legend: "history: % of the USDA projection at the time"
    series: { market_year: string; esr_market_year: number; current: boolean; points: PacePoint[] }[];
    band: PaceBand[];
  };
  weekly: {
    week_ending: string;
    week_of_my: number;
    release_key: string;
    net_sales_mt: number | null;
    weekly_exports_mt: number | null;
    next_my_net_sales_mt: number | null;
    net_sales_4wk_avg_mt: number | null;
  }[];
  destinations: {
    week_ending: string;
    total_commitment_mt: number;
    n_destinations: number;
    rows: {
      country_id: string; // "china", "unknown" (always listed when present), …
      country_label: string;
      total_commitment_mt: number | null;
      accumulated_exports_mt: number | null;
      outstanding_sales_mt: number | null;
      net_sales_mt: number | null;
      share: number | null;
    }[];
    other_mt: number;
    china_unknown_history: { market_year: string; china_share: number | null; unknown_share: number | null }[];
  };
};

// ------------------------------------------------- reports/oilseed_crush/<commodity>.json

export type CrushLatest = {
  release_key: string; // ESMIS release date YYYY-MM-DD
  release_ts_utc: string | null;
  month: string; // first day of the data month (about two months before the release)
  month_of_my: number; // 1 = September
  first_printed_as: "current" | "previous" | null; // previous: a shutdown skipped the month's own release
  vintage_quality: "as_published";
};
export type CrushIndex = {
  schema_version: 1;
  report_id: "oilseed_crush";
  latest: CrushLatest;
  next_release: string | null;
  history_start: string; // "2015-10": first ESMIS Fats & Oils file
  commodities: { id: string; label: string; market_year: string; file: string }[];
};
/** [month_of_my, mean, min, max, n] of the 5 prior MYs at that month */
export type MonthBand = [number, number | null, number | null, number | null, number];

export type CrushCommodity = {
  schema_version: 1;
  report_id: "oilseed_crush";
  commodity_id: "soybeans";
  label: string;
  history_start: string;
  market_year: string;
  my_start: number;
  latest: CrushLatest;
  next_release: string | null;
  target: {
    wasde_release_key: string | null;
    wasde_release_ts_utc: string | null;
    crush_native: number | null; // million bushels
    crush_bu: number | null;
    unit_id: string | null; // m_bu
    flag: string | null;
    oil_release_key: string | null;
    oil_production_native: number | null; // million pounds
    oil_unit_id: string | null; // m_lbs
    implied_oil_yield_lb_bu: number | null;
  };
  kpis: {
    month_crushed_st: number | null;
    month_crushed_bu: number | null;
    month_oil_klb: number | null;
    month_meal_st: number | null;
    oil_yield_lb_bu: number | null;
    cum_bu: number | null;
    cum_st: number | null;
    pct_of_target: number | null;
    n_5yr: number;
    pct_5yr_mean: number | null;
    pct_5yr_min: number | null;
    pct_5yr_max: number | null;
    months_remaining: number;
    required_monthly_bu: number | null;
    last_my_remaining_mean_bu: number | null;
    last_my_remaining_n: number;
    n_yield_5yr: number;
    yield_5yr_mean: number | null;
    yield_5yr_min: number | null;
    yield_5yr_max: number | null;
  };
  pace: {
    basis: "pct_of_usda_projection_at_the_time";
    series: {
      market_year: string;
      my_start: number;
      current: boolean;
      points: PacePoint[]; // [month_of_my, pct, wasde_release_key]
      yield: [number, number | null][]; // [month_of_my, lb/bu as first printed]
    }[];
    band: MonthBand[];
  };
  yield: { unit_id: "lb_per_bu"; band: MonthBand[]; wasde_implied_lb_bu: number | null };
  remaining: { market_year: string; last_my_months: { month: string; month_of_my: number; crushed_bu: number | null }[] };
  monthly: {
    month: string;
    market_year: string;
    month_of_my: number;
    crushed_st: number | null;
    crushed_bu: number | null;
    oil_klb: number | null;
    meal_st: number | null;
    oil_yield_lb_bu: number | null;
    is_revised: boolean;
    latest_release_key: string;
  }[];
};

// ------------------------------------------------------------- meta.json / build.json

export type ReportMeta = {
  latest_release_key: string;
  release_ts_utc: string;
  next_release: string | null;
  rows: number;
  releases: number;
};
export type MetaReports = Record<string, ReportMeta>; // meta.json["reports"]

export type BuildInfo = {
  sha: string;
  tag: string;
  data_tag: string;
  built_at: string;
  reports: Record<
    string,
    { latest_release_key: string; release_ts_utc: string; next_release: string | null; age_days: number; status: "ok" | "stale" | "failed" }
  >;
};
