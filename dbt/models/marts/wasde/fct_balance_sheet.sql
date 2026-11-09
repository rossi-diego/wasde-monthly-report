-- Balance sheet per report × table × commodity × region × marketing year (wide),
-- with stocks-to-use and the accounting residual.
with base as (
    select * from {{ ref('fct_wasde') }}
    where period = 'annual' and reliability_stat is null
),

wide as (
    select
        report_month,
        report_seq,
        table_id,
        commodity_id,
        region_id,
        market_year,
        my_start,
        any_value(commodity_label)                                      as commodity_label,
        any_value(region)                                               as region,
        max(proj_est_flag)                                              as proj_est_flag,
        max(unit_id) filter (where attribute_id = 'ending_stocks')      as unit_id,
        max(unit_label) filter (where attribute_id = 'ending_stocks')   as unit_label,
        max(value) filter (where attribute_id = 'area_planted')         as area_planted,
        max(value) filter (where attribute_id = 'area_harvested')       as area_harvested,
        max(value) filter (where attribute_id = 'yield')                as yield,
        max(value) filter (where attribute_id = 'beginning_stocks')     as beginning_stocks,
        max(value) filter (where attribute_id = 'production')           as production,
        max(value) filter (where attribute_id = 'imports')              as imports,
        max(value) filter (where attribute_id = 'total_supply')         as total_supply,
        max(value) filter (where attribute_id = 'domestic_feed')        as domestic_feed,
        max(value) filter (where attribute_id = 'feed_residual')        as feed_residual,
        max(value) filter (where attribute_id = 'food_seed_industrial') as food_seed_industrial,
        max(value) filter (where attribute_id = 'ethanol')              as ethanol,
        max(value) filter (where attribute_id = 'crush')                as crush,
        max(value) filter (where attribute_id = 'domestic_total')       as domestic_total,
        max(value) filter (where attribute_id = 'exports')              as exports,
        max(value) filter (where attribute_id = 'total_use')            as total_use,
        max(value) filter (where attribute_id = 'ending_stocks')        as ending_stocks,
        max(value) filter (where attribute_id = 'farm_price')           as farm_price
    from base
    group by report_month, report_seq, table_id, commodity_id, region_id, market_year, my_start
),

filled as (
    -- Some tables (e.g. U.S. soybeans) publish crush/seed/residual + total use but no
    -- domestic total: derive it as total use − exports so every sheet has the same shape.
    select
        * replace (coalesce(domestic_total, total_use - coalesce(exports, 0)) as domestic_total)
    from wide
)

select
    *,
    -- World aggregates: trade nets out, so use = domestic use.
    -- Countries and U.S. tables: total use (domestic + exports).
    100 * case
        when region_id in ('world', 'world_less_china') then ending_stocks / nullif(domestic_total, 0)
        when total_use is not null then ending_stocks / nullif(total_use, 0)
        else ending_stocks / nullif(domestic_total + coalesce(exports, 0), 0)
    end as stocks_to_use_pct,
    ending_stocks - (
        coalesce(beginning_stocks, 0) + coalesce(production, 0) + coalesce(imports, 0)
        - coalesce(domestic_total, 0) - coalesce(exports, 0)
    ) as balance_residual
from filled
where ending_stocks is not null
