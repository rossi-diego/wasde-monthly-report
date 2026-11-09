-- One row per commodity × marketing year × week × destination in the published ESR marts,
-- and one row per commodity × marketing year × week in the pace mart.
select commodity_id, esr_market_year, week_ending, country_id, count(*) as n
from {{ ref('fct_export_sales_weekly') }}
group by commodity_id, esr_market_year, week_ending, country_id
having count(*) > 1
union all
select commodity_id, esr_market_year, week_ending, 'all' as country_id, count(*) as n
from {{ ref('fct_export_pace') }}
group by commodity_id, esr_market_year, week_ending
having count(*) > 1
