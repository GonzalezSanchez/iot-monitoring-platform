// Pill badge; `color` carries the text/bg/border classes (Tailwind needs full class strings).
function Badge({ color, children }) {
  return (
    <span className={`${color} rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide`}>
      {children}
    </span>
  );
}

export default Badge;
