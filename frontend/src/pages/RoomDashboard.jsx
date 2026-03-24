import { useEffect, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_ENDPOINT || '';

const STATUS_COLOR = {
  normal: '#16a34a',
  active: '#16a34a',
  warning: '#d97706',
  alert: '#dc2626',
  offline: '#6b7280',
};

const STATUS_BG = {
  normal: '#f0fdf4',
  active: '#f0fdf4',
  warning: '#fffbeb',
  alert: '#fef2f2',
  offline: '#f9fafb',
};

function StatusBadge({ status }) {
  return (
    <span style={{
      background: STATUS_BG[status] || '#f3f4f6',
      color: STATUS_COLOR[status] || '#374151',
      border: `1px solid ${STATUS_COLOR[status] || '#d1d5db'}`,
      borderRadius: '9999px',
      padding: '2px 10px',
      fontSize: '0.75rem',
      fontWeight: 600,
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
    }}>
      {status}
    </span>
  );
}

function RoomCard({ room, selected, onClick }) {
  const state = room.current_state || {};
  const isSelected = selected === room.room_id;

  return (
    <div
      onClick={onClick}
      style={{
        border: `2px solid ${isSelected ? '#2563eb' : STATUS_COLOR[room.status] || '#d1d5db'}`,
        borderRadius: '10px',
        padding: '16px',
        background: isSelected ? '#eff6ff' : (STATUS_BG[room.status] || '#fff'),
        cursor: 'pointer',
        minWidth: '180px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <strong style={{ fontSize: '1rem' }}>{room.name || room.room_id}</strong>
        <StatusBadge status={room.status} />
      </div>
      <div style={{ fontSize: '0.875rem', color: '#374151', lineHeight: '1.8' }}>
        {state.temperature != null && <div>Temperature: <b>{state.temperature} °C</b></div>}
        {state.humidity != null && <div>Humidity: <b>{state.humidity} %</b></div>}
        {state.occupancy != null && <div>Occupancy: <b>{state.occupancy} people</b></div>}
        {state.motion != null && <div>Motion: <b>{state.motion ? 'Yes' : 'No'}</b></div>}
        {Object.keys(state).length === 0 && <div style={{ color: '#9ca3af' }}>No sensor data yet</div>}
      </div>
      <div style={{ marginTop: '8px', fontSize: '0.75rem', color: '#6b7280' }}>
        {room.alert_count_24h > 0 && <span style={{ color: '#dc2626' }}>⚠ {room.alert_count_24h} alert(s) today</span>}
      </div>
    </div>
  );
}

function EventRow({ event }) {
  return (
    <tr>
      <td style={{ padding: '6px 12px', fontSize: '0.8rem', color: '#6b7280', whiteSpace: 'nowrap' }}>
        {new Date(event.timestamp).toLocaleTimeString()}
      </td>
      <td style={{ padding: '6px 12px', fontSize: '0.8rem' }}>{event.sensor_type}</td>
      <td style={{ padding: '6px 12px', fontSize: '0.8rem', fontWeight: 600 }}>
        {event.value} {event.unit}
      </td>
      <td style={{ padding: '6px 12px' }}>
        <StatusBadge status={event.status} />
      </td>
    </tr>
  );
}

const SENSOR_DEFAULTS = {
  temperature: 22.5,
  humidity: 55,
  occupancy: 5,
  motion: 1,
};

function SendEventForm({ onEventSent }) {
  const [roomId, setRoomId] = useState('room-1');
  const [sensorType, setSensorType] = useState('temperature');
  const [value, setValue] = useState(SENSOR_DEFAULTS.temperature);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [open, setOpen] = useState(false);

  const handleSensorChange = (type) => {
    setSensorType(type);
    setValue(SENSOR_DEFAULTS[type]);
    setResult(null);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setSubmitting(true);
    setResult(null);
    fetch(`${API_BASE}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        room_id: roomId,
        sensor_type: sensorType,
        value: parseFloat(value),
        timestamp: new Date().toISOString(),
      }),
    })
      .then(res => res.json().then(data => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        setResult({ ok, data });
        setSubmitting(false);
        if (ok) onEventSent();
      })
      .catch(err => {
        setResult({ ok: false, data: { detail: err.message } });
        setSubmitting(false);
      });
  };

  return (
    <div style={{ marginBottom: '24px', border: '1px solid #e5e7eb', borderRadius: '10px', overflow: 'hidden' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ width: '100%', padding: '12px 16px', background: '#f9fafb', border: 'none', borderBottom: open ? '1px solid #e5e7eb' : 'none', cursor: 'pointer', textAlign: 'left', fontWeight: 600, fontSize: '0.9rem', color: '#374151' }}
      >
        {open ? '▾' : '▸'} Send Sensor Event
      </button>
      {open && (
        <form onSubmit={handleSubmit} style={{ padding: '16px', display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', color: '#6b7280', marginBottom: '4px' }}>Room ID</label>
            <input
              value={roomId}
              onChange={e => setRoomId(e.target.value)}
              required
              style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.875rem', width: '120px' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', color: '#6b7280', marginBottom: '4px' }}>Sensor Type</label>
            <select
              value={sensorType}
              onChange={e => handleSensorChange(e.target.value)}
              style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.875rem' }}
            >
              <option value="temperature">temperature</option>
              <option value="humidity">humidity</option>
              <option value="occupancy">occupancy</option>
              <option value="motion">motion</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', color: '#6b7280', marginBottom: '4px' }}>Value</label>
            <input
              type="number"
              value={value}
              onChange={e => setValue(e.target.value)}
              required
              step="0.1"
              style={{ padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.875rem', width: '80px' }}
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            style={{ padding: '7px 18px', background: submitting ? '#93c5fd' : '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 600, fontSize: '0.875rem', cursor: submitting ? 'not-allowed' : 'pointer' }}
          >
            {submitting ? 'Sending…' : 'Send'}
          </button>
          {result && (
            <div style={{ width: '100%', marginTop: '4px', padding: '8px 12px', background: result.ok ? '#f0fdf4' : '#fef2f2', border: `1px solid ${result.ok ? '#86efac' : '#fca5a5'}`, borderRadius: '6px', fontSize: '0.8rem', color: result.ok ? '#15803d' : '#dc2626' }}>
              {result.ok
                ? `Status: ${result.data.status} — event saved for ${result.data.room_id}`
                : `Error: ${result.data.detail || 'Unknown error'}`}
            </div>
          )}
        </form>
      )}
    </div>
  );
}

function RoomDashboard() {
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [events, setEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(false);

  const fetchRooms = () => {
    fetch(`${API_BASE}/rooms`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setRooms(Array.isArray(data) ? data : []);
        setLoading(false);
        setError(null);
      })
      .catch(err => {
        setError(`Could not reach API: ${err.message}`);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchRooms();
    const interval = setInterval(fetchRooms, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!selectedRoom) {
      setEvents([]);
      return;
    }

    const fetchEvents = () => {
      setEventsLoading(true);
      fetch(`${API_BASE}/rooms/${selectedRoom}/events`)
        .then(res => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then(data => {
          setEvents(Array.isArray(data) ? data.slice().reverse() : []);
          setEventsLoading(false);
        })
        .catch(() => {
          setEvents([]);
          setEventsLoading(false);
        });
    };

    fetchEvents();
    const interval = setInterval(fetchEvents, 30000);
    return () => clearInterval(interval);
  }, [selectedRoom]);

  if (loading) return <div style={{ padding: '2rem', color: '#6b7280' }}>Loading rooms...</div>;

  if (error) return (
    <div style={{ padding: '2rem' }}>
      <p style={{ color: '#dc2626' }}>{error}</p>
      <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>
        Make sure the FastAPI backend is running at <code>{API_BASE}</code>
      </p>
    </div>
  );

  return (
    <div style={{ padding: '24px', fontFamily: 'system-ui, sans-serif', maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Smart Room Monitor</h1>
          <p style={{ margin: '4px 0 0', color: '#6b7280', fontSize: '0.875rem' }}>
            FastAPI + DynamoDB — auto-refreshes every 30s
          </p>
        </div>
        <span style={{ fontSize: '0.875rem', color: '#6b7280' }}>
          {rooms.length} room{rooms.length !== 1 ? 's' : ''}
        </span>
      </div>

      <SendEventForm onEventSent={fetchRooms} />

      {rooms.length === 0 ? (
        <div style={{ padding: '2rem', background: '#f9fafb', borderRadius: '8px', textAlign: 'center', color: '#6b7280' }}>
          No rooms yet — use the form above to send a sensor event and create one.
        </div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
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
        <div style={{ marginTop: '32px', border: '1px solid #e5e7eb', borderRadius: '10px', overflow: 'hidden' }}>
          <div style={{ padding: '16px', background: '#f9fafb', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ margin: 0, fontSize: '1rem' }}>Events — {selectedRoom}</h2>
            <button
              onClick={() => setSelectedRoom(null)}
              style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#6b7280', fontSize: '1.2rem' }}
            >
              ✕
            </button>
          </div>

          {eventsLoading ? (
            <div style={{ padding: '16px', color: '#6b7280' }}>Loading events...</div>
          ) : events.length === 0 ? (
            <div style={{ padding: '16px', color: '#6b7280' }}>No events for this room.</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#f3f4f6', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>
                    <th style={{ padding: '8px 12px', textAlign: 'left' }}>Time</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left' }}>Sensor</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left' }}>Value</th>
                    <th style={{ padding: '8px 12px', textAlign: 'left' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((event, i) => (
                    <tr key={i} style={{ borderTop: '1px solid #f3f4f6' }}>
                      <EventRow event={event} />
                    </tr>
                  ))}
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
