// Full-width top bar with title + subtitle; extra content (tags, links) via children.
function PageHeader({ title, subtitle, children }) {
  return (
    <div className="px-6 py-4 border-b border-gray-200 bg-white shrink-0">
      <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
      <p className="mt-1 text-sm text-gray-500">{subtitle}</p>
      {children}
    </div>
  );
}

export default PageHeader;
