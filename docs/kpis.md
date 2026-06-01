# IoT Monitoring Platform — KPIs

KPIs define measurable goals for the platform. They are distinct from thresholds:
- **Threshold**: a technical trigger (`temperature > 30°C → alert`)
- **KPI**: a business goal (`process 95% of events within 2 seconds by Q4`)

---

## Project KPIs

| KPI | Target | Deadline |
|-----|--------|----------|
| System availability | 99.9% uptime per month | ongoing |
| Sensor coverage | support 500 sensors / 100 rooms | end of year |
| Raw data retention | raw sensor data stored for 6 months | ongoing |
| Processed data retention | processed data stored for 2 years | ongoing |
| Security | 0 unauthorized data access incidents | per quarter |

---

## Day-to-Day KPIs

| KPI | Target | Unit |
|-----|--------|------|
| Event processing latency | 95% of events processed within 2 seconds | per day |
| Data loss rate | < 1% data loss | per day |
| Pipeline error rate | < 5 pipeline errors | per day |
| Anomaly detection latency | anomaly detected and stored within 30 seconds of ingestion | per event |
| Data quality | < 2% null or invalid readings per sensor | per day |

---

## Notes

- Current thresholds (temperature, humidity, occupancy) in `project1a/src/services/anomaly_detector.py` are **not** KPIs — they are operational triggers.
- Current z-score thresholds in `project2b/jobs/analyze.py` (`Z_MEDIUM=3`, `Z_HIGH=5`) are also thresholds, not KPIs.
- These KPIs would be formally defined during the **Planning phase** of a real project, before implementation begins.
