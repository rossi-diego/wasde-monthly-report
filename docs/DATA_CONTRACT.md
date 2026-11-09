# Data contract (cut C: WASDE, Export Sales, NASS crush, Crop Progress, Grain Stocks)

What the Python publisher writes and the site (and any reuser) may rely on. TypeScript types:
[`web/lib/data-contract.ts`](../web/lib/data-contract.ts). Every number comes from gold; the
site only formats and renders words.

How the site reads it (cut C): `web/lib/insight-text.ts` turns each insight's params into card
copy, `web/lib/report-views.ts` the Crop Progress and Grain Stocks page text,
`web/lib/lens.ts` the commodity pages and the home "also released" cards (the Crop Progress or
Grain Stocks finding when the ≤ 5 `home_cards` row has none, respecting
`seasons.crop_progress.shown_on_home`). All of them take a language and format numbers in
that locale (EN `1,234.5`, pt-BR `1.234,5`); the Playwright contract tests call the same
functions on the served JSON and on the frozen-clock fixture `web/e2e/fixtures/offseason/`.

## Files under `web/public/data/` (also attached to each release)

| File | Producer | Content |
|---|---|---|
| `meta.json` | `publish/run.py` | Legacy WASDE keys (`data_release_tag`, `next_release`, `latest`, `history`, `downloads`; **never removed**, Soy Outlook reads them) + `reports: {id: {latest_release_key, release_ts_utc, next_release, rows, releases}}` |
| `insights.json` | `insights/engine.py` | Typed insights W1–W4, E1–E3, F1–F3, C1–C3, G1–G3, home cards, hero and the Crop Progress season state (below) |
| `catalog.json` | `publish/catalog.py` | Data tag of this build, release URL (and site URL for previews ≤ 5 MB) of every catalogue file, report registry summary |
| `datapackage.json` | `publish/datapackage.py` | Frictionless tabular data package: per file sha256, bytes, rows, temporal coverage, latest release key, schema version, licence, Table Schema (descriptions from the dbt manifest) |
| `reports/export_sales/index.json` | `publish/web_export_sales.py` | Commodities with ESR data, latest release, next release |
| `reports/export_sales/<commodity>.json` | same | Latest week KPIs, as-of USDA target, pace series (current + 5 prior MYs), 5-yr band, weekly net sales, top destinations |
| `reports/oilseed_crush/index.json` | `publish/web_crush.py` | Latest NASS release (`release_key` = ESMIS release date, data `month`, `month_of_my`, `first_printed_as`), next release, `history_start` (`2015-10`) |
| `reports/oilseed_crush/soybeans.json` | same | Newest month KPIs (short tons, bushels, oil klb, yield lb/bu), MY-to-date crush, as-of WASDE crush target and implied oil yield, pace series (current + 5 prior MYs, `[month_of_my, pct, wasde_release_key]`) with the 5-yr band, oil yield by month with its band, the remaining months of last MY (F2), last 24 months. Never any NOPA data |
| `reports/crop_progress/index.json` | `publish/web_crop_progress.py` | Latest release (`release_key` = ESMIS date, `week_ending`), next release, `history_start` (`2010-06-07`), `season: {state: in_season\|closed, season, last_scheduled}`, crop files (each with its own `season_state` and `season_scope`: `crop` when that crop's season is complete before the report's) |
| `reports/crop_progress/<crop>.json` | same | corn, soybeans, winter_wheat, spring_wheat: newest week's stages with NASS's published previous-week / previous-year / 5-yr-average columns, newest condition (5 ratings, GE, CI, NASS previous year, own 5-yr), and the season's chapter series: `ge.series` `[week, ge, nass_prev_year_ge, 5yr mean, min, max, n]`, `stage_pace.series` `[week, pct, nass_5yr_avg, nass_prev_year]`, `ci.series` `[week, ci, 5yr mean, min, max, n]` |
| `reports/grain_stocks/index.json` | `publish/web_grain_stocks.py` | Latest release and stock date (`as_of_date`, `quarter_of_my`), next release, `history_start` (`2010-06-30`), commodity files |
| `reports/grain_stocks/<commodity>.json` | same | corn, soybeans, wheat (million bushels): KPIs by position, `by_quarter` (current MY vs the same date of 5 prior MYs), `vs_wasde.rows` (G1, every ending-stock date since 2010), `disappearance` (G2, last 8 quarters with their 5-yr band), last 12 stock dates |
| `lens/index.json`, `lens/<commodity>.json` | `publish/web_commodity.py` | soybeans, corn: per report (WASDE, Export Sales, NASS crush, Crop Progress, Grain Stocks) its release key, release instant, next release and latest headline metrics (`metric, value, unit_id, period, release_key, source_url`) from `fct_commodity_lens`, plus the ids of the commodity's passing insights. (`commodities/` stays the WASDE commodity JSON.) |
| `wasde_tables.json` | `publish/web_json.py` | WASDE table index of the explorer (was `catalog.json` before cut A; `web/lib/data.ts` reads either) |
| `downloads/*` | `publish/run.py` | Excel workbooks, `wasde_full.*`, ESR/cross preview Parquet |
| `../build.json` | `usda-reports build-info` | `sha`, `tag` (= `data_tag`), `built_at`, `reports: {id: {latest_release_key, release_ts_utc, next_release, age_days, status: ok\|stale\|failed, off_season?}}` (`off_season`: a seasonal report with nothing scheduled since its newest release, never `stale`) |

