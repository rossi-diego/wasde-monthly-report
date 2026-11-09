-- U.S. WASDE targets per commodity × marketing year × WASDE vintage, in native units and
-- metric tons (dim_unit: corn 39.3679 bu/t, soybeans/wheat 36.7437 bu/t, soybean meal
-- thousand short tons × 907.185, soybean oil million lb × 453.592). Cross-report marts ASOF
-- JOIN this on wasde_release_ts_utc <= <other report>.release_ts_utc (point in time).
with us as (
    select
        commodity_id,
        market_year,
        my_start,
        report_month   as wasde_release_key,
        release_ts_utc as wasde_release_ts_utc,
        proj_est_flag,
        attribute_id,
        value,
        unit_id
    from {{ ref('fct_wasde') }}
    where period = 'annual'
      and reliability_stat is null
      and region_id = 'united_states'
      and attribute_id in ('exports', 'production', 'ending_stocks', 'crush')
      and (
          (table_id = 'us_feed_grains_corn' and commodity_id = 'corn')
          or (table_id = 'us_soybeans_products'
              and commodity_id in ('soybeans', 'soybean_meal', 'soybean_oil'))
          or (table_id = 'us_wheat' and commodity_id = 'wheat')
      )
      and regexp_matches(market_year, '^[0-9]{4}/[0-9]{2}$')
),

conv as (
    select
        us.*,
        coalesce(uc.to_mt, ug.to_mt) as to_mt
    from us
    left join {{ ref('dim_unit') }} as uc
        on uc.unit_id = us.unit_id and uc.commodity_id = us.commodity_id
    left join {{ ref('dim_unit') }} as ug
        on ug.unit_id = us.unit_id and ug.commodity_id is null
)

select
    commodity_id,
    market_year,
    my_start,
    wasde_release_key,
    wasde_release_ts_utc,
    max(proj_est_flag)                                                   as proj_est_flag,
    max(unit_id)                                                         as unit_id,
    max(value) filter (where attribute_id = 'exports')                   as exports_native,
    max(value * to_mt) filter (where attribute_id = 'exports')           as exports_mt,
    max(value) filter (where attribute_id = 'production')                as production_native,
    max(value * to_mt) filter (where attribute_id = 'production')        as production_mt,
    max(value) filter (where attribute_id = 'ending_stocks')             as ending_stocks_native,
    max(value * to_mt) filter (where attribute_id = 'ending_stocks')     as ending_stocks_mt,
    max(value) filter (where attribute_id = 'crush')                     as crush_native,
    max(value * to_mt) filter (where attribute_id = 'crush')             as crush_mt
from conv
group by commodity_id, market_year, my_start, wasde_release_key, wasde_release_ts_utc
