-- Soybean crush pace vs. USDA, point in time (plan §6 F1–F3).
--
-- One row per marketing year × month (September–August), taken at the instant NASS first
-- printed that month (asof_ts_utc; usually its own release, after a shutdown the next one).
-- Everything on the row is what was public at that instant:
--   * cum_*: the MY-to-date crush using, for every earlier month, the latest NASS vintage
--     released at or before asof_ts_utc (previous-month revisions included, later ones not);
--   * wasde_*: the latest WASDE with wasde_release_ts_utc <= asof_ts_utc (ASOF JOIN; equal
--     instants count as public), for the same marketing year label;
--   * last_my_*: the same remaining months of the previous MY, as known at that instant.
-- Rows exist only when every month of the MY up to that month was known at the instant
-- (n_months_known = month_of_my), which starts the history at MY 2015/16 (ESMIS has NASS
-- files from 2015-10-01 only). History = the same month_of_my of the 5 prior MYs, each against
-- its own as-of WASDE.
with v as (
    select * from {{ ref('stg_oilseed_crush') }}
    where oilseed = 'soybeans' and value is not null
),

bu as (
    select bu_per_unit as bu_per_st from {{ ref('dim_unit') }}
    where unit_id = 'short_ton' and commodity_id = 'soybeans'
),

points as (
    select
        month,
        market_year,
        my_start,
        month_of_my,
        min(release_ts_utc)                    as asof_ts_utc,
        arg_min(release_key, release_ts_utc)   as release_key,
        arg_min(column_role, release_ts_utc)   as first_printed_as
    from v
    where metric = 'crushed_st'
    group by month, market_year, my_start, month_of_my
),

known as (
    -- Latest vintage of every month of the same MY (up to the point month) at the instant.
    select
        p.month                                  as point_month,
        k.month,
        k.metric,
        arg_max(k.value, k.release_ts_utc)       as value,
        max(k.release_ts_utc)                    as vintage_ts_utc
    from points as p
    inner join v as k
        on k.my_start = p.my_start
       and k.month <= p.month
       and k.release_ts_utc <= p.asof_ts_utc
    group by p.month, k.month, k.metric
),

cum as (
    select
        p.*,
        sum(k.value) filter (where k.metric = 'crushed_st')                              as cum_st,
        cast(count(*) filter (where k.metric = 'crushed_st') as integer)                 as n_months_known,
        max(k.value) filter (where k.metric = 'crushed_st' and k.month = p.month)        as month_crushed_st,
        max(k.value) filter (where k.metric = 'crude_oil_produced_klb' and k.month = p.month) as month_oil_klb,
        max(k.vintage_ts_utc)                                                            as nass_inputs_max_ts_utc
    from points as p
    inner join known as k on k.point_month = p.month
    group by all
),

last_my as (
    -- The months still to come in this MY, in the previous MY, as known at the instant.
    select
        p.month                                  as point_month,
        k.month,
        arg_max(k.value, k.release_ts_utc)       as value,
        max(k.release_ts_utc)                    as vintage_ts_utc
    from points as p
    inner join v as k
        on k.metric = 'crushed_st'
       and k.my_start = p.my_start - 1
       and k.month_of_my > p.month_of_my
       and k.release_ts_utc <= p.asof_ts_utc
    group by p.month, k.month
),

last_my_agg as (
    select
        point_month,
        avg(value)                               as last_my_remaining_mean_st,
        cast(count(*) as integer)                as last_my_remaining_n,
        max(vintage_ts_utc)                      as last_my_max_ts_utc
    from last_my
    group by point_month
),

soy as (
    select * from {{ ref('int_wasde_asof') }}
    where commodity_id = 'soybeans' and crush_native is not null
),

oil as (
    select * from {{ ref('int_wasde_asof') }}
    where commodity_id = 'soybean_oil' and production_native is not null
),

with_crush as (
    select
        c.*,
        s.wasde_release_key,
        s.wasde_release_ts_utc,
        s.proj_est_flag      as wasde_proj_est_flag,
        s.unit_id            as wasde_crush_unit_id,
        s.crush_native       as wasde_crush_native
    from cum as c
    asof left join soy as s
        on s.market_year = c.market_year
       and c.asof_ts_utc >= s.wasde_release_ts_utc
),

