/**
 * PORTFOLIO DASHBOARD - Mockup Code
 * 
 * React Dashboard voor Backend Portfolio
 * 3 Projecten: Smart Room Monitor, Behavior Pattern Analyzer, IoT Device Gateway
 * 
 * Gebaseerd op Conference Expense Planner structuur (Redux Toolkit + Tabs)
 */

import React, { useState, useEffect } from 'react';
import './Dashboard.css';

// Mock API calls - Later vervangen door echte AWS endpoints
const mockAPI = {
  smartRoomMonitor: {
    getRooms: () => Promise.resolve([
      { id: 'room-a', name: 'Room A', status: 'active', temp: 22, motion: true, lastUpdate: new Date() },
      { id: 'room-b', name: 'Room B', status: 'warning', temp: 28, motion: false, lastUpdate: new Date() },
      { id: 'room-c', name: 'Room C', status: 'alert', temp: 0, motion: false, lastUpdate: new Date(Date.now() - 7200000) }
    ]),
    getActivity: () => Promise.resolve([
      { hour: '00:00', count: 2 },
      { hour: '06:00', count: 8 },
      { hour: '09:00', count: 45 },
      { hour: '12:00', count: 38 },
      { hour: '15:00', count: 42 },
      { hour: '18:00', count: 25 },
      { hour: '21:00', count: 5 }
    ])
  },
  behaviorAnalyzer: {
    getPatterns: () => Promise.resolve([
      { name: 'Morning Activity', frequency: 98, anomalies: 0 },
      { name: 'Lunch Break', frequency: 95, anomalies: 2 },
      { name: 'Evening Shutdown', frequency: 88, anomalies: 5 }
    ]),
    getStats: () => Promise.resolve({
      processed: 15432,
      anomalies: 7,
      confidence: 94,
      lastRun: new Date(Date.now() - 300000)
    })
  },
  iotGateway: {
    getDevices: () => Promise.resolve([
      { id: 'dev-001', status: 'ok', lastHeartbeat: 2, ratePerMin: 120 },
      { id: 'dev-002', status: 'ok', lastHeartbeat: 5, ratePerMin: 85 },
      { id: 'dev-003', status: 'down', lastHeartbeat: 10800, ratePerMin: 0 },
      { id: 'dev-004', status: 'slow', lastHeartbeat: 45, ratePerMin: 12 }
    ]),
    getEvents: () => Promise.resolve([
      { time: '13:24:15', deviceId: 'dev-001', event: 'Heartbeat received' },
      { time: '13:24:12', deviceId: 'dev-002', event: 'Data upload successful' },
      { time: '13:24:08', deviceId: 'dev-004', event: 'Rate limit warning' }
    ])
  }
};

// Main Dashboard Component
const PortfolioDashboard = () => {
  const [activeTab, setActiveTab] = useState('smart-room');

  return (
    <div className="portfolio-dashboard">
      <Header />
      <TabNavigation activeTab={activeTab} setActiveTab={setActiveTab} />
      <div className="content">
        {activeTab === 'smart-room' && <SmartRoomMonitor />}
        {activeTab === 'behavior' && <BehaviorAnalyzer />}
        {activeTab === 'iot-gateway' && <IoTGateway />}
      </div>
    </div>
  );
};

// Header Component
const Header = () => (
  <header className="dashboard-header">
    <h1>Backend Developer Portfolio</h1>
    <p className="subtitle">Álvaro González | AWS • Python • Docker • REST APIs</p>
  </header>
);

// Tab Navigation Component
const TabNavigation = ({ activeTab, setActiveTab }) => {
  const tabs = [
    { id: 'smart-room', label: '📊 Smart Room Monitor', icon: '🏢' },
    { id: 'behavior', label: '🧠 Behavior Analyzer', icon: '📈' },
    { id: 'iot-gateway', label: '🔐 IoT Gateway', icon: '📱' }
  ];

  return (
    <nav className="tab-navigation">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => setActiveTab(tab.id)}
        >
          <span className="tab-icon">{tab.icon}</span>
          {tab.label}
        </button>
      ))}
    </nav>
  );
};

