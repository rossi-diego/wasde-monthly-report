-- Grain stocks: on farms + off farms = all positions (± 1 thousand bushels of rounding), on the
-- latest revision and on the first print (plan §5).
select commodity_id, as_of_date, on_farm_kbu, off_farm_kbu, total_kbu
from {{ ref('fct_grain_stocks_quarterly') }}
where on_farm_kbu is not null
  and off_farm_kbu is not null
  and abs(on_farm_kbu + off_farm_kbu - total_kbu) > 1
