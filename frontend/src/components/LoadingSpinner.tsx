export default function LoadingSpinner({ text = "加载中..." }: { text?: string }) {
  return (
    <div role="status" aria-live="polite" aria-label={text} className="flex items-center justify-center py-12 gap-3">
      <div className="w-5 h-5 border-2 border-surface-overlay border-t-accent rounded-full animate-spin" />
      <span className="text-gray-400 text-sm">{text}</span>
    </div>
  );
}
