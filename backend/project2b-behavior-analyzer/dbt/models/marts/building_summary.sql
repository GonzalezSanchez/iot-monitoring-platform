select
    r.building_id,
    r.building_name,
    r.lat,
    r.lon,
    count(a.id)                                             as anomaly_count,
    count(a.id) filter (where a.severity = 'high')         as high_count,
    count(a.id) filter (where a.severity = 'medium')       as medium_count,
    mode() within group (order by a.anomaly_type)          as dominant_type,
    max(a.detected_at)                                     as last_anomaly_at
from {{ ref('stg_rooms') }} r
left join {{ ref('stg_anomalies') }} a using (room_id)
group by r.building_id, r.building_name, r.lat, r.lon
