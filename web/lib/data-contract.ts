// Shapes of the JSON written by the Python publisher (see docs/DATA_CONTRACT.md).
// Consumed by lib/data.ts (loaders), lib/insight-text.ts (insight copy) and the report pages.
//   insights.json                       src/usda_reports/insights/schema.py (JSON Schema: docs/schemas/insights.schema.json)
//   catalog.json                        src/usda_reports/publish/catalog.py
//   reports/export_sales/*.json         src/usda_reports/publish/web_export_sales.py
//   reports/oilseed_crush/*.json        src/usda_reports/publish/web_crush.py
//   reports/crop_progress/*.json        src/usda_reports/publish/web_crop_progress.py (cut C)
//   reports/grain_stocks/*.json         src/usda_reports/publish/web_grain_stocks.py (cut C)
//   lens/<commodity>.json               src/usda_reports/publish/web_commodity.py (cut C)
//   meta.json `reports`                 src/usda_reports/publish/run.py (reports_meta)
//   build.json                          `usda-reports build-info`

// ------------------------------------------------------------------ insights.json

export type InsightRule =
  | "W1" | "W2" | "W3" | "W4" | "E1" | "E2" | "E3" | "F1" | "F2" | "F3"
  | "C1" | "C2" | "C3" | "G1" | "G2" | "G3"; // prettier-ignore
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
  | "oil_yield"
  | "good_excellent" // C1
  | "stage_pace" // C2
  | "condition_index" // C3
  | "stocks_vs_wasde" // G1
  | "implied_disappearance" // G2
  | "on_farm_share"; // G3
export type SuppressedReason =
  | "n_below_min"
  | "stale_input"
  | "asof_missing"
  | "weeks_remaining_below_min"
  | "months_remaining_below_min"
  | "no_data"
  | "first_projection"
  | "gap_after_cancelled_report"
  | "season_closed"; // C2/C3 after the Crop Progress season (C1 shows the final rating)
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
  | "wasde_oil_year_oct_sep"
  | "nass_selected_states_aggregate" // Crop Progress national = NASS "<N> States" row
  | "own_5yr_same_week_by_day_of_year" // C1/C3: NASS publishes no 5-yr for condition
  | "own_5yr_final_rating" // C1 season closed: final vs the 5 prior final ratings
  | "nass_5yr_average_as_published" // C2
  | "winter_wheat_fall_ratings_next_crop"
  | "grain_stocks_first_print" // G1
  | "imports_omitted_small_for_corn_soy" // G2
  | "nass_may_revise_production_same_day" // G2
  | "nass_revises_previous_quarter"; // G3
export type InputRef = { report_id: string; release_key: string };

