import { getAvatarLetter, getAvatarBg } from "@/lib/utils";

interface ThinkingIndicatorProps {
  agentName?: string;
  /** Show avatar circle with agent initial (default: false) */
  showAvatar?: boolean;
  /** Agent index for avatar color; defaults to 0 */
  agentIndex?: number;
}

export default function ThinkingIndicator({
  agentName,
  showAvatar = false,
  agentIndex = 0,
}: ThinkingIndicatorProps) {
  return (
    <div className="flex gap-3">
      {showAvatar && (
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0 ${
            agentName ? getAvatarBg(agentIndex) : "bg-gray-600"
          }`}
        >
          {agentName ? getAvatarLetter(agentName) : "?"}
        </div>
      )}
      <div>
        {agentName && (
          <span className="text-xs text-gray-400 mb-1 block">
            {agentName} 正在思考...
          </span>
        )}
        <div className="bg-gray-800 rounded-xl px-4 py-2.5 inline-flex gap-1">
          <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
          <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
          <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    </div>
  );
}
