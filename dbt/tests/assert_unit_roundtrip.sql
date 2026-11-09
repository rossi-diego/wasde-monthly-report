-- Every unit converts to metric tons and back without loss (to_mt × from_mt = 1), and
-- bushel-equivalent rows agree with the commodity's bushel weight.
with u as (select * from {{ ref('dim_unit') }}),

roundtrip as (
    select unit_id, commodity_id, 'roundtrip' as failure
    from u
    where abs(to_mt * from_mt - 1) > 1e-6
),

bushels as (
    select u.unit_id, u.commodity_id, 'bushel_equivalent' as failure
    from u
    inner join u as bu
        on bu.unit_id = 'bu' and bu.commodity_id = u.commodity_id
    where u.bu_per_unit is not null
      and abs(u.to_mt / u.bu_per_unit - bu.to_mt) / bu.to_mt > 1e-4
)

select * from roundtrip
union all
select * from bushels
