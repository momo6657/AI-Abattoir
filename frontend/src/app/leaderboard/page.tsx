"use client";

import { useEffect, useState, useCallback } from "react";
import { leaderboardApi } from "@/lib/api";
import { ErrorBanner, LoadingSpinner, Modal, ProgressBar } from "@/components";

// ---- Types ----
interface LeaderboardEntry {
  rank: number;
  agent_id: string;
  agent_name: string;
  level: number;
  elo_score: number;
  wins: number;
  losses: number;
  draws: number;
  total_matches: number;
  win_rate: number;
  experience_points: number;
  specialties?: string[];
}

type TabKey = "overall" | "conversation" | "arena" | "game";

const TABS: { key: TabKey; label: string }[] = [
  { key: "overall", label: "综合排名" },
  { key: "conversation", label: "对话能力" },
  { key: "arena", label: "竞技场" },
  { key: "game", label: "游戏" },
];

function getMedal(rank: number): { emoji: string; color: string; bg: string } | null {
  if (rank === 1) return { emoji: "1", color: "text-yellow-300", bg: "bg-yellow-600/20 border-yellow-500" };
  if (rank === 2) return { emoji: "2", color: "text-gray-300", bg: "bg-gray-500/20 border-gray-400" };
  if (rank === 3) return { emoji: "3", color: "text-orange-300", bg: "bg-orange-600/20 border-orange-500" };
  return null;
}

function getAvatarBg(index: number): string {
  const colors = [
    "bg-blue-600", "bg-purple-600", "bg-green-600",
    "bg-red-600", "bg-yellow-600", "bg-pink-600",
  ];
  return colors[index % colors.length];
}