// PROJECT 1: Smart Room Monitor
const SmartRoomMonitor = () => {
  const [rooms, setRooms] = useState([]);
  const [activity, setActivity] = useState([]);

  useEffect(() => {
    mockAPI.smartRoomMonitor.getRooms().then(setRooms);
    mockAPI.smartRoomMonitor.getActivity().then(setActivity);
  }, []);

  return (
    <div className="project-container">
      <ProjectHeader
        title="Smart Room Monitor"
        description="Real-time monitoring van conferentiezalen met IoT sensoren"
        tech={['AWS Lambda', 'DynamoDB', 'API Gateway', 'CloudWatch', 'Docker', 'Python']}
      />

      {/* Room Status Cards */}
      <section className="room-cards">
        <h3>Room Status</h3>
        <div className="cards-grid">
          {rooms.map(room => (
            <RoomCard key={room.id} room={room} />
          ))}
        </div>
      </section>

      {/* Activity Graph */}
      <section className="activity-section">
        <h3>Activity Graph (laatste 24u)</h3>
        <ActivityChart data={activity} />
      </section>

      <ProjectFooter
        githubUrl="https://github.com/yourusername/smart-room-monitor"
        apiDocsUrl="#"
        architectureUrl="#"
      />
    </div>
  );
};

// Room Card Component
const RoomCard = ({ room }) => {
  const getStatusIcon = (status) => {
    switch(status) {
      case 'active': return '🟢';
      case 'warning': return '🟡';
      case 'alert': return '🔴';
      default: return '⚪';
    }
  };

  const getTimeSince = (date) => {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  return (
    <div className={`room-card status-${room.status}`}>
      <div className="room-header">
        <h4>{room.name}</h4>
        <span className="status-icon">{getStatusIcon(room.status)}</span>
      </div>
      <div className="room-data">
        <div className="data-item">
          <span className="label">Temperature:</span>
          <span className="value">{room.temp}°C</span>
        </div>
        <div className="data-item">
          <span className="label">Motion:</span>
          <span className="value">{room.motion ? 'Yes' : 'No'}</span>
        </div>
        <div className="data-item">
          <span className="label">Last Update:</span>
          <span className="value">{getTimeSince(room.lastUpdate)}</span>
        </div>
      </div>
    </div>
  );
};

// Simple Activity Chart Component (Kan later vervangen door Chart.js/Recharts)
const ActivityChart = ({ data }) => {
  const maxCount = Math.max(...data.map(d => d.count));
  
  return (
    <div className="activity-chart">
      {data.map((item, index) => (
        <div key={index} className="chart-bar">
          <div 
            className="bar"
            style={{ height: `${(item.count / maxCount) * 100}%` }}
            title={`${item.hour}: ${item.count} events`}
          />
          <span className="bar-label">{item.hour}</span>
        </div>
      ))}
    </div>
  );
};

// PROJECT 2: Behavior Pattern Analyzer
const BehaviorAnalyzer = () => {
  const [patterns, setPatterns] = useState([]);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    mockAPI.behaviorAnalyzer.getPatterns().then(setPatterns);
    mockAPI.behaviorAnalyzer.getStats().then(setStats);
  }, []);

  return (
    <div className="project-container">
      <ProjectHeader
        title="Behavior Pattern Analyzer"
        description="ETL pipeline voor detectie van gedragspatronen en anomalieën"
        tech={['AWS Lambda', 'RDS PostgreSQL', 'Step Functions', 'API Gateway', 'Docker', 'Python']}
      />

      {/* Patterns Table */}
      <section className="patterns-section">
        <h3>📊 Detected Patterns</h3>
        <table className="patterns-table">
          <thead>
            <tr>
              <th>Pattern</th>
              <th>Frequency</th>
              <th>Anomalies</th>
            </tr>
          </thead>
          <tbody>
            {patterns.map((pattern, index) => (
              <tr key={index}>
                <td>{pattern.name}</td>
                <td>{pattern.frequency}%</td>
                <td>
                  {pattern.anomalies}
                  {pattern.anomalies > 0 && <span className="warning-icon"> ⚠️</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Analysis Stats */}
      {stats && (
        <section className="stats-section">
          <h3>🎯 Latest Analysis</h3>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-value">{stats.processed.toLocaleString()}</div>
              <div className="stat-label">Events Processed</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.anomalies}</div>
              <div className="stat-label">Anomalies Detected</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.confidence}%</div>
              <div className="stat-label">Pattern Confidence</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{Math.floor((new Date() - stats.lastRun) / 60000)}m</div>
              <div className="stat-label">Last ETL Run</div>
            </div>
          </div>
        </section>
      )}

      <ProjectFooter
        githubUrl="https://github.com/yourusername/behavior-analyzer"
        apiDocsUrl="#"
        architectureUrl="#"
      />
    </div>
  );
};

