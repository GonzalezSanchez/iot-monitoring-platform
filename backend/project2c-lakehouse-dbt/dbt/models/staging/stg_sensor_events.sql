select
    event_id,
    room_id,
    sensor_type,
    value,
    ts,
    _source_file,
    _ingestion_time
from {{ source('silver', 'sensor_events') }}