export type Insight = {
  id: string; // "W2:corn", "E1:soybeans", "F1:soybeans", "W1:headline" …
  rule: InsightRule;
  report_id: "wasde" | "export_sales" | "oilseed_crush" | "crop_progress" | "grain_stocks" | "cross";
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

/** Crop Progress season state carried by every C1–C3 insight. */
export type SeasonParams = {
  season_state: "in_season" | "closed"; // closed: "Season closed: final GE X% vs 5-yr Y%"
  season: number;
  season_last_scheduled: string | null;
  history_start: string; // "2010-06-07"
};
/** 5-year comparison block of C1, C3, G2, G3 (k = rank among history + current). */
export type RangeParams = {
  hist_mean: number | null;
  hist_min: number | null;
  hist_max: number | null;
  position: "below" | "inside" | "above" | null;
  outside_distance: number | null;
  k: number | null;
  order: "highest_first" | "lowest_first";
};
export type C1Params = SeasonParams &
  RangeParams & {
    crop: "corn" | "soybeans" | "winter_wheat" | "spring_wheat";
    week_ending: string;
    release_key: string;
    n_states: number | null;
    unit_id: "pct";
    final: boolean;
    ge_pct: number | null;
    good_pct: number | null;
    excellent_pct: number | null;
    nass_prev_week_ge_pct: number | null;
    nass_prev_year_ge_pct: number | null; // as published by NASS
    vs_prev_year_pp: number | null;
    history: { season: number; week_ending: string; ge_pct: number }[];
  };
export type C2Params = SeasonParams & {
  crop: string;
  week_ending: string;
  release_key: string;
  n_states: number;
  unit_id: "pct";
  stage: string; // planted | emerged | silking | … | harvested
  value_pct: number | null;
  nass_5yr_avg_pct: number | null; // NASS's own published average
  avg_years: string | null; // "2021-2025"
  pace_vs_5yr_pp: number | null;
  nass_prev_week_pct: number | null;
  nass_prev_year_pct: number | null;
  vs_prev_year_pp: number | null;
  position: "behind" | "ahead" | "on_pace" | null;
  stages: { stage: string; value_pct: number | null; nass_5yr_avg_pct: number | null; nass_prev_year_pct: number | null }[];
};
export type G1Params = {
  as_of_date: string; // corn/soybeans September 1, wheat June 1
  market_year: string; // old-crop MY whose ending stocks these are
  release_key: string;
  is_latest_release: boolean;
  unit_id: "m_bu";
  nass_total_mbu: number | null;
  wasde_release_key: string | null; // as of the Grain Stocks release
  wasde_flag: string | null;
  wasde_ending_stocks_mbu: number | null;
  surprise_mbu: number | null;
  surprise_pct: number | null; // share
  direction: "above" | "below" | "equal" | null;
  k: number | null; // rank of |surprise_pct|, 1 = largest
  order: "largest_abs_first";
  percentile_larger_than: number | null; // only when n >= 10
  first_market_year: string | null;
  history: { market_year: string; as_of_date: string; surprise_mbu: number; surprise_pct: number; wasde_release_key: string }[];
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
    home_hidden_months?: Record<string, number[]>; // since cut C: crop_progress → [12, 1, 2, 3]
    stale_after_days: Record<string, number>;
  };
  n_screened: Record<string, number>;
  insights: Insight[];
  home_cards: string[]; // insight ids, in display order (≤ 5)
  hero: Hero;
  // Since cut C: season state of seasonal reports (crop_progress).
  seasons?: Record<
    string,
    { state: "in_season" | "closed"; season: number; latest_release_key: string; last_scheduled: string | null; shown_on_home: boolean }
  >;
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

// ------------------------------------------------- reports/crop_progress/<crop>.json (cut C)

export type CropId = "corn" | "soybeans" | "winter_wheat" | "spring_wheat";
export type CropProgressLatest = {
  release_key: string; // ESMIS release date (Monday, or Tuesday after a holiday)
  release_ts_utc: string | null; // 16:00 ET
  week_ending: string; // Sunday
  vintage_quality: "as_published";
};
export type CropProgressIndex = {
  schema_version: 1;
  report_id: "crop_progress";
  latest: CropProgressLatest;
  next_release: string | null;
  history_start: string; // "2010-06-07"
  season: { state: "in_season" | "closed"; season: number; last_scheduled: string | null } | null;
  crops: { id: CropId; commodity_id: string; label: string; week_ending: string | null; file: string }[];
};
export type CropProgressCrop = {
  schema_version: 1;
  report_id: "crop_progress";
  crop: CropId;
  commodity_id: string; // winter and spring wheat are both "wheat"
  label: string;
  history_start: string;
  season: number;
  season_state: "in_season" | "closed" | null;
  latest: CropProgressLatest;
  next_release: string | null;
  n_states: number | null; // NASS "<N> States" aggregate
  week_ending: string | null; // newest week with stage tables
  stages: {
    stage: string;
    value_pct: number | null;
    nass_prev_week_pct: number | null;
    nass_prev_year_pct: number | null;
    nass_5yr_avg_pct: number | null;
    vs_5yr_avg_pp: number | null;
    avg_years: string | null;
  }[];
  condition: {
    week_ending: string;
    release_key: string | null;
    very_poor_pct: number | null;
    poor_pct: number | null;
    fair_pct: number | null;
    good_pct: number | null;
    excellent_pct: number | null;
    ge_pct: number | null;
    ci: number | null; // (1·VP + 2·P + 3·F + 4·G + 5·E)/100, 1–5
    nass_prev_week_ge_pct: number | null;
    nass_prev_year_ge_pct: number | null;
    nass_prev_year_ci: number | null;
    n_5yr: number;
    ge_5yr_mean: number | null;
    ge_5yr_min: number | null;
    ge_5yr_max: number | null;
    ci_5yr_mean: number | null;
    ci_5yr_min: number | null;
    ci_5yr_max: number | null;
  } | null;
  /** [week_ending, ge_pct, nass_prev_year_ge_pct, 5yr mean, min, max, n] */
  ge: { basis: "own_5yr_same_week_by_day_of_year"; series: [string, number | null, number | null, number | null, number | null, number | null, number][] };
  /** [week_ending, value_pct, nass_5yr_avg_pct, nass_prev_year_pct] of the stage in progress */
  stage_pace: {
    basis: "nass_5yr_average_as_published";
    stage: string | null;
    avg_years: string | null;
    series: [string, number | null, number | null, number | null][];
  };
  /** [week_ending, ci, 5yr mean, min, max, n] */
  ci: { basis: "own_5yr_same_week_by_day_of_year"; series: [string, number | null, number | null, number | null, number | null, number][] };
};

// ------------------------------------------------- reports/grain_stocks/<commodity>.json (cut C)

export type MbuBand = { mean: number | null; min: number | null; max: number | null; n: number };
export type GrainStocksLatest = {
  release_key: string;
  release_ts_utc: string | null; // 12:00 ET
  as_of_date: string; // December 1 | March 1 | June 1 | September 1
  quarter_of_my: number; // 4 = ending stocks, 1 = harvest quarter
  vintage_quality: "as_published";
};
export type GrainStocksIndex = {
  schema_version: 1;
  report_id: "grain_stocks";
  latest: GrainStocksLatest;
  next_release: string | null;
  history_start: string; // "2010-06-30"
  commodities: { id: "corn" | "soybeans" | "wheat"; label: string; as_of_date: string; file: string }[];
};
export type GrainStocksCommodity = {
  schema_version: 1;
  report_id: "grain_stocks";
  commodity_id: "corn" | "soybeans" | "wheat";
  label: string;
  history_start: string;
  unit_id: "m_bu";
  market_year: string;
  latest: GrainStocksLatest;
  next_release: string | null;
  kpis: {
    total_mbu: number | null;
    on_farm_mbu: number | null;
    off_farm_mbu: number | null;
    total_mt: number | null;
    on_farm_share: number | null;
    total_yoy_pct: number | null;
  };
  /** Chapter 1: each stock date of the current MY vs the same date of the 5 prior MYs. */
  by_quarter: {
    quarter_of_my: number;
    as_of_date: string | null;
    total_mbu: number | null;
    band_mbu: MbuBand;
    history: { market_year: string; total_mbu: number | null }[];
  }[];
  /** Chapter 2 (G1): NASS first print vs the WASDE ending stocks public at the release. */
  vs_wasde: {
    basis: "wasde_ending_stocks_public_at_release";
    rows: {
      market_year: string;
      as_of_date: string;
      release_key: string;
      nass_total_mbu: number | null;
      wasde_release_key: string | null;
      wasde_ending_stocks_mbu: number | null;
      surprise_mbu: number | null;
      surprise_pct: number | null;
    }[];
  };
  /** Chapter 3 (G2): implied disappearance of the last 8 quarters vs the same quarter, 5 prior MYs. */
  disappearance: {
    as_of_date: string;
    prev_as_of_date: string | null;
    quarter_of_my: number;
    market_year: string;
    release_key: string;
    is_harvest_quarter: boolean;
    prev_stocks_mbu: number | null;
    production_mbu: number | null; // WASDE as of the release, harvest quarter only (else 0)
    wasde_release_key: string | null;
    stocks_mbu: number | null;
    implied_disappearance_mbu: number | null;
    band_mbu: MbuBand;
  }[];
  quarters: {
    as_of_date: string;
    market_year: string;
    quarter_of_my: number;
    on_farm_mbu: number | null;
    off_farm_mbu: number | null;
    total_mbu: number | null;
    total_first_mbu: number | null;
    is_revised: boolean;
    first_release_key: string;
  }[];
};

// ------------------------------------------------- lens/<commodity>.json (cut C, /commodities)

export type LensMetric = {
  metric: string; // production | exports | ending_stocks | crush | total_commitment | pct_of_usda_target | month_crushed | <stage>_pct | good_excellent_pct | condition_index | total_stocks | on_farm_share | ending_stocks_vs_usda
  value: number | null;
  unit_id: string | null; // m_bu | mt | bu | k_bu | pct | share | index_1_5
  period: string | null; // marketing year, week ending, month or stock date
  period_date: string | null;
  market_year: string | null;
  release_key: string | null;
  release_ts_utc: string | null;
  source_url: string | null;
};
export type CommodityLens = {
  schema_version: 1;
  commodity_id: "soybeans" | "corn";
  label: string;
  n_reports: number;
  reports: {
    report_id: "wasde" | "export_sales" | "oilseed_crush" | "crop_progress" | "grain_stocks";
    title: string;
    agency: string | null;
    release_key: string | null;
    release_ts_utc: string | null;
    next_release: string | null;
    metrics: LensMetric[];
  }[];
  insight_ids: string[]; // passing insights of this commodity (render from insights.json)
};
export type LensIndex = {
  schema_version: 1;
  commodities: { id: "soybeans" | "corn"; label: string; n_reports: number; file: string }[];
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
    {
      latest_release_key: string;
      release_ts_utc: string;
      next_release: string | null;
      age_days: number;
      status: "ok" | "stale" | "failed";
      off_season?: boolean; // seasonal reports (crop_progress): nothing scheduled since the newest release
    }
  >;
};
