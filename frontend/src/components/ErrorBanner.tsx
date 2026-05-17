"use client";

interface ErrorBannerProps {
  message: string;
  onDismiss: () => void;
  onRetry?: () => void;
}

export default function ErrorBanner({ message, onDismiss, onRetry }: ErrorBannerProps) {
  return (
    <div role="alert" className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg mb-4 flex justify-between items-center gap-3">
      <span>{message}</span>
      <div className="flex items-center gap-2 flex-shrink-0">
        {onRetry && (
          <button
            onClick={onRetry}
            className="text-red-300 hover:text-white text-sm underline"
          >
            重试
          </button>
        )}
        <button onClick={onDismiss} aria-label="关闭" className="text-red-400 hover:text-red-200 text-xl">&times;</button>
      </div>
    </div>
  );
}
