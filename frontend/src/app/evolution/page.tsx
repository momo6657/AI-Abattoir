"use client";

import { useEffect, useState } from "react";
import { agentsApi } from "@/lib/api";
import { ErrorBanner, LoadingSpinner, ProgressBar } from "@/components";

interface Agent {
  id: string;
  name: string;
  level: string;
  experience_points: number;
}

interface EvolutionInfo {
  agent_id: string;
  level: string;
  xp: number;
  next_level_xp: number | null;
  progress: number;
}

interface Experience {
  id: string;
  scene_type: string;
  decision: string;
  outcome: string;
  lesson: string;
  xp_gained: number;
  cumulative_xp: number;
  level_at_time: string;
  created_at: string;
}

export default function EvolutionPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [evolution, setEvolution] = useState<EvolutionInfo | null>(null);
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    agentsApi.list().then((r) => setAgents(r.data)).catch(() => {
      setError("无法加载智能体列表");
    });
  }, []);

  useEffect(() => {
    if (!selectedAgent) {
      setEvolution(null);
      setExperiences([]);
      return;
    }
    setLoading(true);
    Promise.all([
      agentsApi.getEvolution(selectedAgent).catch(() => null),
      agentsApi.getExperiences(selectedAgent).catch(() => ({ data: [] })),
    ]).then(([evo, exp]) => {
      setEvolution(evo?.data ?? null);
      setExperiences(exp?.data ?? []);
    }).finally(() => setLoading(false));
  }, [selectedAgent]);

  const levelColors: Record<string, string> = {
    novice: "text-gray-400",
    proficient: "text-emerald-400",
    expert: "text-blue-400",
    master: "text-amber-400",
  };

  const levelLabels: Record<string, string> = {
    novice: "新手",
    proficient: "熟练",
    expert: "专家",
    master: "大师",
  };

  const levelGradients: Record<string, string> = {
    novice: "from-gray-500/20 to-gray-600/20",
    proficient: "from-emerald-500/20 to-teal-500/20",
    expert: "from-blue-500/20 to-indigo-500/20",
    master: "from-amber-500/20 to-orange-500/20",
  };

  return (
    <div className="animate-fade-in">
      <div className="mb-8">
        <h2 className="text-2xl font-bold">智能体进化日志</h2>
        <p className="text-sm text-gray-400 mt-1">追踪智能体的成长历程与经验积累</p>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <div className="mb-8">
        <select
          value={selectedAgent}
          onChange={(e) => setSelectedAgent(e.target.value)}
          className="input-field max-w-md"
        >
          <option value="">选择智能体</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({levelLabels[a.level] || a.level})
            </option>
          ))}
        </select>
      </div>

      {loading && <LoadingSpinner />}

      {!selectedAgent && !loading && (
        <div className="card p-16 text-center">
          <div className="w-16 h-16 rounded-2xl bg-surface-overlay flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          </div>
          <p className="text-gray-400">请选择一个智能体查看其进化信息</p>
        </div>
      )}

      {evolution && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8 animate-slide-up">
          <div className={`card p-6 bg-gradient-to-br ${levelGradients[evolution.level] || levelGradients.novice}`}>
            <p className="text-sm text-gray-400 mb-1">当前等级</p>
            <p className={`text-2xl font-bold ${levelColors[evolution.level] || "text-white"}`}>
              {levelLabels[evolution.level] || evolution.level}
            </p>
          </div>
          <div className="card p-6">
            <p className="text-sm text-gray-400 mb-1">经验值</p>
            <p className="text-2xl font-bold">{evolution.xp}</p>
            {evolution.next_level_xp && (
              <p className="text-xs text-gray-500 mt-1">距离下一级还需 {evolution.next_level_xp - evolution.xp} XP</p>
            )}
          </div>
          <div className="card p-6">
            <p className="text-sm text-gray-400 mb-2">升级进度</p>
            <ProgressBar value={Math.min(evolution.progress * 100, 100)} />
            <p className="text-xs text-gray-500 mt-2">{Math.round(evolution.progress * 100)}%</p>
          </div>
        </div>
      )}

      {selectedAgent && !loading && (
        <div className="card overflow-hidden animate-slide-up">
          <div className="px-6 py-4 border-b border-border">
            <h3 className="font-semibold">成长日志</h3>
          </div>
          {experiences.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <p className="text-gray-500">暂无经验记录，参与对话或游戏后将自动记录</p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {experiences.map((exp) => (
                <div key={exp.id} className="px-6 py-4 hover:bg-surface-overlay/50 transition-colors">
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex items-center gap-2">
                      <span className="bg-surface-overlay px-2.5 py-0.5 rounded-lg text-xs border border-border">{exp.scene_type}</span>
                      <span className={`text-xs ${levelColors[exp.level_at_time] || "text-gray-400"}`}>
                        {levelLabels[exp.level_at_time] || exp.level_at_time}
                      </span>
                    </div>
                    <span className="text-emerald-400 text-sm font-medium">+{exp.xp_gained} XP</span>
                  </div>
                  {exp.decision && <p className="text-sm text-gray-300 mb-1"><span className="text-gray-500">决策：</span>{exp.decision}</p>}
                  {exp.outcome && <p className="text-sm text-gray-300 mb-1"><span className="text-gray-500">结果：</span>{exp.outcome}</p>}
                  {exp.lesson && <p className="text-sm text-amber-300/80"><span className="text-gray-500">教训：</span>{exp.lesson}</p>}
                  <p className="text-xs text-gray-600 mt-2">累计 XP: {exp.cumulative_xp}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
