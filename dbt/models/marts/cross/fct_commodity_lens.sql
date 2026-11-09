-- One commodity, every report (plan §5, cut line C): the latest value of each headline metric
-- per commodity × report, with the release it comes from. Long format, one row per
-- commodity × report × metric. Feeds the /commodities/<slug> lens (soybeans, corn).
--   wasde          U.S. production / exports / ending stocks (/ crush for soybeans) of the
--                  newest marketing year in the newest WASDE (native units, m_bu)
--   export_sales   commitments and their share of the as-of WASDE target (newest ESR week)
--   oilseed_crush  soybeans crushed in the newest NASS month and the MY-to-date share of USDA
--   crop_progress  every stage printed in the newest week, and good-to-excellent / CI
--   grain_stocks   newest stocks (all positions, on-farm share) and the latest G1 surprise
with wasde_latest as (
    select commodity_id, max(wasde_release_ts_utc) as ts
    from {{ ref('int_wasde_asof') }}
    group by commodity_id
),

wasde as (
    select a.*
    from {{ ref('int_wasde_asof') }} as a
    inner join wasde_latest as l
        on l.commodity_id = a.commodity_id and l.ts = a.wasde_release_ts_utc
    qualify row_number() over (partition by a.commodity_id order by a.my_start desc) = 1
),

wasde_rows as (
    select commodity_id, 'wasde' as report_id, m.metric, m.value, unit_id,
           market_year as period, cast(null as date) as period_date, market_year,
           wasde_release_key as release_key, wasde_release_ts_utc as release_ts_utc,
           cast(null as varchar) as source_url
    from wasde
    cross join lateral (
        values ('production', production_native), ('exports', exports_native),
               ('ending_stocks', ending_stocks_native), ('crush', crush_native)
    ) as m(metric, value)
    where m.value is not null
),

esr as (
    select * from {{ ref('fct_export_pace') }}
    qualify row_number() over (partition by commodity_id
                               order by esr_market_year desc, week_ending desc) = 1
),

esr_rows as (
    select commodity_id, 'export_sales', m.metric, m.value, m.unit_id,
           cast(week_ending as varchar), week_ending, market_year, release_key, release_ts_utc,
           cast(null as varchar)
    from esr
    cross join lateral (
        values ('total_commitment', total_commitment_mt, 'mt'),
               ('pct_of_usda_target', pct_of_target, 'share')
    ) as m(metric, value, unit_id)
    where m.value is not null
),

crush as (
    select * from {{ ref('fct_crush_pace') }}
    qualify row_number() over (order by month desc) = 1
),

crush_rows as (
    select 'soybeans', 'oilseed_crush', m.metric, m.value, m.unit_id,
           cast(month as varchar), month, market_year, release_key, release_ts_utc,
           cast(null as varchar)
    from crush
    cross join lateral (
        values ('month_crushed', month_crushed_bu, 'bu'),
               ('pct_of_usda_target', pct_of_target, 'share')
    ) as m(metric, value, unit_id)
    where m.value is not null
),

progress as (
    select * from {{ ref('fct_crop_progress_weekly') }}
    where kind = 'progress' and crop in ('corn', 'soybeans')
    qualify week_ending = max(week_ending) over (partition by crop)
),

progress_rows as (
    select commodity_id, 'crop_progress', category || '_pct', value_pct, 'pct',
           cast(week_ending as varchar), week_ending, cast(season as varchar), first_release_key,
           first_release_ts_utc, source_url
    from progress
    where value_pct is not null
),

cond as (
    select * from {{ ref('fct_crop_condition') }}
    where crop in ('corn', 'soybeans') and is_latest_week
),

cond_rows as (
    select commodity_id, 'crop_progress', m.metric, m.value, m.unit_id,
           cast(week_ending as varchar), week_ending, cast(season as varchar), first_release_key,
           release_ts_utc, source_url
    from cond
    cross join lateral (
        values ('good_excellent_pct', ge_pct, 'pct'), ('condition_index', ci, 'index_1_5')
    ) as m(metric, value, unit_id)
    where m.value is not null
),

stocks as (
    select * from {{ ref('fct_grain_stocks_quarterly') }}
    where is_latest
),

stocks_rows as (
    select commodity_id, 'grain_stocks', m.metric, m.value, m.unit_id,
           cast(as_of_date as varchar), as_of_date, market_year, latest_release_key,
           latest_release_ts_utc, source_url
    from stocks
    cross join lateral (
        values ('total_stocks', total_kbu, 'k_bu'), ('on_farm_share', on_farm_share, 'share')
    ) as m(metric, value, unit_id)
    where m.value is not null
),

g1 as (
    select * from {{ ref('fct_stocks_vs_wasde') }}
    where is_latest and surprise_mbu is not null
),

g1_rows as (
    select commodity_id, 'grain_stocks', 'ending_stocks_vs_usda', surprise_mbu, 'm_bu',
           cast(as_of_date as varchar), as_of_date, market_year, release_key, release_ts_utc,
           cast(null as varchar)
    from g1
)

select
    commodity_id,
    report_id,
    metric,
    cast(value as double)              as value,
    unit_id,
    period,
    cast(period_date as date)          as period_date,
    market_year,
    release_key,
    cast(release_ts_utc as timestamptz) as release_ts_utc,
    source_url
from (
    select * from wasde_rows
    union all select * from esr_rows
    union all select * from crush_rows
    union all select * from progress_rows
    union all select * from cond_rows
    union all select * from stocks_rows
    union all select * from g1_rows
)
where commodity_id in ('corn', 'soybeans', 'wheat', 'soybean_meal', 'soybean_oil')