with_oil as (
    select
        w.*,
        o.wasde_release_key      as wasde_oil_release_key,
        o.wasde_release_ts_utc   as wasde_oil_release_ts_utc,
        o.unit_id                as wasde_oil_unit_id,
        o.production_native      as wasde_oil_production_native
    from with_crush as w
    asof left join oil as o
        on o.market_year = w.market_year
       and w.asof_ts_utc >= o.wasde_release_ts_utc
),

pace as (
    select
        w.*,
        w.cum_st * b.bu_per_st                                            as cum_bu,
        w.month_crushed_st * b.bu_per_st                                  as month_crushed_bu,
        w.month_oil_klb * 1000 / nullif(w.month_crushed_st * b.bu_per_st, 0) as oil_yield_lb_bu,
        -- WASDE soybean crush is in million bushels (m_bu), soybean oil in million pounds.
        w.wasde_crush_native * 1e6                                        as wasde_crush_bu,
        w.wasde_oil_production_native * 1e6
            / nullif(w.wasde_crush_native * 1e6, 0)                       as wasde_implied_oil_yield_lb_bu,
        12 - w.month_of_my                                                as months_remaining,
        l.last_my_remaining_mean_st * b.bu_per_st                         as last_my_remaining_mean_bu,
        coalesce(l.last_my_remaining_n, 0)                                as last_my_remaining_n,
        greatest(w.nass_inputs_max_ts_utc,
                 coalesce(l.last_my_max_ts_utc, w.nass_inputs_max_ts_utc)) as inputs_max_release_ts_utc
    from with_oil as w
    cross join bu as b
    left join last_my_agg as l on l.point_month = w.month
    where w.n_months_known = w.month_of_my
),

needed as (
    select
        *,
        cum_bu / nullif(wasde_crush_bu, 0)                                as pct_of_target,
        case when wasde_crush_bu is not null and months_remaining > 0
             then (wasde_crush_bu - cum_bu) / months_remaining
        end                                                               as required_monthly_bu
    from pace
),

hist as (
    select
        c.my_start,
        c.month_of_my,
        cast(count(h.pct_of_target) as integer)   as n_5yr,
        avg(h.pct_of_target)                      as pct_5yr_mean,
        min(h.pct_of_target)                      as pct_5yr_min,
        max(h.pct_of_target)                      as pct_5yr_max,
        cast(count(h.oil_yield_lb_bu) as integer) as n_yield_5yr,
        avg(h.oil_yield_lb_bu)                    as yield_5yr_mean,
        min(h.oil_yield_lb_bu)                    as yield_5yr_min,
        max(h.oil_yield_lb_bu)                    as yield_5yr_max
    from needed as c
    left join needed as h
        on h.month_of_my = c.month_of_my
       and h.my_start between c.my_start - 5 and c.my_start - 1
    group by c.my_start, c.month_of_my
)

select
    n.market_year,
    n.my_start,
    n.month_of_my,
    n.month,
    n.release_key,
    n.asof_ts_utc                as release_ts_utc,
    n.first_printed_as,
    n.month_crushed_st,
    n.month_crushed_bu,
    n.month_oil_klb,
    n.oil_yield_lb_bu,
    n.cum_st,
    n.cum_bu,
    n.n_months_known,
    n.inputs_max_release_ts_utc,
    n.wasde_release_key,
    n.wasde_release_ts_utc,
    n.wasde_proj_est_flag,
    n.wasde_crush_unit_id,
    n.wasde_crush_native,
    n.wasde_crush_bu,
    n.wasde_oil_release_key,
    n.wasde_oil_release_ts_utc,
    n.wasde_oil_unit_id,
    n.wasde_oil_production_native,
    n.wasde_implied_oil_yield_lb_bu,
    n.pct_of_target,
    n.months_remaining,
    n.required_monthly_bu,
    n.last_my_remaining_mean_bu,
    n.last_my_remaining_n,
    h.n_5yr,
    h.pct_5yr_mean,
    h.pct_5yr_min,
    h.pct_5yr_max,
    h.n_yield_5yr,
    h.yield_5yr_mean,
    h.yield_5yr_min,
    h.yield_5yr_max,
    n.month = max(n.month) over () as is_latest
from needed as n
inner join hist as h using (my_start, month_of_my)
