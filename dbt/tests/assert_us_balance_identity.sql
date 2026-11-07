-- U.S. corn, soybean and wheat balance sheets must add up (USDA rounds to 1 mbu; allow 3).
select report_month, table_id, commodity_id, market_year, balance_residual
from {{ ref('fct_balance_sheet') }}
where (table_id, commodity_id) in (
        ('us_feed_grains_corn', 'corn'),
        ('us_soybeans_products', 'soybeans'),
        ('us_wheat', 'wheat')
    )
  and abs(balance_residual) > 3
