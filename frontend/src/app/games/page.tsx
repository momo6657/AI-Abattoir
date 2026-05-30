"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { gamesApi, agentsApi } from "@/lib/api";
import { GAME_TYPES } from "@/lib/constants";
import { getGameTypeInfo } from "@/lib/constants";
import { getStatusLabel } from "@/lib/utils";
import { extractErrorMessage } from "@/lib/errors";
import { ErrorBanner, Badge, LoadingSpinner } from "@/components";
import { useGameWebSocket } from "@/hooks/useGameWebSocket";
import GameControlBar from "@/components/games/GameControlBar";
import ChessBoard from "@/components/games/ChessBoard";
import WerewolfPanel from "@/components/games/WerewolfPanel";
import DebatePanel from "@/components/games/DebatePanel";
import AdventurePanel from "@/components/games/AdventurePanel";
import NegotiationPanel from "@/components/games/NegotiationPanel";

// ---- Types ----
interface Agent {
  id: string;
  name: string;
  level: number;
}

interface Game {
  id: string;
  game_type: string;
  title: string;
  status: string;
  current_turn: number;
  max_turns: number;
  players: { agent_id: string; name: string; role?: string; alive?: boolean }[];
  config: Record<string, unknown>;
  winner_id: string | null;
  created_at: string;
}

function getGameStatusLabel(status: string): string {
  return getStatusLabel(status);
}

