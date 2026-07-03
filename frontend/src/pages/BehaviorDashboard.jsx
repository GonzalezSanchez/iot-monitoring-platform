import { useState } from 'react';
import useFetch from '../hooks/useFetch';
import usePostJson from '../hooks/usePostJson';
import Badge from '../components/Badge';
import CollapsibleForm, { Field, SubmitButton, ResultBanner } from '../components/CollapsibleForm';

const P2A_BASE = import.meta.env.VITE_P2A_API_ENDPOINT || '';
const API_BASE = import.meta.env.VITE_API_ENDPOINT || '';

const SEVERITY_BADGE = {
  low:    'text-green-700 bg-green-50 border border-green-600',
  medium: 'text-amber-700 bg-amber-50 border border-amber-600',
  high:   'text-red-700 bg-red-50 border border-red-600',
};
const DEFAULT_BADGE = 'text-gray-700 bg-gray-100 border border-gray-400';

// ── Not deployed banner ───────────────────────────────────────────────────────

function NotDeployed() {
  return (
    <div className="py-12 px-6 text-center font-sans">
      <div className="text-4xl mb-3">☁️</div>
      <h2 className="text-xl font-semibold text-gray-700 mb-2">Project 2a not currently deployed</h2>
      <p className="text-sm text-gray-500 max-w-md mx-auto">
        The Behavior Analyzer runs on AWS Step Functions + Aurora Serverless and is deployed on-demand to save costs.
        Set <code className="bg-gray-100 px-1 rounded">VITE_P2A_API_ENDPOINT</code> and redeploy via Terraform to enable this tab.
      </p>
    </div>
  );
}

// ── Trigger analysis form ─────────────────────────────────────────────────────

function TriggerAnalysisForm() {
  const [daysBack, setDaysBack] = useState(7);
  const { submit, submitting, result } = usePostJson(`${P2A_BASE}/analyze/patterns`);

  const handleSubmit = (e) => {
    e.preventDefault();
    submit({ days_back: parseInt(daysBack) });
  };

  return (
    <CollapsibleForm title="Trigger Analysis" onSubmit={handleSubmit}>
      <Field label="Days back">
        <input
          type="number"
          value={daysBack}
          onChange={e => setDaysBack(e.target.value)}
          min={1}
          max={90}
          required
          className="px-2.5 py-1.5 border border-gray-300 rounded-md text-sm w-24"
        />
      </Field>
      <SubmitButton submitting={submitting} busyLabel="Starting…">Run ETL</SubmitButton>
      {result && (
        <ResultBanner ok={result.ok}>
          {result.ok
            ? `Job started — job_id: ${result.data.job_id}`
            : `Error: ${result.data.error || 'Unknown error'}`}
        </ResultBanner>
      )}
    </CollapsibleForm>
  );
}

// ── Pattern card ──────────────────────────────────────────────────────────────

