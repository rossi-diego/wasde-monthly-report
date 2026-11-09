-- No two values for the same report × table × commodity × region × attribute × MY × period.
select report_month, table_id, commodity_id, region_id, attribute_id, market_year, period, reliability_stat
from {{ ref('fct_wasde') }}
group by all
having count(*) > 1
