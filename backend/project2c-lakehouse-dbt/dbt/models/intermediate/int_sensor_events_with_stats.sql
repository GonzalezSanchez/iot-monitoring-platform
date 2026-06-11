-- Voegt rolling populatie-statistieken toe per room + sensor_type.
-- Ephemeral: wordt geïnlineeerd in downstream modellen, geen fysieke tabel.
select
    event_id,
    room_id,
    sensor_type,
    value,
    ts,
    avg(value)         over (partition by room_id, sensor_type) as mean_value,
    stddev_pop(value)  over (partition by room_id, sensor_type) as stddev_value
from {{ ref('stg_sensor_events') }}
