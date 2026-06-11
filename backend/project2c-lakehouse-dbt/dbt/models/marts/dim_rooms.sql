{{
    config(materialized='table')
}}

-- Kamer-dimensie — statische metadata voor de 10 gesimuleerde kamers.
-- Verdeling: room_001-005 in building_001, room_006-010 in building_002.
select room_id, building_id, floor, capacity
from (values
    ('room_001', 'building_001', 1, 20),
    ('room_002', 'building_001', 1, 15),
    ('room_003', 'building_001', 2, 20),
    ('room_004', 'building_001', 2, 12),
    ('room_005', 'building_001', 3, 18),
    ('room_006', 'building_002', 1, 20),
    ('room_007', 'building_002', 1, 16),
    ('room_008', 'building_002', 2, 20),
    ('room_009', 'building_002', 2, 14),
    ('room_010', 'building_002', 3, 10)
) as t(room_id, building_id, floor, capacity)
