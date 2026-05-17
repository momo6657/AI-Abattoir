"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <h2 className="text-4xl font-bold text-red-400 mb-4">出错了</h2>
      <p className="text-gray-400 mb-8">{error.message}</p>
      <button
        onClick={reset}
        className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg"
      >
        重试
      </button>
    </div>
  );
}