## `insights.json` (schema_version 1)

JSON Schema: [`docs/schemas/insights.schema.json`](schemas/insights.schema.json) (generated from
`src/usda_reports/insights/schema.py`; a test fails on drift).

```
{schema_version, generated_at, data_tag,
 gates: {min_n: 5, percentile_min_n: 10, small_sample_below: 10, e2_min_weeks_remaining: 6,
         f2_min_months_remaining: 5, home_hidden_months: {crop_progress: [12, 1, 2, 3]},
         stale_after_days: {wasde: 76, export_sales: 17, oilseed_crush: 76,
                            crop_progress: 17, grain_stocks: 192}},   # cadence + grace_days
 n_screened: {W1: 66, W2: 3, …},                                 # methodology note
 insights: [{id, rule, report_id, commodity_id, kind, params{}, n, window, robustness,
             caveats[], inputs[{report_id, release_key}], as_of, suppressed_reason}],
 home_cards: ["W3:corn", "E3:soybeans", "E1:soybeans"],
 hero: {kind: story|fallback, clauses[{kind, commodity_id, direction, insight_ids}],
        n_reports, since, reports[]},
 seasons: {crop_progress: {state: in_season|closed, season, latest_release_key,
                           last_scheduled, shown_on_home}}}
```

Rules every renderer must follow:

* `suppressed_reason != null` → do not show the insight as a finding.
* Always show `n`; show the small-sample chip when `"small_sample" in caveats` (n < 10).
* Ranks read "k of n" (`params.k`, `n`, `params.order` says what rank 1 means; C1, C3, G2
  and G3 rank the current value among n history seasons plus itself, so they publish the
  denominator as `params.k_of` = n + 1). A
  `percentile_*` param is non-null only when n ≥ 10; never compute one in the UI.
* "5yr" windows (`window = prior_5_my_same_week`) are labelled small sample, shown as mean and
  min–max; their history is the USDA projection **public at the time** (`history_point_in_time`).
* Ratios (`pct`, `share`, `*_share`) are shares (0.38 = 38 %).

