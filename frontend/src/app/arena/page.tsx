"use client";

import { useEffect, useState, useCallback } from "react";
import { arenaApi, agentsApi } from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import { ErrorBanner, Badge, ProgressBar, Modal, LoadingSpinner } from "@/components";

// ---- Types ----
interface Agent {
  id: string;
  name: string;
  level: number;
}

interface ArenaMatch {
  id: string;
  match_type: string;
  prompt: string;
  agent_a_id: string;
  agent_b_id: string;
  agent_a_name?: string;
  agent_b_name?: string;
  result_a?: string;
  result_b?: string;
  image_a_url?: string;
  image_b_url?: string;
  audio_a_url?: string;
  audio_b_url?: string;
  participant_a_id?: string;
  participant_b_id?: string;
  status: string;
  votes_a: number;
  votes_b: number;
  winner_id?: string;
  created_at: string;
}

const MATCH_TYPES = [
  { value: "qa_pk", label: "问答 PK", icon: "Q", desc: "同一问题，分别作答，投票选出最佳", color: "bg-blue-600" },
  { value: "code", label: "代码竞赛", icon: "C", desc: "编程题自动评测，运行测试用例评分", color: "bg-green-600" },
  { value: "creative", label: "创意比拼", icon: "A", desc: "同一主题，各自创作，比拼创意", color: "bg-purple-600" },
  { value: "reasoning", label: "推理挑战", icon: "R", desc: "逻辑推理题，考验思维深度", color: "bg-yellow-600" },
  { value: "image_gen", label: "生图对决", icon: "I", desc: "同一 prompt，各模型生成图片，投票评选", color: "bg-pink-600" },
  { value: "voice", label: "配音 PK", icon: "V", desc: "同一文本，各 TTS 模型生成语音，比较效果", color: "bg-red-600" },
];

function getMatchTypeInfo(type: string) {
  return MATCH_TYPES.find((t) => t.value === type) || MATCH_TYPES[0];
}

function isVoteReady(status: string): boolean {
  return status === "voting" || status === "completed" || status === "finished";
}

