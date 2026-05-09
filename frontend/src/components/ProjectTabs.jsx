const tabGroups = [
  {
    group: 'Smart Room Monitoring',
    description: 'Real-time sensor visualization and room status tracking',
    tabs: [
      { key: 'room-lambda', label: 'Lambda (project 1a)', desc: 'AWS Lambda serverless' },
      { key: 'room-fastapi', label: 'FastAPI (project 1b)', desc: 'Containerized REST API' },
    ]
  },
  {
    group: 'Behavior Analyzer',
    description: 'Pattern detection and anomaly identification from historical data',
    tabs: [
      { key: 'behavior-aws', label: 'AWS (project 2a)', desc: 'Step Functions + Aurora' },
      { key: 'behavior-spark', label: 'Spark (project 2b)', desc: 'Apache Spark + Airflow' },
    ]
  },
  {
    group: 'AI Assistant',
    description: 'Natural language interface for sensor data queries',
    tabs: [
      { key: 'llm', label: 'AI Assistant (project 4)', desc: 'LLM with MCP protocol' },
    ]
  }
];

function ProjectTabs({ active, onChange }) {
  return (
    <div className="bg-gradient-to-b from-blue-50 to-blue-100 rounded-xl p-6 shadow-lg max-w-4xl mx-auto my-8">
      {tabGroups.map((group, idx) => (
        <div key={group.group} className={idx > 0 ? 'mt-6 pt-6 border-t border-blue-200' : ''}>
          <div className="mb-4 text-center">
            <h3 className="text-lg font-bold text-gray-800">
              {group.group}
            </h3>
            <p className="text-sm text-gray-600 mt-1">
              {group.description}
            </p>
          </div>
          <div className="flex flex-wrap gap-3 justify-center">
            {group.tabs.map(tab => (
              <button
                key={tab.key}
                onClick={() => onChange(tab.key)}
                className={`flex flex-col items-start px-4 py-3 rounded-lg font-semibold text-sm cursor-pointer border transition-all duration-200 shadow-md hover:shadow-lg
                  ${active === tab.key
                    ? 'bg-blue-600 text-white shadow-lg border-blue-700'
                    : 'bg-white text-gray-700 hover:bg-gray-50 border-gray-200'
                  }`}
              >
                <span>{tab.label}</span>
                <span className={`text-xs mt-1.5 font-normal ${active === tab.key ? 'text-blue-100' : 'text-yellow-600'}`}>
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
