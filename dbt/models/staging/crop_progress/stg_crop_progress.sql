-- NASS Crop Progress silver (national rows: one row per release × crop × kind × category)
-- exposed to dbt with light typing. kind = progress (cumulative % of acreage per stage) or
-- condition (% of acreage per rating). Missing values ((NA)) have a null value and a flag.
select
    report_id,
    release_key,
    cast(release_ts_utc as timestamptz)   as release_ts_utc,
    cast(edition as integer)              as edition,
    source,
    bronze_sha256,
    vintage_quality,
    commodity_id,
    region_id,
    unit_id,
    cast(value as double)                 as value,
    value_flag,
    crop,
    kind,
    category,
    cast(week_ending as date)             as week_ending,
    cast(season as integer)               as season,
    state_id,
    cast(n_states as integer)             as n_states,
    cast(nass_prev_week_pct as double)    as nass_prev_week_pct,
    cast(nass_prev_year_pct as double)    as nass_prev_year_pct,
    cast(nass_5yr_avg_pct as double)      as nass_5yr_avg_pct,
    cast(prev_year_week_ending as date)   as prev_year_week_ending,
    avg_years,
    nass_table_id,
    source_label,
    zip_member,
    source_url
from read_parquet('{{ var("silver_dir") }}/crop_progress.parquet')
