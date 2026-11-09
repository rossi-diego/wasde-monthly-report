-- NASS Grain Stocks silver (every printed value: one row per release × commodity × stock date ×
-- position) exposed to dbt with light typing. Values are thousand bushels (k_bu) as printed.
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
    cast(as_of_date as date)              as as_of_date,
    position,
    market_year,
    cast(my_start as integer)             as my_start,
    cast(quarter_of_my as integer)        as quarter_of_my,
    column_role,
    cast(reported_as_of as date)          as reported_as_of,
    nass_table_id,
    source_label,
    source_unit_label,
    zip_member,
    source_url
from read_parquet('{{ var("silver_dir") }}/grain_stocks.parquet')
