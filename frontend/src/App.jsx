import { useState } from 'react';
import RoomDashboard from './pages/RoomDashboard';
import ProjectTabs from './components/ProjectTabs';

function ComingSoon({ title, description }) {
  return (
    <div style={{ padding: '48px 24px', textAlign: 'center', color: '#6b7280', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ fontSize: '2rem', marginBottom: '12px' }}>🚧</div>
      <h2 style={{ margin: '0 0 8px', color: '#374151' }}>{title}</h2>
      <p style={{ margin: 0, fontSize: '0.875rem' }}>{description}</p>
    </div>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState('room');

  return (
    <div className="App">
      <ProjectTabs active={activeTab} onChange={setActiveTab} />
      {activeTab === 'room' && <RoomDashboard />}
      {activeTab === 'behavior' && (
        <ComingSoon
          title="Behavior Pattern Analyzer"
          description="ETL pipeline for detecting behavioral patterns — planned next phase"
        />
      )}
      {activeTab === 'gateway' && (
        <ComingSoon
          title="IoT Device Gateway"
          description="Secure device management with auth and rate limiting — planned next phase"
        />
      )}
    </div>
  );
}

export default App;
