-- U.S. soybean crush per month (NASS Fats & Oils), latest revised value of every metric.
-- Marketing year September–August (the soybean crush year used by WASDE), so month_of_my 1 =
-- September. Units as printed by NASS: short tons and thousand pounds; bushels use dim_unit
-- (short ton of soybeans × 33.3333 bu, 60 lb/bu).
--   first_release_*  the release that first printed the month (point-in-time availability);
--   latest_release_* the release whose (revised) value is shown.
with v as (
    select * from {{ ref('stg_oilseed_crush') }}
    where oilseed = 'soybeans' and value is not null
),

ranked as (
    select
        *,
        row_number() over (partition by month, metric order by release_ts_utc desc) as rn_latest,
        row_number() over (partition by month, metric order by release_ts_utc)      as rn_first,
        count(*) over (partition by month, metric)                                  as n_vintages
    from v
),

bu as (
    select bu_per_unit from {{ ref('dim_unit') }}
    where unit_id = 'short_ton' and commodity_id = 'soybeans'
),

wide as (
    select
        month,
        any_value(market_year)                                                      as market_year,
        any_value(my_start)                                                         as my_start,
        any_value(month_of_my)                                                      as month_of_my,
        max(value) filter (where metric = 'crushed_st' and rn_latest = 1)           as crushed_st,
        max(value) filter (where metric = 'crude_oil_produced_klb' and rn_latest = 1) as oil_klb,
        max(value) filter (where metric = 'meal_produced_st' and rn_latest = 1)     as meal_st,
        max(value) filter (where metric = 'crude_oil_stocks_klb' and rn_latest = 1) as oil_stocks_klb,
        max(value) filter (where metric = 'crushed_st' and rn_first = 1)            as crushed_st_first,
        max(release_key) filter (where metric = 'crushed_st' and rn_first = 1)      as first_release_key,
        max(release_ts_utc) filter (where metric = 'crushed_st' and rn_first = 1)   as first_release_ts_utc,
        max(column_role) filter (where metric = 'crushed_st' and rn_first = 1)      as first_printed_as,
        max(release_key) filter (where metric = 'crushed_st' and rn_latest = 1)     as latest_release_key,
        max(release_ts_utc) filter (where metric = 'crushed_st' and rn_latest = 1)  as latest_release_ts_utc,
        max(source_url) filter (where metric = 'crushed_st' and rn_latest = 1)      as source_url,
        cast(max(n_vintages) filter (where metric = 'crushed_st') as integer)       as n_vintages
    from ranked
    group by month
)

select
    w.market_year,
    w.my_start,
    w.month_of_my,
    w.month,
    w.crushed_st,
    w.crushed_st * b.bu_per_unit                                       as crushed_bu,
    w.oil_klb,
    w.meal_st,
    w.oil_stocks_klb,
    w.oil_klb * 1000 / nullif(w.crushed_st * b.bu_per_unit, 0)         as oil_yield_lb_bu,
    w.meal_st * 2000 / nullif(w.crushed_st * b.bu_per_unit, 0)         as meal_yield_lb_bu,
    w.crushed_st_first,
    w.crushed_st <> w.crushed_st_first                                 as is_revised,
    w.first_release_key,
    w.first_release_ts_utc,
    w.first_printed_as,
    w.latest_release_key,
    w.latest_release_ts_utc,
    w.n_vintages,
    w.source_url,
    w.month = max(w.month) over ()                                     as is_latest_month
from wide as w
cross join bu as b
where w.crushed_st is not null
