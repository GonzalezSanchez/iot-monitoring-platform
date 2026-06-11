{{
    config(materialized='table')
}}

select building_id, name, city, floors
from (values
    ('building_001', 'Main Office',  'Amsterdam', 3),
    ('building_002', 'Warehouse',    'Amsterdam', 3)
) as t(building_id, name, city, floors)
