const projects = [
  { key: 'room',     label: 'Smart Room Monitor' },
  { key: 'behavior', label: 'Behavior Analyzer' },
  { key: 'gateway',  label: 'IoT Gateway' },
];

function ProjectTabs({ active, onChange }) {
  return (
    <div className="flex gap-4 mb-8 px-6 pt-6">
      {projects.map(p => (
        <button
          key={p.key}
          onClick={() => onChange(p.key)}
          className={`px-6 py-2.5 rounded-md font-semibold text-sm cursor-pointer border-none transition-colors
            ${active === p.key
              ? 'bg-blue-600 text-white shadow-md'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

export default ProjectTabs;
