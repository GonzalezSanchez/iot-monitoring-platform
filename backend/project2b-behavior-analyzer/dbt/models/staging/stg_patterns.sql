select
    id,
    job_id,
    entity_id                                   as room_id,
    pattern_type,
    period_start,
    period_end,
    data,
    created_at
from {{ source('p2b', 'patterns') }}
