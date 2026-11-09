# Data contract (cut B: WASDE + Export Sales + NASS crush)

What the Python publisher writes and the site (and any reuser) may rely on. TypeScript types:
[`web/lib/data-contract.ts`](../web/lib/data-contract.ts). Every number comes from gold; the
site only formats and renders words.

## Files under `web/public/data/` (also attached to each release)

| File | Producer | Content |
|---|---|---|
| `meta.json` | `publish/run.py` | Legacy WASDE keys (`data_release_tag`, `next_release`, `latest`, `history`, `downloads`; **never removed**, Soy Outlook reads them) + `reports: {id: {latest_release_key, release_ts_utc, next_release, rows, releases}}` |
| `insights.json` | `insights/engine.py` | Typed insights W1–W4, E1–E3, F1–F3, home cards and hero (below) |
| `catalog.json` | `publish/catalog.py` | Data tag of this build, release URL (and site URL for previews ≤ 5 MB) of every catalogue file, report registry summary |
| `datapackage.json` | `publish/datapackage.py` | Frictionless tabular data package: per file sha256, bytes, rows, temporal coverage, latest release key, schema version, licence, Table Schema (descriptions from the dbt manifest) |
| `reports/export_sales/index.json` | `publish/web_export_sales.py` | Commodities with ESR data, latest release, next release |
| `reports/export_sales/<commodity>.json` | same | Latest week KPIs, as-of USDA target, pace series (current + 5 prior MYs), 5-yr band, weekly net sales, top destinations |
| `reports/oilseed_crush/index.json` | `publish/web_crush.py` | Latest NASS release (`release_key` = ESMIS release date, data `month`, `month_of_my`, `first_printed_as`), next release, `history_start` (`2015-10`) |
| `reports/oilseed_crush/soybeans.json` | same | Newest month KPIs (short tons, bushels, oil klb, yield lb/bu), MY-to-date crush, as-of WASDE crush target and implied oil yield, pace series (current + 5 prior MYs, `[month_of_my, pct, wasde_release_key]`) with the 5-yr band, oil yield by month with its band, the remaining months of last MY (F2), last 24 months. Never any NOPA data |
| `wasde_tables.json` | `publish/web_json.py` | WASDE table index of the explorer (was `catalog.json` before cut A; `web/lib/data.ts` reads either) |
| `downloads/*` | `publish/run.py` | Excel workbooks, `wasde_full.*`, ESR/cross preview Parquet |
| `../build.json` | `usda-reports build-info` | `sha`, `tag` (= `data_tag`), `built_at`, `reports: {id: {latest_release_key, release_ts_utc, next_release, age_days, status: ok\|stale\|failed}}` |

## `insights.json` (schema_version 1)

JSON Schema: [`docs/schemas/insights.schema.json`](schemas/insights.schema.json) (generated from
`src/usda_reports/insights/schema.py`; a test fails on drift).

```
{schema_version, generated_at, data_tag,
 gates: {min_n: 5, percentile_min_n: 10, small_sample_below: 10, e2_min_weeks_remaining: 6,
         f2_min_months_remaining: 5,
         stale_after_days: {wasde: 76, export_sales: 17, oilseed_crush: 76, …}},   # cadence + grace_days
 n_screened: {W1: 66, W2: 3, …},                                 # methodology note
 insights: [{id, rule, report_id, commodity_id, kind, params{}, n, window, robustness,
             caveats[], inputs[{report_id, release_key}], as_of, suppressed_reason}],
 home_cards: ["W3:corn", "E3:soybeans", "E1:soybeans"],
 hero: {kind: story|fallback, clauses[{kind, commodity_id, direction, insight_ids}],
        n_reports, since, reports[]}}
```

Rules every renderer must follow:

* `suppressed_reason != null` → do not show the insight as a finding.
* Always show `n`; show the small-sample chip when `"small_sample" in caveats` (n < 10).
* Ranks read "k of n" (`params.k`, `n`, `params.order` says what rank 1 means). A
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

Hero (deterministic): `wasde_tightness` = a W2 in the tightest (loosest) third **and** that
commodity's W1 ending-stocks Δ < 0 (> 0) → `tighter` (`looser`); `esr_pace` = the cross card's
E1 position → `lagging` / `ahead` / `in_line`. No passing clause → `fallback`
("{n_reports} USDA reports released since {since}", since = the latest WASDE release date).
Cards: one per report (WASDE: most extreme W2/W3 rank; Export Sales: E3, else E2; crush: the
F1/F3 furthest outside its 5-yr range, F1 on ties) plus one cross card (the E1 furthest outside
its 5-yr range). Crush insights add no hero clause.

Crush caveats: `crush_history_from_2015` (history window 2015-10+, no "since 2010" claims),
`nass_revises_previous_month`, `wasde_oil_year_oct_sep`.

## Release and tag contract

* `releases/latest` is always a `data-YYYY-MM` tag (WASDE day) with `meta.json`,
  `manifest.json` and the byte-stable `wasde_full.parquet` (checked by
  `tests/integration/test_release_contract.py`).
* Builds without a new WASDE whose Export Sales **or NASS crush** content changed publish an
  **immutable prerelease** `weekly-YYYY-MM-DD` (named after the build day; `.2`, `.3`… for a
  second change the same day) with `--latest=false`. The release title names what changed
  ("Export Sales 2026-11-05", "NASS crush 2026-12-01" or both). It carries the same file set.
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
