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
  const [activeTab, setActiveTab] = useState('room-fastapi');

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4">
        <div className="pt-12 pb-8 text-center border-b border-gray-200">
          <h1 className="text-4xl font-bold text-gray-800">
            IoT Monitoring Platform
          </h1>
          <p className="text-lg text-gray-600 mt-2">
            Multi-architecture sensor data analytics
          </p>
          <div className="mt-4 flex justify-center gap-6 text-sm">
            <span className="text-gray-700">
              <strong>Álvaro González Sánchez</strong>
            </span>
            <a
              href="https://www.linkedin.com/in/gonzalezsanchez/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 underline"
            >
              LinkedIn
            </a>
          </div>
        </div>
        <ProjectTabs active={activeTab} onChange={setActiveTab} />
      </div>
      {(activeTab === 'room-lambda' || activeTab === 'room-fastapi') && <RoomDashboard />}
      {(activeTab === 'behavior-aws' || activeTab === 'behavior-spark') && (
        activeTab === 'behavior-aws' ? (
          <BehaviorDashboard />
        ) : (
          <ComingSoon
            title="Behavior Analyzer — Spark"
            description="Power BI dashboard with data pipeline results"
          />
        )
      )}
      {activeTab === 'llm' && (
        <ComingSoon
          title="AI Assistant"
          description="Natural language queries over live sensor data — planned for project 4"
        />
      )}
    </div>
  );
}

export default App;
