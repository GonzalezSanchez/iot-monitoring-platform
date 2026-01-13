import React, { useState } from 'react';

const projects = [
  { key: 'room', label: 'Smart Room Monitor' },
  { key: 'behavior', label: 'Behavior Analyzer' },
  { key: 'gateway', label: 'IoT Gateway' },
];

function ProjectTabs({ active, onChange }) {
  return (
    <div style={{ display: 'flex', gap: '16px', marginBottom: '32px' }}>
      {projects.map(p => (
        <button
          key={p.key}
          onClick={() => onChange(p.key)}
          style={{
            padding: '10px 24px',
            borderRadius: '6px',
            border: 'none',
            background: active === p.key ? '#1976d2' : '#e3e3e3',
            color: active === p.key ? '#fff' : '#222',
            fontWeight: 'bold',
            cursor: 'pointer',
            boxShadow: active === p.key ? '0 2px 8px rgba(25,118,210,0.15)' : 'none',
          }}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

export default ProjectTabs;
