-- Every release of every report (one row per report_id × release_key).
-- Each report adds a `union all` block from its staging model.
with releases as (
    select
        report_id,
        release_key,
        min(release_ts_utc)       as release_ts_utc,
        max(edition)              as edition,
        min(source)               as source,
        any_value(bronze_sha256)  as bronze_sha256,
        min(vintage_quality)      as vintage_quality,
        count(*)                  as n_rows
    from {{ ref('stg_wasde') }}
    group by report_id, release_key

    union all

    -- Export Sales: one release per week. vintage_quality is the best quality seen for the
    -- week ('captured' once a weekly pull saw it, else 'latest_only' from the backfill).
    select
        report_id,
        release_key,
        min(release_ts_utc)       as release_ts_utc,
        max(edition)              as edition,
        min(source)               as source,
        max_by(bronze_sha256, snapshot_seq) as bronze_sha256,
        min(vintage_quality)      as vintage_quality,
        count(*)                  as n_rows
    from {{ ref('stg_export_sales') }}
    group by report_id, release_key

    union all

    -- NASS Fats & Oils: one release per ESMIS release date (as published).
    select
        report_id,
        release_key,
        min(release_ts_utc)       as release_ts_utc,
        max(edition)              as edition,
        min(source)               as source,
        any_value(bronze_sha256)  as bronze_sha256,
        min(vintage_quality)      as vintage_quality,
        count(*)                  as n_rows
    from {{ ref('stg_oilseed_crush') }}
    group by report_id, release_key
)

select
    *,
    row_number() over (partition by report_id order by release_key) as release_seq,
    release_key = max(release_key) over (partition by report_id)   as is_latest
from releases