// PROJECT 3: IoT Device Gateway
const IoTGateway = () => {
  const [devices, setDevices] = useState([]);
  const [events, setEvents] = useState([]);

  useEffect(() => {
    mockAPI.iotGateway.getDevices().then(setDevices);
    mockAPI.iotGateway.getEvents().then(setEvents);
    
    // Simulate live event updates
    const interval = setInterval(() => {
      mockAPI.iotGateway.getEvents().then(setEvents);
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status) => {
    switch(status) {
      case 'ok': return '🟢';
      case 'slow': return '🟡';
      case 'down': return '🔴';
      default: return '⚪';
    }
  };

  const formatLastSeen = (seconds) => {
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    return `${Math.floor(seconds / 3600)}h ago`;
  };

  return (
    <div className="project-container">
      <ProjectHeader
        title="IoT Device Gateway Simulator"
        description="Secure device management met auth, heartbeat monitoring en rate limiting"
        tech={['API Gateway', 'Cognito', 'DynamoDB', 'SQS', 'Lambda', 'Docker', 'Python']}
      />

      {/* Devices Table */}
      <section className="devices-section">
        <h3>📱 Registered Devices</h3>
        <table className="devices-table">
          <thead>
            <tr>
              <th>Device ID</th>
              <th>Status</th>
              <th>Last Heartbeat</th>
              <th>Rate</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((device) => (
              <tr key={device.id} className={`device-row status-${device.status}`}>
                <td><code>{device.id}</code></td>
                <td>
                  {getStatusIcon(device.status)} {device.status.toUpperCase()}
                </td>
                <td>{formatLastSeen(device.lastHeartbeat)}</td>
                <td>{device.ratePerMin}/min</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Live Events Stream */}
      <section className="events-section">
        <h3>⚡ Live Events Stream</h3>
        <div className="events-log">
          {events.map((event, index) => (
            <div key={index} className="event-item">
              <span className="event-time">{event.time}</span>
              <span className="event-device">{event.deviceId}</span>
              <span className="event-message">{event.event}</span>
            </div>
          ))}
        </div>
      </section>

      <ProjectFooter
        githubUrl="https://github.com/yourusername/iot-gateway"
        apiDocsUrl="#"
        architectureUrl="#"
      />
    </div>
  );
};

// Reusable Components
const ProjectHeader = ({ title, description, tech }) => (
  <div className="project-header">
    <h2>{title}</h2>
    <p className="project-description">{description}</p>
    <div className="tech-stack">
      {tech.map((technology, index) => (
        <span key={index} className="tech-badge">{technology}</span>
      ))}
    </div>
  </div>
);

const ProjectFooter = ({ githubUrl, apiDocsUrl, architectureUrl }) => (
  <div className="project-footer">
    <a href={githubUrl} className="footer-link" target="_blank" rel="noopener noreferrer">
      📂 View Code
    </a>
    <a href={apiDocsUrl} className="footer-link">
      📄 API Docs
    </a>
    <a href={architectureUrl} className="footer-link">
      🏗️ Architecture
    </a>
  </div>
);

export default PortfolioDashboard;
