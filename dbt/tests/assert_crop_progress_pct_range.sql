-- Crop Progress values are percentages of acreage: every printed value lies in [0, 100].
select crop, kind, category, week_ending, value_pct, nass_prev_week_pct, nass_prev_year_pct,
       nass_5yr_avg_pct
from {{ ref('fct_crop_progress_weekly') }}
where value_pct not between 0 and 100
   or nass_prev_week_pct not between 0 and 100
   or nass_prev_year_pct not between 0 and 100
   or nass_5yr_avg_pct not between 0 and 100
