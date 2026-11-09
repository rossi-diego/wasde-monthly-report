-- NASS Fats & Oils silver (every printed value, one row per release × data month × metric)
-- exposed to dbt with light typing. Withheld values ((D)) have a null value and a value_flag.
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
    oilseed,
    metric,
    cast(month as date)                   as month,
    market_year,
    cast(my_start as integer)             as my_start,
    cast(month_of_my as integer)          as month_of_my,
    column_role,
    cast(reported_month as date)          as reported_month,
    nass_table_id,
    source_label,
    source_unit_label,
    zip_member,
    source_url
from read_parquet('{{ var("silver_dir") }}/oilseed_crush.parquet')
