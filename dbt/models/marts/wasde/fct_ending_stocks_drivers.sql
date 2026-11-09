-- Exact decomposition of every month-over-month ending-stocks revision:
--   Δ ending = Δ beginning + Δ production + Δ imports − Δ domestic use − Δ exports + Δ other
-- "other" captures residual/unaccounted lines and rounding. Where area and yield are both
-- published (U.S. tables), production is split into an area effect and a yield effect.
with b as (
    select
        *,
        lag(report_seq) over s        as prev_seq,
        lag(report_month) over s      as prev_report_month,
        lag(beginning_stocks) over s  as p_beginning_stocks,
        lag(production) over s        as p_production,
        lag(imports) over s           as p_imports,
        lag(domestic_total) over s    as p_domestic_total,
        lag(exports) over s           as p_exports,
        lag(ending_stocks) over s     as p_ending_stocks,
        lag(area_harvested) over s    as p_area_harvested,
        lag(yield) over s             as p_yield,
        lag(stocks_to_use_pct) over s as p_stocks_to_use_pct
    from {{ ref('fct_balance_sheet') }}
    window s as (partition by table_id, commodity_id, region_id, market_year order by report_seq)
),

d as (
    select
        report_month,
        report_seq,
        prev_report_month,
        datediff(
            'month',
            strptime(prev_report_month || '-01', '%Y-%m-%d'),
            strptime(report_month || '-01', '%Y-%m-%d')
        )                                                               as months_since_prev,
        table_id,
        commodity_id,
        commodity_label,
        region_id,
        region,
        market_year,
        proj_est_flag,
        unit_id,
        unit_label,
        ending_stocks,
        p_ending_stocks,
        stocks_to_use_pct,
        p_stocks_to_use_pct,
        ending_stocks - p_ending_stocks                                 as d_ending_stocks,
        coalesce(beginning_stocks, 0) - coalesce(p_beginning_stocks, 0) as d_beginning_stocks,
        coalesce(production, 0) - coalesce(p_production, 0)             as d_production,
        coalesce(imports, 0) - coalesce(p_imports, 0)                   as d_imports,
        coalesce(domestic_total, 0) - coalesce(p_domestic_total, 0)     as d_domestic_total,
        coalesce(exports, 0) - coalesce(p_exports, 0)                   as d_exports,
        area_harvested - p_area_harvested                               as d_area_harvested,
        yield - p_yield                                                 as d_yield,
        p_yield,
        -- mil. acres × yield → production units: bushels for grains/oilseeds,
        -- 480-lb bales for cotton (yield in lb/acre), cwt for rice (yield in lb/acre).
        case
            when table_id = 'us_cotton' then 1.0 / 480
            when table_id = 'us_rice' then 1.0 / 100
            when table_id like 'us_%' then 1.0
        end                                                             as area_yield_factor
    from b
    where prev_seq = report_seq - 1
)

select
    * exclude (p_yield, area_yield_factor),
    d_ending_stocks
    - (d_beginning_stocks + d_production + d_imports - d_domestic_total - d_exports) as d_other,
    d_area_harvested * p_yield * area_yield_factor                                   as d_production_area,
    d_production - d_area_harvested * p_yield * area_yield_factor                    as d_production_yield
from d
