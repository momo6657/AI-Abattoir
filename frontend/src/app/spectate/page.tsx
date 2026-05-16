"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { conversationsApi, gamesApi, spectatorApi } from "@/lib/api";
import { LoadingSpinner, Badge, ErrorBanner, ProgressBar } from "@/components";

// ---- Types ----
interface Conversation {
  id: string;
  title: string;
  mode: string;
  status: string;
  agent_ids: string[];
  created_at: string;
}

interface GamePlayer {
  agent_id: string;
  agent_name: string;
  role: string;
  alive: boolean;
  eliminated_turn?: number;
}

interface Game {
  id: string;
  game_type: string;
  title: string;
  status: string;
  current_turn: number;
  max_turns: number;
  players: GamePlayer[];
  created_at: string;
}

interface SpectateMessage {
  id: string;
  agent_id?: string;
  agent_name?: string;
  role?: string;
  content: string;
  turn_number?: number;
  log_type?: string;
  created_at: string;
}

interface ReplayData {
  conversation_id?: string;
  game_id?: string;
  title: string;
  mode?: string;
  game_type?: string;
  status?: string;
  message_count?: number;
  messages?: SpectateMessage[];
  players?: GamePlayer[];
  state?: Record<string, unknown>;
  created_at?: string;
}

const AVATAR_COLORS = [
  "bg-blue-600", "bg-purple-600", "bg-green-600",
  "bg-red-600", "bg-yellow-600", "bg-pink-600",
  "bg-indigo-600", "bg-teal-600",
];

const GAME_TYPES: Record<string, { label: string; color: string; icon: string }> = {
  werewolf: { label: "狼人杀", color: "bg-red-600", icon: "W" },
  debate: { label: "辩论赛", color: "bg-blue-600", icon: "D" },
  chess: { label: "棋类", color: "bg-green-600", icon: "C" },
  adventure: { label: "文字冒险", color: "bg-purple-600", icon: "A" },
  negotiation: { label: "谈判", color: "bg-yellow-600", icon: "N" },
};

const MODE_LABELS: Record<string, string> = {
  free: "自由对话",
  debate: "辩论",
  relay: "接力",
  interview: "采访",
};

function getAvatarColor(index: number): string {
  return AVATAR_COLORS[index % AVATAR_COLORS.length];
}

function getAvatarLetter(name: string): string {
  return name.charAt(0).toUpperCase();
}

function formatTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
  } catch {
    return "";
  }
}

function getStatusBadgeVariant(status: string): "success" | "warning" | "danger" | "default" | "info" {
  if (status === "active") return "success";
  if (status === "paused") return "warning";
  if (status === "ended" || status === "finished") return "default";
  return "info";
}

function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    active: "进行中",
    paused: "已暂停",
    ended: "已结束",
    finished: "已结束",
    waiting: "等待中",
  };
  return map[status] || status;
}

function getGameTypeInfo(type: string) {
  return GAME_TYPES[type] || { label: type, color: "bg-gray-600", icon: "?" };
}

