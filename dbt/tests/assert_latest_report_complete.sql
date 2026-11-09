-- The newest report must look like a full WASDE (guards against a truncated download).
select report_month, n_rows
from {{ ref('dim_reports') }}
where is_latest and n_rows < 3500
