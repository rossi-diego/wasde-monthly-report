-- NASS Crop Progress, national ("<N> States") rows, one row per crop × kind × category × week.
--   kind = progress: cumulative % of acreage that reached a stage (planted … harvested), with
--          NASS's own published previous-week, previous-year and 5-year-average columns
--          (used exactly as published, plan §6 C2);
--   kind = condition: % of acreage rated very poor … excellent, with NASS's previous-week and
--          previous-year rows (NASS publishes no 5-year average for condition).
-- A week printed by two releases (2018-09-10 and its 2018-09-11 re-issue) keeps the latest
-- values and dates availability from the first release.
with v as (
    select * from {{ ref('stg_crop_progress') }}
),

ranked as (
    select
        *,
        row_number() over w_desc                             as rn_latest,
        min(release_ts_utc) over w_all                       as first_release_ts_utc,
        cast(count(*) over w_all as integer)                 as n_vintages
    from v
    window
        w_desc as (partition by crop, kind, category, week_ending
                   order by release_ts_utc desc, edition desc),
        w_all as (partition by crop, kind, category, week_ending)
),

firsts as (
    select crop, kind, category, week_ending, arg_min(release_key, release_ts_utc) as first_release_key
    from v
    group by all
)

select
    r.crop,
    r.commodity_id,
    r.season,
    r.week_ending,
    r.kind,
    r.category,
    r.value                                                  as value_pct,
    r.value_flag,
    r.nass_prev_week_pct,
    r.nass_prev_year_pct,
    r.nass_5yr_avg_pct,
    r.value - r.nass_5yr_avg_pct                             as vs_5yr_avg_pp,
    r.value - r.nass_prev_year_pct                           as vs_prev_year_pp,
    r.value - r.nass_prev_week_pct                           as vs_prev_week_pp,
    r.prev_year_week_ending,
    r.avg_years,
    r.state_id,
    r.n_states,
    r.unit_id,
    r.release_key,
    r.release_ts_utc,
    f.first_release_key,
    r.first_release_ts_utc,
    r.n_vintages,
    r.source_url,
    r.week_ending = max(r.week_ending) over ()               as is_latest_week
from ranked as r
inner join firsts as f using (crop, kind, category, week_ending)
where r.rn_latest = 1
