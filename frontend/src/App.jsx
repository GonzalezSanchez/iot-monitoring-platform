import React, { useState } from 'react';
import RoomDashboard from './pages/RoomDashboard';
import ProjectTabs from './components/ProjectTabs';

function App() {
  const [activeTab, setActiveTab] = useState('room');

  return (
    <div className="App">
      <ProjectTabs active={activeTab} onChange={setActiveTab} />
      {activeTab === 'room' && <RoomDashboard />}
      {/* Hier kun je later BehaviorDashboard en GatewayDashboard toevoegen */}
    </div>
  );
}

export default App;
