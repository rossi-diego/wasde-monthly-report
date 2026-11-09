-- Crop condition per crop × week (national), wide, with the two indices of plan §6:
--   ge_pct = good% + excellent%                                         (C1)
--   ci     = (1·VP + 2·P + 3·F + 4·G + 5·E) / 100, range 1 (all very poor) to 5   (C3)
-- NASS's own "Previous year" row gives nass_prev_year_ge_pct. NASS publishes no 5-year average
-- for condition, so the 5-year comparison is computed here: the same crop in each of the 5
-- previous seasons at the week whose day of year is within ±3 days of this week's (weekly
-- data, so at most one week matches per season). A season without a matching week (a funding
-- lapse cancelled it, e.g. October 2025) is skipped and n_5yr drops: it is always shown.
-- Point in time: every history week was released before this week (tested).
with c as (
    select * from {{ ref('fct_crop_progress_weekly') }}
    where kind = 'condition'
),

wide as (
    select
        crop,
        any_value(commodity_id)                                               as commodity_id,
        season,
        week_ending,
        max(release_key)                                                      as release_key,
        max(first_release_key)                                                as first_release_key,
        min(first_release_ts_utc)                                             as release_ts_utc,
        max(n_states)                                                         as n_states,
        max(value_pct) filter (where category = 'very_poor')                  as very_poor_pct,
        max(value_pct) filter (where category = 'poor')                       as poor_pct,
        max(value_pct) filter (where category = 'fair')                       as fair_pct,
        max(value_pct) filter (where category = 'good')                       as good_pct,
        max(value_pct) filter (where category = 'excellent')                  as excellent_pct,
        max(nass_prev_year_pct) filter (where category = 'very_poor')         as py_vp,
        max(nass_prev_year_pct) filter (where category = 'poor')              as py_p,
        max(nass_prev_year_pct) filter (where category = 'fair')              as py_f,
        max(nass_prev_year_pct) filter (where category = 'good')              as py_g,
        max(nass_prev_year_pct) filter (where category = 'excellent')         as py_e,
        max(nass_prev_week_pct) filter (where category = 'good')              as pw_g,
        max(nass_prev_week_pct) filter (where category = 'excellent')         as pw_e,
        max(source_url)                                                       as source_url
    from c
    group by crop, season, week_ending
),

idx as (
    select
        *,
        good_pct + excellent_pct                                              as ge_pct,
        (1 * very_poor_pct + 2 * poor_pct + 3 * fair_pct + 4 * good_pct + 5 * excellent_pct)
            / 100                                                             as ci,
        very_poor_pct + poor_pct + fair_pct + good_pct + excellent_pct        as sum_pct,
        py_g + py_e                                                           as nass_prev_year_ge_pct,
        (1 * py_vp + 2 * py_p + 3 * py_f + 4 * py_g + 5 * py_e) / 100         as nass_prev_year_ci,
        pw_g + pw_e                                                           as nass_prev_week_ge_pct
    from wide
),

hist as (
    select
        cur.crop,
        cur.week_ending,
        cast(count(h.ge_pct) as integer)                                      as n_5yr,
        avg(h.ge_pct)                                                         as ge_5yr_mean,
        min(h.ge_pct)                                                         as ge_5yr_min,
        max(h.ge_pct)                                                         as ge_5yr_max,
        avg(h.ci)                                                             as ci_5yr_mean,
        min(h.ci)                                                             as ci_5yr_min,
        max(h.ci)                                                             as ci_5yr_max,
        min(h.season)                                                         as hist_first_season,
        max(h.release_ts_utc)                                                 as hist_max_release_ts_utc
    from idx as cur
    left join idx as h
        on h.crop = cur.crop
       and h.season between cur.season - 5 and cur.season - 1
       and abs(dayofyear(h.week_ending) - dayofyear(cur.week_ending)) <= 3
       and h.ge_pct is not null
    group by cur.crop, cur.week_ending
)

select
    i.crop,
    i.commodity_id,
    i.season,
    i.week_ending,
    i.release_key,
    i.first_release_key,
    i.release_ts_utc,
    i.n_states,
    i.very_poor_pct,
    i.poor_pct,
    i.fair_pct,
    i.good_pct,
    i.excellent_pct,
    i.sum_pct,
    i.ge_pct,
    i.ci,
    i.nass_prev_week_ge_pct,
    i.nass_prev_year_ge_pct,
    i.nass_prev_year_ci,
    i.ge_pct - i.nass_prev_year_ge_pct                                        as ge_vs_prev_year_pp,
    h.n_5yr,
    h.ge_5yr_mean,
    h.ge_5yr_min,
    h.ge_5yr_max,
    h.ci_5yr_mean,
    h.ci_5yr_min,
    h.ci_5yr_max,
    h.hist_first_season,
    h.hist_max_release_ts_utc,
    i.source_url,
    i.week_ending = max(i.week_ending) over (partition by i.crop)              as is_latest_week
from idx as i
inner join hist as h using (crop, week_ending)
