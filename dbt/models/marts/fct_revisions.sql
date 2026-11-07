-- Revision path of every annual estimate: how USDA's number for one marketing year moved
-- report after report, from the first projection to the last time it was published.
with base as (
    select
        report_month, report_date, report_seq, series_key,
        table_id, commodity_id, region_id, attribute_id, market_year, my_start,
        proj_est_flag, value, unit_id,
        commodity_label, region, attribute_label, unit_label
    from {{ ref('fct_wasde') }}
    where period = 'annual' and reliability_stat is null
),

w as (
    select
        *,
        lag(value) over s                 as prev_value,
        lag(report_seq) over s            as prev_report_seq,
        first_value(value) over s_all     as first_value,
        first_value(report_month) over s_all as first_report_month,
        last_value(value) over s_all      as last_value,
        last_value(report_month) over s_all  as last_report_month,
        row_number() over s               as nth_estimate,
        count(*) over (partition by series_key, market_year) as n_estimates
    from base
    window
        s as (partition by series_key, market_year order by report_seq),
        s_all as (
            partition by series_key, market_year order by report_seq
            rows between unbounded preceding and unbounded following
        )
)

select
    w.*,
    case when prev_report_seq = report_seq - 1 then value - prev_value end as delta,
    case
        when prev_report_seq = report_seq - 1 and prev_value <> 0
            then (value - prev_value) / abs(prev_value)
    end                                                                    as pct_delta,
    value - first_value                                                    as delta_vs_first,
    report_month = first_report_month                                      as is_first,
    report_month = last_report_month                                       as is_last,
    -- 0 = first projection in May of the marketing-year start; null for calendar years.
    case
        when regexp_matches(market_year, '^[0-9]{4}/[0-9]{2}$')
            then datediff('month', make_date(my_start, 5, 1), report_date)
    end                                                                    as cycle_month,
    last_report_month < (select max(report_month) from base)               as is_complete
from w