function PatternCard({ pattern }) {
  const data = pattern.data || {};

  const renderData = () => {
    if (pattern.pattern_type === 'occupancy_schedule') {
      const schedule = data.schedule || {};
      const DAY = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
      return (
        <div className="mt-2 space-y-0.5">
          {Object.entries(schedule).map(([day, hours]) => (
            <div key={day} className="text-xs text-gray-600">
              <span className="font-medium w-10 inline-block">{DAY[day] || `Day ${day}`}:</span>{' '}
              {Array.isArray(hours) ? hours.map(h => `${h}:00`).join(', ') : String(hours)}
            </div>
          ))}
        </div>
      );
    }
    if (pattern.pattern_type === 'temperature_trend') {
      return (
        <div className="mt-2 text-xs text-gray-600 space-y-0.5">
          {data.trend        && <div><span className="font-medium">Trend:</span> {data.trend}</div>}
          {data.delta_celsius != null && <div><span className="font-medium">Δ temp:</span> {data.delta_celsius > 0 ? '+' : ''}{data.delta_celsius}°C</div>}
          {data.mean_start   != null && <div><span className="font-medium">Start avg:</span> {data.mean_start}°C → <b>{data.mean_end}°C</b></div>}
          {data.slope        != null && <div><span className="font-medium">Slope:</span> {data.slope}</div>}
          {data.r_squared    != null && <div><span className="font-medium">R²:</span> {data.r_squared}</div>}
        </div>
      );
    }
    return (
      <pre className="mt-2 text-xs text-gray-600 bg-gray-50 rounded p-2 overflow-x-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    );
  };

  return (
    <div className="border border-gray-200 rounded-xl p-4 bg-white">
      <div className="flex justify-between items-start mb-1">
        <span className="text-sm font-semibold text-gray-800">{pattern.pattern_type}</span>
        <span className="text-xs text-gray-400">
          {pattern.period_start?.slice(0, 10)} → {pattern.period_end?.slice(0, 10)}
        </span>
      </div>
      {renderData()}
    </div>
  );
}

// ── Anomaly row ───────────────────────────────────────────────────────────────

function AnomalyRow({ anomaly }) {
  const data = anomaly.data || {};

  const renderData = () => {
    if (anomaly.anomaly_type === 'temperature_spike') {
      return (
        <span className="text-xs text-gray-500">
          value: <b>{data.value}</b> — mean: {data.mean} — σ: {data.std_dev}
        </span>
      );
    }
    return <span className="text-xs text-gray-500">{JSON.stringify(data)}</span>;
  };

  return (
    <tr className="border-t border-gray-100">
      <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">
        {new Date(anomaly.detected_at).toLocaleString()}
      </td>
      <td className="px-3 py-2 text-xs font-medium text-gray-700">{anomaly.anomaly_type}</td>
      <td className="px-3 py-2">
        <Badge color={SEVERITY_BADGE[anomaly.severity] || DEFAULT_BADGE}>{anomaly.severity}</Badge>
      </td>
      <td className="px-3 py-2">{renderData()}</td>
    </tr>
  );
}

// ── Room insights ─────────────────────────────────────────────────────────────

function RoomInsights({ roomId }) {
  const { data, loading, error } = useFetch(`${P2A_BASE}/insights/room/${roomId}`);

  if (loading) return <div className="p-4 text-gray-500 text-sm">Loading insights...</div>;
  if (error)   return <div className="p-4 text-red-600 text-sm">Could not load insights: {error}</div>;

  const patterns  = data?.patterns  || [];
  const anomalies = data?.anomalies || [];

  return (
    <div className="mt-6 space-y-6">
      {/* Patterns */}
      <div>
        <h3 className="text-base font-semibold text-gray-800 mb-3">
          Patterns <span className="text-gray-400 font-normal text-sm">({patterns.length})</span>
        </h3>
        {patterns.length === 0 ? (
          <p className="text-sm text-gray-400">No patterns detected for this room.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {patterns.map((p, i) => <PatternCard key={i} pattern={p} />)}
          </div>
        )}
      </div>

      {/* Anomalies */}
      <div>
        <h3 className="text-base font-semibold text-gray-800 mb-3">
          Anomalies <span className="text-gray-400 font-normal text-sm">({anomalies.length})</span>
        </h3>
        {anomalies.length === 0 ? (
          <p className="text-sm text-gray-400">No anomalies detected for this room.</p>
        ) : (
          <div className="overflow-x-auto border border-gray-200 rounded-xl">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-100 text-xs text-gray-500 uppercase">
                  <th className="px-3 py-2 text-left">Detected at</th>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Severity</th>
                  <th className="px-3 py-2 text-left">Details</th>
                </tr>
              </thead>
              <tbody>
                {anomalies.map((a, i) => <AnomalyRow key={i} anomaly={a} />)}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main dashboard ────────────────────────────────────────────────────────────

function BehaviorDashboard() {
  const [selectedRoom, setSelectedRoom] = useState(null);
  const { data: roomsData } = useFetch(`${API_BASE}/rooms`);
  const rooms = Array.isArray(roomsData) ? roomsData : [];

  if (!P2A_BASE) return <NotDeployed />;

  return (
    <div className="px-6 py-6 font-sans max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 m-0">Behavior Pattern Analyzer</h1>
        <p className="mt-1 text-sm text-gray-500">AWS Step Functions + Aurora Serverless — on-demand ETL</p>
      </div>

      <TriggerAnalysisForm />

      {/* Room selector */}
      <div className="mb-6">
        <h2 className="text-base font-semibold text-gray-800 mb-3">Select a room</h2>
        {rooms.length === 0 ? (
          <p className="text-sm text-gray-400">No rooms found — make sure project 1b is running.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {rooms.map(room => (
              <button
                key={room.room_id}
                onClick={() => setSelectedRoom(selectedRoom === room.room_id ? null : room.room_id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium border cursor-pointer transition-colors
                  ${selectedRoom === room.room_id
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'
                  }`}
              >
                {room.name || room.room_id}
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedRoom && <RoomInsights roomId={selectedRoom} />}
    </div>
  );
}

export default BehaviorDashboard;
