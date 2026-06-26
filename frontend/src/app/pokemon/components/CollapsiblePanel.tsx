'use client';

import { useState } from 'react';

interface CollapsiblePanelProps {
  title: string;
  subtitle?: string;
  color?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

export default function CollapsiblePanel({
  title,
  subtitle,
  color = 'border-accent/30 bg-accent/5',
  children,
  defaultOpen = false,
}: CollapsiblePanelProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className={`rounded-xl border ${color} overflow-hidden transition-all duration-200`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-white/5"
      >
        <div className="flex items-center gap-3">
          <span className={`text-sm transition-transform duration-200 ${isOpen ? 'rotate-90' : ''}`}>
            ▶
          </span>
          <div>
            <h3 className="text-sm font-semibold text-white">{title}</h3>
            {subtitle && <p className="mt-0.5 text-xs text-gray-500">{subtitle}</p>}
          </div>
        </div>
        <span className="text-xs text-gray-500">{isOpen ? '收起' : '展开'}</span>
      </button>
      {isOpen && (
        <div className="border-t border-white/5 px-4 py-3 animate-fade-in">
          {children}
        </div>
      )}
    </div>
  );
}
