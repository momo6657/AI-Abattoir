"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { conversationsApi, gamesApi, spectatorApi, arenaApi } from "@/lib/api";
import { useSpectateWebSocket, SpectateMessage } from "@/hooks/useSpectateWebSocket";
import { useArenaWebSocket } from "@/hooks/useArenaWebSocket";
import ArenaMatchView from "@/components/arena/ArenaMatchView";
import { LoadingSpinner, Badge, ErrorBanner, ProgressBar, ChatMessage, ThinkingIndicator } from "@/components";
import ChessBoard from "@/components/games/ChessBoard";
import WerewolfGameState from "@/components/games/WerewolfGameState";
import DebateScoreboard from "@/components/games/DebateScoreboard";
import TextAdventureState from "@/components/games/TextAdventureState";
import NegotiationTracker from "@/components/games/NegotiationTracker";
import { Conversation, Game, GamePlayer, ArenaMatch, ArenaParticipant } from "@/types";
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
const EVENT_LABELS: Record<string, string> = {
  game_start: "游戏开始",
  night_result: "夜晚结算",
  day_discussion: "白天讨论",
  vote_result: "投票结果",
  game_over: "游戏结束",
  game_started: "游戏开始",
  game_ended: "游戏结束",
};
const BackBtn = ({ onClick }: { onClick: () => void }) => (
  <button onClick={onClick} className="btn-ghost text-sm mb-3 flex items-center gap-1"><span>&larr;</span> 返回列表</button>
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
  if (typeof evt.message === "string") return evt.message;
  if (t === "phase_change") return `阶段: ${evt.phase || "切换"}`;
  if (t === "elimination") return `${evt.agent_name || "玩家"} 被淘汰`;
  if (t === "turn_start") return `回合 ${evt.turn || "?"} 开始`;
  if (t === "night_result") {
    const names = Array.isArray(evt.death_names) ? evt.death_names : [];
    return names.length > 0 ? `昨晚 ${names.join("、")} 死亡` : "昨晚是平安夜";
  }
  if (t === "vote_result") return `投票：${evt.exiled_name || evt.exiled || "玩家"} 被放逐`;
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

// ---- Game Visualization Helper ----
function GameVisualization({ gameType, gameState, chessBoard, chessLastMove, chessInCheck, chessCurrentColor }: {
  gameType: string;
  gameState?: Record<string, unknown>;
  chessBoard?: Record<string, [string, string]>;
  chessLastMove?: { from: string; to: string } | null;
  chessInCheck?: string | null;
  chessCurrentColor?: string;
}) {
  if (gameType === "chess") {
    const board = chessBoard || {};
    return (
      <>
        <div className="flex items-center gap-3 mb-3">
          <span className="text-sm font-semibold">国际象棋</span>
          <Badge text={chessCurrentColor === "white" ? "白方走棋" : "黑方走棋"} variant={chessCurrentColor === "white" ? "info" : "default"} />
          {chessInCheck && <Badge text="将军!" variant="danger" />}
        </div>
        <ChessBoard board={board} lastMove={chessLastMove} inCheck={chessInCheck} />
        {chessLastMove && (
          <div className="mt-2 text-xs text-gray-400">
            最近走法: <span className="text-white font-mono">{chessLastMove.from} → {chessLastMove.to}</span>
          </div>
        )}
        {Object.keys(board).length === 0 && (
          <p className="text-xs text-gray-500 mt-3">等待第一步...</p>
        )}
      </>
    );
  }
  if (!gameState) return null;
  switch (gameType) {
    case "werewolf":
      return <WerewolfGameState
        phase={gameState.phase as "night" | "day" | "vote" | "result" | undefined}
        turn={gameState.turn as number}
        players={gameState.players as Array<{agent_id: string; name: string; role?: string; role_name?: string; alive?: boolean}>}
        nightActions={gameState.night_actions as Record<string, unknown>}
        deathNames={gameState.death_names as string[]}
        exiledName={gameState.exiled_name as string}
        winner={gameState.winner as string}
        aliveCount={gameState.alive_count as number}
      />;
    case "debate":
      return <DebateScoreboard
        topic={gameState.topic as string}
        phase={gameState.phase as 'opening' | 'cross' | 'closing' | 'result'}
        proOpening={gameState.pro_opening as string}
        conOpening={gameState.con_opening as string}
        proCross={gameState.pro_cross as string}
        conCross={gameState.con_cross as string}
        proClosing={gameState.pro_closing as string}
        conClosing={gameState.con_closing as string}
        proScores={gameState.pro_scores as {arguments?: number; logic?: number; expression?: number}}
        conScores={gameState.con_scores as {arguments?: number; logic?: number; expression?: number}}
        winner={gameState.winner as 'pro' | 'con' | null}
      />;
    case "text_adventure":
      return <TextAdventureState
        hp={gameState.hp as number}
        maxHp={gameState.max_hp as number}
        inventory={gameState.inventory as string[]}
        currentLocation={gameState.current_location as string}
        exploredLocations={gameState.explored_locations as string[]}
        scene={gameState.scene as string}
        lastAction={gameState.last_action as string}
        lastResult={gameState.last_result as string}
        lastHpChange={gameState.last_hp_change as number}
        lastItem={gameState.last_item as string}
        turn={gameState.turn as number}
      />;
    case "negotiation":
      return <NegotiationTracker
        phase={gameState.phase as 'negotiating' | 'accepted' | 'rejected'}
        proposals={gameState.proposals as Array<{player: string; proposal: string; accepted?: boolean}>}
        currentProposal={gameState.current_proposal as string}
        proposedBy={gameState.proposed_by as string}
        scores={gameState.scores as {player1?: number; player2?: number; fairness?: number}}
      />;
    default:
      return null;
  }
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
  const { messages, connected, thinkingAgent, gameEvents, disconnect, chessBoard, chessLastMove, chessInCheck, chessCurrentColor } = useSpectateWebSocket({ targetId, type });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [title, setTitle] = useState<string>("");
  const [targetPlayers, setTargetPlayers] = useState<GamePlayer[]>([]);
  const [gameType, setGameType] = useState<string>("");

  useEffect(() => {
    (async () => {
      try {
        const r = type === "conversation" ? await conversationsApi.get(targetId) : await gamesApi.get(targetId);
        setTitle(r.data.title || (type === "conversation" ? "对话" : "游戏"));
        setTargetPlayers(type === "game" ? (r.data.players || []) : []);
        if (type === "game" && r.data.game_type) {
          setGameType(r.data.game_type);
        }
      } catch { setTitle(type === "conversation" ? "对话" : "游戏"); }
    })();
  }, [targetId, type]);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  const handleBack = () => { disconnect(); onBack(); };

  const participants = useMemo(() => {
    if (type === "game" && targetPlayers.length > 0) {
      return targetPlayers.map((p) => ({ id: p.agent_id, name: p.agent_name || p.name || "玩家" }));
    }
    return buildParticipants(messages);
  }, [messages, targetPlayers, type]);

  const isChess = gameType === "chess";

  return (
    <div className="flex flex-col md:flex-row gap-4" style={{ height: "calc(100vh - 180px)" }}>
      {/* Left Sidebar */}
      <div className="w-full md:w-64 flex-shrink-0 flex flex-col card overflow-hidden">
        <div className="border-b border-border p-4">
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

      {/* Center - Game Visualization */}
      {type === "game" && gameType && (
        <div className="flex-shrink-0 flex flex-col items-center justify-start card overflow-y-auto p-4">
          <GameVisualization
            gameType={gameType}
            gameState={gameEvents.length > 0 ? ((gameEvents[gameEvents.length - 1].config as Record<string, unknown>) || (gameEvents[gameEvents.length - 1].data as Record<string, unknown>) || gameEvents[gameEvents.length - 1]) : undefined}
            chessBoard={chessBoard}
            chessLastMove={chessLastMove}
            chessInCheck={chessInCheck}
            chessCurrentColor={chessCurrentColor}
          />
        </div>
      )}

      {/* Right - Message Stream */}
      <div className="flex-1 flex flex-col card overflow-hidden">
        <div className="border-b border-border px-4 py-3">
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
  const participants = useMemo(() => {
    if (type === "game" && replayData?.players?.length) {
      return replayData.players.map((p) => ({ id: p.agent_id, name: p.agent_name || p.name || "玩家" }));
    }
    return buildParticipants(messages);
  }, [messages, replayData?.players, type]);

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

  // 从可见消息中提取当前回放位置的游戏状态
  const replayVisualizationProps = useMemo(() => {
    if (!replayData?.game_type) return null;

    const gameType = replayData.game_type;

    // 国际象棋：从最新的 chess_move 或 turn_result 事件提取棋盘状态
    if (gameType === "chess") {
      for (let i = visibleMessages.length - 1; i >= 0; i--) {
        const msg = visibleMessages[i];
        if (msg.game_data?.event_type === "chess_move" || msg.game_data?.event_type === "turn_result") {
          return {
            gameType,
            chessBoard: (msg.game_data?.board as Record<string, [string, string]>) || {},
            chessLastMove: (msg.game_data?.last_move as { from: string; to: string }) || undefined,
            chessInCheck: (msg.game_data?.in_check as string) || undefined,
            chessCurrentColor: (msg.game_data?.current_color as string) || undefined,
          };
        }
      }
      return { gameType, chessBoard: {}, chessLastMove: undefined, chessInCheck: undefined, chessCurrentColor: undefined };
    }

    // 其他游戏类型：从最新的有 config 的消息提取状态
    for (let i = visibleMessages.length - 1; i >= 0; i--) {
      const msg = visibleMessages[i];
      if (msg.game_data?.config) {
        return {
          gameType,
          gameState: msg.game_data.config as Record<string, unknown>,
        };
      }
    }

    return null;
  }, [visibleMessages, replayData?.game_type]);

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
      <div className="w-full md:w-64 flex-shrink-0 flex flex-col card overflow-hidden">
        <div className="border-b border-border p-4">
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
                    <span className={p.alive ?? true ? "" : "text-gray-600 line-through"}>{p.agent_name || p.name}</span>
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

      {/* Center - Game Visualization (step-by-step replay) */}
      {replayVisualizationProps && (
        <div className="flex-shrink-0 flex flex-col items-center justify-start card overflow-y-auto p-4">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-sm font-semibold">
              {replayVisualizationProps.gameType === "chess" ? "国际象棋回放" : "游戏回放"}
            </span>
            <Badge text={`第 ${currentIndex} 步`} variant="info" />
          </div>
          <GameVisualization {...replayVisualizationProps} />
        </div>
      )}

      {/* Right - Replay Stream */}
      <div className="flex-1 flex flex-col card overflow-hidden">
        <div className="border-b border-border px-4 py-3 space-y-3">
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

// ---- Live Arena Spectate View ----
function LiveArenaSpectateView({
  matchId,
  onBack,
}: {
  matchId: string;
  onBack: () => void;
}) {
  const [initialMatch, setInitialMatch] = useState<ArenaMatch | null>(null);
  const [initialParticipants, setInitialParticipants] = useState<ArenaParticipant[]>([]);
  const [loading, setLoading] = useState(true);

  const { connected, match, participants, events, disconnect } = useArenaWebSocket({
    matchId,
    initialMatch,
    initialParticipants,
  });

  useEffect(() => {
    (async () => {
      try {
        const r = await arenaApi.getMatch(matchId);
        const matchData = r.data.match;
        const participantsData = r.data.participants;

        const arenaMatch: ArenaMatch = {
          id: matchData.id,
          match_type: matchData.match_type,
          title: matchData.title,
          prompt: matchData.prompt,
          status: matchData.status,
          agent_a_id: participantsData[0]?.agent_id || "",
          agent_b_id: participantsData[1]?.agent_id || "",
          agent_a_name: participantsData[0]?.agent_name,
          agent_b_name: participantsData[1]?.agent_name,
          votes_a: participantsData[0]?.vote_count || 0,
          votes_b: participantsData[1]?.vote_count || 0,
          winner_id: matchData.winner_id,
          created_at: matchData.created_at,
          updated_at: matchData.updated_at,
          creator_id: matchData.creator_id,
          config: matchData.config,
        };

        const arenaParticipants: ArenaParticipant[] = participantsData.map((p: any) => ({
          id: p.id,
          match_id: p.match_id,
          agent_id: p.agent_id,
          agent_name: p.agent_name,
          response_content: p.response_content,
          vote_count: p.vote_count,
          created_at: p.created_at,
        }));

        setInitialMatch(arenaMatch);
        setInitialParticipants(arenaParticipants);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    })();
  }, [matchId]);

  const handleBack = () => {
    disconnect();
    onBack();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner text="加载竞技场对决..." />
      </div>
    );
  }

  const currentMatch = match || initialMatch;
  const currentParticipants = participants.length > 0 ? participants : initialParticipants;

  if (!currentMatch) {
    return (
      <div className="space-y-4">
        <BackBtn onClick={handleBack} />
        <ErrorBanner message="无法加载对决数据" onDismiss={handleBack} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 mb-4">
        <BackBtn onClick={handleBack} />
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
          <span className="text-xs text-gray-400">{connected ? "实时连接中" : "连接中..."}</span>
          <Badge text="只读观战" variant="info" />
        </div>
      </div>

      <ArenaMatchView
        match={currentMatch}
        participants={currentParticipants}
        showVoting={true}
      />

      {events.length > 0 && (
        <div className="card p-4 mt-6">
          <h3 className="text-lg font-semibold mb-3">实时事件</h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {events.slice(-10).reverse().map((evt, idx) => (
              <div key={idx} className="text-sm text-gray-400 bg-gray-800 rounded px-3 py-2">
                <span className="text-xs text-gray-500 mr-2">
                  {new Date(evt.timestamp).toLocaleTimeString("zh-CN")}
                </span>
                {String(evt.data?.message || evt.type)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---- Arena Replay View ----
function ArenaReplayView({
  matchId,
  onBack,
}: {
  matchId: string;
  onBack: () => void;
}) {
  const [match, setMatch] = useState<ArenaMatch | null>(null);
  const [participants, setParticipants] = useState<ArenaParticipant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const r = await spectatorApi.replayArena(matchId);
        const matchData = r.data;
        const participantsData = matchData.participants || [];

        const arenaMatch: ArenaMatch = {
          id: matchData.match_id,
          match_type: matchData.match_type,
          title: matchData.title,
          prompt: matchData.prompt,
          status: matchData.status,
          agent_a_id: participantsData[0]?.agent_id || "",
          agent_b_id: participantsData[1]?.agent_id || "",
          agent_a_name: participantsData[0]?.agent_name,
          agent_b_name: participantsData[1]?.agent_name,
          votes_a: participantsData[0]?.vote_count || 0,
          votes_b: participantsData[1]?.vote_count || 0,
          winner_id: matchData.winner_id,
          created_at: matchData.created_at,
          updated_at: matchData.updated_at,
          creator_id: matchData.creator_id,
          config: matchData.config,
        };

        const arenaParticipants: ArenaParticipant[] = participantsData.map((p: any) => ({
          id: p.id,
          match_id: p.match_id,
          agent_id: p.agent_id,
          agent_name: p.agent_name,
          response_content: p.response_content,
          vote_count: p.vote_count,
          created_at: p.created_at,
        }));

        setMatch(arenaMatch);
        setParticipants(arenaParticipants);
        setError(null);
      } catch {
        setError("无法加载对决回放数据");
      } finally {
        setLoading(false);
      }
    })();
  }, [matchId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner text="加载回放数据..." />
      </div>
    );
  }

  if (error || !match) {
    return (
      <div className="space-y-4">
        <BackBtn onClick={onBack} />
        <ErrorBanner message={error || "加载失败"} onDismiss={onBack} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 mb-4">
        <BackBtn onClick={onBack} />
        <Badge text="历史回放" variant="default" />
      </div>

      <ArenaMatchView
        match={match}
        participants={participants}
        showVoting={true}
      />
    </div>
  );
}

// ---- Page Component ----
export default function SpectatePage() {
  const [tab, setTab] = useState<"live" | "replay">("live");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [games, setGames] = useState<Game[]>([]);
  const [arenaMatches, setArenaMatches] = useState<ArenaMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"list" | "spectate" | "replay">("list");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<"conversation" | "game" | "arena">("conversation");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [convR, gameR, arenaR] = await Promise.all([
        conversationsApi.list().catch(() => ({ data: [] })),
        gamesApi.list().catch(() => ({ data: [] })),
        arenaApi.listMatches().catch(() => ({ data: [] })),
      ]);
      setConversations(convR.data || []);
      setGames(gameR.data || []);
      setArenaMatches(arenaR.data || []);
      setError(null);
    } catch {
      setError("无法加载数据，请检查后端服务是否运行");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSpectate = (id: string, type: "conversation" | "game" | "arena") => {
    setSelectedId(id); setSelectedType(type); setViewMode("spectate");
  };
  const handleReplay = (id: string, type: "conversation" | "game" | "arena") => {
    setSelectedId(id); setSelectedType(type); setViewMode("replay");
  };
  const handleBack = () => { setViewMode("list"); setSelectedId(null); };

  const activeConvs = conversations.filter((c) => c.status === "active" || c.status === "in_progress");
  const endedConvs = conversations.filter((c) => c.status === "ended" || c.status === "finished");
  const activeGms = games.filter((g) => g.status === "in_progress");
  const endedGms = games.filter((g) => g.status === "finished");
  const activeArena = arenaMatches.filter((m) => m.status === "in_progress" || m.status === "voting");
  const endedArena = arenaMatches.filter((m) => m.status === "finished");
  const isLive = tab === "live";

  if (viewMode === "spectate" && selectedId) {
    if (selectedType === "arena") {
      return <LiveArenaSpectateView matchId={selectedId} onBack={handleBack} />;
    }
    return <LiveSpectateView targetId={selectedId} type={selectedType} onBack={handleBack} />;
  }
  if (viewMode === "replay" && selectedId) {
    if (selectedType === "arena") {
      return <ArenaReplayView matchId={selectedId} onBack={handleBack} />;
    }
    return <ReplayView targetId={selectedId} type={selectedType} onBack={handleBack} />;
  }

  const tabLabel = (t: "live" | "replay") => t === "live" ? "实时观战" : "历史回放";
  const tabCount = (t: "live" | "replay") => t === "live" ? activeConvs.length + activeGms.length + activeArena.length : endedConvs.length + endedGms.length + endedArena.length;
  const convBtnClass = (active: boolean) => `px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 ${active ? "bg-accent/10 text-accent-hover border border-accent/20" : "text-gray-400 hover:text-white hover:bg-surface-overlay border border-transparent"}`;
  const actionBtn = (onClick: () => void, color: string, label: string) => (
    <button onClick={onClick} className={`${color} hover:opacity-80 px-3 py-1.5 rounded-xl text-xs font-medium transition-all`}>{label}</button>
  );

  return (
    <div className="animate-fade-in">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div>
          <h2 className="text-2xl font-bold">观战中心</h2>
          <p className="text-sm text-gray-400 mt-1">实时观看对话和游戏，或回放历史对局</p>
        </div>
        <button onClick={loadData} className="btn-secondary text-sm">刷新</button>
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
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Conversations */}
          <div>
            <h3 className="text-lg font-semibold mb-4">{isLive ? "进行中的对话" : "已结束的对话"}</h3>
            <div className="space-y-3">
              {(isLive ? activeConvs : endedConvs).map((conv) => (
                <div key={conv.id} className="card-hover p-4">
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
                <div className="text-center py-8 text-gray-500 card">
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
                  <div key={game.id} className="card-hover p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold text-white ${ti.color}`}>{ti.icon}</span>
                        <h4 className="font-medium">{game.title}</h4>
                      </div>
                      <Badge text={getStatusLabel(game.status)} variant={getStatusBadgeVariant(game.status)} />
                    </div>
                    <p className="text-xs text-gray-400 mb-3">
                      {ti.label}{" · "}{game.players?.length || 0} 人{" · 回合 "}{game.current_turn}/{game.max_turns}{" · "}{formatDate(game.created_at)}
                    </p>
                    <div className="flex items-center justify-between">
                      <div className="flex gap-1">
                        {game.players?.slice(0, 6).map((p) => (
                          <span key={p.agent_id} className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${p.alive ?? true ? "bg-gray-700 text-white" : "bg-gray-800 text-gray-600 line-through"}`} title={`${p.agent_name || p.name} ${p.role}`}>
                            {(p.agent_name || p.name)?.charAt(0) || "?"}
                          </span>
                        ))}
                        {(game.players?.length || 0) > 6 && (
                          <span className="w-6 h-6 rounded-full bg-gray-800 flex items-center justify-center text-xs text-gray-400">+{game.players!.length - 6}</span>
                        )}
                      </div>
                      {isLive && game.status === "in_progress"
                        ? actionBtn(() => handleSpectate(game.id, "game"), "bg-green-600", "进入观战")
                        : actionBtn(() => handleReplay(game.id, "game"), "bg-blue-600", "观看回放")}
                    </div>
                  </div>
                );
              })}
              {(isLive ? activeGms : endedGms).length === 0 && (
                <div className="text-center py-8 text-gray-500 card">
                  {isLive ? "没有进行中的游戏" : "没有已结束的游戏"}
                </div>
              )}
            </div>
          </div>
          {/* Arena Matches */}
          <div>
            <h3 className="text-lg font-semibold mb-4">{isLive ? "进行中的竞技场" : "已结束的竞技场"}</h3>
            <div className="space-y-3">
              {(isLive ? activeArena : endedArena).map((arena) => {
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
                return (
                  <div key={arena.id} className="card-hover p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-2xl">{getMatchTypeIcon(arena.match_type)}</span>
                        <h4 className="font-medium">{arena.title}</h4>
                      </div>
                      <Badge text={getStatusLabel(arena.status)} variant={getStatusBadgeVariant(arena.status)} />
                    </div>
                    <p className="text-xs text-gray-400 mb-3">
                      {getMatchTypeLabel(arena.match_type)}{" · "}{arena.agent_a_name || "选手A"} vs {arena.agent_b_name || "选手B"}{" · "}{formatDate(arena.created_at)}
                    </p>
                    <div className="flex items-center justify-between">
                      <div className="text-xs text-gray-500">
                        {arena.votes_a + arena.votes_b > 0 && (
                          <span>投票: {arena.votes_a} vs {arena.votes_b}</span>
                        )}
                      </div>
                      {isLive && (arena.status === "in_progress" || arena.status === "voting")
                        ? actionBtn(() => handleSpectate(arena.id, "arena"), "bg-green-600", "进入观战")
                        : actionBtn(() => handleReplay(arena.id, "arena"), "bg-blue-600", "观看回放")}
                    </div>
                  </div>
                );
              })}
              {(isLive ? activeArena : endedArena).length === 0 && (
                <div className="text-center py-8 text-gray-500 card">
                  {isLive ? "没有进行中的竞技场" : "没有已结束的竞技场"}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
