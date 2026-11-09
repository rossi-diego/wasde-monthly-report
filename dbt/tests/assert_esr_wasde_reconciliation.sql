-- ESR ↔ WASDE reconciliation (warning only): for completed marketing years the final ESR
-- accumulated exports should be within ±10% of WASDE's final U.S. exports. ESR counts
-- reported sales/shipments, WASDE uses Census trade data, and definitions differ (e.g. meal
-- and oil coverage), so a gap is a flag to read, not a failure.
{{ config(severity = 'warn') }}

with final_esr as (
    select commodity_id, market_year, accumulated_exports_mt
    from {{ ref('fct_export_sales_totals') }}
    where is_latest_week_of_my
),

final_wasde as (
    select commodity_id, market_year, max_by(exports_mt, wasde_release_key) as exports_mt
    from {{ ref('int_wasde_asof') }}
    group by commodity_id, market_year
),

completed as (
    -- A MY is complete once a later MY has ESR data.
    select distinct a.commodity_id, a.market_year
    from {{ ref('fct_export_sales_totals') }} as a
    where exists (
        select 1 from {{ ref('fct_export_sales_totals') }} as b
        where b.commodity_id = a.commodity_id and b.esr_market_year > a.esr_market_year + 1
    )
)

select
    e.commodity_id,
    e.market_year,
    e.accumulated_exports_mt,
    w.exports_mt as wasde_exports_mt,
    e.accumulated_exports_mt / nullif(w.exports_mt, 0) - 1 as gap
from final_esr as e
inner join completed using (commodity_id, market_year)
inner join final_wasde as w using (commodity_id, market_year)
where abs(e.accumulated_exports_mt / nullif(w.exports_mt, 0) - 1) > 0.10
