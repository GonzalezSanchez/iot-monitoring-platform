select
    id,
    job_id,
    entity_id                                   as room_id,
    anomaly_type,
    severity,
    detected_at,
    data,
    created_at
from {{ source('p2b', 'anomalies') }}
