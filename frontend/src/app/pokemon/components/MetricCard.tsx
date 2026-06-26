'use client';

interface MetricCardProps {
  label: string;
  value: string | number;
  compact?: boolean;
  color?: string;
}

export default function MetricCard({ label, value, compact = false, color }: MetricCardProps) {
  return (
    <div className={`rounded-lg border border-border bg-surface-overlay/50 p-3 ${compact ? 'py-2' : ''}`}>
      <p className={`text-xs uppercase tracking-wider text-gray-500 ${compact ? 'text-[10px]' : ''}`}>{label}</p>
      <p className={`mt-1 font-bold text-white ${compact ? 'text-sm' : 'text-lg'} ${color || ''}`}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
    </div>
  );
}
