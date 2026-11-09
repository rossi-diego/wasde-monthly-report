-- U.S. grain stocks per commodity × stock date (NASS Grain Stocks, table 1), latest revised
-- value of every position, with the release that first printed the date and the value as
-- first printed. Thousand bushels (k_bu) as printed; metric tons through dim_unit.
--   market_year    the marketing year in which the stocks are held (corn/soybeans Sep-Aug,
--                  wheat Jun-May): September 1 corn stocks are the 2025/26 ending stocks;
--   quarter_of_my  1-4, where 4 = that marketing year's ending stocks (corn/soy Sep 1, wheat
--                  Jun 1) and 1 = the harvest quarter (corn/soy Dec 1, wheat Sep 1).
with v as (
    select * from {{ ref('stg_grain_stocks') }}
    where value is not null
),

ranked as (
    select
        *,
        row_number() over (partition by commodity_id, as_of_date, position
                           order by release_ts_utc desc, edition desc) as rn_latest,
        row_number() over (partition by commodity_id, as_of_date, position
                           order by release_ts_utc, edition)           as rn_first,
        count(*) over (partition by commodity_id, as_of_date, position) as n_vintages
    from v
),

wide as (
    select
        commodity_id,
        as_of_date,
        any_value(market_year)                                                      as market_year,
        any_value(my_start)                                                         as my_start,
        any_value(quarter_of_my)                                                    as quarter_of_my,
        max(value) filter (where position = 'on_farm' and rn_latest = 1)            as on_farm_kbu,
        max(value) filter (where position = 'off_farm' and rn_latest = 1)           as off_farm_kbu,
        max(value) filter (where position = 'total' and rn_latest = 1)              as total_kbu,
        max(value) filter (where position = 'on_farm' and rn_first = 1)             as on_farm_first_kbu,
        max(value) filter (where position = 'total' and rn_first = 1)               as total_first_kbu,
        max(release_key) filter (where position = 'total' and rn_first = 1)         as first_release_key,
        max(release_ts_utc) filter (where position = 'total' and rn_first = 1)      as first_release_ts_utc,
        max(column_role) filter (where position = 'total' and rn_first = 1)         as first_printed_as,
        max(release_key) filter (where position = 'total' and rn_latest = 1)        as latest_release_key,
        max(release_ts_utc) filter (where position = 'total' and rn_latest = 1)     as latest_release_ts_utc,
        max(source_url) filter (where position = 'total' and rn_latest = 1)         as source_url,
        cast(max(n_vintages) filter (where position = 'total') as integer)          as n_vintages
    from ranked
    group by commodity_id, as_of_date
),

mt as (
    select commodity_id, to_mt from {{ ref('dim_unit') }} where unit_id = 'k_bu'
)

select
    w.commodity_id,
    w.market_year,
    w.my_start,
    w.quarter_of_my,
    w.as_of_date,
    'k_bu'                                                                as unit_id,
    w.on_farm_kbu,
    w.off_farm_kbu,
    w.total_kbu,
    w.total_kbu * m.to_mt                                                 as total_mt,
    w.on_farm_kbu / nullif(w.total_kbu, 0)                                as on_farm_share,
    w.total_kbu / nullif(y.total_kbu, 0) - 1                              as total_yoy_pct,
    w.total_first_kbu,
    w.on_farm_first_kbu,
    w.total_kbu <> w.total_first_kbu                                      as is_revised,
    w.first_release_key,
    w.first_release_ts_utc,
    w.first_printed_as,
    w.latest_release_key,
    w.latest_release_ts_utc,
    w.n_vintages,
    w.source_url,
    w.as_of_date = max(w.as_of_date) over (partition by w.commodity_id)  as is_latest
from wide as w
left join wide as y
    on y.commodity_id = w.commodity_id
   and y.as_of_date = w.as_of_date - interval 1 year
left join mt as m on m.commodity_id = w.commodity_id
where w.total_kbu is not null
