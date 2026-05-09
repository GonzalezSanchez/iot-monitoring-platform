const tabGroups = [
  {
    group: 'Smart Room Monitoring',
    icon: '🏠',
    description: 'Real-time sensor visualization and room status tracking',
    tabs: [
      { key: 'room-lambda', label: '⚡ AWS Lambda serverless (project 1a)' },
      { key: 'room-fastapi', label: '🐍 Containerized REST API - FastAPI (project 1b)' },
    ]
  },
  {
    group: 'Behavior Analyzer',
    icon: '📊',
    description: 'Pattern detection and anomaly identification from historical data',
    tabs: [
      { key: 'behavior-aws', label: '☁️ AWS Step Functions + Aurora (project 2a)' },
      { key: 'behavior-spark', label: '⚡ Apache Spark + Airflow (project 2b)' },
    ]
  },
  {
    group: 'AI Assistant',
    icon: '🤖',
    description: 'Natural language interface for sensor data queries',
    tabs: [
      { key: 'llm', label: '💬 AI Assistant - LLM with MCP protocol (project 4)' },
    ]
  }
];

function ProjectTabs({ active, onChange }) {
  return (
    <div className="bg-gradient-to-b from-blue-50 to-blue-100 rounded-xl p-8 shadow-lg max-w-3xl mx-auto my-8">
      {tabGroups.map((group, idx) => (
        <div key={group.group} className={idx > 0 ? 'mt-8 pt-8 border-t border-blue-200' : ''}>
          <div className="mb-6 text-center">
            <div className="text-3xl mb-2">{group.icon}</div>
            <h3 className="text-lg font-bold text-gray-800">
              {group.group}
            </h3>
            <p className="text-sm text-gray-600 mt-2">
              {group.description}
            </p>
          </div>
          <ul className="space-y-2 flex flex-col items-center">
            {group.tabs.map(tab => (
              <li
                key={tab.key}
                onClick={() => onChange(tab.key)}
                className={`px-4 py-2 rounded-lg cursor-pointer border-l-4 transition-all duration-200 w-fit
                  ${active === tab.key
                    ? 'bg-blue-800 text-white border-l-blue-900 shadow-lg'
                    : 'bg-white text-gray-700 border-l-gray-300 hover:bg-blue-50 hover:border-l-blue-400'
                  }`}
              >
                <span className="font-semibold text-sm">{tab.label}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

export default ProjectTabs;
