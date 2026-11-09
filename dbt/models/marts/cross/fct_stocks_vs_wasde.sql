-- Grain Stocks vs. USDA, point in time (plan §6 G1).
--
-- Only the stock dates that are a WASDE ending stock: corn and soybeans on September 1, wheat
-- on June 1 (quarter_of_my = 4: the ending stocks of the marketing year that just ended). For
-- each, the NASS total as first printed on its own release day is compared with the U.S.
-- ending stocks of that (old-crop) marketing year in the latest WASDE public at that instant
-- (ASOF JOIN on wasde_release_ts_utc <= release_ts_utc; equal instants count as public).
--   surprise = NASS total − WASDE ending stocks (as of the release), in million bushels and
--   as a share of the WASDE figure. Ranks among years are computed by the insight (G1).
with first_print as (
    select
        s.commodity_id,
        s.market_year,
        s.my_start,
        s.as_of_date,
        s.release_key,
        s.release_ts_utc,
        s.value                     as nass_total_kbu
    from {{ ref('stg_grain_stocks') }} as s
    where s.position = 'total'
      and s.quarter_of_my = 4
      and s.column_role = 'current'
      and s.value is not null
    qualify row_number() over (partition by s.commodity_id, s.as_of_date
                               order by s.release_ts_utc, s.edition) = 1
),

wasde as (
    select * from {{ ref('int_wasde_asof') }}
    where commodity_id in ('corn', 'soybeans', 'wheat') and ending_stocks_native is not null
),

joined as (
    select
        f.*,
        w.wasde_release_key,
        w.wasde_release_ts_utc,
        w.proj_est_flag            as wasde_proj_est_flag,
        w.unit_id                  as wasde_unit_id,
        w.ending_stocks_native     as wasde_ending_stocks_native
    from first_print as f
    asof left join wasde as w
        on w.commodity_id = f.commodity_id
       and w.market_year = f.market_year
       and f.release_ts_utc >= w.wasde_release_ts_utc
)

select
    commodity_id,
    market_year,
    my_start,
    as_of_date,
    release_key,
    release_ts_utc,
    'm_bu'                                                              as unit_id,
    nass_total_kbu,
    nass_total_kbu / 1000                                               as nass_total_mbu,
    wasde_release_key,
    wasde_release_ts_utc,
    wasde_proj_est_flag,
    wasde_unit_id,
    -- WASDE U.S. corn / soybean / wheat ending stocks are in million bushels (m_bu).
    wasde_ending_stocks_native                                          as wasde_ending_stocks_mbu,
    nass_total_kbu / 1000 - wasde_ending_stocks_native                  as surprise_mbu,
    (nass_total_kbu / 1000 - wasde_ending_stocks_native)
        / nullif(wasde_ending_stocks_native, 0)                         as surprise_pct,
    as_of_date = max(as_of_date) over (partition by commodity_id)       as is_latest
from joined
