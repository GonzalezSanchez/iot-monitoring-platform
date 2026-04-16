import { useState } from 'react';
import RoomDashboard from './pages/RoomDashboard';
import ProjectTabs from './components/ProjectTabs';

function ComingSoon({ title, description }) {
  return (
    <div className="py-12 px-6 text-center font-sans">
      <div className="text-4xl mb-3">🚧</div>
      <h2 className="text-xl font-semibold text-gray-700 mb-2">{title}</h2>
      <p className="text-sm text-gray-500">{description}</p>
    </div>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState('room');

  return (
    <div>
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
