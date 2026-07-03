import useFetch from '../hooks/useFetch';
import Badge from '../components/Badge';
import PageHeader from '../components/PageHeader';

const API = import.meta.env.VITE_API_ENDPOINT || 'http://localhost:8000';

const SENSOR_UNIT = {
  temperature: '°C',
  co2: 'ppm',
  occupancy: 'people',
  humidity: '%',
};

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 px-6 py-4 flex flex-col gap-1">
      <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{label}</span>
      <span className="text-2xl font-bold text-gray-800">{value ?? '—'}</span>
      {sub && <span className="text-xs text-gray-400">{sub}</span>}
    </div>
  );
}

function zColor(z) {
  const abs = Math.abs(z);
  if (abs >= 4) return 'bg-red-100 text-red-700';
  if (abs >= 3) return 'bg-orange-100 text-orange-700';
  return 'bg-amber-100 text-amber-700';
}

function fmtTs(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString('nl-BE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export default function LakehouseDashboard() {
  const { data: summary, error } = useFetch(`${API}/lakehouse/summary`);
  const { data: anomaliesData } = useFetch(`${API}/lakehouse/anomalies?limit=50`);
  const anomalies = Array.isArray(anomaliesData) ? anomaliesData : [];

  const loading = !summary && !error;

  return (
    <div className="flex flex-col h-full font-sans">
      <PageHeader
        title="Azure Databricks Lakehouse"
        subtitle="PySpark · Delta Lake · Unity Catalog · dbt Gold layer — weekly pipeline"
      >
        <div className="mt-2 flex flex-wrap gap-2">
          {['Delta Lake', 'Unity Catalog', 'dbt', 'WAP pattern', 'Z-score'].map(t => (
            <span key={t} className="px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">{t}</span>
          ))}
        </div>
      </PageHeader>

      <div className="flex-1 overflow-auto px-6 py-5">
        {loading && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-400">
            <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin" />
            <p className="text-sm">Querying Gold layer…</p>
            <p className="text-xs text-gray-300">SQL Warehouse may need a moment to warm up</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
            Could not reach the lakehouse: <span className="font-mono">{error}</span>
          </div>
        )}

        {summary && (
          <>
            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <StatCard
                label="Total events"
                value={summary.total_events?.toLocaleString()}
                sub="in Gold fact_anomalies"
              />
              <StatCard
                label="Anomalies detected"
                value={summary.total_anomalies?.toLocaleString()}
                sub={`${summary.total_events ? ((summary.total_anomalies / summary.total_events) * 100).toFixed(1) : 0}% of total  ·  |z| > 2.5`}
              />
              <StatCard
                label="Last dbt run"
                value={fmtTs(summary.last_dbt_run)}
                sub="weekly · every Monday 07:00"
              />
            </div>

            {/* Anomaly table */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 flex justify-between items-center">
                <h2 className="text-sm font-semibold text-gray-700">
                  Recent anomalies
                  <span className="ml-2 text-xs font-normal text-gray-400">Gold · fact_anomalies · is_anomaly = true</span>
                </h2>
                <span className="text-xs text-gray-400">{anomalies.length} records</span>
              </div>
              {anomalies.length === 0 ? (
                <p className="px-5 py-6 text-sm text-gray-400">No anomalies found.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
                    <tr>
                      <th className="px-5 py-2 text-left">Room</th>
                      <th className="px-5 py-2 text-left">Sensor</th>
                      <th className="px-5 py-2 text-right">Value</th>
                      <th className="px-5 py-2 text-right">Z-score</th>
                      <th className="px-5 py-2 text-left">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {anomalies.map((a, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-5 py-2 font-medium text-gray-700">{a.room_id}</td>
                        <td className="px-5 py-2 text-gray-500">{a.sensor_type}</td>
                        <td className="px-5 py-2 text-right text-gray-700">
                          {a.value} {SENSOR_UNIT[a.sensor_type] ?? ''}
                        </td>
                        <td className="px-5 py-2 text-right">
                          <Badge color={zColor(a.z_score)}>{a.z_score}</Badge>
                        </td>
                        <td className="px-5 py-2 text-gray-400 text-xs">{fmtTs(a.ts)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
