import { AVATAR_COLORS, getAvatarLetter, formatTime } from "@/lib/utils";

interface ChatMessageProps {
  agentId?: string;
  agentName?: string;
  content: string | Record<string, unknown>;
  contentType?: "text" | "image" | "audio";
  imageUrl?: string;
  audioUrl?: string;
  createdAt: string;
  agentIndex?: number;
  isSystem?: boolean;
  /** Spectate-specific: show elimination styling */
  isElimination?: boolean;
  /** Spectate-specific: turn number to display */
  turnNumber?: number;
  /** Whether this is a user-sent message (right-aligned) */
  isUser?: boolean;
}

export default function ChatMessage({
  agentName,
  content,
  contentType = "text",
  imageUrl,
  audioUrl,
  createdAt,
  agentIndex = 0,
  isSystem = false,
  isElimination = false,
  turnNumber,
  isUser = false,
}: ChatMessageProps) {
  const displayContent = typeof content === "string"
    ? content
    : (content as Record<string, unknown>)?.text
      ? String((content as Record<string, unknown>).text)
      : JSON.stringify(content);

  const bgColor = agentIndex >= 0
    ? AVATAR_COLORS[agentIndex % AVATAR_COLORS.length]
    : "bg-gray-600";

  // System / elimination message
  if (isSystem || isElimination) {
    return (
      <div className="text-center">
        <span
          className={`text-xs px-3 py-1 rounded-full ${
            isElimination
              ? "bg-red-900/40 text-red-300"
              : "bg-gray-800 text-gray-500"
          }`}
        >
          {displayContent}
        </span>
      </div>
    );
  }

  // User message (right-aligned, blue bubble)
  if (isUser) {
    return (
      <div className="flex gap-3 flex-row-reverse">
        <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0 bg-gray-600">
          U
        </div>
        <div className="max-w-[70%] items-end flex flex-col">
          <span className="text-xs text-gray-400 mb-1">
            {agentName || "用户"} · {formatTime(createdAt)}
          </span>
          <div className="bg-blue-600 text-white rounded-xl px-4 py-2.5 text-sm">
            <p className="whitespace-pre-wrap">{displayContent}</p>
          </div>
        </div>
      </div>
    );
  }

  // Agent message
  return (
    <div className="flex gap-3">
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0 ${bgColor}`}
      >
        {agentName ? getAvatarLetter(agentName) : "?"}
      </div>
      <div className="max-w-[80%] flex flex-col">
        <span className="text-xs text-gray-400 mb-1">
          {agentName || "未知"}
          {turnNumber !== undefined && ` · 回合 ${turnNumber}`}
          {` · ${formatTime(createdAt)}`}
        </span>
        <div className="bg-gray-800 rounded-xl px-4 py-2.5 text-sm">
          {contentType === "image" && imageUrl && (
            <div>
              <img
                src={imageUrl}
                alt="shared image"
                className="rounded-lg max-w-full max-h-64 object-contain"
              />
              {displayContent && <p className="mt-2">{displayContent}</p>}
            </div>
          )}
          {contentType === "audio" && audioUrl && (
            <div>
              <audio controls className="max-w-full">
                <source src={audioUrl} />
              </audio>
              {displayContent && <p className="mt-2">{displayContent}</p>}
            </div>
          )}
          {(!contentType || contentType === "text") && (
            <p className="whitespace-pre-wrap">{displayContent}</p>
          )}
        </div>
      </div>
    </div>
  );
}
