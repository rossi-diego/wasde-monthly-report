-- One row per WASDE report (release), in publication order.
select
    report_month,
    report_date,
    max(wasde_number)                         as wasde_number,
    max(release_date)                         as release_date,
    min(source)                               as source,
    count(*)                                  as n_rows,
    row_number() over (order by report_month) as report_seq,
    report_month = max(report_month) over ()  as is_latest
from {{ ref('stg_wasde') }}
group by report_month, report_date
