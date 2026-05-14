select
    room_id,
    building_id,
    building_name,
    floor,
    lat,
    lon
from {{ source('p2b', 'rooms') }}
