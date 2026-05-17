"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { gamesApi, agentsApi } from "@/lib/api";
import { ErrorBanner, Badge, LoadingSpinner } from "@/components";

// ---- Types ----
interface Agent {
  id: string;
  name: string;
  level: number;
}

interface GamePlayer {
  agent_id: string;
  agent_name: string;
  role: string;
  alive: boolean;
  eliminated_turn?: number;
}

interface GameLog {
  id: string;
  turn: number;
  agent_id?: string;
  agent_name?: string;
  content: string;
  log_type: "action" | "speech" | "vote" | "system" | "elimination";
  created_at: string;
}

interface Game {
  id: string;
  game_type: string;
  title: string;
  status: string;
  current_turn: number;
  max_turns: number;
  players: GamePlayer[];
  config: Record<string, unknown>;
  created_at: string;
}

const GAME_TYPES = [
  { value: "werewolf", label: "狼人杀", desc: "智能体扮演角色，进行社交推理博弈", color: "bg-red-600", icon: "W", minPlayers: 4 },
  { value: "debate", label: "辩论赛", desc: "正反方结构化辩论对决", color: "bg-blue-600", icon: "D", minPlayers: 2 },
  { value: "chess", label: "棋类", desc: "围棋、象棋等策略对弈", color: "bg-green-600", icon: "C", minPlayers: 2 },
  { value: "adventure", label: "文字冒险", desc: "合作解谜、探索未知世界", color: "bg-purple-600", icon: "A", minPlayers: 2 },
  { value: "negotiation", label: "谈判", desc: "囚徒困境、资源分配等博弈论场景", color: "bg-yellow-600", icon: "N", minPlayers: 2 },
];

function getGameTypeInfo(type: string) {
  return GAME_TYPES.find((t) => t.value === type) || GAME_TYPES[0];
}

