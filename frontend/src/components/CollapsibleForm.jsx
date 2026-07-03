import { useState } from 'react';

// Collapsible ▸/▾ panel with a form inside; fields go in as children.
function CollapsibleForm({ title, onSubmit, children }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-6 border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className={`w-full px-4 py-3 bg-gray-50 text-left font-semibold text-sm text-gray-700 cursor-pointer border-none ${open ? 'border-b border-gray-200' : ''}`}
      >
        {open ? '▾' : '▸'} {title}
      </button>
      {open && (
        <form onSubmit={onSubmit} className="p-4 flex flex-wrap gap-3 items-end">
          {children}
        </form>
      )}
    </div>
  );
}

export function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      {children}
    </div>
  );
}

export function SubmitButton({ submitting, busyLabel, children }) {
  return (
    <button
      type="submit"
      disabled={submitting}
      className={`px-4 py-1.5 text-white border-none rounded-md font-semibold text-sm ${submitting ? 'bg-blue-300 cursor-not-allowed' : 'bg-blue-600 cursor-pointer'}`}
    >
      {submitting ? busyLabel : children}
    </button>
  );
}

export function ResultBanner({ ok, children }) {
  return (
    <div className={`w-full mt-1 px-3 py-2 rounded-md text-xs ${ok ? 'bg-green-50 border border-green-300 text-green-700' : 'bg-red-50 border border-red-300 text-red-600'}`}>
      {children}
    </div>
  );
}

export default CollapsibleForm;
