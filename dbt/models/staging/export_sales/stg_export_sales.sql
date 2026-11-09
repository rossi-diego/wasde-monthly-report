-- Export Sales silver (a change log of API snapshots) exposed to dbt with light typing.
-- One row per snapshot × commodity × MY × week × destination × metric whose value is new or
-- changed (0-valued tombstones mark destinations a later snapshot dropped).
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
    cast(esr_commodity_code as integer)   as esr_commodity_code,
    market_year,
    cast(esr_market_year as integer)      as esr_market_year,
    cast(my_start as integer)             as my_start,
    cast(week_ending as date)             as week_ending,
    cast(week_of_my as integer)           as week_of_my,
    country_id,
    cast(esr_country_code as integer)     as esr_country_code,
    metric,
    snapshot_key,
    cast(snapshot_seq as integer)         as snapshot_seq,
    snapshot_kind,
    release_ts_source
from read_parquet('{{ var("silver_dir") }}/export_sales.parquet')
