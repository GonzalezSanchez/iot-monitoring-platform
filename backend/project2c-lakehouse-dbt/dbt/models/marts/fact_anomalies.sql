{{
    config(
        unique_key='event_id',
        on_schema_change='sync_all_columns'
    )
}}

-- Z-score per event op basis van de volledige distributie per room + sensor_type.
-- Elke run recomputed z-scores voor alle records via MERGE op event_id,
-- zodat scores altijd consistent zijn met de actuele verdeling in Silver.
-- is_anomaly = True wanneer |z| > 2.5 (buiten ~99% van de verwachte waarden).
select
    event_id,
    room_id,
    sensor_type,
    value,
    ts,
    round(mean_value, 4)   as mean_value,
    round(stddev_value, 4) as stddev_value,
    case
        when stddev_value > 0
        then round((value - mean_value) / stddev_value, 4)
        else 0.0
    end                    as z_score,
    case
        when stddev_value > 0
        then abs((value - mean_value) / stddev_value) > 2.5
        else false
    end                    as is_anomaly
from {{ ref('int_sensor_events_with_stats') }}
