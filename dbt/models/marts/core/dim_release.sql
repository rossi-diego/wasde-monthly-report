-- Every release of every report (one row per report_id × release_key).
-- Only WASDE exists so far; later reports add a `union all` block from their staging model.
with releases as (
    select
        report_id,
        release_key,
        min(release_ts_utc) as release_ts_utc,
        max(edition)        as edition,
        min(source)         as source,
        any_value(bronze_sha256) as bronze_sha256,
        min(vintage_quality) as vintage_quality,
        count(*)            as n_rows
    from {{ ref('stg_wasde') }}
    group by report_id, release_key
)

select
    *,
    row_number() over (partition by report_id order by release_key) as release_seq,
    release_key = max(release_key) over (partition by report_id)   as is_latest
from releases
