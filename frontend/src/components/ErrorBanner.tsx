"use client";

interface ErrorBannerProps {
  message: string;
  onDismiss: () => void;
  onRetry?: () => void;
}

export default function ErrorBanner({ message, onDismiss, onRetry }: ErrorBannerProps) {
  return (
    <div role="alert" className="bg-red-500/10 border border-red-500/20 text-red-300 px-4 py-3 rounded-xl mb-4 flex justify-between items-center gap-3 animate-slide-up">
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-red-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        <span className="text-sm">{message}</span>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {onRetry && (
          <button onClick={onRetry} className="text-red-300 hover:text-white text-xs px-2 py-1 rounded-lg hover:bg-red-500/10 transition-colors">
            重试
          </button>
        )}
        <button onClick={onDismiss} aria-label="关闭" className="text-red-400 hover:text-red-200 w-6 h-6 rounded-lg flex items-center justify-center hover:bg-red-500/10 transition-colors">&times;</button>
      </div>
    </div>
  );
}
