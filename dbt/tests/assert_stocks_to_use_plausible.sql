-- Stocks-to-use for the main grains and oilseeds at U.S./World level stays within 0–200%.
select report_month, table_id, region_id, market_year, stocks_to_use_pct
from {{ ref('fct_balance_sheet') }}
where table_id in ('us_feed_grains_corn', 'us_soybeans_products', 'us_wheat',
                   'world_corn', 'world_soybeans', 'world_wheat')
  and region_id in ('united_states', 'world', 'world_less_china')
  and (stocks_to_use_pct < 0 or stocks_to_use_pct > 200)