function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    waiting: "等待中",
    active: "进行中",
    finished: "已结束",
    paused: "已暂停",
  };
  return map[status] || status;
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
  const [gameLogs, setGameLogs] = useState<GameLog[]>([]);
  const [gameState, setGameState] = useState<Record<string, unknown> | null>(null);
  const [filter, setFilter] = useState<"all" | "waiting" | "active" | "finished">("all");
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const loadGames = useCallback(async () => {
    try {
      setLoading(true);
      const r = await gamesApi.list();
      setGames(r.data);
      setError(null);
    } catch {
      setError("无法加载游戏列表，请检查后端服务是否运行");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAgents = useCallback(async () => {
    try {
      const r = await agentsApi.list();
      setAgents(r.data);
    } catch {
      // Agent list failure is non-critical
    }
  }, []);

  useEffect(() => {
    loadGames();
    loadAgents();
  }, [loadGames, loadAgents]);

  const loadGameDetail = useCallback(async (gameId: string) => {
    try {
      const r = await gamesApi.get(gameId);
      setActiveGame(r.data);
      const stateR = await gamesApi.getState(gameId);
      setGameLogs(stateR.data.logs || []);
      setGameState(stateR.data);
    } catch {
      setActiveGame(null);
      setGameLogs([]);
      setGameState(null);
    }
  }, []);

  useEffect(() => {
    if (activeGameId) {
      loadGameDetail(activeGameId);
    }
  }, [activeGameId, loadGameDetail]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [gameLogs]);

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
    } catch {
      setError("创建失败");
    }
  };

  const handleStartGame = async (gameId: string) => {
    try {
      await gamesApi.start(gameId);
      await loadGames();
      if (activeGameId === gameId) await loadGameDetail(gameId);
    } catch {
      setError("启动失败");
    }
  };

  const handleProcessTurn = async () => {
    if (!activeGameId || isProcessing) return;
    setIsProcessing(true);
    try {
      await gamesApi.processTurn(activeGameId);
      await loadGameDetail(activeGameId);
      await loadGames();
    } catch {
      setError("回合处理失败");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleEndGame = async (gameId: string) => {
    if (!confirm("确定要结束这个游戏吗？")) return;
    try {
      await gamesApi.end(gameId);
      await loadGames();
      if (activeGameId === gameId) await loadGameDetail(gameId);
    } catch {
      setError("结束失败");
    }
  };

  const toggleAgent = (id: string) => {
    setSelectedAgentIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const filteredGames = filter === "all" ? games : games.filter((g) => g.status === filter);

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <h2 className="text-2xl font-bold">游戏房间</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
        >
          {showCreate ? "取消" : "创建游戏"}
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <ErrorBanner message={error} onDismiss={() => setError(null)} />
      )}

      {/* Create Game Form */}
      {showCreate && (
        <form onSubmit={handleCreate} className="bg-gray-900 p-6 rounded-xl mb-6 space-y-4">
          <h3 className="text-lg font-semibold">创建游戏</h3>

          {/* Game Type */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">选择游戏类型</label>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {GAME_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setSelectedGameType(t.value)}
                  className={`p-4 rounded-lg text-left transition-all ${
                    selectedGameType === t.value
                      ? "ring-2 ring-blue-500 bg-gray-700"
                      : "bg-gray-800 hover:bg-gray-700"
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
              <input
                placeholder="给游戏取个名字"
                value={gameTitle}
                onChange={(e) => setGameTitle(e.target.value)}
                className="w-full bg-gray-800 rounded-lg px-4 py-2"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">最大回合数</label>
              <input
                type="number"
                min={1}
                max={100}
                value={maxTurns}
                onChange={(e) => setMaxTurns(parseInt(e.target.value) || 20)}
                className="w-full bg-gray-800 rounded-lg px-4 py-2"
              />
            </div>
          </div>

          {/* Agent Selection */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              选择参与智能体 ({selectedAgentIds.length} 已选)
            </label>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-40 overflow-y-auto">
              {agents.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => toggleAgent(a.id)}
                  className={`p-2 rounded-lg text-sm text-left transition-colors ${
                    selectedAgentIds.includes(a.id)
                      ? "bg-blue-600 text-white"
                      : "bg-gray-800 text-gray-300 hover:bg-gray-700"
                  }`}
                >
                  {a.name}
                  <span className="text-xs opacity-70 ml-1">Lv.{a.level || 1}</span>
                </button>
              ))}
            </div>
          </div>

          <button type="submit" className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
            创建游戏
          </button>
        </form>
      )}

      <div className="flex gap-6">
        {/* Game List */}
        <div className="flex-1">
          {/* Filter Tabs */}
          <div className="flex gap-2 mb-4">
            {(["all", "waiting", "active", "finished"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-lg text-sm ${
                  filter === f ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {f === "all" ? "全部" : getStatusLabel(f)}
                <span className="ml-1 text-xs opacity-70">
                  ({f === "all" ? games.length : games.filter((g) => g.status === f).length})
                </span>
              </button>
            ))}
          </div>

          {/* Game Cards */}
          {loading ? (
            <div className="flex justify-center py-12"><LoadingSpinner /></div>
          ) : (
          <div className="space-y-3">
            {filteredGames.map((game) => {
              const typeInfo = getGameTypeInfo(game.game_type);
              const alivePlayers = game.players?.filter((p) => p.alive).length || 0;
              return (
                <div
                  key={game.id}
                  className={`bg-gray-900 p-4 rounded-xl cursor-pointer transition-colors ${
                    activeGameId === game.id ? "ring-2 ring-blue-500" : "hover:bg-gray-800"
                  }`}
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
                      text={getStatusLabel(game.status)}
                      variant={game.status === "active" ? "success" : game.status === "waiting" || game.status === "paused" ? "warning" : "default"}
                      size="sm"
                    />
                  </div>
                  <p className="text-xs text-gray-400">
                    {typeInfo.label} · {game.players?.length || 0} 人 · 回合 {game.current_turn}/{game.max_turns}
                    {game.status === "active" && ` · 存活 ${alivePlayers}`}
                  </p>
                  <div className="flex gap-1 mt-2">
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
                </div>
              );
            })}
            {filteredGames.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                {filter === "all" ? "还没有游戏，点击上方按钮创建" : `没有${getStatusLabel(filter)}的游戏`}
              </div>
            )}
          </div>
          )}
        </div>

        {/* Game Room (Right Panel) */}
        {activeGameId && activeGame && (
          <div className="w-96 flex-shrink-0 bg-gray-900 rounded-xl flex flex-col overflow-hidden" style={{ height: "calc(100vh - 220px)" }}>
            {/* Game Header */}
            <div className="border-b border-gray-800 p-4">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-bold">{activeGame.title}</h3>
                  <p className="text-xs text-gray-400">
                    {getGameTypeInfo(activeGame.game_type).label} · 回合 {activeGame.current_turn}/{activeGame.max_turns}
                  </p>
                </div>
                <Badge
                  text={getStatusLabel(activeGame.status)}
                  variant={activeGame.status === "active" ? "success" : activeGame.status === "waiting" || activeGame.status === "paused" ? "warning" : "default"}
                  size="sm"
                />
              </div>

              {/* Controls */}
              <div className="flex gap-2 mt-3">
                {activeGame.status === "waiting" && (
                  <button
                    onClick={() => handleStartGame(activeGame.id)}
                    className="bg-green-600 hover:bg-green-700 px-3 py-1.5 rounded-lg text-xs"
                  >
                    开始游戏
                  </button>
                )}
                {activeGame.status === "active" && (
                  <>
                    <button
                      onClick={handleProcessTurn}
                      disabled={isProcessing}
                      className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 px-3 py-1.5 rounded-lg text-xs"
                    >
                      {isProcessing ? "处理中..." : "下一回合"}
                    </button>
                    <button
                      onClick={() => handleEndGame(activeGame.id)}
                      className="bg-red-600 hover:bg-red-700 px-3 py-1.5 rounded-lg text-xs"
                    >
                      结束
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Players */}
            <div className="border-b border-gray-800 p-4">
              <h4 className="text-xs text-gray-400 mb-2">玩家列表</h4>
              <div className="space-y-1">
                {activeGame.players?.map((p) => (
                  <div key={p.agent_id} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${p.alive ? "bg-green-500" : "bg-red-500"}`} />
                      <span className={p.alive ? "" : "text-gray-600 line-through"}>{p.agent_name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">{p.role}</span>
                      {!p.alive && p.eliminated_turn && (
                        <span className="text-xs text-red-400">T{p.eliminated_turn}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Game State */}
            {gameState && (
              <div className="border-b border-gray-800 p-4">
                <h4 className="text-xs text-gray-400 mb-2">游戏状态</h4>
                <div className="text-xs text-gray-300 space-y-1">
                  {Object.entries(gameState)
                    .filter(([k]) => !["logs", "players"].includes(k))
                    .slice(0, 5)
                    .map(([k, v]) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-gray-500">{k}</span>
                        <span>{typeof v === "object" ? JSON.stringify(v).slice(0, 30) : String(v)}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Game Logs */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              <h4 className="text-xs text-gray-400 mb-2">游戏日志</h4>
              {gameLogs.map((log) => (
                <div
                  key={log.id}
                  className={`text-sm rounded-lg px-3 py-2 ${
                    log.log_type === "system"
                      ? "bg-gray-800 text-gray-400 text-center text-xs"
                      : log.log_type === "elimination"
                      ? "bg-red-900/30 text-red-300"
                      : log.log_type === "vote"
                      ? "bg-yellow-900/30 text-yellow-300"
                      : "bg-gray-800"
                  }`}
                >
                  {log.agent_name && (
                    <span className="font-medium text-blue-400">{log.agent_name}: </span>
                  )}
                  {log.content}
                  <span className="text-xs text-gray-600 ml-2">T{log.turn}</span>
                </div>
              ))}
              {gameLogs.length === 0 && (
                <p className="text-center text-gray-500 text-sm py-4">暂无日志</p>
              )}
              <div ref={logsEndRef} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
