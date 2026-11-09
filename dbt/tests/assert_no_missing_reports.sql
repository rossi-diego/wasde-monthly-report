-- Every month between the first and last report must be present, except months in which
-- USDA genuinely published no WASDE (government shutdowns). A gap here means an ingest
-- silently failed, and month-over-month deltas would span two months.
with bounds as (
    select min(report_date) as first_date, max(report_date) as last_date from {{ ref('dim_reports') }}
),
months as (
    select strftime(m, '%Y-%m') as report_month
    from bounds, generate_series(first_date, last_date, interval 1 month) as g(m)
)
select report_month
from months
where report_month not in (select report_month from {{ ref('dim_reports') }})
  and report_month not in ('2013-10', '2019-01', '2025-10')
