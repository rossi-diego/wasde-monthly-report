-- U.S. export sales to all destinations per commodity × marketing year × week (metric tons),
-- with the China and "unknown destinations" commitments used by the destination insight.
with w as (
    select * from {{ ref('fct_export_sales_weekly') }}
),

totals as (
    select
        commodity_id,
        market_year,
        esr_market_year,
        my_start,
        week_ending,
        week_of_my,
        release_key,
        release_ts_utc,
        release_ts_source,
        max(vintage_quality)                       as vintage_quality,
        cast(count(*) as integer)                  as n_destinations,
        sum(weekly_exports_mt)                     as weekly_exports_mt,
        sum(accumulated_exports_mt)                as accumulated_exports_mt,
        sum(outstanding_sales_mt)                  as outstanding_sales_mt,
        sum(net_sales_mt)                          as net_sales_mt,
        sum(total_commitment_mt)                   as total_commitment_mt,
        sum(next_my_net_sales_mt)                  as next_my_net_sales_mt,
        sum(next_my_outstanding_mt)                as next_my_outstanding_mt,
        coalesce(sum(total_commitment_mt) filter (where country_id = 'china'), 0)   as china_commitment_mt,
        coalesce(sum(total_commitment_mt) filter (where country_id = 'unknown'), 0) as unknown_commitment_mt,
        any_value(source_url)                      as source_url
    from w
    group by commodity_id, market_year, esr_market_year, my_start, week_ending, week_of_my,
             release_key, release_ts_utc, release_ts_source
)

select
    *,
    'mt' as unit_id,
    -- Mean of the last 4 weekly net sales of the same MY (null until 4 weeks exist).
    case when count(*) over last4 = 4 then avg(net_sales_mt) over last4 end as net_sales_4wk_avg_mt,
    max(week_ending) over (partition by commodity_id, esr_market_year) = week_ending
        as is_latest_week_of_my
from totals
window last4 as (
    partition by commodity_id, esr_market_year order by week_ending
    rows between 3 preceding and current row
)