| id | kind | key params |
|---|---|---|
| `W1:headline`, `W1:<c>:ending_stocks` | change_vs_prev | `headline, table_id, attribute_id, market_year, value, prev_value, delta, pct_delta, unit_id, seasonal_score, median_abs_delta, materiality_floor, n_screened` |
| `W2:<c>` (corn, soybeans, wheat) | stocks_to_use_rank | `stocks_to_use_pct, ending_stocks, unit_id, k, order=tightest_first, tercile (tight\|middle\|loose), percentile_tighter_than, first_market_year, history[]` |
| `W3:<c>` | revision_rank | `delta, abs_delta, unit_id, cycle_month, k, order=largest_abs_first, percentile_larger_than, history[]` |
| `W4:soybeans` | brazil_soy_export_share | `share, brazil_exports, denominator_exports, unit_id=mmt, countries[], k, order=highest_first, history[]` |
| `E1:<c>` (5 ESR commodities) | commitment_pace | `pct, total_commitment_mt, target_mt, target_native, target_unit_id, wasde_release_key, hist_mean/min/max, position (below\|inside\|above), outside_distance, history[]` |
| `E2:<c>` | required_weekly_sales | `required_weekly_mt, net_sales_4wk_avg_mt, ratio_required_to_avg, weeks_remaining, remaining_to_target_mt` (n = 4 weeks) |
| `E3:soybeans` | china_share_soy | `china_share, unknown_share, china/unknown/total_commitment_mt, hist_mean/min/max, position, history[]` |
| `F1:soybeans` (report_id `oilseed_crush`) | crush_pace | `market_year, month, month_of_my, release_key, first_printed_as, history_start=2015-10, unit_id=bu, cum_bu, cum_st, month_crushed_bu/st, wasde_release_key, target_bu, target_native, target_unit_id=m_bu, target_flag, pct, hist_mean/min/max, position, outside_distance, history[]` (window `prior_5_my_same_month`) |
| `F2:soybeans` | required_monthly_crush | `required_monthly_bu, last_my_remaining_mean_bu, last_my_remaining_n, ratio_required_to_last_my, months_remaining, remaining_to_target_bu, target_bu` (n = months compared, so F2 is suppressed `months_remaining_below_min` with < 5 months left, the default `min_n`; unlike E2 it has no small-window exception) |
| `F3:soybeans` | oil_yield | `oil_yield_lb_bu, month_oil_klb, month_crushed_bu, hist_mean/min/max, position, outside_distance, wasde_oil_release_key, wasde_implied_yield_lb_bu, diff_vs_wasde_lb_bu, history[]` |
| `C1:<crop>` (corn, soybeans, winter_wheat, spring_wheat; report_id `crop_progress`, commodity_id `wheat` for both wheats) | good_excellent | `crop, season, week_ending, release_key, n_states, season_state (in_season\|closed), season_scope (report\|crop), final, ge_pct, good_pct, excellent_pct, nass_prev_week_ge_pct, nass_prev_year_ge_pct, vs_prev_year_pp, hist_mean/min/max, position, outside_distance, k, k_of, order=highest_first, history[]`. In season: window `prior_5_seasons_same_week_doy_pm3` (own 5-yr, the week within ±3 days by day of year; NASS publishes none for condition). Season closed: window `prior_5_seasons_final_rating` ("Season closed: final GE X% vs 5-yr Y%", final vs final), exempt from the staleness gate. `season_scope = crop`: this crop's season is complete while the report's is open (missing from the newest release, harvest ≥ 90 %, e.g. spring wheat in November): final rating as when closed, C2/C3 `season_closed`, never `stale_input`, not a home card |
| `C2:<crop>` | stage_pace | `stage` (the stage in progress: latest in crop-calendar order strictly between 0 and 100 %), `value_pct, nass_5yr_avg_pct` (NASS's published average, used as published), `avg_years, pace_vs_5yr_pp, nass_prev_week_pct, nass_prev_year_pct, vs_prev_year_pp, position (behind\|ahead\|on_pace), stages[]` + season params. n = 5 (window `nass_published_5yr_average`). Suppressed `season_closed` off-season |
| `C3:<crop>` | condition_index | `ci` ((1·VP + 2·P + 3·F + 4·G + 5·E)/100, `unit_id=index_1_5`), `nass_prev_year_ci`, own 5-yr range params, `history[]`. Suppressed `season_closed` off-season |
| `G1:<c>` (corn, soybeans, wheat; report_id `grain_stocks`) | stocks_vs_wasde | Only stock dates that are a WASDE ending stock (corn/soybeans September 1, wheat June 1): `as_of_date, market_year` (old crop), `release_key, is_latest_release, nass_total_mbu` (first print), `wasde_release_key, wasde_flag, wasde_ending_stocks_mbu` (as of the release), `surprise_mbu, surprise_pct, direction, k, order=largest_abs_first, rank_basis=abs_surprise_pct, percentile_larger_than` (n ≥ 10), `first_market_year, history[]` (window `ending_stock_dates_since_2010`) |
| `G2:<c>` | implied_disappearance | `stocks_{q-1} + production_q − stocks_q`: `as_of_date, prev_as_of_date, quarter_of_my, is_harvest_quarter, prev_stocks_mbu` (as printed in the same release), `production_mbu` (WASDE as of the release, harvest quarter only, else 0), `wasde_release_key, stocks_mbu, implied_disappearance_mbu`, range params vs the same quarter of the 5 prior MYs. Caveats always `imports_omitted_small_for_corn_soy`, `nass_may_revise_production_same_day` |
| `G3:<c>` | on_farm_share | `on_farm_share, on_farm_mbu, off_farm_mbu, total_mbu, total_mt, total_prev_year_mbu, total_yoy_pct` (total_t / total_{t−4q} − 1), range params of the share vs the same date of the 5 prior years |

Hero (deterministic): `wasde_tightness` = a W2 in the tightest (loosest) third **and** that
commodity's W1 ending-stocks Δ < 0 (> 0) → `tighter` (`looser`); `esr_pace` = the cross card's
E1 position → `lagging` / `ahead` / `in_line`. No passing clause → `fallback`
("{n_reports} USDA reports released since {since}", since = the latest WASDE release date).
Cards: one per report (WASDE: most extreme W2/W3 rank; Export Sales: E3, else E2; crush: the
F1/F3 furthest outside its 5-yr range, F1 on ties; Crop Progress: the C1/C3 furthest outside
its 5-yr range, C1 on ties, else the C2 with the largest gap to NASS's 5-yr average, and once
the season is closed the C1 final rating; Grain Stocks, from its newest release only: G1 with
the smallest k/n when that release prints a WASDE ending-stock date, else the G2/G3 furthest
outside its range) plus one cross card (the E1 furthest outside its 5-yr range). Display order
WASDE, Export Sales, Crop Progress, crush, Grain Stocks, cross; the Crop Progress card is left
off the home page in December–March (`gates.home_hidden_months`); with more than 5 candidates
the report card (never WASDE or cross) whose newest input is oldest is dropped. NASS insights
add no hero clause.

Staleness: the insight's own report is measured against now; a point-in-time input from another
report (the WASDE public at a Grain Stocks release) is measured against the own release instant
(it must not have been stale *then*). Cross insights measure every input against now.

Crush caveats: `crush_history_from_2015` (history window 2015-10+, no "since 2010" claims),
`nass_revises_previous_month`, `wasde_oil_year_oct_sep`.

## Release and tag contract

* `releases/latest` is always a `data-YYYY-MM` tag (WASDE day) with `meta.json`,
  `manifest.json` and the byte-stable `wasde_full.parquet` (checked by
  `tests/integration/test_release_contract.py`).
* Builds without a new WASDE whose Export Sales, NASS crush, Crop Progress or Grain Stocks
  content changed publish an
  **immutable prerelease** `weekly-YYYY-MM-DD` (named after the build day; `.2`, `.3`… for a
  second change the same day) with `--latest=false`. The release title names what changed
  ("Export Sales 2026-11-05", "NASS crush 2026-12-01", "Crop Progress 2026-11-09", "Grain
  Stocks 2027-01-12", joined with " · "). It carries the same file set.
* Retention (`.github/workflows/retention.yml`, selection in `publish/retention.py`): only
  superseded `weekly-*` prereleases older than 90 days, always keeping the newest 8 and the tag
  the live site is built from. `data-*`, the Latest release and `bronze-store` are never
  touched. Dry run by default (deletes only on a manual run with `apply: true` or with the
  repository variable `RETENTION_APPLY=true`).
* Schema guard (`catalog-diff` CI job): `docs/schemas/catalog.schema.json` (every dataset's
  columns and Table Schema types, generated from the dbt models; a test fails on drift) is
  compared with the base branch's snapshot and with the live `datapackage.json`. A column
  removed, renamed or retyped, or a dataset removed, fails unless that dataset's
  `schema_version` is bumped in `config/datasets.yaml` (a new `__v<major>` file).
* A code-only rebuild whose newest release is an (immutable) `weekly-*` compares the new
  `datasets.json` hashes with that release's (`usda-reports datasets-changed`); when any file
  was added, removed or changed bytes it publishes a new `weekly-*` tag, so the catalogue never
  points at assets whose sha256 differs.
* `catalog.json.data_tag` / `build.json.tag` name the release the site was built from.
* Timestamp columns (`*_ts_utc`) are written in UTC in every CSV (`2015-10-01 19:00:00+00`):
  the catalogue export pins the DuckDB session `TimeZone` to UTC, so CSV bytes and their
  sha256 do not depend on the build machine's time zone.

## Export Sales envelope and isolation

* `release_ts_source`: `api` (the API's own `releaseTimeStamp` for the newest week of a pull),
  `calendar_override` (a week published late after a government shutdown, pinned to its actual
  FAS catch-up release date in `config/calendars/export_sales.yaml`: 2013, 2018–19, 2025), or
  `calendar_rule` (the Thursday 08:30 ET rule with the federal-holiday shift).
* `vintage_quality`: `latest_only` = backfilled, values as revised by the backfill day;
  `captured` = tracked by weekly pulls since first capture. The marts and the published
  datasets carry the **latest revision**; every vintage stays in silver.
* Isolation: a pulled ESR bundle is parsed and contract-checked before it reaches bronze (an
  unseen destination code fails `detect --report export_sales`). If bronze still holds a bad
  snapshot, silver falls back to the last good ESR state, `data/silver/build_status.json`
  records the failure, `build.json.reports.export_sales.status` is `failed`, and WASDE gold,
  publish and the `data-*` release proceed.

## NASS crush envelope and isolation

* `release_key` is the ESMIS release date (`YYYY-MM-DD`, from `release_datetime`, never from the
  zip name: `cafo0726.zip` names two different releases). `release_ts_utc` = that date at 15:00 ET.
  Two releases can fall in one month after a shutdown (2019-02-04 and 2019-02-22).
* Silver (`data/silver/oilseed_crush.parquet`) keeps every printed value: release × data `month`
  × `metric` (`crushed_st`, `crude_oil_produced_klb`, `meal_produced_st`, `crude_oil_stocks_klb`)
  with `column_role` (`current`, `previous`, `year_ago`, `earlier`), `unit_id` (`short_ton`,
  `klb`, as printed by NASS) and `vintage_quality = as_published`.
* `fct_crush_pace` rows are taken at the instant NASS first printed the month; the year-to-date
  sum uses the NASS vintages public then and the WASDE crush public then (`assert_no_lookahead`
  on `wasde_release_ts_utc`, `wasde_oil_release_ts_utc` and `inputs_max_release_ts_utc`).
* Isolation mirrors Export Sales: every downloaded zip is parsed and contract-checked before it
  reaches bronze (an unseen row label, unit or header fails `detect --report oilseed_crush`); a
  bad bronze state falls back to the last good releases, `build.json.reports.oilseed_crush.status`
  becomes `failed`, and WASDE, Export Sales and the `data-*` release proceed.

## Crop Progress envelope and isolation

* `release_key` is the ESMIS release date (Monday; Tuesday after a federal holiday Monday;
  2012-10-31 and 2017-07-05 were Wednesdays). `release_ts_utc` = that date at 16:00 ET. The
  data `week_ending` is the Sunday before (lag checked: 1–4 days).
* National level only: the NASS "<N> States" aggregate row (`state_id = us_total`,
  `n_states` 18 for corn / soybeans / winter wheat, 6 for spring wheat). Silver
  (`data/silver/crop_progress.parquet`) has one row per release × `crop` × `kind`
  (`progress`, `condition`) × `category` (stage or rating) with NASS's published
  `nass_prev_week_pct`, `nass_prev_year_pct`, `nass_5yr_avg_pct` (progress only; `avg_years`).
  Symbols: `(NA)`/`NA` → null with `value_flag = NA`; `* 61` (revised) → 61 with `revised`.
* History from the 2010-06-07 release (the first regular `prog_all_tables.csv`; the 2010
  season is partial). No releases during funding lapses (2013-10, 2025-10-06 → 2025-11-10):
  5-yr windows skip those weeks and `n` drops. 2018-09-11 re-issued 2018-09-10 (identical
  national rows): gold keeps the latest values and dates availability from the first.
* Season: weekly from April through November (`config/calendars/crop_progress.yaml`). After the
  season's final release (or a week after its last scheduled date) `insights.seasons
  .crop_progress.state = closed`; nothing is due and the stale watchdog does not fire off-season.
* dbt tests: values in [0, 100], cumulative stages non-decreasing within a season, the five
  ratings sum to 100 ± 1, `assert_no_lookahead` on the own 5-yr comparison.
* Isolation mirrors NASS crush (`detect --report crop_progress`, last-good silver fallback,
  `build.json.reports.crop_progress.status = failed`).

## Grain Stocks envelope and isolation

* `release_key` is the ESMIS release date; `release_ts_utc` = 12:00 ET. Table 1 (national
  summary, domestic units) only: corn, soybeans, all wheat × on farms / off farms / all
  positions, thousand bushels (`k_bu`) as printed. Every release prints all four stock dates
  of two years, so silver keeps each date as revised by every later release (`column_role`
  `current` = the newest date of the release).
* `market_year` = the marketing year in which the stocks are held (September 1 corn stocks are
  the 2025/26 ending stocks), `quarter_of_my` 4 = ending stocks, 1 = harvest quarter.
* `fct_stocks_vs_wasde` (G1) and `fct_stocks_disappearance` (G2) take every value at the
  instant NASS first printed the stock date; the WASDE ending stocks / production is the one
  public then (`assert_no_lookahead`; same-instant releases count as public, unit-tested).
* dbt tests: on farms + off farms = total ± 1 on every date; revisions above 10 % fail silver.
* History from the 2010-06-30 release (the first `grst_all_tables.csv`); WASDE history from
  2010-07, so G1 starts with September 1, 2010 for corn and soybeans and June 1, 2011 for wheat.
