-- Export pace vs. USDA, point in time: every ESR week ASOF-joined to the latest WASDE that
-- was public at the ESR release (wasde_release_ts_utc <= release_ts_utc; equal instants
-- count as public). History uses the same formula, so a prior MY at the same week_of_my is
-- compared with the WASDE of *that* time, never with its final number (plan §6 E1/E2).
with esr as (
    select e.*, c.my_start_month
    from {{ ref('fct_export_sales_totals') }} as e
    inner join {{ ref('dim_commodity') }} as c using (commodity_id)
),

targets as (
    select * from {{ ref('int_wasde_asof') }} where exports_mt is not null
),

joined as (
    select
        e.*,
        t.wasde_release_key,
        t.wasde_release_ts_utc,
        t.proj_est_flag      as wasde_proj_est_flag,
        t.exports_mt         as wasde_exports_mt,
        t.exports_native     as wasde_exports_native,
        t.unit_id            as wasde_unit_id
    from esr as e
    asof left join targets as t
        on t.commodity_id = e.commodity_id
       and t.market_year = e.market_year
       and e.release_ts_utc >= t.wasde_release_ts_utc
),

pace as (
    select
        *,
        total_commitment_mt / nullif(wasde_exports_mt, 0)       as pct_of_target,
        accumulated_exports_mt / nullif(wasde_exports_mt, 0)    as pct_shipped,
        -- ESR weeks still to report in this MY (the last one may be partial).
        greatest(
            0,
            cast(ceil(datediff('day', week_ending,
                               cast(make_date(my_start + 1, my_start_month, 1) - interval 1 day as date))
                      / 7.0) as integer)
        )                                                       as weeks_remaining
    from joined
),

needed as (
    select
        *,
        case when wasde_exports_mt is not null and weeks_remaining > 0
             then (wasde_exports_mt - total_commitment_mt) / weeks_remaining
        end as required_weekly_sales_mt
    from pace
),

hist as (
    -- The same week of the 5 previous marketing years (n drops below 5 when a prior MY has
    -- no as-of WASDE target or no ESR week with that index).
    select
        c.commodity_id,
        c.esr_market_year,
        c.week_of_my,
        count(h.pct_of_target)  as n_5yr,
        avg(h.pct_of_target)    as pct_5yr_mean,
        min(h.pct_of_target)    as pct_5yr_min,
        max(h.pct_of_target)    as pct_5yr_max
    from needed as c
    left join needed as h
        on h.commodity_id = c.commodity_id
       and h.week_of_my = c.week_of_my
       and h.esr_market_year between c.esr_market_year - 5 and c.esr_market_year - 1
       and h.pct_of_target is not null
    group by c.commodity_id, c.esr_market_year, c.week_of_my
)

select
    n.commodity_id,
    n.market_year,
    n.esr_market_year,
    n.my_start,
    n.week_ending,
    n.week_of_my,
    n.release_key,
    n.release_ts_utc,
    n.release_ts_source,
    n.vintage_quality,
    n.unit_id,
    n.weekly_exports_mt,
    n.accumulated_exports_mt,
    n.outstanding_sales_mt,
    n.total_commitment_mt,
    n.net_sales_mt,
    n.net_sales_4wk_avg_mt,
    n.next_my_net_sales_mt,
    n.next_my_outstanding_mt,
    n.china_commitment_mt,
    n.unknown_commitment_mt,
    n.wasde_release_key,
    n.wasde_release_ts_utc,
    n.wasde_proj_est_flag,
    n.wasde_unit_id,
    n.wasde_exports_native,
    n.wasde_exports_mt,
    n.pct_of_target,
    n.pct_shipped,
    n.weeks_remaining,
    n.required_weekly_sales_mt,
    cast(h.n_5yr as integer) as n_5yr,
    h.pct_5yr_mean,
    h.pct_5yr_min,
    h.pct_5yr_max,
    n.is_latest_week_of_my
from needed as n
inner join hist as h using (commodity_id, esr_market_year, week_of_my)
