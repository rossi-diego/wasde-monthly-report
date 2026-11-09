{#
  Point-in-time guard for cross-report marts (plan §5): a row may only use information that
  was public when the left-hand report was released. Fails on every row whose right-hand
  timestamp is later than the left-hand one. Equal instants are allowed (a WASDE published at
  the same moment counts as public); dbt unit tests in cross/schema.yml pin that boundary.

  Usage (schema.yml):
    data_tests:
      - assert_no_lookahead:
          arguments: {left_ts: release_ts_utc, right_ts: wasde_release_ts_utc}
#}
{% test assert_no_lookahead(model, left_ts, right_ts) %}
select *
from {{ model }}
where {{ right_ts }} is not null
  and {{ right_ts }} > {{ left_ts }}
{% endtest %}
