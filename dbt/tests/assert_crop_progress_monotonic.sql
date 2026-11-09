-- Progress stages are cumulative: within a season, the share of acreage that reached a stage
-- never falls from one week to the next (plan §5). Missing (NA) weeks are skipped.
with p as (
    select
        crop,
        category,
        season,
        week_ending,
        value_pct,
        lag(value_pct) over (partition by crop, category, season order by week_ending) as prev_pct
    from {{ ref('fct_crop_progress_weekly') }}
    where kind = 'progress' and value_pct is not null
)

select *
from p
where value_pct < prev_pct
