import { useState } from 'react';
import useFetch from '../hooks/useFetch';
import usePostJson from '../hooks/usePostJson';
import Badge from '../components/Badge';
import CollapsibleForm, { Field, SubmitButton, ResultBanner } from '../components/CollapsibleForm';

const API_ENDPOINTS = {
  'room-fastapi': import.meta.env.VITE_API_ENDPOINT || 'http://localhost:8000',
  'room-lambda': import.meta.env.VITE_LAMBDA_API_ENDPOINT || 'https://6c20a9bn61.execute-api.eu-central-1.amazonaws.com/dev',
};

// The two backends expose room events differently:
// - FastAPI has GET /rooms/{id}/events, sorted oldest-first
// - the Lambda API has no /events route; GET /rooms/{id} includes
//   recent_events, sorted newest-first
const EVENT_SOURCES = {
  'room-fastapi': {
    url: (base, roomId) => `${base}/rooms/${encodeURIComponent(roomId)}/events`,
    extract: (data) => (Array.isArray(data) ? [...data].reverse() : []),
  },
  'room-lambda': {
    url: (base, roomId) => `${base}/rooms/${encodeURIComponent(roomId)}`,
    extract: (data) => data?.recent_events || [],
  },
};

const STATUS_STYLES = {
  normal:  { badge: 'text-green-700 bg-green-50 border border-green-600', card: 'border-green-600 bg-green-50' },
  active:  { badge: 'text-green-700 bg-green-50 border border-green-600', card: 'border-green-600 bg-green-50' },
  warning: { badge: 'text-amber-700 bg-amber-50 border border-amber-600', card: 'border-amber-600 bg-amber-50' },
  alert:   { badge: 'text-red-700 bg-red-50 border border-red-600',       card: 'border-red-600 bg-red-50' },
  offline: { badge: 'text-gray-500 bg-gray-50 border border-gray-400',    card: 'border-gray-400 bg-gray-50' },
};
const DEFAULT_STYLE = { badge: 'text-gray-700 bg-gray-100 border border-gray-400', card: 'border-gray-300 bg-white' };

function StatusBadge({ status }) {
  const { badge } = STATUS_STYLES[status] || DEFAULT_STYLE;
  return <Badge color={badge}>{status}</Badge>;
}

function RoomCard({ room, selected, onClick }) {
  const state = room.current_state || {};
  const isSelected = selected === room.room_id;
  const card = isSelected
    ? 'border-blue-600 bg-blue-50'
    : (STATUS_STYLES[room.status] || DEFAULT_STYLE).card;

  return (
    <div onClick={onClick} className={`${card} border-2 rounded-xl p-4 cursor-pointer min-w-[180px]`}>
      <div className="flex justify-between items-center gap-2 mb-2.5">
        <strong className="text-base">{room.name || room.room_id}</strong>
        <span className="shrink-0"><StatusBadge status={room.status} /></span>
      </div>
      <div className="text-sm text-gray-700 leading-loose">
        {state.temperature != null && <div>Temperature: <b>{state.temperature} °C</b></div>}
        {state.humidity    != null && <div>Humidity: <b>{state.humidity} %</b></div>}
        {state.occupancy   != null && <div>Occupancy: <b>{state.occupancy} people</b></div>}
        {state.motion      != null && <div>Motion: <b>{state.motion ? 'Yes' : 'No'}</b></div>}
        {Object.keys(state).length === 0 && <div className="text-gray-400">No sensor data yet</div>}
      </div>
      {room.alert_count_24h > 0 && (
        <div className="mt-2 text-xs text-red-600">⚠ {room.alert_count_24h} alert(s) today</div>
      )}
    </div>
  );
}

function EventRow({ event }) {
  return (
    <tr className="border-t border-gray-100">
      <td className="px-3 py-1.5 text-xs text-gray-500 whitespace-nowrap">
        {new Date(event.timestamp).toLocaleTimeString()}
      </td>
      <td className="px-3 py-1.5 text-xs">{event.sensor_type}</td>
      <td className="px-3 py-1.5 text-xs font-semibold">{event.value} {event.unit}</td>
      <td className="px-3 py-1.5"><StatusBadge status={event.status} /></td>
    </tr>
  );
}

const SENSOR_DEFAULTS = { temperature: 22.5, humidity: 55, occupancy: 5, motion: 1 };

