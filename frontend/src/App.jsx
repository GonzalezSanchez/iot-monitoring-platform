import { useState } from 'react';
import RoomDashboard from './pages/RoomDashboard';
import BehaviorDashboard from './pages/BehaviorDashboard';
import LakehouseDashboard from './pages/LakehouseDashboard';
import PowerBIDashboard from './pages/PowerBIDashboard';
import AiDashboard from './pages/AiDashboard';
import ProjectTabs from './components/ProjectTabs';

function App() {
  const [activeTab, setActiveTab] = useState(
    () => localStorage.getItem('activeTab') || 'room-fastapi'
  );

  const handleTabChange = (tab) => {
    localStorage.setItem('activeTab', tab);
    setActiveTab(tab);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">

      {/* Header */}
      <header className="bg-blue-50 border-b border-blue-100 px-6 py-4 flex flex-col items-center shrink-0">
        <h1 className="text-3xl font-bold text-gray-800">IoT Monitoring Platform</h1>
        <p className="text-sm text-gray-500 mt-0.5">Multi-architecture sensor data analytics</p>
        <div className="flex items-center gap-3 mt-2 text-sm">
          <span className="text-gray-700 font-medium">Álvaro González Sánchez</span>
          <span className="text-gray-300">|</span>
          <a
            href="https://www.linkedin.com/in/gonzalezsanchez/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 underline"
          >
            LinkedIn
          </a>
        </div>
      </header>

      {/* Sidebar + content */}
      <div className="flex flex-1">
        <ProjectTabs active={activeTab} onChange={handleTabChange} />

        <main className="flex-1 overflow-auto">
          {(activeTab === 'room-lambda' || activeTab === 'room-fastapi') && (
            // key forces a remount when switching between the two room tabs,
            // so fetch state and room selection reset to the new API
            <RoomDashboard key={activeTab} tab={activeTab} />
          )}
          {activeTab === 'behavior-aws' && <BehaviorDashboard />}
          {activeTab === 'behavior-spark' && <PowerBIDashboard />}
          {activeTab === 'behavior-lakehouse' && <LakehouseDashboard />}
          {activeTab === 'llm' && <AiDashboard />}
        </main>
      </div>

    </div>
  );
}

export default App;
