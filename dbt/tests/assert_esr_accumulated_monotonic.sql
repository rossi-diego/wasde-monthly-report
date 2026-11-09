-- ESR accumulated exports (all destinations) never fall within a marketing year, except for
-- corrections FAS actually published, listed in seeds/esr_corrections.csv.
with t as (
    select
        commodity_id,
        market_year,
        week_ending,
        accumulated_exports_mt,
        lag(accumulated_exports_mt) over (
            partition by commodity_id, esr_market_year order by week_ending
        ) as prev_accumulated_mt
    from {{ ref('fct_export_sales_totals') }}
)

select t.*
from t
left join {{ ref('esr_corrections') }} as c
    on c.commodity_id = t.commodity_id
   and c.market_year = t.market_year
   and c.week_ending = t.week_ending
where t.prev_accumulated_mt is not null
  and t.accumulated_exports_mt < t.prev_accumulated_mt - 0.5
  and c.commodity_id is null
