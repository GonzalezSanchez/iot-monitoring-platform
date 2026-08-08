---
description: Generate varied synthetic sensor/test records with typicality weights
argument-hint: <schema, or a path to a model/schema file — defaults to the platform SensorEvent>
---

Generate synthetic records matching the schema below.

If the schema is given as a path (pydantic model, dbt `schema.yml`, DDL), read it
and derive fields, types, and constraints from the source rather than guessing.
If no schema is given, default to the platform's shared sensor-event contract —
read `backend/project1b-smart-room-monitor-fastapi/src/models/sensor_event.py`
first (field constraints live there, e.g. the `sensor_type` pattern). Other
common schemas in this repo:

- `backend/project3b-iot-gateway/src/common/models.py` — gateway messages (device
  registration, auth, readings)
- `backend/project2b-behavior-analyzer/dbt/models/**/schema.yml` and
  `backend/project2c-lakehouse-dbt/dbt/models/**/schema.yml` — analytics layers

Output a JSON array of objects:

```json
[{"record": {...}, "typicality": 0.42}]
```

where `typicality` estimates how common this shape of record is in real
production data.

Cover the distribution, not the mode: roughly half the records should have
typicality below 0.10. Edge cases that matter in this platform:

- float precision that breaks naive Decimal conversion (`22.500000000001`,
  `1e-7`, negative temperatures)
- boundary values per sensor type (temperature extremes, occupancy 0, humidity
  0/100)
- timestamps at UTC day boundaries, DST transitions, and far in the past/future
- room/device ids with unusual-but-legal shapes (long names, unicode, embedded
  hyphens like the `room-loadtest-*` and `p3-` prefixed ids)
- plausible-but-unusual combinations (motion event with occupancy 0, duplicate
  event ids for idempotency tests)

Do not generate records that violate the stated constraints. Edge cases must
still be *valid* — unusual-but-legal data, not malformed data. (For malformed
input tests, say so explicitly and I'll mark those records `"invalid": true`.)

Default to 20 records unless the request specifies a count.

The weights are for ranking, not sampling: sort ascending to get an edge-case
suite. Do not treat them as calibrated probabilities.

Schema and constraints: $ARGUMENTS
