{{
    config(
        unique_key=['window_hour', 'room_id', 'sensor_type'],
        incremental_strategy='merge'
    )
}}

-- Uurlijkse aggregaties per room + sensor_type.
-- Bij incrementele runs: verwerk het laatste uur opnieuw (late arrivals)
-- plus alle nieuwe uren daarna.
select
    date_trunc('HOUR', ts)   as window_hour,
    room_id,
    sensor_type,
    round(avg(value), 4)     as avg_value,
    round(min(value), 4)     as min_value,
    round(max(value), 4)     as max_value,
    count(*)                 as event_count,
    current_timestamp()      as _dbt_updated_at
from {{ ref('stg_sensor_events') }}
{% if is_incremental() %}
where ts >= (select dateadd(hour, -1, max(window_hour)) from {{ this }})
{% endif %}
group by 1, 2, 3
