import { useState } from 'react';
import RoomDashboard from './pages/RoomDashboard';
import BehaviorDashboard from './pages/BehaviorDashboard';
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
      {activeTab === 'behavior' && <BehaviorDashboard />}
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
