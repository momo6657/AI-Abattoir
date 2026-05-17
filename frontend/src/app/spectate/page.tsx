"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { conversationsApi, gamesApi, spectatorApi } from "@/lib/api";
import { useSpectateWebSocket, SpectateMessage } from "@/hooks/useSpectateWebSocket";
import { LoadingSpinner, Badge, ErrorBanner, ProgressBar, ChatMessage, ThinkingIndicator } from "@/components";
import { Conversation, Game, GamePlayer } from "@/types";
import { getAvatarBg, getAvatarLetter, getStatusLabel } from "@/lib/utils";
import { getGameTypeInfo } from "@/lib/constants";

// ---- Local types ----
interface ReplayData {
  conversation_id?: string; game_id?: string; title: string;
  mode?: string; game_type?: string; status?: string;
  message_count?: number; messages?: SpectateMessage[];
  players?: GamePlayer[]; state?: Record<string, unknown>; created_at?: string;
}
const MODE_LABELS: Record<string, string> = { free: "自由对话", debate: "辩论", relay: "接力", interview: "采访" };
const EVENT_LABELS: Record<string, string> = { vote_result: "投票结果", game_started: "游戏开始", game_ended: "游戏结束" };
const BackBtn = ({ onClick }: { onClick: () => void }) => (
  <button onClick={onClick} className="text-gray-400 hover:text-white text-sm mb-3 flex items-center gap-1"><span>&larr;</span> 返回列表</button>
);
function formatDate(d: string) { try { return new Date(d).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" }); } catch { return ""; } }
function getStatusBadgeVariant(s: string): "success" | "warning" | "danger" | "default" | "info" {
  if (s === "active") return "success"; if (s === "paused") return "warning";
  if (s === "ended" || s === "finished") return "default"; return "info";
}
function buildParticipants(messages: SpectateMessage[]) {
  const map = new Map<string, string>();
  for (const m of messages) { if (m.agent_id && m.agent_name) map.set(m.agent_id, m.agent_name); }
  return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
}
function getEventLabel(evt: Record<string, unknown>): string {
  const t = evt.type as string;
  if (t === "phase_change") return `阶段: ${evt.phase || "切换"}`;
  if (t === "elimination") return `${evt.agent_name || "玩家"} 被淘汰`;
  if (t === "turn_start") return `回合 ${evt.turn || "?"} 开始`;
  return EVENT_LABELS[t] || String(t);
}

// ---- Shared: Participant sidebar ----
function ParticipantList({ participants }: { participants: { id: string; name: string }[] }) {
  return (
    <div className="space-y-2">
      {participants.map((p, idx) => (
        <div key={p.id} className="flex items-center gap-2">
          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white ${getAvatarBg(idx)}`}>{getAvatarLetter(p.name)}</div>
          <span className="text-sm">{p.name}</span>
        </div>
      ))}
    </div>
  );
}

// ---- Live Spectating View ----
function LiveSpectateView({
  targetId,
  type,
  onBack,
}: {
  targetId: string;
  type: "conversation" | "game";
  onBack: () => void;
}) {
  const { messages, connected, thinkingAgent, gameEvents, disconnect } = useSpectateWebSocket({ targetId, type });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [title, setTitle] = useState<string>("");

  useEffect(() => {
    (async () => {
      try {
        const r = type === "conversation" ? await conversationsApi.get(targetId) : await gamesApi.get(targetId);
        setTitle(r.data.title || (type === "conversation" ? "对话" : "游戏"));
      } catch { setTitle(type === "conversation" ? "对话" : "游戏"); }
    })();
  }, [targetId, type]);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  const handleBack = () => { disconnect(); onBack(); };

  const participants = useMemo(() => buildParticipants(messages), [messages]);

  return (
    <div className="flex flex-col md:flex-row gap-4" style={{ height: "calc(100vh - 180px)" }}>
      {/* Left Sidebar */}
      <div className="w-full md:w-64 flex-shrink-0 flex flex-col bg-gray-900 rounded-xl overflow-hidden">
        <div className="border-b border-gray-800 p-4">
          <BackBtn onClick={handleBack} />
          <h3 className="font-bold truncate">{title}</h3>
          <div className="flex items-center gap-2 mt-2">
            <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
            <span className="text-xs text-gray-400">{connected ? "实时连接中" : "连接中..."}</span>
            <Badge text="只读" variant="info" />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <h4 className="text-xs text-gray-400 mb-3">参与者</h4>
          {participants.length > 0 ? (
            <ParticipantList participants={participants} />
          ) : (
            <p className="text-xs text-gray-500">等待消息...</p>
          )}
          {type === "game" && gameEvents.length > 0 && (
            <div className="mt-6">
              <h4 className="text-xs text-gray-400 mb-3">游戏事件</h4>
              <div className="space-y-1">
                {gameEvents.slice(-10).map((evt, idx) => (
                  <div key={idx} className="text-xs text-gray-500 bg-gray-800 rounded px-2 py-1">{getEventLabel(evt)}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right - Message Stream */}
      <div className="flex-1 flex flex-col bg-gray-900 rounded-xl overflow-hidden">
        <div className="border-b border-gray-800 px-4 py-3">
          <h3 className="font-semibold text-sm">
            {type === "conversation" ? "对话实时流" : "游戏实时流"}
            <span className="text-xs text-gray-500 ml-2">{messages.length} 条消息</span>
          </h3>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="flex-1 flex items-center justify-center h-full text-gray-500 text-center">
              <div><p className="text-lg mb-2">等待消息...</p><p className="text-sm">连接成功后将实时显示消息</p></div>
            </div>
          )}
          {messages.map((msg, idx) => {
            const isSystem = msg.role === "system" || msg.log_type === "system";
            const isElimination = msg.log_type === "elimination";
            const agentIdx = participants.findIndex((p) => p.id === msg.agent_id);
            return (
              <ChatMessage
                key={msg.id || idx}
                agentName={msg.agent_name || "系统"}
                content={msg.content}
                createdAt={msg.created_at}
                agentIndex={agentIdx >= 0 ? agentIdx : 0}
                isSystem={isSystem && !isElimination}
                isElimination={isElimination}
                turnNumber={msg.turn_number}
              />
            );
          })}
          {thinkingAgent && (
            <ThinkingIndicator agentName={thinkingAgent} showAvatar />
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
}

// ---- Replay View ----
function ReplayView({
  targetId,
  type,
  onBack,
}: {
  targetId: string;
  type: "conversation" | "game";
  onBack: () => void;
}) {
  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [speed, setSpeed] = useState(1);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const playTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const messages = replayData?.messages || [];
  const participants = useMemo(() => buildParticipants(messages), [messages]);

  useEffect(() => {
    const loadReplay = async () => {
      setLoading(true);
      try {
        const r = type === "conversation"
          ? await spectatorApi.replayConversation(targetId)
          : await spectatorApi.replayGame(targetId);
        setReplayData(r.data);
        setCurrentIndex(r.data.messages?.length || 0);
        setError(null);
      } catch {
        setError("无法加载回放数据");
      } finally {
        setLoading(false);
      }
    };
    loadReplay();
  }, [targetId, type]);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [currentIndex]);
  useEffect(() => {
    if (isPlaying && messages.length > 0) {
      const interval = Math.max(500, 2000 / speed);
      playTimerRef.current = setInterval(() => {
        setCurrentIndex((prev) => {
          if (prev >= messages.length) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, interval);
    }
    return () => {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    };
  }, [isPlaying, speed, messages.length]);

  const handlePlay = () => { if (currentIndex >= messages.length) setCurrentIndex(0); setIsPlaying(true); };
  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setCurrentIndex(Math.floor(((e.clientX - rect.left) / rect.width) * messages.length));
  };

  const visibleMessages = messages.slice(0, currentIndex);
  const progressPct = messages.length > 0 ? (currentIndex / messages.length) * 100 : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner text="加载回放数据..." />
      </div>
    );
  }

  if (error || !replayData) {
    return (
      <div className="space-y-4">
        <BackBtn onClick={onBack} />
        <ErrorBanner message={error || "加载失败"} onDismiss={() => setError(null)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col md:flex-row gap-4" style={{ height: "calc(100vh - 180px)" }}>
      {/* Left Sidebar */}
      <div className="w-full md:w-64 flex-shrink-0 flex flex-col bg-gray-900 rounded-xl overflow-hidden">
        <div className="border-b border-gray-800 p-4">
          <BackBtn onClick={onBack} />
          <h3 className="font-bold truncate">{replayData.title}</h3>
          <div className="flex items-center gap-2 mt-2">
            <Badge text="回放" variant="default" />
            {replayData.status && (
              <Badge text={getStatusLabel(replayData.status)} variant={getStatusBadgeVariant(replayData.status)} />
            )}
          </div>
          {replayData.created_at && (
            <p className="text-xs text-gray-500 mt-2">{formatDate(replayData.created_at)}</p>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <h4 className="text-xs text-gray-400 mb-3">参与者 ({participants.length})</h4>
          <ParticipantList participants={participants} />
          {type === "game" && replayData.players && replayData.players.length > 0 && (
            <div className="mt-6">
              <h4 className="text-xs text-gray-400 mb-3">游戏角色</h4>
              <div className="space-y-2">
                {replayData.players.map((p) => (
                  <div key={p.agent_id} className="flex items-center justify-between text-sm">
                    <span className={p.alive ? "" : "text-gray-600 line-through"}>{p.agent_name}</span>
                    <span className="text-xs text-gray-500">{p.role}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {type === "game" && replayData.state && Object.keys(replayData.state).length > 0 && (
            <div className="mt-6">
              <h4 className="text-xs text-gray-400 mb-3">最终状态</h4>
              <div className="text-xs text-gray-300 space-y-1">
                {Object.entries(replayData.state).filter(([k]) => !["logs", "players"].includes(k)).slice(0, 8).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-gray-500">{k}</span>
                    <span className="truncate ml-2">{typeof v === "object" ? JSON.stringify(v).slice(0, 30) : String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right - Replay Stream */}
      <div className="flex-1 flex flex-col bg-gray-900 rounded-xl overflow-hidden">
        <div className="border-b border-gray-800 px-4 py-3 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm">
              回放
              <span className="text-xs text-gray-500 ml-2">{currentIndex} / {messages.length} 条</span>
            </h3>
            <div className="flex items-center gap-2">
              {[0.5, 1, 2].map((s) => (
                <button key={s} onClick={() => setSpeed(s)} className={`px-2 py-1 rounded text-xs ${speed === s ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}>{s}x</button>
              ))}
            </div>
          </div>
          <div className="cursor-pointer" onClick={handleProgressClick}>
            <ProgressBar value={progressPct} />
          </div>
          <div className="flex gap-2">
            {isPlaying ? (
              <button onClick={() => setIsPlaying(false)} className="bg-yellow-600 hover:bg-yellow-700 px-3 py-1.5 rounded-lg text-xs">暂停</button>
            ) : (
              <button onClick={handlePlay} className="bg-green-600 hover:bg-green-700 px-3 py-1.5 rounded-lg text-xs">
                {currentIndex >= messages.length ? "重新播放" : "播放"}
              </button>
            )}
            <button onClick={() => { setIsPlaying(false); setCurrentIndex(0); }} className="bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded-lg text-xs">重置</button>
            <button onClick={() => { setIsPlaying(false); setCurrentIndex(messages.length); }} className="bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded-lg text-xs">显示全部</button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {visibleMessages.length === 0 && (
            <div className="flex items-center justify-center h-full text-gray-500">
              <p className="text-lg">{messages.length > 0 ? "点击播放开始回放" : "暂无消息"}</p>
            </div>
          )}
          {visibleMessages.map((msg, idx) => {
            const isSystem = msg.role === "system" || msg.log_type === "system";
            const isElimination = msg.log_type === "elimination";
            const agentIdx = participants.findIndex((p) => p.id === msg.agent_id);
            return (
              <ChatMessage
                key={msg.id || idx}
                agentName={msg.agent_name || "系统"}
                content={msg.content}
                createdAt={msg.created_at}
                agentIndex={agentIdx >= 0 ? agentIdx : 0}
                isSystem={isSystem && !isElimination}
                isElimination={isElimination}
                turnNumber={msg.turn_number}
              />
            );
          })}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
}

// ---- Page Component ----
export default function SpectatePage() {
  const [tab, setTab] = useState<"live" | "replay">("live");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"list" | "spectate" | "replay">("list");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<"conversation" | "game">("conversation");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [convR, gameR] = await Promise.all([
        conversationsApi.list().catch(() => ({ data: [] })),
        gamesApi.list().catch(() => ({ data: [] })),
      ]);
      setConversations(convR.data || []);
      setGames(gameR.data || []);
      setError(null);
    } catch {
      setError("无法加载数据，请检查后端服务是否运行");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSpectate = (id: string, type: "conversation" | "game") => {
    setSelectedId(id); setSelectedType(type); setViewMode("spectate");
  };
  const handleReplay = (id: string, type: "conversation" | "game") => {
    setSelectedId(id); setSelectedType(type); setViewMode("replay");
  };
  const handleBack = () => { setViewMode("list"); setSelectedId(null); };

  const activeConvs = conversations.filter((c) => c.status === "active");
  const endedConvs = conversations.filter((c) => c.status === "ended");
  const activeGms = games.filter((g) => g.status === "active");
  const endedGms = games.filter((g) => g.status === "finished" || g.status === "ended");
  const isLive = tab === "live";

  if (viewMode === "spectate" && selectedId) {
    return <LiveSpectateView targetId={selectedId} type={selectedType} onBack={handleBack} />;
  }
  if (viewMode === "replay" && selectedId) {
    return <ReplayView targetId={selectedId} type={selectedType} onBack={handleBack} />;
  }

  const tabLabel = (t: "live" | "replay") => t === "live" ? "实时观战" : "历史回放";
  const tabCount = (t: "live" | "replay") => t === "live" ? activeConvs.length + activeGms.length : endedConvs.length + endedGms.length;
  const convBtnClass = (active: boolean) => `px-4 py-2 rounded-lg text-sm font-medium ${active ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`;
  const actionBtn = (onClick: () => void, color: string, label: string) => (
    <button onClick={onClick} className={`${color} hover:${color.replace("600", "700")} px-3 py-1.5 rounded-lg text-xs`}>{label}</button>
  );

  return (
    <div>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <h2 className="text-2xl font-bold">观战中心</h2>
        <button onClick={loadData} className="bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg text-sm">刷新</button>
      </div>
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
      <div className="flex gap-2 mb-6">
        {(["live", "replay"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={convBtnClass(tab === t)}>
            {tabLabel(t)}<span className="ml-2 text-xs opacity-70">({tabCount(t)})</span>
          </button>
        ))}
      </div>

      {loading ? <LoadingSpinner text="加载中..." /> : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Conversations */}
          <div>
            <h3 className="text-lg font-semibold mb-4">{isLive ? "进行中的对话" : "已结束的对话"}</h3>
            <div className="space-y-3">
              {(isLive ? activeConvs : endedConvs).map((conv) => (
                <div key={conv.id} className="bg-gray-900 p-4 rounded-xl hover:bg-gray-800 transition-colors">
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-medium">{conv.title || "未命名对话"}</h4>
                    <Badge text={getStatusLabel(conv.status)} variant={getStatusBadgeVariant(conv.status)} />
                  </div>
                  <p className="text-xs text-gray-400 mb-3">
                    {MODE_LABELS[conv.mode] || conv.mode}{" . "}{conv.agent_ids?.length || 0} 个智能体{" . "}{formatDate(conv.created_at)}
                  </p>
                  {isLive && conv.status === "active"
                    ? actionBtn(() => handleSpectate(conv.id, "conversation"), "bg-green-600", "进入观战")
                    : actionBtn(() => handleReplay(conv.id, "conversation"), "bg-blue-600", "观看回放")}
                </div>
              ))}
              {(isLive ? activeConvs : endedConvs).length === 0 && (
                <div className="text-center py-8 text-gray-500 bg-gray-900 rounded-xl">
                  {isLive ? "没有进行中的对话" : "没有已结束的对话"}
                </div>
              )}
            </div>
          </div>
          {/* Games */}
          <div>
            <h3 className="text-lg font-semibold mb-4">{isLive ? "进行中的游戏" : "已结束的游戏"}</h3>
            <div className="space-y-3">
              {(isLive ? activeGms : endedGms).map((game) => {
                const ti = getGameTypeInfo(game.game_type);
                return (
                  <div key={game.id} className="bg-gray-900 p-4 rounded-xl hover:bg-gray-800 transition-colors">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold text-white ${ti.color}`}>{ti.icon}</span>
                        <h4 className="font-medium">{game.title}</h4>
                      </div>
                      <Badge text={getStatusLabel(game.status)} variant={getStatusBadgeVariant(game.status)} />
                    </div>
                    <p className="text-xs text-gray-400 mb-3">
                      {ti.label}{" . "}{game.players?.length || 0} 人{" . 回合 "}{game.current_turn}/{game.max_turns}{" . "}{formatDate(game.created_at)}
                    </p>
                    <div className="flex items-center justify-between">
                      <div className="flex gap-1">
                        {game.players?.slice(0, 6).map((p) => (
                          <span key={p.agent_id} className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${p.alive ? "bg-gray-700 text-white" : "bg-gray-800 text-gray-600 line-through"}`} title={`${p.agent_name} ${p.role}`}>
                            {p.agent_name?.charAt(0) || "?"}
                          </span>
                        ))}
                        {(game.players?.length || 0) > 6 && (
                          <span className="w-6 h-6 rounded-full bg-gray-800 flex items-center justify-center text-xs text-gray-400">+{game.players!.length - 6}</span>
                        )}
                      </div>
                      {isLive && game.status === "active"
                        ? actionBtn(() => handleSpectate(game.id, "game"), "bg-green-600", "进入观战")
                        : actionBtn(() => handleReplay(game.id, "game"), "bg-blue-600", "观看回放")}
                    </div>
                  </div>
                );
              })}
              {(isLive ? activeGms : endedGms).length === 0 && (
                <div className="text-center py-8 text-gray-500 bg-gray-900 rounded-xl">
                  {isLive ? "没有进行中的游戏" : "没有已结束的游戏"}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
