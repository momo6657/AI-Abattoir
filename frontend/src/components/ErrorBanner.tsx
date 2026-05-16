"use client";

interface ErrorBannerProps {
  message: string;
  onDismiss: () => void;
}

export default function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg mb-4 flex justify-between items-center">
      <span>{message}</span>
      <button onClick={onDismiss} className="text-red-400 hover:text-red-200 text-xl">&times;</button>
    </div>
  );
}
