-- U.S. export sales per commodity × marketing year × week × destination (metric tons),
-- latest known value of every metric (the API revises history; silver keeps every vintage).
--   vintage_quality: 'captured' when the week was first seen by a weekly pull (as published),
--   'latest_only' when it comes from the one-time backfill (values as revised by then).
with ranked as (
    select
        *,
        row_number() over k_desc                        as rn,
        first_value(vintage_quality) over k_asc         as first_vintage_quality,
        count(*) over k_all                             as n_vintages
    from {{ ref('stg_export_sales') }}
    window
        k_desc as (partition by commodity_id, esr_market_year, week_ending, country_id, metric
                   order by snapshot_seq desc),
        k_asc as (partition by commodity_id, esr_market_year, week_ending, country_id, metric
                  order by snapshot_seq
                  rows between unbounded preceding and unbounded following),
        k_all as (partition by commodity_id, esr_market_year, week_ending, country_id, metric)
),

latest as (
    select * from ranked where rn = 1
)

select
    l.commodity_id,
    l.market_year,
    l.esr_market_year,
    l.my_start,
    l.week_ending,
    l.week_of_my,
    l.country_id,
    any_value(c.country_label)                                         as country_label,
    any_value(l.esr_country_code)                                      as esr_country_code,
    l.release_key,
    l.release_ts_utc,
    l.release_ts_source,
    -- 'latest_only' sorts after 'captured': any backfilled metric makes the row latest_only.
    max(l.first_vintage_quality)                                       as vintage_quality,
    cast(max(l.n_vintages) as integer)                                 as n_vintages,
    max(l.snapshot_key)                                                as latest_snapshot_key,
    'mt'                                                               as unit_id,
    coalesce(sum(l.value) filter (where l.metric = 'weekly_exports'), 0)      as weekly_exports_mt,
    coalesce(sum(l.value) filter (where l.metric = 'accumulated_exports'), 0) as accumulated_exports_mt,
    coalesce(sum(l.value) filter (where l.metric = 'outstanding_sales'), 0)   as outstanding_sales_mt,
    coalesce(sum(l.value) filter (where l.metric = 'net_sales'), 0)           as net_sales_mt,
    coalesce(sum(l.value) filter (where l.metric = 'total_commitment'), 0)    as total_commitment_mt,
    coalesce(sum(l.value) filter (where l.metric = 'next_my_net_sales'), 0)   as next_my_net_sales_mt,
    coalesce(sum(l.value) filter (where l.metric = 'next_my_outstanding'), 0) as next_my_outstanding_mt,
    'https://api.fas.usda.gov/api/esr/exports/commodityCode/'
        || cast(any_value(l.esr_commodity_code) as varchar)
        || '/allCountries/marketYear/' || cast(l.esr_market_year as varchar)  as source_url
from latest as l
left join {{ ref('dim_country') }} as c using (country_id)
group by l.commodity_id, l.market_year, l.esr_market_year, l.my_start, l.week_ending,
         l.week_of_my, l.country_id, l.release_key, l.release_ts_utc, l.release_ts_source
-- Destinations whose every metric was revised to zero (tombstones) drop out.
having sum(abs(l.value)) > 0
