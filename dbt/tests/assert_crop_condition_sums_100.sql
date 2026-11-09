-- The five condition ratings of a crop and week sum to 100 (± 1 of rounding) (plan §5).
select crop, week_ending, sum_pct
from {{ ref('fct_crop_condition') }}
where sum_pct is not null
  and abs(sum_pct - 100) > 1
