-- The complete harmonized WASDE dataset: every table, every report since 2010-07.
select
    s.*,
    r.report_seq,
    r.is_latest as is_latest_report,
    s.table_id || '|' || s.commodity_id || '|' || s.region_id || '|' || s.attribute_id as series_key
from {{ ref('stg_wasde') }} as s
inner join {{ ref('dim_reports') }} as r using (report_month)