// ---- Page Component ----
export default function GamesPage() {
  const [games, setGames] = useState<Game[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedGameType, setSelectedGameType] = useState("");
  const [gameTitle, setGameTitle] = useState("");
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([]);
  const [maxTurns, setMaxTurns] = useState(20);
  const [activeGameId, setActiveGameId] = useState<string | null>(null);
  const [activeGame, setActiveGame] = useState<Game | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorRetryFn, setErrorRetryFn] = useState<(() => void) | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "waiting" | "in_progress" | "paused" | "finished">("all");

  const { events, connected, send, clearEvents } = useGameWebSocket(activeGameId);
  const processedEventCountRef = useRef(0);

  const loadGames = useCallback(async () => {
    try {
      setLoading(true);
      const r = await gamesApi.list();
      setGames(r.data);
      setError(null);
      setErrorRetryFn(null);
    } catch (err) {
      setError(extractErrorMessage(err, "无法加载游戏列表"));
      setErrorRetryFn(() => loadGames);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAgents = useCallback(async () => {
    try {
      const r = await agentsApi.list();
      setAgents(r.data);
    } catch { /* non-critical */ }
  }, []);

  useEffect(() => { loadGames(); loadAgents(); }, [loadGames, loadAgents]);

  useEffect(() => {
    processedEventCountRef.current = 0;
  }, [activeGameId]);

  // 加载游戏详情
  const loadGameDetail = useCallback(async (gameId: string) => {
    try {
      const r = await gamesApi.get(gameId);
      setActiveGame(r.data);
      clearEvents();
    } catch (err) {
      setActiveGame(null);
      setError(extractErrorMessage(err, "无法加载游戏详情"));
    }
  }, [clearEvents]);

  useEffect(() => {
    if (activeGameId) loadGameDetail(activeGameId);
  }, [activeGameId, loadGameDetail]);

  // WebSocket 事件更新游戏状态
  useEffect(() => {
    if (activeGame && events.length > processedEventCountRef.current) {
      const newEvents = events.slice(processedEventCountRef.current);
      processedEventCountRef.current = events.length;
      const lastEvent = newEvents[newEvents.length - 1];
      const data = lastEvent.data || {};
      if ("config" in data || "current_turn" in data || "status" in data) {
        setActiveGame(prev => prev ? {
          ...prev,
          current_turn: (data.current_turn as number) || prev.current_turn,
          status: (data.status as string) || prev.status,
          config: { ...prev.config, ...(data.config as Record<string, unknown> || {}) },
        } : prev);
      }
      if (lastEvent.type === "game_over" || lastEvent.type === "max_turns_reached") {
        setActiveGame(prev => prev ? { ...prev, status: "finished" } : prev);
      }
      if (lastEvent.type === "paused") {
        setActiveGame(prev => prev ? { ...prev, status: "paused" } : prev);
      }
      if (lastEvent.type === "resumed") {
        setActiveGame(prev => prev ? { ...prev, status: "in_progress" } : prev);
      }
    }
  }, [events, activeGame?.id]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedGameType || !gameTitle.trim() || selectedAgentIds.length === 0) return;
    try {
      await gamesApi.create({
        game_type: selectedGameType,
        title: gameTitle,
        agent_ids: selectedAgentIds,
        max_turns: maxTurns,
        config: {},
      });
      await loadGames();
      setShowCreate(false);
      setSelectedGameType("");
      setGameTitle("");
      setSelectedAgentIds([]);
      setMaxTurns(20);
    } catch (err) {
      setError(extractErrorMessage(err, "创建游戏失败"));
    }
  };

  const handleStartGame = async (gameId: string) => {
    try {
      await gamesApi.start(gameId);
      await loadGameDetail(gameId);
      await loadGames();
    } catch (err) {
      setError(extractErrorMessage(err, "启动游戏失败"));
    }
  };

  const handlePause = async () => {
    if (!activeGameId) return;
    try {
      await gamesApi.pause(activeGameId);
      await loadGameDetail(activeGameId);
    } catch (err) {
      setError(extractErrorMessage(err, "暂停失败"));
    }
  };

  const handleResume = async () => {
    if (!activeGameId) return;
    try {
      await gamesApi.resume(activeGameId);
      await loadGameDetail(activeGameId);
    } catch (err) {
      setError(extractErrorMessage(err, "恢复失败"));
    }
  };

  const handleEndGame = async (gameId: string) => {
    if (!confirm("确定要结束这个游戏吗？")) return;
    try {
      await gamesApi.end(gameId);
      await loadGameDetail(gameId);
      await loadGames();
    } catch (err) {
      setError(extractErrorMessage(err, "结束游戏失败"));
    }
  };

  const handleSpeedChange = (speed: number) => {
    send({ type: "set_speed", speed });
  };

  const toggleAgent = (id: string) => {
    setSelectedAgentIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const filteredGames = filter === "all"
    ? games
    : games.filter(g => g.status === filter);

  // 提取游戏特定数据
  const gameConfig = activeGame?.config || {};
  const liveEvents = events.filter(e => e.type !== "game_state" && e.type !== "pong");
  const storedEvents = Array.isArray(gameConfig.events) ? gameConfig.events as typeof liveEvents : [];
  const gameEventsList = liveEvents.length > 0 ? liveEvents : storedEvents;

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold gradient-text">游戏房间</h2>
          <p className="text-sm text-gray-400 mt-1">让 AI 智能体在博弈中碰撞智慧</p>
        </div>
        <button onClick={() => setShowCreate(!showCreate)} className={showCreate ? "btn-secondary" : "btn-primary"}>
          {showCreate ? "取消" : "创建游戏"}
        </button>
      </div>

      {error && (
        <ErrorBanner
          message={error}
          onDismiss={() => { setError(null); setErrorRetryFn(null); }}
          onRetry={errorRetryFn || undefined}
        />
      )}

      {/* Create Game Form */}
      {showCreate && (
        <form onSubmit={handleCreate} className="card p-6 mb-6 space-y-4 animate-slide-up">
          <h3 className="text-lg font-semibold">创建游戏</h3>
          <div>
            <label className="block text-sm text-gray-400 mb-2">选择游戏类型</label>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {GAME_TYPES.map(t => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setSelectedGameType(t.value)}
                  className={`p-4 rounded-xl text-left transition-all ${
                    selectedGameType === t.value
                      ? "ring-2 ring-accent bg-surface-overlay"
                      : "bg-surface-overlay hover:bg-surface-overlay/80 border border-border hover:border-border-hover"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-8 h-8 rounded flex items-center justify-center text-sm font-bold text-white ${t.color}`}>
                      {t.icon}
                    </span>
                    <span className="font-medium">{t.label}</span>
                  </div>
                  <p className="text-xs text-gray-400">{t.desc}</p>
                  <p className="text-xs text-gray-500 mt-1">最少 {t.minPlayers} 人</p>
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">游戏标题</label>
              <input placeholder="给游戏取个名字" value={gameTitle} onChange={e => setGameTitle(e.target.value)} className="input-field" required />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">最大回合数</label>
              <input type="number" min={1} max={100} value={maxTurns} onChange={e => setMaxTurns(parseInt(e.target.value) || 20)} className="input-field" />
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">选择参与智能体 ({selectedAgentIds.length} 已选)</label>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-40 overflow-y-auto">
              {agents.map(a => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => toggleAgent(a.id)}
                  className={`p-2 rounded-xl text-sm text-left transition-colors ${
                    selectedAgentIds.includes(a.id) ? "bg-accent text-white" : "bg-surface-overlay text-gray-300 hover:bg-surface-overlay/80 border border-border"
                  }`}
                >
                  {a.name}
                  <span className="text-xs opacity-70 ml-1">Lv.{a.level || 1}</span>
                </button>
              ))}
            </div>
          </div>
          <button type="submit" className="btn-primary">创建游戏</button>
        </form>
      )}

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Game List */}
        <div className="min-w-0 flex-1">
          <div className="mb-4 flex gap-2 overflow-x-auto pb-1">
            {(["all", "waiting", "in_progress", "paused", "finished"] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-xl text-sm transition-all duration-200 ${
                  filter === f ? "bg-accent text-white shadow-lg shadow-accent/25" : "btn-ghost"
                }`}
              >
                {f === "all" ? "全部" : getGameStatusLabel(f)}
                <span className="ml-1 text-xs opacity-70">
                  ({f === "all" ? games.length : games.filter(g => g.status === f).length})
                </span>
              </button>
            ))}
          </div>

          {loading ? (
            <div className="flex justify-center py-12"><LoadingSpinner /></div>
          ) : (
            <div className="space-y-3">
              {filteredGames.map(game => {
                const typeInfo = getGameTypeInfo(game.game_type);
                return (
                  <div
                    key={game.id}
                    className={`card-hover p-4 cursor-pointer ${activeGameId === game.id ? "ring-2 ring-accent" : ""}`}
                    onClick={() => setActiveGameId(game.id)}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold text-white ${typeInfo.color}`}>
                          {typeInfo.icon}
                        </span>
                        <h3 className="font-semibold">{game.title}</h3>
                      </div>
                      <Badge
                        text={getGameStatusLabel(game.status)}
                        variant={game.status === "in_progress" ? "success" : game.status === "waiting" || game.status === "paused" ? "warning" : "default"}
                        size="sm"
                      />
                    </div>
                    <p className="text-xs text-gray-400">
                      {typeInfo.label} · {game.players?.length || 0} 人 · 回合 {game.current_turn}/{game.max_turns}
                    </p>
                    <div className="flex gap-1 mt-2">
                      {game.players?.slice(0, 6).map(p => (
                        <span key={p.agent_id} className="w-6 h-6 rounded-full bg-surface-overlay flex items-center justify-center text-xs font-bold text-white" title={p.name}>
                          {p.name?.charAt(0) || "?"}
                        </span>
                      ))}
                      {(game.players?.length || 0) > 6 && (
                        <span className="w-6 h-6 rounded-full bg-surface-overlay flex items-center justify-center text-xs text-gray-400">
                          +{(game.players?.length || 0) - 6}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
              {filteredGames.length === 0 && (
                <div className="card p-12 text-center">
                  <p className="text-gray-500">没有{filter === "all" ? "" : getGameStatusLabel(filter)}的游戏</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Game Room (Right Panel) */}
        {activeGameId && activeGame && (
          <div className="card flex max-h-[760px] min-h-[520px] w-full flex-col overflow-hidden lg:sticky lg:top-24 lg:w-[480px] lg:flex-shrink-0" style={{ height: "calc(100vh - 220px)" }}>
            {/* Game Control Bar */}
            <GameControlBar
              status={activeGame.status as 'waiting' | 'in_progress' | 'paused' | 'finished' | 'cancelled'}
              currentTurn={activeGame.current_turn}
              maxTurns={activeGame.max_turns}
              connected={connected}
              onStart={() => handleStartGame(activeGame.id)}
              onPause={handlePause}
              onResume={handleResume}
              onSpeedChange={handleSpeedChange}
            />

            {/* Game-specific visualization */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {/* Chess */}
              {activeGame.game_type === "chess" && (
                <ChessBoard
                  board={gameConfig.board as Record<string, [string, string]> || {}}
                  lastMove={gameConfig.last_move as { from: string; to: string } | null}
                  inCheck={gameConfig.in_check as string | null}
                />
              )}

              {/* Werewolf */}
              {activeGame.game_type === "werewolf" && (
                <WerewolfPanel
                  players={(activeGame.players || []).map(p => ({
                    ...p,
                    alive: p.alive ?? true,
                  }))}
                  phase={gameConfig.phase as 'night' | 'day' || 'night'}
                  currentTurn={activeGame.current_turn}
                  lastDeath={gameConfig.last_deaths as string[]}
                  voteResult={gameConfig.vote_result as { votes: Record<string, string>; vote_counts: Record<string, number>; exiled: string }}
                  gameOver={gameConfig.game_over as { winner: string; roles: Record<string, string> } | null}
                />
              )}

              {/* Debate */}
              {activeGame.game_type === "debate" && (
                <DebatePanel
                  topic={gameConfig.topic as string || ""}
                  rounds={gameConfig.rounds as { phase: string; side: 'pro' | 'con'; content: string }[] || []}
                  currentPhase={gameConfig.current_phase as string || "opening"}
                  scores={gameConfig.scores as { pro_arguments?: number; pro_logic?: number; pro_expression?: number; con_arguments?: number; con_logic?: number; con_expression?: number; pro_total?: number; con_total?: number; winner?: string; reason?: string } | null}
                />
              )}

              {/* Text Adventure */}
              {activeGame.game_type === "text_adventure" && (
                <AdventurePanel
                  scene={gameConfig.scene as string}
                  options={gameConfig.options as Record<string, string>}
                  lastResult={gameConfig.last_result as { choice: string; result: string; hp_change?: number; item?: string; new_location?: string }}
                  state={gameConfig.adventure_state as { hp: number; max_hp: number; inventory: string[]; current_location: string; explored_locations: string[] } || { hp: 100, max_hp: 100, inventory: [], current_location: "起始之地", explored_locations: ["起始之地"] }}
                  gameOver={gameConfig.game_over as { result: string } | null}
                />
              )}

              {/* Negotiation */}
              {activeGame.game_type === "negotiation" && (
                <NegotiationPanel
                  scenario={gameConfig.scenario as { name: string; description: string; resources?: Record<string, unknown> }}
                  currentProposal={gameConfig.current_proposal as string}
                  turns={gameConfig.turns as { party: 'A' | 'B'; proposal: string; action: 'propose' | 'accept' | 'reject'; reason: string }[] || []}
                  dealReached={gameConfig.deal_reached as string | null}
                  scores={gameConfig.scores as { party_a_score: number; party_b_score: number; fairness: number; evaluation: string } | null}
                />
              )}

              {/* Event Log (shared for all game types) */}
              <div className="mt-4">
                <h4 className="text-xs text-gray-400 mb-2">事件日志</h4>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {gameEventsList.map((evt, i) => {
                    const eventData = (evt.data?.data as Record<string, unknown> | undefined) || evt.data;
                    return (
                      <div key={i} className={`text-sm rounded-xl px-3 py-2 ${
                        evt.type === "game_over" ? "bg-green-900/30 text-green-300" :
                        evt.type === "night_result" ? "bg-gray-800 text-gray-200" :
                        evt.type === "vote_result" ? "bg-yellow-900/30 text-yellow-200" :
                        evt.type === "error" || evt.type === "turn_error" ? "bg-red-900/30 text-red-300" :
                        evt.type === "paused" ? "bg-yellow-900/20 text-yellow-300" :
                        evt.type === "resumed" ? "bg-green-900/20 text-green-300" :
                        "bg-surface-overlay text-gray-200"
                      }`}>
                        <span className="font-medium text-accent-hover">{evt.type}</span>
                        {eventData && <span className="text-gray-300 ml-2">{JSON.stringify(eventData).slice(0, 120)}</span>}
                      </div>
                    );
                  })}
                  {gameEventsList.length === 0 && (
                    <p className="text-center text-gray-500 text-sm py-4">等待事件...</p>
                  )}
                </div>
              </div>

              {/* End game button */}
              {activeGame.status === "in_progress" && (
                <button
                  onClick={() => handleEndGame(activeGame.id)}
                  className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 w-full mt-2"
                >
                  强制结束游戏
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
