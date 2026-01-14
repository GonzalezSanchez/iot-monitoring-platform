
import React, { useEffect, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_ENDPOINT || 'https://<API-ID>.execute-api.eu-west-1.amazonaws.com/dev';


function RoomDashboard() {
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [roomDetail, setRoomDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);


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

  // Fetch room detail when selectedRoom changes
  useEffect(() => {
    if (!selectedRoom) {
      setRoomDetail(null);
      setDetailError(null);
      return;
    }
    setDetailLoading(true);
    setDetailError(null);
    fetch(`${API_BASE}/rooms/${selectedRoom}`)
      .then(res => {
        if (!res.ok) throw new Error('Fout bij ophalen details');
        return res.json();
      })
      .then(data => {
        setRoomDetail(data);
        setDetailLoading(false);
      })
      .catch(err => {
        setDetailError('Kan kamer detail niet ophalen');
        setDetailLoading(false);
      });
  }, [selectedRoom]);


  if (loading) return <div>Loading...</div>;
  if (error) return <div>{error}</div>;


  return (
    <div>
      <h1>Smart Room Monitor Dashboard</h1>
      <ul>
        {rooms.map(room => (
          <li key={room.room_id}>
            <button
              style={{
                background: 'none',
                border: 'none',
                color: '#2563eb',
                textDecoration: 'underline',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '1em',
                padding: 0,
              }}
              onClick={() => setSelectedRoom(room.room_id)}
            >
              {room.room_id}
            </button>
            {' '} - Occupancy: {room.occupancy ? 'Ja' : 'Nee'}
          </li>
        ))}
      </ul>

      {selectedRoom && (
        <div style={{marginTop: '2em', padding: '1em', border: '1px solid #eee', borderRadius: '8px', background: '#fafbfc'}}>
          <h2>Details voor kamer: {selectedRoom}</h2>
          {detailLoading && <div>Details laden...</div>}
          {detailError && <div style={{color: 'red'}}>{detailError}</div>}
          {roomDetail && (
            <pre style={{textAlign: 'left', background: '#f3f4f6', padding: '1em', borderRadius: '6px'}}>
              {JSON.stringify(roomDetail, null, 2)}
            </pre>
          )}
          <button onClick={() => setSelectedRoom(null)} style={{marginTop: '1em'}}>Sluiten</button>
        </div>
      )}
    </div>
  );
}

export default RoomDashboard;
