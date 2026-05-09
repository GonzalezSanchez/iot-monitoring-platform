const tabGroups = [
  {
    group: 'Smart room monitoring',
    tabs: [
      { key: 'room-lambda',  label: 'AWS Lambda', sub: 'project 1a' },
      { key: 'room-fastapi', label: 'FastAPI',     sub: 'project 1b' },
    ],
  },
  {
    group: 'Behavior analyzer',
    tabs: [
      { key: 'behavior-aws',   label: 'Step Functions + Aurora', sub: 'project 2a' },
      { key: 'behavior-spark', label: 'Spark + Airflow',         sub: 'project 2b' },
    ],
  },
  {
    group: 'AI assistant',
    tabs: [
      { key: 'llm', label: 'LLM + MCP', sub: 'project 4' },
    ],
  },
];

function ProjectTabs({ active, onChange }) {
  return (
    <nav className="w-56 shrink-0 bg-blue-50 border-r border-blue-100 py-6 px-3 flex flex-col">
      {tabGroups.map((group, idx) => (
        <div key={group.group}>
          <p className={`text-xs font-bold text-gray-700 uppercase tracking-widest px-2 mb-3 ${idx > 0 ? 'mt-6' : ''}`}>
            {group.group}
          </p>
          <ul className="flex flex-col gap-1">
            {group.tabs.map((tab) => (
              <li
                key={tab.key}
                onClick={() => onChange(tab.key)}
                className={`ml-3 px-3 py-2 rounded-lg cursor-pointer transition-colors
                  ${active === tab.key
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:bg-gray-100'
                  }`}
              >
                <span className="block text-sm font-semibold">{tab.label}</span>
                <span className={`block text-xs ${active === tab.key ? 'text-blue-200' : 'text-gray-400'}`}>
                  {tab.sub}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export default ProjectTabs;
