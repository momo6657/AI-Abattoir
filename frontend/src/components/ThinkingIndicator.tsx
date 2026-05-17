interface ThinkingIndicatorProps {
  agentName?: string;
}

export default function ThinkingIndicator({ agentName }: ThinkingIndicatorProps) {
  return (
    <div className="flex items-center gap-2 py-2">
      <div className="flex gap-1">
        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
      {agentName && (
        <span className="text-sm text-gray-500">{agentName} 正在思考...</span>
      )}
    </div>
  );
}
