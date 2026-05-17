interface ProgressBarProps {
  value: number; // 0-100
  color?: string;
  height?: string;
  showLabel?: boolean;
}

export default function ProgressBar({
  value,
  color = "bg-blue-600",
  height = "h-2",
  showLabel = false,
}: ProgressBarProps) {
  const clamped = Math.min(Math.max(value, 0), 100);
  return (
    <div role="progressbar" aria-valuenow={clamped} aria-valuemin={0} aria-valuemax={100} className="w-full">
      <div className={`w-full bg-gray-800 rounded-full ${height}`}>
        <div
          className={`${color} ${height} rounded-full transition-all duration-300`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && (
        <p className="text-xs text-gray-500 mt-1">{Math.round(clamped)}%</p>
      )}
    </div>
  );
}
