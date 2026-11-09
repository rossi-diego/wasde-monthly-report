-- Implied disappearance per quarter, point in time (plan §6 G2).
--
--   implied_disappearance = stocks_{q-1} + production_q − stocks_q
--
-- taken on the release that first printed quarter q (its own release day):
--   * stocks_q:     the NASS total as first printed;
--   * stocks_{q-1}: the previous stock date (three months earlier) as printed in that same
--                   release (i.e. with the revision NASS published that day);
--   * production_q: the U.S. WASDE production of the marketing year in the latest WASDE public
--                   at the release instant (ASOF), but only in the harvest quarter (corn and
--                   soybeans September 1 → December 1, wheat June 1 → September 1; quarter_of_my
--                   = 1); every other quarter uses 0.
-- Imports are omitted (small for corn and soybeans). NASS may revise production on the same day
-- (annual Crop Production in January, Small Grains Summary in September); this uses the WASDE
-- figure public at the release. Both caveats travel with the G2 insight.
with s as (
    select * from {{ ref('stg_grain_stocks') }}
    where position = 'total' and value is not null
),

cur as (
    select
        commodity_id,
        market_year,
        my_start,
        quarter_of_my,
        as_of_date,
        release_key,
        release_ts_utc,
        edition,
        value as stocks_kbu
    from s
    where column_role = 'current'
    qualify row_number() over (partition by commodity_id, as_of_date
                               order by release_ts_utc, edition) = 1
),

with_prev as (
    select
        c.*,
        p.as_of_date        as prev_as_of_date,
        p.value             as prev_stocks_kbu,
        p.release_ts_utc    as prev_vintage_ts_utc
    from cur as c
    left join s as p
        on p.commodity_id = c.commodity_id
       and p.release_key = c.release_key
       and p.edition = c.edition
       and p.as_of_date = c.as_of_date - interval 3 month
),

wasde as (
    select * from {{ ref('int_wasde_asof') }}
    where commodity_id in ('corn', 'soybeans', 'wheat') and production_native is not null
),

joined as (
    select
        w.*,
        a.wasde_release_key,
        a.wasde_release_ts_utc,
        a.production_native as wasde_production_mbu
    from with_prev as w
    asof left join wasde as a
        on a.commodity_id = w.commodity_id
       and a.market_year = w.market_year
       and w.release_ts_utc >= a.wasde_release_ts_utc
)

select
    commodity_id,
    market_year,
    my_start,
    quarter_of_my,
    as_of_date,
    prev_as_of_date,
    release_key,
    release_ts_utc,
    'k_bu'                                                                   as unit_id,
    stocks_kbu,
    prev_stocks_kbu,
    prev_vintage_ts_utc,
    quarter_of_my = 1                                                        as is_harvest_quarter,
    case when quarter_of_my = 1 then wasde_release_key end                   as wasde_release_key,
    case when quarter_of_my = 1 then wasde_release_ts_utc end                as wasde_release_ts_utc,
    case when quarter_of_my = 1 then wasde_production_mbu end                as wasde_production_mbu,
    case when quarter_of_my = 1 then wasde_production_mbu * 1000 else 0 end  as production_kbu,
    prev_stocks_kbu
        + case when quarter_of_my = 1 then wasde_production_mbu * 1000 else 0 end
        - stocks_kbu                                                         as implied_disappearance_kbu,
    as_of_date = max(as_of_date) over (partition by commodity_id)            as is_latest
from joined
