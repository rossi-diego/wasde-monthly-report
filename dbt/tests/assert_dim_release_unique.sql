-- One row per report_id × release_key.
select report_id, release_key, count(*) as n
from {{ ref('dim_release') }}
group by 1, 2
having count(*) > 1
