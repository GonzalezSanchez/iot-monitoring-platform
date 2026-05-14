select
    p.id,
    p.job_id,
    p.room_id,
    r.building_id,
    r.building_name,
    r.floor,
    r.lat,
    r.lon,
    p.pattern_type,
    p.period_start,
    p.period_end,
    p.data,
    p.created_at
from {{ ref('stg_patterns') }} p
left join {{ ref('stg_rooms') }} r using (room_id)
