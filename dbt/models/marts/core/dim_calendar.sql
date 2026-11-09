-- Scheduled releases of every enabled report (from config/calendars/<report_id>.yaml),
-- with whether each one has been ingested yet. Both sides derive release_ts_utc from the
-- same configured ET release time, so the join is exact and time-zone safe.
with cal as (
    select
        report_id,
        cast(release_date as date)              as release_date,
        cast(release_ts_utc as timestamptz)     as release_ts_utc,
        cadence
    from read_parquet('{{ var("silver_dir") }}/calendar.parquet')
)

select
    c.report_id,
    c.release_date,
    c.release_ts_utc,
    c.cadence,
    r.release_key,
    r.release_key is not null as is_ingested
from cal as c
left join {{ ref('dim_release') }} as r
    on r.report_id = c.report_id and r.release_ts_utc = c.release_ts_utc
