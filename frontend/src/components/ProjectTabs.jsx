const tabGroups = [
  {
    group: 'Smart Room Monitoring',
    icon: '🏠',
    description: 'Real-time sensor visualization and room status tracking',
    tabs: [
      { key: 'room-lambda', label: 'Lambda (1a)', desc: 'AWS Lambda serverless architecture' },
      { key: 'room-fastapi', label: 'FastAPI (1b)', desc: 'Containerized REST API with Docker' },
    ]
  },
  {
    group: 'Behavior Analyzer',
    icon: '📊',
    description: 'Pattern detection and anomaly identification from historical data',
    tabs: [
      { key: 'behavior-aws', label: 'AWS (2a)', desc: 'AWS Step Functions + Aurora pipeline' },
      { key: 'behavior-spark', label: 'Spark (2b)', desc: 'Apache Spark + Airflow data engineering' },
    ]
  },
  {
    group: 'AI Assistant',
    icon: '🤖',
    description: 'Natural language interface for sensor data queries',
    tabs: [
      { key: 'llm', label: 'AI Assistant (4)', desc: 'LLM with MCP protocol integration' },
    ]
  }
];

function ProjectTabs({ active, onChange }) {
  return (
    <div className="bg-gradient-to-b from-blue-50 to-blue-100 rounded-xl p-8 shadow-lg max-w-4xl mx-auto">
      {tabGroups.map((group, idx) => (
        <div key={group.group} className={idx > 0 ? 'mt-10 pt-10 border-t border-blue-200' : ''}>
          <div className="flex items-start gap-4 mb-5 justify-center">
            <div className="text-center">
              <span className="text-3xl block mb-2">{group.icon}</span>
              <div>
                <h3 className="text-xl font-bold text-gray-800">
                  {group.group}
                </h3>
                <p className="text-sm text-gray-600 mt-2 max-w-xs">
                  {group.description}
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-4 justify-center">
            {group.tabs.map(tab => (
              <button
                key={tab.key}
                onClick={() => onChange(tab.key)}
                className={`flex flex-col items-center px-6 py-4 rounded-lg font-semibold text-sm cursor-pointer border transition-all duration-200 shadow-md hover:shadow-lg min-w-48
                  ${active === tab.key
                    ? 'bg-blue-600 text-white shadow-lg border-blue-700'
                    : 'bg-white text-gray-700 hover:bg-gray-50 border-gray-200'
                  }`}
              >
                <span className="font-bold">{tab.label}</span>
                <span className={`text-xs mt-2 font-normal text-center ${active === tab.key ? 'text-blue-100' : 'text-yellow-600'}`}>
                  {tab.desc}
                </span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default ProjectTabs;
