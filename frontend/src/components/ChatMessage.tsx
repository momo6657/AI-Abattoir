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
}: ChatMessageProps) {
  const bgColor = AVATAR_COLORS[agentIndex % AVATAR_COLORS.length];

  if (isSystem) {
    return (
      <div className="flex justify-center py-2">
        <span className="text-xs text-gray-500 bg-gray-800/50 px-3 py-1 rounded-full">
          {typeof content === "string" ? content : JSON.stringify(content)}
        </span>
      </div>
    );
  }

  return (
    <div className="flex gap-3 py-2">
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0 ${bgColor}`}>
        {agentName ? getAvatarLetter(agentName) : "?"}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 mb-1">
          <span className="font-medium text-sm">{agentName || "未知"}</span>
          <span className="text-xs text-gray-500">{formatTime(createdAt)}</span>
        </div>
        <div className="text-sm text-gray-300">
          {contentType === "text" && (
            <p className="whitespace-pre-wrap">{typeof content === "string" ? content : JSON.stringify(content)}</p>
          )}
          {contentType === "image" && imageUrl && (
            <img src={imageUrl} alt="生成的图片" className="max-w-sm rounded-lg mt-1" />
          )}
          {contentType === "audio" && audioUrl && (
            <audio controls src={audioUrl} className="mt-1" />
          )}
        </div>
      </div>
    </div>
  );
}
