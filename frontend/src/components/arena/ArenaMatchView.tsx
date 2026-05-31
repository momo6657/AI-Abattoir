"use client";

import { Badge } from "@/components";
import { ArenaMatch, ArenaParticipant } from "@/types";

interface ArenaMatchViewProps {
  match: ArenaMatch;
  participants: ArenaParticipant[];
  showVoting?: boolean;
}

export default function ArenaMatchView({ match, participants, showVoting = true }: ArenaMatchViewProps) {
  const getMatchTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      qa: "问答对决",
      creative: "创意对决",
      code: "编程对决",
      image: "图像对决",
      voice: "语音对决",
    };
    return labels[type] || type;
  };

  const getMatchTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      qa: "💬",
      creative: "🎨",
      code: "💻",
      image: "🖼️",
      voice: "🎤",
    };
    return icons[type] || "⚔️";
  };

  const getStatusBadgeVariant = (status: string): "default" | "success" | "warning" | "danger" => {
    const variants: Record<string, "default" | "success" | "warning" | "danger"> = {
      waiting: "default",
      in_progress: "warning",
      voting: "warning",
      finished: "success",
    };
    return variants[status] || "default";
  };

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      waiting: "等待中",
      in_progress: "进行中",
      voting: "投票中",
      finished: "已结束",
    };
    return labels[status] || status;
  };

  const getTotalVotes = () => {
    return participants.reduce((sum, p) => sum + (p.vote_count || 0), 0);
  };

  const getVotePercentage = (participant: ArenaParticipant) => {
    const total = getTotalVotes();
    if (total === 0) return 0;
    return ((participant.vote_count || 0) / total) * 100;
  };

  const isWinner = (participant: ArenaParticipant) => {
    return match.winner_id === participant.agent_id;
  };

  const renderResponse = (participant: ArenaParticipant) => {
    const content = participant.response_content;
    if (!content) return <p className="text-gray-500 text-sm">暂无回应</p>;

    switch (match.match_type) {
      case "image":
        return (
          <div className="space-y-2">
            {content.image_url && (
              <img
                src={content.image_url}
                alt={`${participant.agent_name} 生成的图像`}
                className="w-full h-64 object-cover rounded-lg"
              />
            )}
            {content.prompt && (
              <p className="text-xs text-gray-400 mt-2">提示词: {content.prompt}</p>
            )}
          </div>
        );

      case "voice":
        return (
          <div className="space-y-2">
            {content.audio_url && (
              <audio controls className="w-full">
                <source src={content.audio_url} type="audio/mpeg" />
                您的浏览器不支持音频播放
              </audio>
            )}
            {content.transcript && (
              <p className="text-sm text-gray-300 mt-2">{content.transcript}</p>
            )}
          </div>
        );

      case "qa":
      case "creative":
      case "code":
      default:
        return (
          <div className="bg-gray-800/50 rounded-lg p-4 max-h-96 overflow-y-auto">
            <pre className="text-sm text-gray-200 whitespace-pre-wrap font-mono">
              {content.response || "无内容"}
            </pre>
          </div>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Match Header */}
      <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 rounded-xl p-6 border border-purple-500/20">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-4xl">{getMatchTypeIcon(match.match_type)}</span>
            <div>
              <h2 className="text-2xl font-bold text-white">{match.title}</h2>
              <p className="text-sm text-gray-400">{getMatchTypeLabel(match.match_type)}</p>
            </div>
          </div>
          <Badge
            text={getStatusLabel(match.status)}
            variant={getStatusBadgeVariant(match.status)}
          />
        </div>

        {/* Prompt/Question */}
        {match.prompt && (
          <div className="mt-4 bg-gray-800/50 rounded-lg p-4">
            <p className="text-xs text-gray-400 mb-1">问题/提示</p>
            <p className="text-gray-200">{match.prompt}</p>
          </div>
        )}
      </div>

      {/* Participants Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {participants.map((participant, index) => (
          <div
            key={participant.id}
            className={`relative rounded-xl p-6 border-2 transition-all ${
              isWinner(participant)
                ? "border-yellow-500 bg-yellow-900/20 shadow-lg shadow-yellow-500/20"
                : "border-gray-700 bg-gray-800/30"
            }`}
          >
            {/* Winner Badge */}
            {isWinner(participant) && (
              <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                <span className="bg-yellow-500 text-black px-4 py-1 rounded-full text-sm font-bold">
                  🏆 获胜者
                </span>
              </div>
            )}

            {/* Agent Header */}
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-12 h-12 rounded-full flex items-center justify-center text-2xl font-bold ${
                index === 0 ? "bg-blue-600" : "bg-red-600"
              }`}>
                {participant.agent_name.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-white">{participant.agent_name}</h3>
                <p className="text-xs text-gray-400">
                  {index === 0 ? "选手 A" : "选手 B"}
                </p>
              </div>
            </div>

            {/* Response Content */}
            <div className="mb-4">{renderResponse(participant)}</div>

            {/* Voting Section */}
            {showVoting && match.status !== "waiting" && (
              <div className="mt-4 pt-4 border-t border-gray-700">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">得票</span>
                  <span className="text-lg font-bold text-white">
                    {participant.vote_count || 0} 票
                  </span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
                  <div
                    className={`h-full transition-all duration-500 ${
                      index === 0 ? "bg-blue-500" : "bg-red-500"
                    }`}
                    style={{ width: `${getVotePercentage(participant)}%` }}
                  />
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  {getVotePercentage(participant).toFixed(1)}%
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Match Metadata */}
      <div className="bg-gray-800/30 rounded-lg p-4 border border-gray-700">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-gray-400">总投票数</p>
            <p className="text-white font-semibold">{getTotalVotes()}</p>
          </div>
          <div>
            <p className="text-gray-400">创建时间</p>
            <p className="text-white font-semibold">
              {new Date(match.created_at).toLocaleString("zh-CN")}
            </p>
          </div>
          {match.updated_at && (
            <div>
              <p className="text-gray-400">更新时间</p>
              <p className="text-white font-semibold">
                {new Date(match.updated_at).toLocaleString("zh-CN")}
              </p>
            </div>
          )}
          {match.creator_id && (
            <div>
              <p className="text-gray-400">创建者 ID</p>
              <p className="text-white font-semibold font-mono text-xs">
                {match.creator_id.substring(0, 8)}...
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
