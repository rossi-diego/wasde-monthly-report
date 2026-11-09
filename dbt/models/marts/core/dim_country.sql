-- Destination countries of FAS Export Sales (from config/vocab/countries.yaml).
select
    country_id,
    label                                as country_label,
    cast(esr_country_code as integer)    as esr_country_code,
    genc_code
from read_parquet('{{ var("silver_dir") }}/countries.parquet')