// ---- Page Component ----
export default function ArenaPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [matches, setMatches] = useState<ArenaMatch[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedType, setSelectedType] = useState("");
  const [agentAId, setAgentAId] = useState("");
  const [agentBId, setAgentBId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [viewingMatch, setViewingMatch] = useState<ArenaMatch | null>(null);
  const [votedMatches, setVotedMatches] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [errorRetryFn, setErrorRetryFn] = useState<(() => void) | null>(null);
  const [loading, setLoading] = useState(true);

  const loadAgents = useCallback(async () => {
    try {
      const r = await agentsApi.list();
      setAgents(r.data);
    } catch {
      // Agent list failure is non-critical
    }
  }, []);

  const loadMatches = useCallback(async () => {
    try {
      setLoading(true);
      const r = await arenaApi.listMatches();
      setMatches(r.data);
      setError(null);
      setErrorRetryFn(null);
    } catch (err) {
      setError(extractErrorMessage(err, "无法加载竞技场数据，请检查后端服务是否运行"));
      setErrorRetryFn(() => loadMatches);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAgents();
    loadMatches();
  }, [loadAgents, loadMatches]);

  const handleCreateMatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedType || !agentAId || !agentBId || !prompt.trim()) return;
    if (agentAId === agentBId) {
      setError("请选择两个不同的智能体");
      return;
    }
    try {
      const res = await arenaApi.createMatch({
        match_type: selectedType,
        prompt,
        agent_ids: [agentAId, agentBId],
      });
      const matchId = res.data?.id;
      // Auto-start the match after creation
      if (matchId) {
        try {
          await arenaApi.startMatch(matchId);
        } catch {
          // Start may fail if the backend auto-starts; non-critical
        }
      }
      await loadMatches();
      setShowCreate(false);
      setSelectedType("");
      setAgentAId("");
      setAgentBId("");
      setPrompt("");
    } catch (err) {
      setError(extractErrorMessage(err, "创建对决失败"));
    }
  };

  const handleVote = async (matchId: string, side: "a" | "b") => {
    if (votedMatches.has(matchId)) return;
    try {
      await arenaApi.vote(matchId, { side });
      setVotedMatches((prev) => new Set(prev).add(matchId));
      await loadMatches();
    } catch (err) {
      setError(extractErrorMessage(err, "投票失败"));
    }
  };

  const getAgentName = (id: string) => {
    const a = agents.find((x) => x.id === id);
    return a ? a.name : id;
  };

  const renderMatchContent = (match: ArenaMatch) => {
    const typeInfo = getMatchTypeInfo(match.match_type);
    const totalVotes = match.votes_a + match.votes_b;
    const pctA = totalVotes > 0 ? Math.round((match.votes_a / totalVotes) * 100) : 50;

    return (
      <div className="space-y-4">
        {/* Prompt */}
        <div className="bg-surface-overlay rounded-lg p-4">
          <p className="text-xs text-gray-400 mb-1">题目 / Prompt</p>
          <p className="text-sm">{match.prompt}</p>
        </div>

        {/* Results Side by Side */}
        <div className="grid grid-cols-2 gap-4">
          {/* Side A */}
          <div className={`rounded-lg p-4 ${match.winner_id === match.agent_a_id ? "ring-2 ring-yellow-500" : ""}`}>
            <div className="flex items-center justify-between mb-3">
              <span className="font-medium text-sm">{getAgentName(match.agent_a_id)}</span>
              {match.winner_id === match.agent_a_id && (
                <span className="text-xs bg-yellow-600 text-white px-2 py-0.5 rounded-full">胜</span>
              )}
            </div>
            {typeInfo.value === "image_gen" && match.image_a_url ? (
              <img src={match.image_a_url} alt="Agent A" className="rounded-lg w-full max-h-64 object-contain bg-surface-overlay" />
            ) : typeInfo.value === "voice" && match.audio_a_url ? (
              <audio controls className="w-full"><source src={match.audio_a_url} /></audio>
            ) : (
              <div className="bg-surface-overlay rounded-lg p-3 text-sm max-h-48 overflow-y-auto whitespace-pre-wrap">
                {match.result_a || <span className="text-gray-500">等待结果...</span>}
              </div>
            )}
            <div className="mt-3">
              {!votedMatches.has(match.id) && isVoteReady(match.status) && (
                <button
                  onClick={() => handleVote(match.id, "a")}
                  className="w-full btn-primary text-xs"
                >
                  投票
                </button>
              )}
            </div>
          </div>

          {/* Side B */}
          <div className={`rounded-lg p-4 ${match.winner_id === match.agent_b_id ? "ring-2 ring-yellow-500" : ""}`}>
            <div className="flex items-center justify-between mb-3">
              <span className="font-medium text-sm">{getAgentName(match.agent_b_id)}</span>
              {match.winner_id === match.agent_b_id && (
                <span className="text-xs bg-yellow-600 text-white px-2 py-0.5 rounded-full">胜</span>
              )}
            </div>
            {typeInfo.value === "image_gen" && match.image_b_url ? (
              <img src={match.image_b_url} alt="Agent B" className="rounded-lg w-full max-h-64 object-contain bg-surface-overlay" />
            ) : typeInfo.value === "voice" && match.audio_b_url ? (
              <audio controls className="w-full"><source src={match.audio_b_url} /></audio>
            ) : (
              <div className="bg-surface-overlay rounded-lg p-3 text-sm max-h-48 overflow-y-auto whitespace-pre-wrap">
                {match.result_b || <span className="text-gray-500">等待结果...</span>}
              </div>
            )}
            <div className="mt-3">
              {!votedMatches.has(match.id) && isVoteReady(match.status) && (
                <button
                  onClick={() => handleVote(match.id, "b")}
                  className="w-full btn-primary text-xs"
                >
                  投票
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Vote Bar */}
        {totalVotes > 0 && (
          <div>
            <div className="flex justify-between text-xs text-gray-400 mb-1">
              <span>{match.votes_a} 票</span>
              <span>{match.votes_b} 票</span>
            </div>
            <ProgressBar value={pctA} color="bg-accent" />
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold gradient-text">竞技场</h2>
          <p className="text-sm text-gray-400 mt-1">让 AI 模型同台竞技，投票选出最强选手</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className={showCreate ? "btn-secondary" : "btn-primary"}
        >
          {showCreate ? "取消" : "发起 PK"}
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <ErrorBanner
          message={error}
          onDismiss={() => { setError(null); setErrorRetryFn(null); }}
          onRetry={errorRetryFn || undefined}
        />
      )}

      {/* Create Match Form */}
      {showCreate && (
        <form onSubmit={handleCreateMatch} className="card p-6 mb-6 space-y-4 animate-slide-up">
          <h3 className="text-lg font-semibold">发起对决</h3>

          {/* Match Type Selection */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">选择竞技类型</label>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {MATCH_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setSelectedType(t.value)}
                  className={`p-3 rounded-xl text-left transition-all border ${
                    selectedType === t.value
                      ? "ring-2 ring-accent border-accent bg-surface-overlay"
                      : "border-border bg-surface-overlay hover:border-border-hover"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold text-white ${t.color}`}>
                      {t.icon}
                    </span>
                    <span className="text-sm font-medium">{t.label}</span>
                  </div>
                  <p className="text-xs text-gray-400">{t.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Agent Selection */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">智能体 A</label>
              <select
                value={agentAId}
                onChange={(e) => setAgentAId(e.target.value)}
                className="input-field"
                required
              >
                <option value="">选择智能体</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">智能体 B</label>
              <select
                value={agentBId}
                onChange={(e) => setAgentBId(e.target.value)}
                className="input-field"
                required
              >
                <option value="">选择智能体</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">题目 / Prompt</label>
            <textarea
              placeholder="输入对决题目..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="input-field h-24 resize-none"
              required
            />
          </div>

          <button type="submit" className="btn-primary">
            开始对决
          </button>
        </form>
      )}

      {/* Match Type Cards & Records */}
      {loading ? (
        <div className="flex justify-center py-16"><LoadingSpinner /></div>
      ) : (
      <>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
        {MATCH_TYPES.map((t) => {
          const count = matches.filter((m) => m.match_type === t.value).length;
          return (
            <div
              key={t.value}
              className="card-hover p-5 cursor-pointer"
              onClick={() => {
                setSelectedType(t.value);
                setShowCreate(true);
              }}
            >
              <div className="flex items-center gap-3 mb-2">
                <span className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg font-bold text-white ${t.color}`}>
                  {t.icon}
                </span>
                <div>
                  <h3 className="font-semibold">{t.label}</h3>
                  <p className="text-xs text-gray-400">{count} 场对决</p>
                </div>
              </div>
              <p className="text-sm text-gray-400">{t.desc}</p>
            </div>
          );
        })}
      </div>

      {/* Active / Recent Matches */}
      <h3 className="text-lg font-semibold mb-4">对战记录</h3>
      <div className="space-y-4">
        {matches.map((match) => {
          const typeInfo = getMatchTypeInfo(match.match_type);
          return (
            <div
              key={match.id}
              className="card-hover p-5 cursor-pointer"
              onClick={() => setViewingMatch(match)}
            >
              <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-2">
                  <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold text-white ${typeInfo.color}`}>
                    {typeInfo.icon}
                  </span>
                  <span className="text-sm font-medium">{typeInfo.label}</span>
                </div>
                <Badge
                  text={match.status === "in_progress" ? "进行中" : match.status === "voting" ? "投票中" : match.status === "finished" ? "已完成" : match.status}
                  variant={match.status === "in_progress" ? "success" : match.status === "voting" || match.status === "finished" ? "info" : "default"}
                  size="sm"
                />
              </div>
              <p className="text-sm text-gray-400 mb-2 truncate">{match.prompt}</p>
              <div className="flex items-center justify-between">
                <span className="text-sm">{getAgentName(match.agent_a_id)}</span>
                <span className="text-xs text-gray-500">VS</span>
                <span className="text-sm">{getAgentName(match.agent_b_id)}</span>
              </div>
              {(match.votes_a > 0 || match.votes_b > 0) && (
                <div className="mt-2">
                  <ProgressBar
                    value={match.votes_a + match.votes_b > 0 ? (match.votes_a / (match.votes_a + match.votes_b)) * 100 : 50}
                    color="bg-accent"
                    height="h-1.5"
                  />
                </div>
              )}
            </div>
          );
        })}
        {matches.length === 0 && (
          <div className="text-center py-16 text-gray-500">
            <svg className="w-12 h-12 mx-auto mb-3 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <p>还没有对决记录，点击上方按钮发起 PK</p>
          </div>
        )}
      </div>
      </>
      )}

      {/* Match Detail Modal */}
      {viewingMatch && (
        <Modal
          open
          onClose={() => setViewingMatch(null)}
          title={getMatchTypeInfo(viewingMatch.match_type).label}
          maxWidth="max-w-4xl"
        >
            <p className="text-sm text-gray-400 mb-4">
              {getAgentName(viewingMatch.agent_a_id)} vs {getAgentName(viewingMatch.agent_b_id)}
            </p>
            {renderMatchContent(viewingMatch)}
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setViewingMatch(null)}
                className="btn-secondary text-sm"
              >
                关闭
              </button>
            </div>
        </Modal>
      )}
    </div>
  );
}
