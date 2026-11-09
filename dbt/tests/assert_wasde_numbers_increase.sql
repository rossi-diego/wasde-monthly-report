-- WASDE numbers increase with publication order (catches mis-dated or duplicated reports).
select *
from (
    select report_month, wasde_number,
           lag(wasde_number) over (order by report_seq) as prev_number
    from {{ ref('dim_reports') }}
)
where wasde_number is not null and prev_number is not null and wasde_number <= prev_number