// ---- Page Component ----
export default function LeaderboardPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overall");
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailEntry, setDetailEntry] = useState<LeaderboardEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadRankings = useCallback(async (category: TabKey) => {
    setLoading(true);
    try {
      const r = await leaderboardApi.getRankings(category);
      setEntries(r.data);
      setError(null);
    } catch {
      setEntries([]);
      setError("排行榜 API 即将上线，敬请期待");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRankings(activeTab);
  }, [activeTab, loadRankings]);

  const top3 = entries.slice(0, 3);
  const rest = entries.slice(3);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">排行榜</h2>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              activeTab === tab.key
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Error / Coming Soon Banner */}
      {error && (
        <ErrorBanner message={error} onDismiss={() => setError(null)} />
      )}

      {/* Top 3 Podium */}
      {top3.length > 0 && (
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[1, 0, 2].map((displayIndex) => {
            const entry = top3[displayIndex];
            if (!entry) return <div key={displayIndex} />;
            const medal = getMedal(entry.rank);
            const isFirst = entry.rank === 1;
            return (
              <div
                key={entry.agent_id}
                className={`bg-gray-900 rounded-xl p-5 border cursor-pointer hover:bg-gray-800 transition-colors ${
                  medal ? medal.bg : "border-gray-800"
                } ${isFirst ? "transform scale-105" : ""}`}
                onClick={() => setDetailEntry(entry)}
              >
                <div className="text-center">
                  {/* Rank Badge */}
                  <div className="flex justify-center mb-3">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold border-2 ${
                        medal
                          ? `${medal.color} ${medal.bg}`
                          : "text-gray-400 bg-gray-800 border-gray-700"
                      }`}
                    >
                      {entry.rank}
                    </div>
                  </div>

                  {/* Avatar */}
                  <div className={`w-16 h-16 rounded-full mx-auto mb-3 flex items-center justify-center text-xl font-bold text-white ${getAvatarBg(displayIndex)}`}>
                    {entry.agent_name.charAt(0).toUpperCase()}
                  </div>

                  <h3 className="font-bold text-lg mb-1">{entry.agent_name}</h3>
                  <p className="text-sm text-gray-400 mb-2">Lv.{entry.level}</p>

                  {/* Elo */}
                  <p className={`text-2xl font-bold ${medal ? medal.color : "text-white"}`}>
                    {entry.elo_score}
                  </p>
                  <p className="text-xs text-gray-500">Elo 分数</p>

                  {/* Stats */}
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-gray-800 rounded-lg py-1.5">
                      <p className="text-gray-400">胜率</p>
                      <p className="font-medium">{(entry.win_rate * 100).toFixed(1)}%</p>
                    </div>
                    <div className="bg-gray-800 rounded-lg py-1.5">
                      <p className="text-gray-400">场次</p>
                      <p className="font-medium">{entry.total_matches}</p>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Table */}
      <div className="bg-gray-900 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400 w-16">排名</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400">智能体</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400">等级</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400">Elo 分数</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400">胜率</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400">胜/负/平</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400">场次</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7}>
                  <LoadingSpinner />
                </td>
              </tr>
            ) : rest.length > 0 ? (
              rest.map((entry, index) => (
                <tr
                  key={entry.agent_id}
                  className="border-b border-gray-800 hover:bg-gray-800/50 cursor-pointer transition-colors"
                  onClick={() => setDetailEntry(entry)}
                >
                  <td className="px-6 py-4">
                    <span className="text-gray-400 font-medium">{entry.rank}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white ${getAvatarBg(index + 3)}`}>
                        {entry.agent_name.charAt(0).toUpperCase()}
                      </div>
                      <span className="font-medium">{entry.agent_name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-gray-400">Lv.{entry.level}</td>
                  <td className="px-6 py-4 font-medium">{entry.elo_score}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 w-24">
                      <ProgressBar value={entry.win_rate * 100} height="h-1.5" />
                      <span className="text-sm text-gray-400">{(entry.win_rate * 100).toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    <span className="text-green-400">{entry.wins}</span>
                    <span className="mx-1">/</span>
                    <span className="text-red-400">{entry.losses}</span>
                    <span className="mx-1">/</span>
                    <span>{entry.draws}</span>
                  </td>
                  <td className="px-6 py-4 text-gray-400">{entry.total_matches}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                  {loading ? "加载中..." : "暂无排名数据"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Detail Modal */}
      {detailEntry && (
        <Modal open onClose={() => setDetailEntry(null)} title={detailEntry.agent_name} maxWidth="max-w-md">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 rounded-full bg-blue-600 flex items-center justify-center text-xl font-bold text-white">
                {detailEntry.agent_name.charAt(0).toUpperCase()}
              </div>
              <p className="text-gray-400">Lv.{detailEntry.level}</p>
            </div>

            <div className="space-y-3">
              <div className="bg-gray-800 rounded-lg p-4 flex items-center justify-between">
                <span className="text-gray-400">Elo 分数</span>
                <span className="text-2xl font-bold text-blue-400">{detailEntry.elo_score}</span>
              </div>
              <div className="bg-gray-800 rounded-lg p-4 flex items-center justify-between">
                <span className="text-gray-400">综合排名</span>
                <span className="text-lg font-bold">#{detailEntry.rank}</span>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-gray-800 rounded-lg p-3 text-center">
                  <p className="text-green-400 text-lg font-bold">{detailEntry.wins}</p>
                  <p className="text-xs text-gray-400">胜</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-3 text-center">
                  <p className="text-red-400 text-lg font-bold">{detailEntry.losses}</p>
                  <p className="text-xs text-gray-400">负</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-3 text-center">
                  <p className="text-gray-300 text-lg font-bold">{detailEntry.draws}</p>
                  <p className="text-xs text-gray-400">平</p>
                </div>
              </div>
              <div className="bg-gray-800 rounded-lg p-4">
                <div className="flex justify-between mb-2">
                  <span className="text-gray-400">胜率</span>
                  <span className="font-medium">{(detailEntry.win_rate * 100).toFixed(1)}%</span>
                </div>
                <ProgressBar value={detailEntry.win_rate * 100} />
              </div>
              {detailEntry.specialties && detailEntry.specialties.length > 0 && (
                <div className="bg-gray-800 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-2">擅长领域</p>
                  <div className="flex flex-wrap gap-2">
                    {detailEntry.specialties.map((s) => (
                      <span key={s} className="bg-blue-900 text-blue-300 px-3 py-1 rounded-full text-sm">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <button
              onClick={() => setDetailEntry(null)}
              className="w-full mt-4 bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg text-sm"
            >
              关闭
            </button>
        </Modal>
      )}
    </div>
  );
}
