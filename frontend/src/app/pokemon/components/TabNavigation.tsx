'use client';

interface Tab {
  id: string;
  label: string;
  icon: string;
}

interface TabNavigationProps {
  tabs: Tab[];
  activeTab: string;
  onChange: (tabId: string) => void;
}

export default function TabNavigation({ tabs, activeTab, onChange }: TabNavigationProps) {
  return (
    <nav className="flex gap-1 rounded-xl border border-border bg-surface-raised/50 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`relative flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all duration-200 ${
            activeTab === tab.id
              ? 'bg-accent text-white shadow-lg shadow-accent/25'
              : 'text-gray-400 hover:text-white hover:bg-surface-overlay'
          }`}
        >
          <span className="text-base">{tab.icon}</span>
          <span>{tab.label}</span>
          {activeTab === tab.id && (
            <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-white" />
          )}
        </button>
      ))}
    </nav>
  );
}