function SendEventForm({ onEventSent, apiBase }) {
  const [roomId, setRoomId]         = useState('room-1');
  const [sensorType, setSensorType] = useState('temperature');
  const [value, setValue]           = useState(SENSOR_DEFAULTS.temperature);
  const { submit, submitting, result, setResult } = usePostJson(`${apiBase}/events`);

  const handleSensorChange = (type) => {
    setSensorType(type);
    setValue(SENSOR_DEFAULTS[type]);
    setResult(null);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    submit({
      room_id: roomId,
      sensor_type: sensorType,
      value: parseFloat(value),
      timestamp: new Date().toISOString(),
    }, onEventSent);
  };

  return (
    <CollapsibleForm title="Send Sensor Event" onSubmit={handleSubmit}>
      <Field label="Room ID">
        <input
          value={roomId}
          onChange={e => setRoomId(e.target.value)}
          required
          className="px-2.5 py-1.5 border border-gray-300 rounded-md text-sm w-28"
        />
      </Field>
      <Field label="Sensor Type">
        <select
          value={sensorType}
          onChange={e => handleSensorChange(e.target.value)}
          className="px-2.5 py-1.5 border border-gray-300 rounded-md text-sm"
        >
          {Object.keys(SENSOR_DEFAULTS).map(type => (
            <option key={type} value={type}>{type}</option>
          ))}
        </select>
      </Field>
      <Field label="Value">
        <input
          type="number"
          value={value}
          onChange={e => setValue(e.target.value)}
          required
          step="0.1"
          className="px-2.5 py-1.5 border border-gray-300 rounded-md text-sm w-20"
        />
      </Field>
      <SubmitButton submitting={submitting} busyLabel="Sending…">Send</SubmitButton>
      {result && (
        <ResultBanner ok={result.ok}>
          {result.ok
            ? `Status: ${result.data.status ?? result.data.event_status} — event saved for ${result.data.room_id ?? roomId}`
            : `Error: ${result.data.detail || result.data.error || 'Unknown error'}`}
        </ResultBanner>
      )}
    </CollapsibleForm>
  );
}

function RoomDashboard({ tab = 'room-fastapi' }) {
  const API_BASE = API_ENDPOINTS[tab];
  const [selectedRoom, setSelectedRoom] = useState(null);

  const { data: roomsData, loading, error, refetch } = useFetch(`${API_BASE}/rooms`, { refreshMs: 30000 });
  const rooms = Array.isArray(roomsData) ? roomsData : (roomsData?.rooms || []);

  const eventSource = EVENT_SOURCES[tab];
  const { data: eventsData, loading: eventsLoading } = useFetch(
    selectedRoom && eventSource.url(API_BASE, selectedRoom),
    { refreshMs: 30000 }
  );
  const events = eventSource.extract(eventsData);

  if (loading) return <div className="p-8 text-gray-500">Loading rooms...</div>;

  if (error) return (
    <div className="p-8">
      <p className="text-red-600">Could not reach API: {error}</p>
      <p className="text-sm text-gray-500">Make sure the backend is running at <code>{API_BASE}</code></p>
    </div>
  );

  return (
    <div className="px-6 py-6 font-sans max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 m-0">Smart Room Monitor</h1>
          <p className="mt-1 text-sm text-gray-500">{tab === 'room-lambda' ? 'AWS Lambda + API Gateway' : 'FastAPI + DynamoDB'} — auto-refreshes every 30s</p>
        </div>
        <span className="text-sm text-gray-500">{rooms.length} room{rooms.length !== 1 ? 's' : ''}</span>
      </div>

      <SendEventForm onEventSent={refetch} apiBase={API_BASE} />

      {rooms.length === 0 ? (
        <div className="p-8 bg-gray-50 rounded-lg text-center text-gray-500">
          No rooms yet — use the form above to send a sensor event and create one.
        </div>
      ) : (
        <div className="flex flex-wrap gap-4">
          {rooms.map(room => (
            <RoomCard
              key={room.room_id}
              room={room}
              selected={selectedRoom}
              onClick={() => setSelectedRoom(selectedRoom === room.room_id ? null : room.room_id)}
            />
          ))}
        </div>
      )}

      {selectedRoom && (
        <div className="mt-8 border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-4 py-4 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
            <h2 className="text-base font-semibold text-gray-800 m-0">Events — {selectedRoom}</h2>
            <button onClick={() => setSelectedRoom(null)} className="border-none bg-transparent cursor-pointer text-gray-500 text-lg">
              ✕
            </button>
          </div>
          {eventsLoading ? (
            <div className="p-4 text-gray-500">Loading events...</div>
          ) : events.length === 0 ? (
            <div className="p-4 text-gray-500">No events for this room.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-gray-100 text-xs text-gray-500 uppercase">
                    <th className="px-3 py-2 text-left">Time</th>
                    <th className="px-3 py-2 text-left">Sensor</th>
                    <th className="px-3 py-2 text-left">Value</th>
                    <th className="px-3 py-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((event, i) => <EventRow key={i} event={event} />)}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default RoomDashboard;
