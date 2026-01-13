import React, { useEffect, useState } from 'react';

const API_BASE = process.env.REACT_APP_API_ENDPOINT || 'https://<API-ID>.execute-api.eu-west-1.amazonaws.com/dev';

function RoomDashboard() {
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/rooms`)
      .then(res => res.json())
      .then(data => {
        setRooms(data.rooms || []);
        setLoading(false);
      })
      .catch(err => {
        setError('Kan kamers niet ophalen');
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>{error}</div>;

  return (
    <div>
      <h1>Smart Room Monitor Dashboard</h1>
      <ul>
        {rooms.map(room => (
          <li key={room.room_id}>
            <strong>{room.room_id}</strong> - Occupancy: {room.occupancy ? 'Ja' : 'Nee'}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default RoomDashboard;
