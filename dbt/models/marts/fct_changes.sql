-- Every month-over-month revision, scored for materiality.
--   seasonal_score = |Δ| / median |Δ| of the same series in the same calendar report month
--   (an August yield cut is compared with other August yield cuts, not with June noise).
--   streak = consecutive revisions in the same direction for this marketing year.
with r as (
    select
        *,
        month(strptime(report_month || '-01', '%Y-%m-%d')) as report_cal_month,
        sign(delta)                                         as dir
    from {{ ref('fct_revisions') }}
    where delta is not null
),

seasonal as (
    select
        series_key,
        report_cal_month,
        median(abs(delta)) filter (where delta <> 0) as median_abs_delta,
        count(*)                                     as n_history
    from r
    group by series_key, report_cal_month
),

runs as (
    select
        *,
        sum(case when dir = coalesce(prev_dir, 99) then 0 else 1 end)
            over (partition by series_key, market_year order by report_seq) as run_id
    from (
        select *, lag(dir) over (partition by series_key, market_year order by report_seq) as prev_dir
        from r
    )
)

select
    runs.* exclude (run_id, prev_dir),
    seasonal.median_abs_delta,
    seasonal.n_history,
    abs(delta) / nullif(seasonal.median_abs_delta, 0) as seasonal_score,
    case when dir = 0 then 0
         else row_number() over (partition by series_key, market_year, run_id order by report_seq)
    end                                               as streak
from runs
left join seasonal using (series_key, report_cal_month)
