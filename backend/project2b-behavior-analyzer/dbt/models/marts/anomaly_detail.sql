select
    a.id,
    a.job_id,
    a.room_id,
    r.building_id,
    r.building_name,
    r.floor,
    r.lat,
    r.lon,
    a.anomaly_type,
    a.severity,
    a.detected_at,
    extract(hour from a.detected_at)            as detected_hour,
    extract(dow from a.detected_at)             as detected_dow,
    a.data,
    a.created_at
from {{ ref('stg_anomalies') }} a
left join {{ ref('stg_rooms') }} r using (room_id)
