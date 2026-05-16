"use client";

import { useEffect, useState } from "react";
import { agentsApi } from "@/lib/api";

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

  useEffect(() => {
    agentsApi.list().then((r) => setAgents(r.data)).catch(() => {});
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
    proficient: "text-green-400",
    expert: "text-blue-400",
    master: "text-yellow-400",
  };

  const levelLabels: Record<string, string> = {
    novice: "新手",
    proficient: "熟练",
    expert: "专家",
    master: "大师",
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">智能体进化日志</h2>

      <div className="mb-6">
        <select
          value={selectedAgent}
          onChange={(e) => setSelectedAgent(e.target.value)}
          className="bg-gray-800 rounded-lg px-4 py-2 w-full max-w-md"
        >
          <option value="">选择智能体</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({levelLabels[a.level] || a.level})
            </option>
          ))}
        </select>
      </div>

      {loading && <p className="text-gray-400">加载中...</p>}

      {!selectedAgent && !loading && (
        <p className="text-gray-500">请选择一个智能体查看其进化信息</p>
      )}

      {evolution && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-gray-900 p-6 rounded-xl">
            <p className="text-sm text-gray-400 mb-1">当前等级</p>
            <p className={`text-2xl font-bold ${levelColors[evolution.level] || "text-white"}`}>
              {levelLabels[evolution.level] || evolution.level}
            </p>
          </div>
          <div className="bg-gray-900 p-6 rounded-xl">
            <p className="text-sm text-gray-400 mb-1">经验值</p>
            <p className="text-2xl font-bold">{evolution.xp}</p>
            {evolution.next_level_xp && (
              <p className="text-xs text-gray-500">距离下一级还需 {evolution.next_level_xp - evolution.xp} XP</p>
            )}
          </div>
          <div className="bg-gray-900 p-6 rounded-xl">
            <p className="text-sm text-gray-400 mb-1">升级进度</p>
            <div className="mt-2">
              <div className="w-full bg-gray-800 rounded-full h-3">
                <div
                  className="bg-blue-600 h-3 rounded-full transition-all"
                  style={{ width: `${Math.min(evolution.progress * 100, 100)}%` }}
                />
              </div>
              <p className="text-xs text-gray-500 mt-1">{Math.round(evolution.progress * 100)}%</p>
            </div>
          </div>
        </div>
      )}

      {selectedAgent && !loading && (
        <div className="bg-gray-900 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-800">
            <h3 className="font-semibold">成长日志</h3>
          </div>
          {experiences.length === 0 ? (
            <p className="px-6 py-8 text-gray-500 text-center">暂无经验记录，参与对话或游戏后将自动记录</p>
          ) : (
            <div className="divide-y divide-gray-800">
              {experiences.map((exp) => (
                <div key={exp.id} className="px-6 py-4">
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex items-center gap-2">
                      <span className="bg-gray-800 px-2 py-0.5 rounded text-xs">{exp.scene_type}</span>
                      <span className={`text-xs ${levelColors[exp.level_at_time] || "text-gray-400"}`}>
                        {levelLabels[exp.level_at_time] || exp.level_at_time}
                      </span>
                    </div>
                    <span className="text-green-400 text-sm font-medium">+{exp.xp_gained} XP</span>
                  </div>
                  {exp.decision && <p className="text-sm text-gray-300 mb-1"><span className="text-gray-500">决策：</span>{exp.decision}</p>}
                  {exp.outcome && <p className="text-sm text-gray-300 mb-1"><span className="text-gray-500">结果：</span>{exp.outcome}</p>}
                  {exp.lesson && <p className="text-sm text-yellow-300/80"><span className="text-gray-500">教训：</span>{exp.lesson}</p>}
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