// ---- Live Spectating Hook ----
function useSpectateWebSocket(targetId: string | null, type: "conversation" | "game") {
  const wsRef = useRef<WebSocket | null>(null);
  const [messages, setMessages] = useState<SpectateMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const [thinkingAgent, setThinkingAgent] = useState<string | null>(null);
  const [gameEvents, setGameEvents] = useState<Record<string, unknown>[]>([]);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCount = useRef(0);

  const connect = useCallback(() => {
    if (!targetId) return;

    const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const endpoint = type === "conversation"
      ? `${wsBase}/ws/spectate/conversation/${targetId}`
      : `${wsBase}/ws/spectate/game/${targetId}`;
    const ws = new WebSocket(endpoint);

    ws.onopen = () => {
      setConnected(true);
      retryCount.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const payload = msg.data || {};
        switch (msg.type) {
          case "new_message":
            setMessages((prev) => [...prev, {
              id: payload.id || crypto.randomUUID(),
              agent_id: payload.agent_id,
              agent_name: payload.agent_name,
              role: payload.role || "agent",
              content: typeof payload.content === "string" ? payload.content : JSON.stringify(payload.content),
              turn_number: payload.turn_number,
              created_at: payload.created_at || new Date().toISOString(),
            }]);
            break;
          case "agent_thinking":
            setThinkingAgent(payload.agent_name || payload.agent_id || null);
            break;
          case "agent_done_thinking":
            setThinkingAgent(null);
            break;
          case "game_event":
          case "turn_start":
          case "turn_end":
          case "phase_change":
          case "vote_result":
          case "elimination":
            setGameEvents((prev) => [...prev, { type: msg.type, ...payload, timestamp: new Date().toISOString() }]);
            if (msg.type === "elimination") {
              setMessages((prev) => [...prev, {
                id: crypto.randomUUID(),
                role: "system",
                content: payload.content || `${payload.agent_name || "玩家"} 已被淘汰`,
                log_type: "elimination",
                created_at: new Date().toISOString(),
              }]);
            }
            break;
          case "game_started":
          case "game_ended":
            setGameEvents((prev) => [...prev, { type: msg.type, ...payload, timestamp: new Date().toISOString() }]);
            setMessages((prev) => [...prev, {
              id: crypto.randomUUID(),
              role: "system",
              content: msg.type === "game_started" ? "游戏开始" : "游戏结束",
              log_type: "system",
              created_at: new Date().toISOString(),
            }]);
            break;
          case "conversation_started":
          case "conversation_ended":
          case "conversation_paused":
            setMessages((prev) => [...prev, {
              id: crypto.randomUUID(),
              role: "system",
              content: msg.type === "conversation_started" ? "对话开始"
                : msg.type === "conversation_ended" ? "对话结束" : "对话已暂停",
              log_type: "system",
              created_at: new Date().toISOString(),
            }]);
            break;
          case "ping":
            ws.send(JSON.stringify({ type: "pong" }));
            break;
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      setThinkingAgent(null);
      const delay = Math.min(1000 * 2 ** retryCount.current, 30000);
      retryCount.current++;
      reconnectTimeout.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [targetId, type]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
    if (wsRef.current) wsRef.current.close();
    wsRef.current = null;
    setConnected(false);
    setMessages([]);
    setThinkingAgent(null);
    setGameEvents([]);
    retryCount.current = 0;
  }, []);

  return { messages, connected, thinkingAgent, gameEvents, disconnect, setMessages };
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
  const { messages, connected, thinkingAgent, gameEvents, disconnect } = useSpectateWebSocket(targetId, type);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [title, setTitle] = useState<string>("");

  // Load basic info for the header
  useEffect(() => {
    const loadInfo = async () => {
      try {
        if (type === "conversation") {
          const r = await conversationsApi.get(targetId);
          setTitle(r.data.title || "对话");
        } else {
          const r = await gamesApi.get(targetId);
          setTitle(r.data.title || "游戏");
        }
      } catch {
        setTitle(type === "conversation" ? "对话" : "游戏");
      }
    };
    loadInfo();
  }, [targetId, type]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleBack = () => {
    disconnect();
    onBack();
  };

  // Build participant list from messages
  const participants = useMemo(() => {
    const map = new Map<string, string>();
    for (const msg of messages) {
      if (msg.agent_id && msg.agent_name) {
        map.set(msg.agent_id, msg.agent_name);
      }
    }
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [messages]);

  return (
    <div className="flex flex-col md:flex-row gap-4" style={{ height: "calc(100vh - 180px)" }}>
      {/* Left Sidebar - Participants */}
      <div className="w-full md:w-64 flex-shrink-0 flex flex-col bg-gray-900 rounded-xl overflow-hidden">
        <div className="border-b border-gray-800 p-4">
          <button
            onClick={handleBack}
            className="text-gray-400 hover:text-white text-sm mb-3 flex items-center gap-1"
          >
            <span>&larr;</span> 返回列表
          </button>
          <h3 className="font-bold truncate">{title}</h3>
          <div className="flex items-center gap-2 mt-2">
            <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
            <span className="text-xs text-gray-400">
              {connected ? "实时连接中" : "连接中..."}
            </span>
            <Badge text="只读" variant="info" />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <h4 className="text-xs text-gray-400 mb-3">参与者</h4>
          {participants.length > 0 ? (
            <div className="space-y-2">
              {participants.map((p, idx) => (
                <div key={p.id} className="flex items-center gap-2">
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white ${getAvatarColor(idx)}`}
                  >
                    {getAvatarLetter(p.name)}
                  </div>
                  <span className="text-sm">{p.name}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-500">等待消息...</p>
          )}

          {type === "game" && gameEvents.length > 0 && (
            <div className="mt-6">
              <h4 className="text-xs text-gray-400 mb-3">游戏事件</h4>
              <div className="space-y-1">
                {gameEvents.slice(-10).map((evt, idx) => (
                  <div key={idx} className="text-xs text-gray-500 bg-gray-800 rounded px-2 py-1">
                    {evt.type === "phase_change" && `阶段: ${evt.phase || "切换"}`}
                    {evt.type === "elimination" && `${evt.agent_name || "玩家"} 被淘汰`}
                    {evt.type === "turn_start" && `回合 ${evt.turn || "?"} 开始`}
                    {evt.type === "vote_result" && "投票结果"}
                    {evt.type === "game_started" && "游戏开始"}
                    {evt.type === "game_ended" && "游戏结束"}
                    {!["phase_change", "elimination", "turn_start", "vote_result", "game_started", "game_ended"].includes(evt.type as string) && String(evt.type)}
                  </div>
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
            <div className="flex-1 flex items-center justify-center h-full">
              <div className="text-center text-gray-500">
                <p className="text-lg mb-2">等待消息...</p>
                <p className="text-sm">连接成功后将实时显示消息</p>
              </div>
            </div>
          )}

          {messages.map((msg, idx) => {
            const isSystem = msg.role === "system" || msg.log_type === "system";
            const isElimination = msg.log_type === "elimination";
            const agentName = msg.agent_name || "系统";
            const agentIdx = participants.findIndex((p) => p.id === msg.agent_id);

            if (isSystem || isElimination) {
              return (
                <div key={msg.id || idx} className="text-center">
                  <span
                    className={`text-xs px-3 py-1 rounded-full ${
                      isElimination
                        ? "bg-red-900/40 text-red-300"
                        : "bg-gray-800 text-gray-500"
                    }`}
                  >
                    {msg.content}
                  </span>
                </div>
              );
            }

            return (
              <div key={msg.id || idx} className="flex gap-3">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0 ${
                    agentIdx >= 0 ? getAvatarColor(agentIdx) : "bg-gray-600"
                  }`}
                >
                  {getAvatarLetter(agentName)}
                </div>
                <div className="max-w-[80%] flex flex-col">
                  <span className="text-xs text-gray-400 mb-1">
                    {agentName}
                    {msg.turn_number !== undefined && ` · 回合 ${msg.turn_number}`}
                    {` · ${formatTime(msg.created_at)}`}
                  </span>
                  <div className="bg-gray-800 rounded-xl px-4 py-2.5 text-sm">
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              </div>
            );
          })}

          {/* Thinking Indicator */}
          {thinkingAgent && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0 bg-gray-600">
                {getAvatarLetter(thinkingAgent)}
              </div>
              <div>
                <span className="text-xs text-gray-400 mb-1 block">
                  {thinkingAgent} 正在思考...
                </span>
                <div className="bg-gray-800 rounded-xl px-4 py-2.5 inline-flex gap-1">
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
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
  const [speed, setSpeed] = useState(1); // 1x, 2x, 0.5x
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const playTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const messages = replayData?.messages || [];
  const participants = useMemo(() => {
    if (!messages) return [];
    const map = new Map<string, string>();
    for (const msg of messages) {
      if (msg.agent_id && msg.agent_name) {
        map.set(msg.agent_id, msg.agent_name);
      }
    }
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [messages]);

  useEffect(() => {
    const loadReplay = async () => {
      setLoading(true);
      try {
        let r;
        if (type === "conversation") {
          r = await spectatorApi.replayConversation(targetId);
        } else {
          r = await spectatorApi.replayGame(targetId);
        }
        setReplayData(r.data);
        setCurrentIndex(r.data.messages?.length || 0); // Show all by default
        setError(null);
      } catch {
        setError("无法加载回放数据");
      } finally {
        setLoading(false);
      }
    };
    loadReplay();
  }, [targetId, type]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [currentIndex]);

  // Playback timer
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

  const handlePlay = () => {
    if (currentIndex >= messages.length) {
      setCurrentIndex(0);
    }
    setIsPlaying(true);
  };

  const handlePause = () => {
    setIsPlaying(false);
  };

  const handleReset = () => {
    setIsPlaying(false);
    setCurrentIndex(0);
  };

  const handleShowAll = () => {
    setIsPlaying(false);
    setCurrentIndex(messages.length);
  };

  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    setCurrentIndex(Math.floor(pct * messages.length));
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
        <button onClick={onBack} className="text-gray-400 hover:text-white text-sm flex items-center gap-1">
          <span>&larr;</span> 返回列表
        </button>
        <ErrorBanner message={error || "加载失败"} onDismiss={() => setError(null)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col md:flex-row gap-4" style={{ height: "calc(100vh - 180px)" }}>
      {/* Left Sidebar - Info */}
      <div className="w-full md:w-64 flex-shrink-0 flex flex-col bg-gray-900 rounded-xl overflow-hidden">
        <div className="border-b border-gray-800 p-4">
          <button
            onClick={onBack}
            className="text-gray-400 hover:text-white text-sm mb-3 flex items-center gap-1"
          >
            <span>&larr;</span> 返回列表
          </button>
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

        {/* Participants */}
        <div className="flex-1 overflow-y-auto p-4">
          <h4 className="text-xs text-gray-400 mb-3">
            参与者 ({participants.length})
          </h4>
          <div className="space-y-2">
            {participants.map((p, idx) => (
              <div key={p.id} className="flex items-center gap-2">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white ${getAvatarColor(idx)}`}
                >
                  {getAvatarLetter(p.name)}
                </div>
                <span className="text-sm">{p.name}</span>
              </div>
            ))}
          </div>

          {/* Game players info (for game replays) */}
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

          {/* Game state (for game replays) */}
          {type === "game" && replayData.state && Object.keys(replayData.state).length > 0 && (
            <div className="mt-6">
              <h4 className="text-xs text-gray-400 mb-3">最终状态</h4>
              <div className="text-xs text-gray-300 space-y-1">
                {Object.entries(replayData.state)
                  .filter(([k]) => !["logs", "players"].includes(k))
                  .slice(0, 8)
                  .map(([k, v]) => (
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
        {/* Playback Controls */}
        <div className="border-b border-gray-800 px-4 py-3 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm">
              回放
              <span className="text-xs text-gray-500 ml-2">
                {currentIndex} / {messages.length} 条
              </span>
            </h3>
            <div className="flex items-center gap-2">
              {/* Speed Controls */}
              {[0.5, 1, 2].map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={`px-2 py-1 rounded text-xs ${
                    speed === s ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                  }`}
                >
                  {s}x
                </button>
              ))}
            </div>
          </div>

          {/* Progress Bar */}
          <div className="cursor-pointer" onClick={handleProgressClick}>
            <ProgressBar value={progressPct} />
          </div>

          {/* Control Buttons */}
          <div className="flex gap-2">
            {isPlaying ? (
              <button
                onClick={handlePause}
                className="bg-yellow-600 hover:bg-yellow-700 px-3 py-1.5 rounded-lg text-xs"
              >
                暂停
              </button>
            ) : (
              <button
                onClick={handlePlay}
                className="bg-green-600 hover:bg-green-700 px-3 py-1.5 rounded-lg text-xs"
              >
                {currentIndex >= messages.length ? "重新播放" : "播放"}
              </button>
            )}
            <button
              onClick={handleReset}
              className="bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded-lg text-xs"
            >
              重置
            </button>
            <button
              onClick={handleShowAll}
              className="bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded-lg text-xs"
            >
              显示全部
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {visibleMessages.length === 0 && (
            <div className="flex items-center justify-center h-full text-gray-500">
              <div className="text-center">
                <p className="text-lg mb-2">
                  {messages.length > 0 ? "点击播放开始回放" : "暂无消息"}
                </p>
              </div>
            </div>
          )}

          {visibleMessages.map((msg, idx) => {
            const isSystem = msg.role === "system" || msg.log_type === "system";
            const isElimination = msg.log_type === "elimination";
            const agentName = msg.agent_name || "系统";
            const agentIdx = participants.findIndex((p) => p.id === msg.agent_id);

            if (isSystem || isElimination) {
              return (
                <div key={msg.id || idx} className="text-center">
                  <span
                    className={`text-xs px-3 py-1 rounded-full ${
                      isElimination
                        ? "bg-red-900/40 text-red-300"
                        : "bg-gray-800 text-gray-500"
                    }`}
                  >
                    {msg.content}
                  </span>
                </div>
              );
            }

            return (
              <div key={msg.id || idx} className="flex gap-3">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0 ${
                    agentIdx >= 0 ? getAvatarColor(agentIdx) : "bg-gray-600"
                  }`}
                >
                  {getAvatarLetter(agentName)}
                </div>
                <div className="max-w-[80%] flex flex-col">
                  <span className="text-xs text-gray-400 mb-1">
                    {agentName}
                    {msg.turn_number !== undefined && ` · 回合 ${msg.turn_number}`}
                    {` · ${formatTime(msg.created_at)}`}
                  </span>
                  <div className="bg-gray-800 rounded-xl px-4 py-2.5 text-sm">
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              </div>
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

  // View state
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

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSpectate = (id: string, type: "conversation" | "game") => {
    setSelectedId(id);
    setSelectedType(type);
    setViewMode("spectate");
  };

  const handleReplay = (id: string, type: "conversation" | "game") => {
    setSelectedId(id);
    setSelectedType(type);
    setViewMode("replay");
  };

  const handleBack = () => {
    setViewMode("list");
    setSelectedId(null);
  };

  // Filter items by status
  const activeConversations = conversations.filter((c) => c.status === "active");
  const endedConversations = conversations.filter((c) => c.status === "ended");
  const activeGames = games.filter((g) => g.status === "active");
  const endedGames = games.filter((g) => g.status === "finished" || g.status === "ended");

  // Spectating or replay view
  if (viewMode === "spectate" && selectedId) {
    return (
      <LiveSpectateView
        targetId={selectedId}
        type={selectedType}
        onBack={handleBack}
      />
    );
  }

  if (viewMode === "replay" && selectedId) {
    return (
      <ReplayView
        targetId={selectedId}
        type={selectedType}
        onBack={handleBack}
      />
    );
  }

  // List view
  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <h2 className="text-2xl font-bold">观战中心</h2>
        <button
          onClick={loadData}
          className="bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg text-sm"
        >
          刷新
        </button>
      </div>

      {/* Error */}
      {error && (
        <ErrorBanner message={error} onDismiss={() => setError(null)} />
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setTab("live")}
          className={`px-4 py-2 rounded-lg text-sm font-medium ${
            tab === "live" ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
          }`}
        >
          实时观战
          {(activeConversations.length + activeGames.length) > 0 && (
            <span className="ml-2 text-xs opacity-70">
              ({activeConversations.length + activeGames.length})
            </span>
          )}
        </button>
        <button
          onClick={() => setTab("replay")}
          className={`px-4 py-2 rounded-lg text-sm font-medium ${
            tab === "replay" ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
          }`}
        >
          历史回放
          {(endedConversations.length + endedGames.length) > 0 && (
            <span className="ml-2 text-xs opacity-70">
              ({endedConversations.length + endedGames.length})
            </span>
          )}
        </button>
      </div>

      {loading ? (
        <LoadingSpinner text="加载中..." />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Conversations Column */}
          <div>
            <h3 className="text-lg font-semibold mb-4">
              {tab === "live" ? "进行中的对话" : "已结束的对话"}
            </h3>
            <div className="space-y-3">
              {(tab === "live" ? activeConversations : endedConversations).map((conv) => (
                <div
                  key={conv.id}
                  className="bg-gray-900 p-4 rounded-xl hover:bg-gray-800 transition-colors"
                >
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-medium">{conv.title || "未命名对话"}</h4>
                    <Badge
                      text={getStatusLabel(conv.status)}
                      variant={getStatusBadgeVariant(conv.status)}
                    />
                  </div>
                  <p className="text-xs text-gray-400 mb-3">
                    {MODE_LABELS[conv.mode] || conv.mode}
                    {" · "}
                    {conv.agent_ids?.length || 0} 个智能体
                    {" · "}
                    {formatDate(conv.created_at)}
                  </p>
                  <div className="flex gap-2">
                    {tab === "live" && conv.status === "active" ? (
                      <button
                        onClick={() => handleSpectate(conv.id, "conversation")}
                        className="bg-green-600 hover:bg-green-700 px-3 py-1.5 rounded-lg text-xs"
                      >
                        进入观战
                      </button>
                    ) : (
                      <button
                        onClick={() => handleReplay(conv.id, "conversation")}
                        className="bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg text-xs"
                      >
                        观看回放
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {(tab === "live" ? activeConversations : endedConversations).length === 0 && (
                <div className="text-center py-8 text-gray-500 bg-gray-900 rounded-xl">
                  {tab === "live" ? "没有进行中的对话" : "没有已结束的对话"}
                </div>
              )}
            </div>
          </div>

          {/* Games Column */}
          <div>
            <h3 className="text-lg font-semibold mb-4">
              {tab === "live" ? "进行中的游戏" : "已结束的游戏"}
            </h3>
            <div className="space-y-3">
              {(tab === "live" ? activeGames : endedGames).map((game) => {
                const typeInfo = getGameTypeInfo(game.game_type);
                return (
                  <div
                    key={game.id}
                    className="bg-gray-900 p-4 rounded-xl hover:bg-gray-800 transition-colors"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold text-white ${typeInfo.color}`}
                        >
                          {typeInfo.icon}
                        </span>
                        <h4 className="font-medium">{game.title}</h4>
                      </div>
                      <Badge
                        text={getStatusLabel(game.status)}
                        variant={getStatusBadgeVariant(game.status)}
                      />
                    </div>
                    <p className="text-xs text-gray-400 mb-3">
                      {typeInfo.label}
                      {" · "}
                      {game.players?.length || 0} 人
                      {" · 回合 "}
                      {game.current_turn}/{game.max_turns}
                      {" · "}
                      {formatDate(game.created_at)}
                    </p>
                    <div className="flex items-center justify-between">
                      <div className="flex gap-1">
                        {game.players?.slice(0, 6).map((p) => (
                          <span
                            key={p.agent_id}
                            className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                              p.alive ? "bg-gray-700 text-white" : "bg-gray-800 text-gray-600 line-through"
                            }`}
                            title={`${p.agent_name} ${p.role}`}
                          >
                            {p.agent_name?.charAt(0) || "?"}
                          </span>
                        ))}
                        {(game.players?.length || 0) > 6 && (
                          <span className="w-6 h-6 rounded-full bg-gray-800 flex items-center justify-center text-xs text-gray-400">
                            +{game.players!.length - 6}
                          </span>
                        )}
                      </div>
                      <div className="flex gap-2">
                        {tab === "live" && game.status === "active" ? (
                          <button
                            onClick={() => handleSpectate(game.id, "game")}
                            className="bg-green-600 hover:bg-green-700 px-3 py-1.5 rounded-lg text-xs"
                          >
                            进入观战
                          </button>
                        ) : (
                          <button
                            onClick={() => handleReplay(game.id, "game")}
                            className="bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg text-xs"
                          >
                            观看回放
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
              {(tab === "live" ? activeGames : endedGames).length === 0 && (
                <div className="text-center py-8 text-gray-500 bg-gray-900 rounded-xl">
                  {tab === "live" ? "没有进行中的游戏" : "没有已结束的游戏"}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
